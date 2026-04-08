# CLAUDE_CONTEXT.md — Shift-Left Test Data Engine POC

## Project Purpose
This is a POC validating the Agentic Test Data Setup Engine concept for automated test data provisioning in ETL/data warehouse environments.
Built on a personal Windows machine using a personal Claude subscription.
Goal: Demonstrate the 4-agent pipeline works end-to-end.

## Current Status
- Phase 1 (Fix POC bugs): COMPLETE
- Phase 1.5 (Code quality, CI, tests): COMPLETE — 48 tests, GitHub Actions CI, hardened DB handling
- Phase 2 (Map to real stack): IN PROGRESS — Enterprise mode, Bedrock, SSH execution, XFR/BTEQ generation done

## Working Commands
```
# Activate venv (always do this first)
venv\Scripts\Activate.ps1

# Reset and seed databases
python -m utils.db_setup

# Run demo pipeline (CLI)
python -m orchestrator.demo

# Run API server
python -m uvicorn api.main:app --port 8000
# Then open: http://127.0.0.1:8000/docs

# Run tests (48 tests)
python -m pytest tests/ -v
```

## Development Stack

### Language & Runtime
- Python 3.14 (local dev) — install packages with `--prefer-binary` flag
- Python 3.10+ minimum for production compatibility

### POC Python Libraries (currently installed & working)
| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.135.2 | REST API framework |
| uvicorn | 0.42.0 | ASGI server |
| pydantic | 2.12.5 | Data validation & settings |
| python-dotenv | 1.2.2 | .env file loader |
| anthropic | 0.86.0 | Claude API client (LLM mode) |
| pandas | 3.0.1 | Data manipulation |
| faker | 40.11.1 | Synthetic data generation & PII masking |
| sqlalchemy | 2.0.48 | ORM / DB abstraction (SQLite POC) |
| boto3 | 1.35.0 | AWS SDK — Bedrock LLM provider (optional) |
| paramiko | 3.5.0 | SSH client — enterprise remote execution (optional) |
| rich | 14.3.3 | Terminal output formatting |
| loguru | 0.7.3 | Structured logging |
| httpx | 0.28.1 | HTTP client (API testing) |
| pytest | 9.0.2 | Test framework |
| pytest-cov | 7.1.0 | Test coverage reporting |

> **Note:** Install with `pip install <package> --prefer-binary` on Python 3.14 to avoid build failures.

### Dev Tools
- **IDE:** VS Code
- **Version Control:** Git
- **Shell:** PowerShell (Windows)
- **Virtual Env:** venv (`venv\Scripts\Activate.ps1`)
- **API Testing:** curl / FastAPI Swagger UI (`/docs`)
- **AI Assistants:** Claude Code (claude.ai/code), Antigravity (Google Gemini)

### Phase 2 Target — Enterprise Stack
| Component | Technology | Status |
|---|---|---|
| ETL | Ab Initio (GDE + air commands on RHEL servers) | XFR generation done |
| Data Warehouse | Teradata | BTEQ generation done |
| LLM (cloud) | AWS Bedrock (Claude via Bedrock SDK) | Done |
| Remote Execution | SSH via paramiko | Done (mock by default) |
| Job Scheduling | Autosys | Pending |
| File Transfer | Connect:Direct | Pending |
| Container Platform | AWS EKS (Docker + Nexus + ArgoCD) | Pending |
| Object Storage | AWS S3 (boto3) | Pending |
| CI/CD | Jenkins + ArgoCD | Pending |
| Ingress | AWS ALB | Pending |
| OS (servers) | RHEL | Pending |
| Test Volume | 7 cycles/quarter, 3 batches/cycle, ~10 hrs manual/batch | — |

## Folder Structure
```
shift-left-test-engine/
├── agents/
│   ├── base_agent.py           # Abstract base — all agents inherit from this
│   ├── profiling_agent.py      # Scans tables, detects PII, maps relationships
│   ├── subsetting_agent.py     # Extracts anchor-based data slice
│   ├── masking_agent.py        # Type-aware PII masking (local) or XFR generation (enterprise)
│   └── provisioning_agent.py   # SQLite load (local) or BTEQ generation (enterprise)
├── orchestrator/
│   ├── engine.py               # OrchestratorEngine — coordinates all 4 agents, persistent job store
│   ├── coordinator.py          # AgentCoordinator — task assignment & progress
│   ├── status.py               # StatusTracker — request lifecycle tracking
│   └── demo.py                 # CLI demo runner
├── api/
│   └── main.py                 # FastAPI REST endpoints (lifespan-based startup)
├── parsers/
│   ├── dml_parser.py           # Ab Initio DML format parser
│   └── ddl_parser.py           # Teradata DDL parser
├── utils/
│   ├── db_setup.py             # Seeds source_data.db with ~780 mock records (5 tables)
│   ├── llm_client.py           # LLM client (Anthropic/Bedrock) with graceful fallback
│   ├── logger.py               # Loguru logger with console + file rotation
│   └── remote_executor.py      # SSH remote executor (mock/real) for enterprise mode
├── config/
│   └── settings.py             # Env vars, PII/relationship patterns, enterprise host config
├── tests/
│   ├── test_pipeline.py        # Pipeline + agent tests (15 tests)
│   ├── test_api.py             # API endpoint tests (5 tests)
│   ├── test_parsers.py         # DML/DDL parser tests (10 tests)
│   └── test_engine_features.py # Retry, skip flags, persistence, enterprise mode (18 tests)
├── knowledge_base/
│   └── profiles/               # JSON reports saved after each run
├── mock_data/
│   ├── dml/                    # Sample Ab Initio DML files
│   └── ddl/                    # Sample Teradata DDL files
├── .github/workflows/test.yml  # GitHub Actions CI pipeline
├── .env.example                # Config template (LLM, enterprise, paths)
├── requirements.txt            # Pinned Python dependencies
├── CHANGELOG.md                # Project changelog
└── Dockerfile                  # Python 3.12, non-root, healthcheck
```

## Bugs Fixed
1. Table deduplication: Profiling agent was treating STG_BUSINESS_ENTITY and 
   stg_business_entity as separate tables due to case sensitivity. Fixed by 
   normalizing table names to uppercase at ingestion.

2. Masking quality: All PII fields were getting generic tokens (1 MASKED ST, PERSON_0001).
   Fixed masking_agent.py to use type-aware Faker routing:
   - name/nm fields → fake.name()
   - street/addr fields → fake.street_address()
   - city/cty fields → fake.city()
   - state/st_abbr fields → fake.state_abbr()
   - zip/postal fields → fake.zipcode()
   - Referential consistency maintained via cache dict per field type

## Demo Output (clean run)
- Tables Profiled: 3
- Fields: 130
- PII Fields: 36
- Relationships: 30
- Rows Extracted: 150
- Values Masked: 1644
- Rows Loaded: 150
- Validation: PASSED (27/27 checks)

## LLM Mode
Currently running in Rule-Based Fallback (no API key set).
To enable LLM mode: add ANTHROPIC_API_KEY=sk-ant-xxx to .env file.
To use Bedrock: set LLM_PROVIDER=BEDROCK and AWS_DEFAULT_REGION.
Do NOT spend personal money on this — wait for work API access.

---

At the start of every new Claude Code session, just say:
```
Read CLAUDE_CONTEXT.md and use it as your starting context for this project.
```
