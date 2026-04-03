# Shift-Left Test Data Engine — POC

![CI](https://github.com/Yugikratos/shift-left-test-engine/actions/workflows/test.yml/badge.svg)

**Proof of Concept**

An AI-powered multi-agent system that automates test data provisioning for ETL/data warehouse testing workflows. Eliminates manual effort in preparing test datasets by profiling schemas, extracting referentially-intact data subsets, masking PII, and loading into target test environments.

---

## What It Does

Submit a test data request → The system automatically:
1. **Profiles** source metadata (DML/DDL) to understand schemas, relationships, and PII
2. **Subsets** production-like data with referential integrity preserved
3. **Masks** PII fields (names, addresses, phone numbers) for compliance
4. **Provisions** the processed data into a target test database
5. **Validates** integrity (row counts, FK checks, null checks) and returns a full report

---

## Tech Stack

### Language & Runtime
| Tool | Version | Purpose |
|---|---|---|
| Python | 3.10+ (3.14 local dev) | Core runtime |
| venv | built-in | Isolated virtual environment |

> On Python 3.14, install all packages with `--prefer-binary` to avoid C-extension build failures.

### Python Libraries
| Package | Version | Purpose |
|---|---|---|
| **fastapi** | 0.135.2 | REST API framework — async, auto-generates `/docs` Swagger UI |
| **uvicorn** | 0.42.0 | ASGI server that runs FastAPI |
| **pydantic** | 2.12.5 | Request/response validation, typed settings management |
| **python-dotenv** | 1.2.2 | Loads `.env` file into environment variables at startup |
| **anthropic** | 0.86.0 | Official Claude API client — used by ProfilingAgent in LLM mode |
| **pandas** | 3.0.1 | DataFrame operations for data extraction, transformation, and CSV export |
| **faker** | 40.11.1 | Generates realistic synthetic data for seeding DBs and PII masking |
| **sqlalchemy** | 2.0.48 | ORM and DB abstraction layer — used for SQLite in POC |
| **boto3** | 1.35.0 | AWS SDK — used for Bedrock LLM provider (optional) |
| **paramiko** | 3.5.0 | SSH client — used for enterprise remote execution (optional) |
| **rich** | 14.3.3 | Pretty terminal output — tables, colors, progress in CLI demo |
| **loguru** | 0.7.3 | Structured logging with automatic file rotation |
| **httpx** | 0.28.1 | Async HTTP client used internally and for API integration tests |
| **pytest** | 8.3.3 | Test framework — runs smoke tests and unit tests |

### Dev Tools
| Tool | Purpose |
|---|---|
| VS Code | IDE |
| Git | Version control |
| PowerShell | Shell (Windows) |
| Claude Code | AI coding assistant (claude.ai/code) |
| Antigravity (Gemini) | AI coding assistant (Google Gemini) |
| curl / Swagger UI | API testing (`http://localhost:8000/docs`) |
| SQLite | Lightweight local database for POC (no server needed) |

---

## Quick Start (Windows)

### Prerequisites
- Python 3.10+ installed and on PATH
- Git installed
- VS Code (recommended)

### Step 1: Clone and Set Up Virtual Environment
```powershell
git clone <repo-url>
cd shift-left-test-engine

# Create virtual environment
python -m venv venv

# Activate it (run this every session)
venv\Scripts\Activate.ps1
```

> If PowerShell blocks activation: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### Step 2: Install Dependencies
```powershell
# Standard install
pip install -r requirements.txt

# If on Python 3.14 (avoids C-extension build failures)
pip install fastapi uvicorn pydantic python-dotenv anthropic pandas faker sqlalchemy rich loguru httpx --prefer-binary
```

### Step 3: Configure API Key (Optional)
```powershell
copy .env.example .env
# Edit .env — add your Anthropic API key if you have one:
# ANTHROPIC_API_KEY=sk-ant-...
# The system works fully without it using rule-based fallback
```

### Step 4: Initialize the Database
```powershell
python -m utils.db_setup
```
**What this does:** Creates `source_data.db` (SQLite) with 3 tables and ~690 rows of Faker-generated mock records. Also creates an empty `target_test.db` for provisioning output.

### Step 5: Run the Engine

**Option A — CLI demo (quickest way to test)**
```powershell
python -m orchestrator.demo
```
Runs the full 4-agent pipeline against the mock data. Prints a rich formatted report to terminal. No server needed.

**Option B — API server**
```powershell
python -m uvicorn api.main:app --port 8000
# Open browser: http://127.0.0.1:8000/docs
```
Starts a REST API server. Use Swagger UI at `/docs` to submit requests interactively.

### Step 6: Submit a Test Data Request via API
```powershell
# Submit request
curl -X POST http://localhost:8000/api/v1/provision `
  -H "Content-Type: application/json" `
  -d '{\"scenario\": \"business_entity_flow\", \"tables\": [\"stg_business_entity\", \"business_address_match\", \"business_credit_score\"], \"record_count\": 100, \"date_range\": {\"start\": \"2024-01-01\", \"end\": \"2024-12-31\"}}'

# Check status (replace <request_id> with ID returned above)
curl http://localhost:8000/api/v1/status/<request_id>

# Get full results
curl http://localhost:8000/api/v1/results/<request_id>
```

### Step 7: Run Tests
```powershell
python -m pytest tests/
```

---

## All Commands Reference

| Command | What It Does |
|---|---|
| `venv\Scripts\Activate.ps1` | Activates the virtual environment (required every session) |
| `pip install -r requirements.txt` | Installs all dependencies |
| `pip install <pkg> --prefer-binary` | Safe install on Python 3.14 |
| `python -m utils.db_setup` | Creates and seeds SQLite databases with mock data |
| `python -m orchestrator.demo` | Runs full pipeline demo via CLI, no server needed |
| `python -m uvicorn api.main:app --port 8000` | Starts REST API server on port 8000 |
| `python -m uvicorn api.main:app --reload --port 8000` | Starts server with auto-reload on file changes (dev mode) |
| `python -m pytest tests/` | Runs all unit and integration tests |
| `curl -X POST http://localhost:8000/api/v1/provision ...` | Submits a test data provisioning request |
| `curl http://localhost:8000/api/v1/status/<id>` | Polls status of a provisioning request |
| `curl http://localhost:8000/api/v1/results/<id>` | Retrieves full results of a completed request |

---

## Project Structure

```
shift-left-test-engine/
├── agents/
│   ├── base_agent.py           # Abstract base — all agents inherit from this
│   ├── profiling_agent.py      # Parses DML/DDL, detects PII, maps relationships
│   ├── subsetting_agent.py     # Generates anchor-based SQL, extracts data slice
│   ├── masking_agent.py        # Type-aware PII anonymization using Faker
│   └── provisioning_agent.py   # Loads masked data to target DB, runs validation
├── orchestrator/
│   ├── engine.py               # OrchestratorEngine — validates requests, runs pipeline
│   ├── coordinator.py          # AgentCoordinator — task assignment and progress tracking
│   ├── status.py               # StatusTracker — request lifecycle tracking
│   └── demo.py                 # CLI demo runner (no server required)
├── api/
│   └── main.py                 # FastAPI REST endpoints + in-memory request store
├── parsers/
│   ├── dml_parser.py           # Ab Initio DML format parser
│   └── ddl_parser.py           # Teradata DDL parser
├── config/
│   └── settings.py             # Env var loading, PII/relationship detection patterns
├── utils/
│   ├── db_setup.py             # Creates + seeds source_data.db (~690 mock records)
│   ├── llm_client.py           # LLM client (Anthropic/Bedrock) — returns None if unavailable
│   ├── logger.py               # Loguru logger configuration
│   └── remote_executor.py      # SSH remote executor (mock/real) for enterprise mode
├── knowledge_base/
│   └── profiles/               # JSON profile reports saved after each run
├── mock_data/
│   ├── dml/                    # Sample Ab Initio DML files
│   └── ddl/                    # Sample Teradata DDL files
├── extracted_data/             # CSVs output by SubsettingAgent
├── tests/
│   ├── test_pipeline.py        # Pipeline + agent tests (15 tests)
│   ├── test_api.py             # API endpoint tests (5 tests)
│   ├── test_parsers.py         # DML/DDL parser tests (10 tests)
│   └── test_gemini_features.py # Enterprise, retry, skip flags, persistence (18 tests)
├── source_data.db              # SQLite source DB (mock production data)
├── target_test.db              # SQLite target DB (provisioned test data)
├── .env                        # Local config (ANTHROPIC_API_KEY — gitignored)
├── .env.example                # Template for .env
├── .github/workflows/test.yml  # GitHub Actions CI pipeline
├── requirements.txt            # Pinned Python dependencies
└── Dockerfile                  # Container definition
```

---

## Architecture

```
[API Request or CLI Demo]
        │
        ▼
[OrchestratorEngine]
   ├── Validates request (tables, scenario, date range)
   ├── Builds execution plan
   └── Passes mutable context dict through pipeline
        │
        ▼
[Agent Pipeline — sequential, context-passing]
   Step 1: ProfilingAgent     → Parses DML/DDL, detects PII, maps FK relationships
   Step 2: SubsettingAgent    → Generates SQL, extracts referentially-intact data slice
   Step 3: MaskingAgent       → Anonymizes PII fields with type-aware Faker routing
   Step 4: ProvisioningAgent  → Loads to target DB, runs row/column/null validation
        │
        ▼
[Output]
   ├── Profile Report (JSON → knowledge_base/profiles/)
   ├── Extracted CSVs (extracted_data/)
   ├── Masked Dataset (in-memory → target DB)
   └── Validation Report (returned via API or printed to terminal)
```

**Agent communication:** A single mutable `context` dict flows through all agents. Each agent reads its inputs and writes its outputs into the same dict. Agents never call each other directly.

**Key context keys:**
- After Profiling: `context["profile_report"]`, `context["pii_summary"]`
- After Subsetting: `context["extracted_data"]`
- After Masking: `context["masked_data"]`
- Provisioning reads all of the above

---

## Operating Modes

### Rule-Based Fallback (default, no API key needed)
- ProfilingAgent uses regex pattern matching from `config/settings.py`
- PII detection: column name patterns (`*_nm`, `*_addr`, `*_phone`, `*_email`)
- Relationship detection: matching `_id` / `_nbr` columns across tables
- Fully functional — just less intelligent than LLM mode

### LLM Mode — Anthropic Direct
- ProfilingAgent sends schema metadata to Claude for intelligent analysis
- Set `ANTHROPIC_API_KEY` in `.env` to enable

### LLM Mode — AWS Bedrock
- Routes LLM calls through AWS Bedrock instead of direct Anthropic API
- Set `LLM_PROVIDER=BEDROCK` and `AWS_DEFAULT_REGION` in `.env`
- Uses `boto3` — requires valid AWS credentials in environment

### Enterprise Mode
- Set `ENTERPRISE_MODE=true` to switch agents from local execution to script generation
- **MaskingAgent** generates Ab Initio `.xfr` transform scripts instead of in-memory masking
- **ProvisioningAgent** generates Teradata `.bteq` load scripts instead of SQLite inserts
- Scripts are executed remotely via SSH (`RemoteExecutor` — mock by default)
- Configure remote hosts via `ETL_SSH_HOST`, `ETL_SSH_USER`, `TD_SSH_HOST`, `TD_SSH_USER`
- Pipeline steps can be skipped with `skip_profiling`, `skip_subsetting`, `skip_masking`, `skip_provisioning` flags

---

## Agent Details

### ProfilingAgent
Reads DML/DDL files from `mock_data/`, parses field names and types, classifies each field as: PII, Control, SCD-2, Key, or Business. Detects FK relationships via naming conventions. Optionally calls Claude API for deeper analysis. Saves a JSON profile report to `knowledge_base/profiles/`.

### SubsettingAgent
Takes profiled tables and generates referentially-intact SQL using an anchor table strategy (IN-subquery joins). Validates FK integrity before extraction. Saves extracted data as CSVs to `extracted_data/`.

### MaskingAgent
Anonymizes PII fields with deterministic masking (same input always produces same output via a hash-keyed cache dict). Type-specific routing:
- `name`/`nm` fields → `fake.name()`
- `street`/`addr` fields → `fake.street_address()`
- `city`/`cty` fields → `fake.city()`
- `state`/`st_abbr` fields → `fake.state_abbr()`
- `zip`/`postal` fields → `fake.zipcode()`
- `phone` fields → `555-XXXX` format
- `id` fields → SHA-256 hash

### ProvisioningAgent
Loads masked data into target SQLite DB with transaction safety (rollback on partial failure). Runs validation checks: row counts match, all expected columns exist, NOT NULL constraints satisfied. Returns pass/fail per check.

---

## POC Results (clean run)

| Metric | Value |
|---|---|
| Tables Profiled | 3 |
| Fields Analyzed | 130 |
| PII Fields Detected | 36 |
| Relationships Mapped | 30 |
| Rows Extracted | 150 |
| Values Masked | 1,644 |
| Rows Provisioned | 150 |
| Validation Checks | 27/27 PASSED |

---

## CI/CD

GitHub Actions runs automatically on every push to `main`:

1. Sets up Python 3.12
2. Installs dependencies from `requirements.txt`
3. Seeds the SQLite databases (`python -m utils.db_setup`)
4. Runs the full 4-agent pipeline demo (`python -m orchestrator.demo`)
5. Runs pytest — **48 tests** across pipeline, API, parsers, and enterprise features (`python -m pytest tests/ -v`)

Workflow file: [`.github/workflows/test.yml`](.github/workflows/test.yml)

### Test Coverage
| Test File | Tests | What's Covered |
|---|---|---|
| `test_pipeline.py` | 15 | End-to-end pipeline, individual agents, input validation, edge cases |
| `test_api.py` | 5 | Health check, list tables, provision, 404 handling |
| `test_parsers.py` | 10 | DML/DDL parsing, field extraction, empty input handling |
| `test_gemini_features.py` | 18 | Retry logic, skip flags, persistent storage, enterprise XFR/BTEQ generation, RemoteExecutor, Bedrock fallback |

---

## Phase 2 — Enterprise Stack Mapping

When productionizing, these POC components swap out:

| POC Component | Enterprise Replacement | Status |
|---|---|---|
| SQLite (source DB) | Teradata | Pending — swap SQLAlchemy dialect + teradatasql driver |
| SQLite (target DB) | Teradata test schema | Pending — same swap |
| Local DML files | Ab Initio GDE file system (RHEL paths) | Pending — config change only |
| Claude API direct | AWS Bedrock (Claude via Bedrock SDK) | **Done** — `LLM_PROVIDER=BEDROCK` in `llm_client.py` |
| In-memory masking | Ab Initio `.xfr` script generation | **Done** — `ENTERPRISE_MODE=true` in MaskingAgent |
| SQLite provisioning | Teradata `.bteq` script generation | **Done** — `ENTERPRISE_MODE=true` in ProvisioningAgent |
| Local execution | SSH remote execution via `paramiko` | **Done** — `RemoteExecutor` (mock by default) |
| Local JSON storage | AWS S3 (boto3) | Pending — profile reports pushed to S3 bucket |
| Local Docker run | Docker → Nexus → ArgoCD → EKS | Pending — same container, different deployment |
| FastAPI local server | EKS service + AWS ALB | Pending — Kubernetes deployment |
| Autosys | Trigger provisioning jobs via Autosys JIL | Pending — replaces manual curl |
| Connect:Direct | File transfer of DML/DDL to engine | Pending — replaces local file reads |

**Current test volume (manual baseline):** 7 cycles/quarter × 3 batches/cycle × ~10 hrs/batch = ~210 hrs/quarter manual effort being targeted for automation.

---

## License

Confidential — All rights reserved. Not for redistribution or reuse without explicit permission.
