# CLAUDE.md
<!-- Modified by Antigravity to include AI Collaboration Rules -->

This file provides guidance to Claude Code (claude.ai/code) and Antigravity when working with code in this repository.

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
python -m pytest tests/ -v                     # Run all 30 tests
python -m orchestrator.demo                    # Run full pipeline demo
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
- **MaskingAgent** — Anonymizes PII with consistent masking (same input → same output via hash-keyed cache). Uses Faker for type-specific output: names→`fake.name()`, addresses→`fake.street_address()`, cities→`fake.city()`, states→`fake.state_abbr()`, zips→`fake.zipcode()`, phones→`555-XXXX`, IDs→SHA-256 hash. Pattern-based detection only (Presidio removed).
- **ProvisioningAgent** — Loads masked data into target SQLite DB with transaction safety (rollback on partial failure). Runs validation checks (row counts, column existence, NOT NULL constraints).

### Key Modules

- **`orchestrator/engine.py`** — Core engine: request validation (empty tables, invalid date ranges), plan building, pipeline execution, report consolidation
- **`api/main.py`** — FastAPI REST layer with lifespan-based startup and in-memory request store
- **`config/settings.py`** — All settings including PII/control/SCD-2/relationship detection patterns; all paths overridable via env vars
- **`utils/llm_client.py`** — Singleton Claude API client with lazy init and graceful degradation
- **`utils/db_setup.py`** — Creates SQLite schema (mirrors Teradata structure) and seeds with Faker data
- **`parsers/dml_parser.py`** — Ab Initio DML format parser
- **`parsers/ddl_parser.py`** — Teradata DDL parser

## Dual-Mode Design

The system operates without an API key via rule-based pattern matching defined in `config/settings.py` (PII patterns like `_nm`, `_addr`, `_phone`; relationship patterns via `_id`/`_nbr` column matching). With an API key, the profiling agent uses Claude for intelligent schema analysis. The `LLMClient` returns `None` when unavailable — callers must handle this gracefully.

## Testing

30 tests across 3 files:
- `tests/test_pipeline.py` (15) — End-to-end pipeline, individual agents, input validation, edge cases
- `tests/test_api.py` (5) — Health check, list tables, provision, 404 handling
- `tests/test_parsers.py` (10) — DML/DDL parsing, field extraction, empty input handling

GitHub Actions CI runs on every push/PR to `main` (`.github/workflows/test.yml`).

## Environment

- Python 3.10+ (3.14 local dev — use `--prefer-binary` flag)
- SQLite for local dev (production target: Teradata)
- `.env` file for config (see `.env.example`); all paths overridable via env vars
- Reports saved as JSON to `knowledge_base/profiles/`
- Mock data (DML/DDL/CSV) lives in `mock_data/`

## AI Assistant Rules
Whenever an AI assistant (Google Gemini or Claude) makes changes to this repository:
1. **Git Commits:** Always add the respective AI (or both) as co-authors to Git commit messages via Git trailers.
   Example: 
   `Co-authored-by: Google Gemini <noreply@google.com>`
   `Co-authored-by: Claude <claude@anthropic.com>`
2. **File Modifications:** Explicitly add a mention/comment indicating that the change was done by you (e.g., `Authored by Google Gemini` or `Modified by Claude`) in docstrings or inline comments wherever required or whenever significant logic is changed.
