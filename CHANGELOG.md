# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Orchestrator:** Refactored `OrchestratorEngine` to use structured `loguru` logging instead of naked `print()` statements for enterprise tracing. (Authored by Antigravity)

### Added
- **Docs:** Added an explicit `CHANGELOG.md` to track project evolution. (Authored by Antigravity)
- **Docs:** Established AI collaboration guidelines in `CLAUDE.md`, mandating co-authorship markers and inline code attribution for both Claude and Antigravity. (Authored by Antigravity)

## [0.1.0] - POC Baseline
### Added
- Initial Proof of Concept (POC) for Agentic Test Data Setup Engine.
- 4 sequenced AI agents: Profiling, Smart Subsetting, Data Masking, Data Provisioning.
- FastAPI backend with in-memory request store.
- Parsers for Ab Initio target DMLs and Teradata DDL definitions.
- Local SQLite database handling for `source_data` and `target_test`.
- Test suite with 30 comprehensive validations.
