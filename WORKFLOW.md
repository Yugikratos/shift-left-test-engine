<div align="center">

# 🔀 Shift-Left Test Data Engine

### Workflow & Functionality Guide

*An AI-powered multi-agent system for automated test data provisioning*
**Ab Initio ETL · Teradata Data Warehouse context**

[![Tests](https://img.shields.io/badge/tests-62%20passing-brightgreen?style=flat-square)](#-testing)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](#-environment)
[![Mode](https://img.shields.io/badge/mode-dual%20(LLM%20%2F%20rule--based)-purple?style=flat-square)](#-dual-mode-design)
[![API](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square)](#-rest-api-surface)

</div>

---

## 📖 Table of Contents

| # | Section |
|---|---------|
| 1 | [What It Does](#-what-it-does) |
| 2 | [The Big Picture](#-the-big-picture) |
| 3 | [The 4-Agent Pipeline](#-the-4-agent-pipeline) |
| 4 | [Request Lifecycle](#-request-lifecycle) |
| 5 | [Context Flow Between Agents](#-context-flow-between-agents) |
| 6 | [REST API Surface](#-rest-api-surface) |
| 7 | [Dual-Mode Design](#-dual-mode-design) |
| 8 | [Resilience & Skip Logic](#-resilience--skip-logic) |
| 9 | [Quick Start](#-quick-start) |
| 10 | [Testing](#-testing) |
| 11 | [Project Map](#-project-map) |

---

## ✨ What It Does

The engine takes a plain provisioning request — *"give me 100 referentially-intact rows
for these tables, with all PII anonymized"* — and runs it through **four specialised AI
agents** in sequence. The result: a fully-loaded target database, validated end-to-end,
plus a rich JSON report describing everything that happened.

```
┌────────────────────────────────────────────────────────────────────┐
│  "I need realistic, safe test data for tables X, Y, Z"               │
│                            ⬇                                         │
│   Profile  →  Subset  →  Mask  →  Provision  →  📊 Validated Report  │
└────────────────────────────────────────────────────────────────────┘
```

| Goal | How the engine delivers |
|------|-------------------------|
| 🧠 **Understand the schema** | Parses Ab Initio DMLs + Teradata DDLs, classifies every field |
| 🔒 **Protect sensitive data** | Detects PII and masks it with consistent, type-aware fakes |
| 🔗 **Keep data valid** | Extracts subsets that preserve foreign-key referential integrity |
| 📦 **Deliver safely** | Loads into the target DB transactionally, then validates |
| 🤖 **Work anywhere** | Runs with *or* without a Claude API key (rule-based fallback) |

---

## 🗺 The Big Picture

```mermaid
flowchart TD
    Client([🌐 HTTP / CLI Request]):::entry
    API["⚡ FastAPI<br/><i>api/main.py</i>"]:::api
    Engine["🎯 OrchestratorEngine<br/><i>orchestrator/engine.py</i>"]:::core
    DB[("🗄️ metadata.db<br/>job persistence")]:::store

    subgraph SUP [" Supporting Services "]
        direction LR
        Coord["📋 AgentCoordinator<br/>assigns + logs"]:::svc
        Status["📡 StatusTracker<br/>live progress"]:::svc
        LLM["🤖 LLMClient<br/>Claude / none"]:::svc
    end

    subgraph PIPE [" Sequential Agent Pipeline "]
        direction LR
        P1["🧠 Profiling"]:::agent --> P2["🔗 Subsetting"]:::agent --> P3["🔒 Masking"]:::agent --> P4["📦 Provisioning"]:::agent
    end

    Out[("🎯 Target SQLite DB<br/>+ 📊 JSON report → S3")]:::store

    Client --> API -->|request dict| Engine
    Engine <-->|jobs| DB
    Engine --> SUP
    Coord --> PIPE
    P4 --> Out

    classDef entry fill:#1e293b,stroke:#475569,color:#fff,stroke-width:2px;
    classDef api fill:#0d9488,stroke:#0f766e,color:#fff,stroke-width:2px;
    classDef core fill:#7c3aed,stroke:#6d28d9,color:#fff,stroke-width:2px;
    classDef svc fill:#1e40af,stroke:#1e3a8a,color:#fff;
    classDef agent fill:#b45309,stroke:#92400e,color:#fff,stroke-width:2px;
    classDef store fill:#374151,stroke:#1f2937,color:#fff;
```

> **Coordination principle:** Agents **never** call each other directly. The
> `OrchestratorEngine` is the single conductor — it passes a mutable `context` dict
> down the line, and each agent reads what it needs and appends its own output.

---

## 🧩 The 4-Agent Pipeline

All agents inherit from `BaseAgent` and implement `execute(context) → AgentResult`.
The `run()` wrapper adds timing, error capture, and **retry-on-transient-failure**
(connection / timeout / OS I/O errors → up to 3 attempts with linear backoff).

<table>
<tr>
<th width="50">Step</th>
<th>Agent</th>
<th>What it does</th>
<th>Produces</th>
</tr>

<tr>
<td align="center">

### 1️⃣
</td>
<td>

**🧠 Profiling Agent**
</td>
<td>

Parses DML/DDL files. Classifies every field as **PII**, **Control/Audit**,
**SCD-2**, **Key**, or **Business** data. Detects table relationships via naming
conventions (`_id` / `_nbr`). Optionally calls **Claude** for deeper schema analysis.
</td>
<td>

`profile_report`
`pii_summary`
*(saved to `knowledge_base/profiles/`)*
</td>
</tr>

<tr>
<td align="center">

### 2️⃣
</td>
<td>

**🔗 Subsetting Agent**
</td>
<td>

Generates referentially-intact SQL using an **anchor-table strategy** with
`IN`-subquery joins. Validates FK integrity so child rows never dangle.
</td>
<td>

`extracted_data`
*(CSVs → `extracted_data/`)*
</td>
</tr>

<tr>
<td align="center">

### 3️⃣
</td>
<td>

**🔒 Masking Agent**
</td>
<td>

Anonymizes PII with **consistent masking** — the same input always maps to the
same output (hash-keyed cache). Uses **Faker** for type-aware values:
names→`fake.name()`, emails→`fake.email()`, SSNs→`fake.ssn()`, etc.
</td>
<td>

`masked_data`
+ before/after samples
</td>
</tr>

<tr>
<td align="center">

### 4️⃣
</td>
<td>

**📦 Provisioning Agent**
</td>
<td>

Loads masked data into the **target SQLite DB** with transaction safety
(rollback on partial failure). Runs validation: row counts, column existence,
NOT NULL constraints.
</td>
<td>

`load_summary`
`validation` status
</td>
</tr>
</table>

### 🎯 Field Classification Cheat-Sheet

| Class | Detected by | Example columns | Treatment |
|-------|-------------|-----------------|-----------|
| 🔴 **PII** | name/address/phone/id patterns | `cust_nm`, `home_addr`, `phone_nbr` | **Masked** |
| 🟡 **Control** | audit patterns | `load_dt`, `src_sys_cd` | Preserved |
| 🟣 **SCD-2** | `eff_start_dt` / `eff_end_dt` / `logc_del_ind` | versioning columns | Preserved |
| 🔵 **Key** | `_id` / `_nbr` suffixes | `entity_id`, `acct_nbr` | Drives relationships |
| ⚪ **Business** | everything else | `credit_score`, `status` | Passed through |

---

## 🔄 Request Lifecycle

```mermaid
flowchart LR
    subgraph SUBMIT [" 📥 submit_request() "]
        direction TB
        S1["Generate request_id<br/>(8-char uuid)"] --> S2{"Validate<br/>• tables not empty?<br/>• date range valid?<br/>• skip-flag deps?"}
        S2 -->|❌ invalid| ERR["raise ValueError"]:::fail
        S2 -->|✅ ok| S3["Build execution plan<br/>persist → metadata.db<br/>status = submitted"]
    end

    subgraph EXEC [" ⚙️ execute_request() "]
        direction TB
        E1["Seed context<br/>db paths · tables · dates"] --> E2{"for each<br/>non-skipped agent"}
        E2 --> E3["mark running →<br/>coordinator.assign()"]
        E3 --> E4{"result<br/>status?"}
        E4 -->|FAILED| FAIL["status = failed<br/>stop early"]:::fail
        E4 -->|OK| E5["enrich context<br/>→ next agent"]
        E5 --> E2
        E2 -->|done| FIN["_build_report()<br/>upload → S3"]:::done
    end

    S3 ==> E1

    classDef fail fill:#7f1d1d,stroke:#b91c1c,color:#fff;
    classDef done fill:#14532d,stroke:#16a34a,color:#fff;
```

**Status terminal states**

| Status | Meaning |
|--------|---------|
| `completed` | All requested agents succeeded ✅ |
| `partial` | Provisioning didn't fully complete, but pipeline ran ⚠️ |
| `failed` | An upstream agent (profiling/subsetting/masking) failed ❌ |

`submit_request` + `execute_request` can be called separately (async), or together
via the `process_request()` convenience method.

---

## 🔁 Context Flow Between Agents

The `context` dict is the spine of the pipeline. It starts with request metadata and
grows as each agent contributes:

```mermaid
sequenceDiagram
    autonumber
    participant O as 🎯 Orchestrator
    participant P as 🧠 Profiling
    participant S as 🔗 Subsetting
    participant M as 🔒 Masking
    participant V as 📦 Provisioning

    Note over O: context = { request_id, scenario,<br/>tables, record_count, date_range,<br/>source_db, target_db }

    O->>P: assign(context)
    P-->>O: + profile_report, pii_summary
    O->>S: assign(context)
    S-->>O: + extracted_data
    O->>M: assign(context)
    M-->>O: + masked_data
    O->>V: assign(context)
    V-->>O: load_summary + validation ✅
    Note over O: _build_report() → S3
```

Each agent returns a standardised **`AgentResult`**:

```python
AgentResult(
    agent_name, status,            # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    started_at, completed_at, duration_seconds,
    data={...},                    # the agent's payload (merged into context)
    errors=[...], warnings=[...],
    summary="human-readable one-liner",
)
```

---

## 🌐 REST API Surface

Served by **FastAPI** (`api/main.py`). Start with:
`uvicorn api.main:app --reload --port 8000`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/provision` | Submit **and** run the full pipeline (synchronous) |
| `POST` | `/api/v1/provision/async` | Submit, run in background, return receipt immediately |
| `GET`  | `/api/v1/status/{request_id}` | Live status — tries in-memory tracker, falls back to `metadata.db` |
| `GET`  | `/api/v1/results/{request_id}` | Full consolidated report (fetched from S3) |
| `GET`  | `/api/v1/tables` | List available source tables |
| `GET`  | `/api/v1/health` | Health check + active LLM mode |

<details>
<summary><b>📨 Example request</b></summary>

```bash
curl -X POST http://localhost:8000/api/v1/provision \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "business_entity_flow",
    "tables": ["stg_business_entity", "business_address_match", "business_credit_score"],
    "record_count": 100,
    "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
  }'
```
</details>

---

## 🤖 Dual-Mode Design

The engine is built to degrade gracefully — **no API key required**.

```mermaid
flowchart TD
    Q{"🔑 CLAUDE_API_KEY<br/>present?<br/><i>LLMClient lazy init</i>"}:::q
    Q -->|yes| L["🟢 LLM MODE<br/>Claude analyses<br/>schema intelligently"]:::on
    Q -->|no| R["⚪ RULE-BASED MODE<br/>Pattern matching from<br/>config/settings.py<br/>(_nm · _addr · _phone …)"]:::off
    L --> C["✅ Same AgentResult contract<br/>either way"]:::contract
    R --> C
    C -.->|LLMClient returns None<br/>when unavailable| Note["callers handle gracefully"]:::note

    classDef q fill:#7c3aed,stroke:#6d28d9,color:#fff,stroke-width:2px;
    classDef on fill:#14532d,stroke:#16a34a,color:#fff;
    classDef off fill:#334155,stroke:#64748b,color:#fff;
    classDef contract fill:#0d9488,stroke:#0f766e,color:#fff,stroke-width:2px;
    classDef note fill:#1e293b,stroke:#475569,color:#cbd5e1;
```

> Pattern rules (PII / control / SCD-2 / relationships) all live in
> **`config/settings.py`** and every path is overridable via env vars.

---

## 🛡 Resilience & Skip Logic

**Retry** — `BaseAgent.run()` retries only **transient** errors
(`ConnectionError`, `TimeoutError`, `OSError`) up to 3× with linear backoff.
Everything else fails fast.

**Skip flags** — any agent can be skipped, but dependencies are enforced at submit time:

```mermaid
flowchart LR
    A["skip_subsetting<br/>✅ true"]:::skip --> B{"skip_masking<br/>also true?"}:::q
    B -->|no| X1["❌ ValueError<br/><i>masking needs<br/>extracted data</i>"]:::fail
    B -->|yes| C["skip_masking<br/>✅ true"]:::skip
    C --> D{"skip_provisioning<br/>also true?"}:::q
    D -->|no| X2["❌ ValueError<br/><i>provisioning needs<br/>masked data</i>"]:::fail
    D -->|yes| OK["✅ valid plan"]:::ok

    classDef skip fill:#334155,stroke:#64748b,color:#fff;
    classDef q fill:#7c3aed,stroke:#6d28d9,color:#fff;
    classDef fail fill:#7f1d1d,stroke:#b91c1c,color:#fff;
    classDef ok fill:#14532d,stroke:#16a34a,color:#fff;
```

| Flag | Allowed alone? | Reason |
|------|:--------------:|--------|
| `skip_profiling` | ✅ | Downstream agents don't hard-require the profile |
| `skip_subsetting` | only with `skip_masking` | Masking consumes extracted data |
| `skip_masking` | only with `skip_provisioning` | Provisioning consumes masked data |
| `skip_provisioning` | ✅ | It's the last step |

---

## 🚀 Quick Start

> 💡 Commands shown for **Windows / PowerShell**.

```powershell
# 1 — Environment
python -m venv venv; venv\Scripts\activate
pip install -r requirements.txt --prefer-binary

# 2 — Initialize the source & target SQLite DBs (seeded with Faker data)
python -m utils.db_setup

# 3 — Run the full pipeline demo end-to-end
python -m orchestrator.demo

# 4 — Or serve the REST API
uvicorn api.main:app --reload --port 8000
```

---

## 🧪 Testing

```powershell
python -m pytest tests/ -v        # all 62 tests
python -m orchestrator.demo       # full pipeline smoke run
```

```mermaid
pie title Tests by Suite
    "Engine features" : 18
    "Pipeline e2e" : 15
    "Coordinator and Status" : 14
    "Parsers" : 10
    "API" : 5
```

| File | Tests | Covers |
|------|:-----:|--------|
| `tests/test_pipeline.py` | 15 | End-to-end pipeline, individual agents, validation, edge cases |
| `tests/test_api.py` | 5 | Health, list tables, provision, 404 handling |
| `tests/test_parsers.py` | 10 | DML/DDL parsing, field extraction, empty input |
| `tests/test_engine_features.py` | 18 | Retry, skip flags, persistence, enterprise mode, RemoteExecutor, Bedrock fallback |
| `tests/test_coordinator_status.py` | 14 | Coordinator assignment/progress/reset, StatusTracker lifecycle |

> 🔄 **CI:** GitHub Actions runs the full suite on every push / PR to `main`
> (`.github/workflows/test.yml`).

---

## 🗂 Project Map

```
shift-left-test-engine/
├── api/
│   └── main.py              # FastAPI REST layer (lifespan startup, endpoints)
├── orchestrator/
│   ├── engine.py            # 🎯 Core conductor: validate → plan → run → report
│   ├── coordinator.py       # Assigns tasks to agents, logs progress
│   ├── status.py            # In-memory live status tracker
│   └── demo.py              # End-to-end demo scenario
├── agents/
│   ├── base_agent.py        # Abstract base: AgentResult + run() w/ retry
│   ├── profiling_agent.py   # 1️⃣ Schema analysis + PII detection
│   ├── subsetting_agent.py  # 2️⃣ Referentially-intact extraction
│   ├── masking_agent.py     # 3️⃣ Consistent PII anonymization (Faker)
│   └── provisioning_agent.py# 4️⃣ Transactional load + validation
├── parsers/
│   ├── dml_parser.py        # Ab Initio DML format parser
│   └── ddl_parser.py        # Teradata DDL parser
├── config/
│   └── settings.py          # Patterns (PII/control/SCD-2/rel) + paths (env-overridable)
├── utils/
│   ├── llm_client.py        # Singleton Claude client (lazy, graceful degradation)
│   ├── db_setup.py          # Builds SQLite schema, seeds Faker data
│   ├── database.py          # SQLAlchemy engines / sessions
│   ├── storage_client.py    # S3 report upload/download
│   └── remote_executor.py   # Enterprise remote execution
├── mock_data/               # Sample DML / DDL / CSV inputs
├── knowledge_base/profiles/ # Saved profile reports (JSON)
└── tests/                   # 62 tests across 5 files
```

---

<div align="center">

### 🔀 Profile → Subset → Mask → Provision

*Safe, valid, realistic test data — shifted left.*

<sub>Workflow documentation authored by Claude.</sub>

</div>
