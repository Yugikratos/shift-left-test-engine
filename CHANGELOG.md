# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (Phase 2 - GitOps & Architecture)
- **Infrastructure:** Created `docker-compose.yml` to orchestrate isolated API and PostgreSQL containers, mocking the Teradata network boundary. (Authored by Google Gemini)
- **Kubernetes:** Created production-ready K8s manifests in `k8s/` (`deployment.yaml`, `service.yaml`, `ingress.yaml`) featuring liveness probes and resource limits. (Authored by Google Gemini)
- **GitOps:** Configured declarative continuous deployment via `argocd-application.yaml`. (Authored by Google Gemini)
- **Local Simulation:** Created `init_local_gitops.ps1` to locally mock the entire Enterprise release perimeter by booting Sonatype Nexus and natively installing ArgoCD to the local K8s cluster. (Authored by Google Gemini)
- **CI/CD:** Extended GitHub Actions test workflow to securely build and push Docker images. Bypassed external credential firewalls to deploy strictly to the local simulated Nexus. (Authored by Google Gemini)

### Fixed
- **Provisioning Warnings:** Suppressed native Pandas `UserWarning` case-sensitivity SQLite table insertion spam by proactively lowering target tables prior to executing standard ORM `.to_sql()` operations. (Authored by Google Gemini)
- **Terminal Crash:** Swapped strict Unicode dashboard console characters for UTF/ASCII compliant output formatting to prevent localized Windows encoding crashes. (Authored by Google Gemini)
- **Object Storage:** Created `S3StorageClient` in `utils/storage_client.py` wrapping standard AWS `boto3` capabilities unconditionally to ensure Kubernetes stateless architecture compliance. (Authored by Google Gemini)
- **Database Pooling:** Added `utils/database.py` leveraging `sqlalchemy.engine` and `psycopg2` context managers for synchronous standard execution. (Authored by Google Gemini)

### Changed (Phase 2 - GitOps & Architecture)
- **Stateless Infrastructure:** Stripped ephemeral file creations (`with open()`) across all agents and orchestrators, replacing disk logic with direct Boto3 string-buffer remote streams to S3 buckets. (Authored by Google Gemini)
- **Database Engine Refactoring:** Replaced all hard-coded `sqlite3` driver usage with standard Pandas `DataFrame.to_sql()` and `pd.read_sql()` executions to resolve PostgreSQL/Teradata query incompatibilities. (Authored by Google Gemini)
- **Database Orchestration:** Refactored `orchestrator/engine.py` pipeline job tracking to use active SQLAlchemy ORM `.merge()` logic instead of fragile flat files. (Authored by Google Gemini)
- **Docker:** Optimized `Dockerfile` for Enterprise production — runs securely as non-root `appuser`, configured performance ENV variables, and stripped stateful SQLite seeding from the build. (Authored by Google Gemini)

### Added
- **Orchestrator:** Wired up `AgentCoordinator` and `StatusTracker` into `OrchestratorEngine` — agents now run through the coordinator with task logging, and request lifecycle is tracked in-memory via the status tracker. (Modified by Claude)
- **API:** `POST /api/v1/provision/async` now actually runs the pipeline in the background via FastAPI `BackgroundTasks`. Poll `/api/v1/status/{id}` for progress. (Modified by Claude)
- **Tests:** Added `tests/test_coordinator_status.py` with 14 tests covering `AgentCoordinator` (assign, progress, task log, reset) and `StatusTracker` (register, lifecycle, summary, errors). Total tests: 62. (Modified by Claude)

### Changed
- **Masking:** `MaskingAgent._detect_pii_type()` now includes `PII_ID_PATTERNS` (`tax_id`, `ein`, `passport`) in fallback detection — previously these columns could bypass masking entirely. (Modified by Claude)
- **Subsetting:** Added `_sanitize_identifier()` to `SubsettingAgent` — validates all table and column names against `^\w+$` before SQL interpolation to prevent injection. (Modified by Claude)
- **Parsers:** Replaced `print()` warnings in `dml_parser.py` and `ddl_parser.py` with structured `loguru` logging. (Modified by Claude)
- **Deps:** Updated `requirements.txt` to match installed versions (fastapi 0.135.2, uvicorn 0.42.0, pydantic 2.12.5, pandas 3.0.1, faker 40.11.1, rich 14.3.3, loguru 0.7.3, httpx 0.28.1, pytest 9.0.2). Added `pytest-cov==7.1.0`. (Modified by Claude)

### Fixed
- **db_setup:** Corrected seed count print from ~690 to ~780 (was missing 90 `etl_src_ctl` records). (Modified by Claude)

