# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Shift-Left Test Data Engine — POC

## What this is
An AI-powered multi-agent system for automated test data provisioning (Ab Initio ETL / Teradata data warehouse context).

## How to run
```bash
python -m utils.db_setup                       # Initialize databases with Faker data
python -m orchestrator.demo                    # Run full pipeline demo
uvicorn api.main:app --reload --port 8000      # Start API server
```

## How to test
```bash
python -m orchestrator.demo
```

## Key architecture
- 4 agents run in sequence: Profiling → Subsetting → Masking → Provisioning
- Works without Claude API key (rule-based fallback)
- DML/DDL parsers handle Ab Initio target format DMLs and Teradata DDL

## Commands

```bash
# Setup
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m utils.db_setup                       # Initialize SQLite source/target DBs

# Run
uvicorn api.main:app --reload --port 8000      # API server
python -m orchestrator.demo                    # Run demo scenario directly

# Test
python -m pytest tests/

# Test API manually
curl -X POST http://localhost:8000/api/v1/provision \
  -H "Content-Type: application/json" \
  -d '{"scenario": "business_entity_flow", "tables": ["stg_business_entity", "business_address_match", "business_credit_score"], "record_count": 100, "date_range": {"start": "2024-01-01", "end": "2024-12-31"}}'
```

## Architecture

**Sequential 4-agent pipeline** coordinated by `OrchestratorEngine`:

```
API Request → OrchestratorEngine → Profiling → Subsetting → Masking → Provisioning → Report
```

**Agent communication:** A mutable `context` dict is passed through the pipeline. Each agent reads what it needs and adds its output for the next agent. Agents never call each other directly — only the orchestrator coordinates.

**Key context keys accumulated through the pipeline:**
- After Profiling: `context["profile_report"]`, `context["pii_summary"]`
- After Subsetting: `context["extracted_data"]`
- After Masking: `context["masked_data"]`
- Provisioning uses all of the above

**All agents** inherit from `BaseAgent` (abstract) and implement `execute(context) -> AgentResult`. The `run()` wrapper adds timing. `AgentResult` standardizes output with status, data dict, errors, warnings, summary, and timing.

### Agent Details

- **ProfilingAgent** — Parses DML/DDL files, classifies fields (PII, Control, SCD-2, Key, Business), detects relationships via naming conventions, optionally uses Claude for deeper analysis. Saves profile to `knowledge_base/profiles/`.
- **SubsettingAgent** — Generates referentially-intact SQL using anchor table strategy with IN-subquery joins. Validates FK integrity. Saves CSVs to `extracted_data/`.
- **MaskingAgent** — Anonymizes PII with consistent masking (same input → same output via hash map). Type-specific: names→`PERSON_XXXX`, addresses→`N MASKED ST`, phones→`555XXXX`, IDs→SHA256.
- **ProvisioningAgent** — Loads masked data into target SQLite DB. Runs validation checks (row counts, column existence, NOT NULL constraints).

### Key Modules

- **`orchestrator/engine.py`** — Core engine: request validation, plan building, pipeline execution, report consolidation
- **`api/main.py`** — FastAPI REST layer with in-memory request store
- **`config/settings.py`** — All settings including PII/control/SCD-2/relationship detection patterns
- **`utils/llm_client.py`** — Singleton Claude API client with lazy init and graceful degradation
- **`utils/db_setup.py`** — Creates SQLite schema (mirrors Teradata structure) and seeds with Faker data
- **`parsers/dml_parser.py`** — Ab Initio DML format parser
- **`parsers/ddl_parser.py`** — Teradata DDL parser

## Dual-Mode Design

The system operates without an API key via rule-based pattern matching defined in `config/settings.py` (PII patterns like `_nm`, `_addr`, `_phone`; relationship patterns via `_id`/`_nbr` column matching). With an API key, the profiling agent uses Claude for intelligent schema analysis. The `LLMClient` returns `None` when unavailable — callers must handle this gracefully.

## Environment

- Python 3.10+
- SQLite for local dev (production target: Teradata)
- `.env` file for config (see `.env.example`)
- Reports saved as JSON to `knowledge_base/profiles/`
- Mock data (DML/DDL/CSV) lives in `mock_data/`
