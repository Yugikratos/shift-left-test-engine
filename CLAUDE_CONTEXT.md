# CLAUDE_CONTEXT.md — Shift-Left Test Data Engine POC

## Project Purpose
This is a POC validating the Agentic Test Data Setup Engine concept for automated test data provisioning in ETL/data warehouse environments.
Built on a personal Windows machine using a personal Claude subscription.
Goal: Demonstrate the 5-agent pipeline works end-to-end.

## Current Status
- Phase 1 (Fix POC bugs): COMPLETE
- Phase 2 (Map to real stack — Ab Initio, Teradata, Autosys): NOT STARTED

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
| rich | 14.3.3 | Terminal output formatting |
| loguru | 0.7.3 | Structured logging |
| httpx | 0.28.1 | HTTP client (API testing) |
| pytest | 8.3.3 | Test framework |
| presidio-analyzer | NOT installed | PII detection (masking works via pattern fallback) |
| presidio-anonymizer | NOT installed | PII anonymization (not needed for POC) |

> **Note:** Install with `pip install <package> --prefer-binary` on Python 3.14 to avoid build failures.

### Dev Tools
- **IDE:** VS Code
- **Version Control:** Git
- **Shell:** PowerShell (Windows)
- **Virtual Env:** venv (`venv\Scripts\Activate.ps1`)
- **API Testing:** curl / FastAPI Swagger UI (`/docs`)
- **AI Assistant:** Claude Code (claude.ai/code)

### Phase 2 Target — Enterprise Stack
| Component | Technology |
|---|---|
| ETL | Ab Initio (GDE + air commands on RHEL servers) |
| Data Warehouse | Teradata |
| Job Scheduling | Autosys |
| File Transfer | Connect:Direct |
| Container Platform | AWS EKS (Docker + Nexus + ArgoCD) |
| Object Storage | AWS S3 (boto3) |
| LLM (cloud) | AWS Bedrock (Claude via Bedrock SDK) |
| CI/CD | Jenkins + ArgoCD |
| Ingress | AWS ALB |
| OS (servers) | RHEL |
| Test Volume | 7 cycles/quarter, 3 batches/cycle, ~10 hrs manual/batch |

## Folder Structure
```
shift-left-test-engine/
├── agents/
│   ├── profiling_agent.py      # Scans tables, detects PII, maps relationships
│   ├── subsetting_agent.py     # Extracts anchor-based data slice
│   ├── masking_agent.py        # Type-aware PII masking using Faker
│   └── provisioning_agent.py   # Loads to target DB, runs validation checks
├── orchestrator/
│   ├── engine.py               # OrchestratorEngine — coordinates all 4 agents
│   └── demo.py                 # CLI demo runner
├── api/
│   └── main.py                 # FastAPI REST endpoints
├── utils/
│   ├── db_setup.py             # Seeds source_data.db with ~690 mock records
│   ├── llm_client.py           # Anthropic API client (falls back to rule-based)
│   └── logger.py               # Loguru logger
├── config/
│   └── settings.py             # Loads .env, defines BASE_DIR
├── knowledge_base/
│   └── profiles/               # JSON reports saved after each run
├── source_data.db              # SQLite source database (mock data)
├── target_test.db              # SQLite target database (provisioned output)
├── requirements.txt            # Original pinned versions (some fail on Python 3.14)
└── .env                        # API keys (ANTHROPIC_API_KEY not set — fallback mode)
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
Do NOT spend personal money on this — wait for work API access.

## Real Stack (for Phase 2 mapping — TO BE DOCUMENTED)
- ETL: Ab Initio (GDE + air commands on RHEL servers)
- Database: Teradata
- Job Scheduling: Autosys
- File Transfer: Connect:Direct
- Cloud: AWS (EKS, S3, Docker, Jenkins, ArgoCD)
- Test cycles: 7 per quarter, 3 batches per cycle, ~10 hours manual per batch

---

At the start of every new Claude Code session, just say:
```
Read CLAUDE_CONTEXT.md and use it as your starting context for this project.