### Previously Added
- **Enterprise Mode:** Implemented `ENTERPRISE_MODE` toggle in `config/settings.py` to bypass local execution. (Authored by Google Gemini)
- **Code Generation:** `MaskingAgent` now generates Ab Initio `.XFR` transform scripts natively when in Enterprise Mode. (Authored by Google Gemini)
- **Code Generation:** `ProvisioningAgent` now generates Teradata `.BTEQ` load scripts natively when in Enterprise Mode. (Authored by Google Gemini)
- **Cloud Security:** Upgraded `llm_client.py` to dynamically proxy requests securely through AWS Bedrock using `boto3` when `LLM_PROVIDER=BEDROCK`. (Authored by Google Gemini)
- **Remote Execution:** Added `RemoteExecutor` stub via `paramiko` to safely trigger Ab Initio `air sandbox run` mock commands over SSH. (Authored by Google Gemini)
- **Orchestrator:** Introduced `skip_profiling`, `skip_subsetting`, `skip_masking`, and `skip_provisioning` execution flags for flexible selective pipeline execution. (Authored by Google Gemini)
- **Docs:** Added `CHANGELOG.md` to track project evolution. (Authored by Google Gemini)
- **Docs:** Established AI collaboration guidelines in `CLAUDE.md` for co-authorship attribution. (Authored by Google Gemini)
- **Tests:** Added `tests/test_engine_features.py` with 11 tests covering retry logic, skip flag validation, and persistent job storage. (Authored by Claude)
- **Tests:** Added 7 enterprise mode tests — XFR generation, BTEQ generation, RemoteExecutor mock, Bedrock fallback validation. (Authored by Claude)

### Changed
- **Orchestrator:** Replaced in-memory `self._requests` dict with persistent `metadata.db` SQLite store — pipeline jobs now survive API restarts. (Authored by Google Gemini)
- **Orchestrator:** Replaced all `print()` calls with structured `loguru` logging (console + rotating file at `logs/`). (Authored by Google Gemini)
- **Orchestrator:** Skip flags now validate dependency chain — cannot skip subsetting without masking, or masking without provisioning. (Authored by Claude)
- **Orchestrator:** Restored strict empty-tables validation regardless of skip flags. (Authored by Claude)
- **Orchestrator:** Restored docstrings removed during Gemini refactor. (Authored by Claude)
- **Agents:** `BaseAgent.run()` now only retries on transient errors (`ConnectionError`, `TimeoutError`, `OSError`) with linear backoff — non-transient exceptions fail immediately. (Authored by Claude, improved from Google Gemini)

### Fixed
- **Security:** `RemoteExecutor` now uses `paramiko.RejectPolicy()` with known-hosts verification instead of `AutoAddPolicy()`. (Authored by Claude)
- **Security:** BTEQ scripts no longer contain hardcoded `.LOGON TDPID/USER,PASSWORD` — use `.RUN FILE=logon.bteq` for credential sourcing. (Authored by Claude)
- **Security:** BTEQ scripts now wrap operations in `BT;`/`ET;` transaction blocks. (Authored by Claude)
- **Enterprise:** Hardcoded SSH hostnames/users moved to `config/settings.py` with env var overrides (`ETL_SSH_HOST`, `ETL_SSH_USER`, `TD_SSH_HOST`, `TD_SSH_USER`). (Authored by Claude)
- **Enterprise:** `MaskingAgent` now emits a warning that XFR stub passes unmasked schema only. (Authored by Claude)
- **Enterprise:** Both agents now validate data exists before generating scripts in enterprise mode. (Authored by Claude)
- **LLM:** `LLM_ENABLED` for Bedrock now requires `AWS_DEFAULT_REGION` to be set, preventing silent failures. (Authored by Claude)
- **Deps:** Re-pinned `sqlalchemy==2.0.48`, `boto3==1.35.0`, `paramiko==3.5.0` — unpinned deps removed. (Authored by Claude)
- **Imports:** Moved `RemoteExecutor` imports from inside `execute()` to top-level in both agents. (Authored by Claude)

### Removed
- **Repo:** Removed accidentally committed output files (`.coverage`, `test_results*.txt`, `coverage_results.txt`) and added them to `.gitignore`. (Authored by Claude)

## [0.1.0] - POC Baseline
### Added
- Initial Proof of Concept (POC) for Agentic Test Data Setup Engine.
- 4 sequenced AI agents: Profiling, Smart Subsetting, Data Masking, Data Provisioning.
- FastAPI backend with in-memory request store.
- Parsers for Ab Initio target DMLs and Teradata DDL definitions.
- Local SQLite database handling for `source_data` and `target_test`.
- Test suite with 30 comprehensive validations.
