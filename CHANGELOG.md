# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
