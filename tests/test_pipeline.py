"""Pipeline tests — end-to-end and agent-level testing."""

import sqlite3

from orchestrator.engine import OrchestratorEngine
from agents.profiling_agent import ProfilingAgent
from agents.subsetting_agent import SubsettingAgent
from agents.masking_agent import MaskingAgent
from agents.provisioning_agent import ProvisioningAgent
from agents.base_agent import AgentStatus
from config.settings import BASE_DIR


# ── Helpers ─────────────────────────────────────────────

def _make_context(tables=None, record_count=10):
    """Build a standard test context dict."""
    return {
        "scenario": "test",
        "tables": tables or ["stg_business_entity", "business_credit_score", "business_address_match"],
        "record_count": record_count,
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        "source_db": str(BASE_DIR / "source_data.db"),
        "target_db": str(BASE_DIR / "target_test.db"),
    }


# ── End-to-End Pipeline ────────────────────────────────

def test_full_pipeline_completes():
    """Run the 4-agent pipeline end-to-end and verify it completes."""
    engine = OrchestratorEngine()
    report = engine.process_request({
        "scenario": "business_entity_flow",
        "tables": ["stg_business_entity", "business_credit_score", "business_address_match"],
        "record_count": 10,
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    })

    assert report["status"] == "completed"
    assert report["summary"]["tables_profiled"] == 3
    assert report["summary"]["rows_extracted"] > 0
    assert report["summary"]["values_masked"] > 0
    assert report["summary"]["rows_loaded"] > 0
    assert report["summary"]["validation_status"] == "PASSED"


def test_pipeline_with_single_table():
    """Pipeline works with just one table."""
    engine = OrchestratorEngine()
    report = engine.process_request({
        "scenario": "single_table",
        "tables": ["stg_business_entity"],
        "record_count": 5,
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    })

    assert report["status"] == "completed"
    assert report["summary"]["tables_profiled"] >= 1


# ── Input Validation ────────────────────────────────────

def test_empty_tables_raises():
    """Submitting empty tables list raises ValueError."""
    engine = OrchestratorEngine()
    try:
        engine.process_request({
            "scenario": "test",
            "tables": [],
            "record_count": 10,
        })
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "table" in str(e).lower()


def test_invalid_date_range_raises():
    """Date range with start > end raises ValueError."""
    engine = OrchestratorEngine()
    try:
        engine.process_request({
            "scenario": "test",
            "tables": ["stg_business_entity"],
            "record_count": 10,
            "date_range": {"start": "2025-01-01", "end": "2024-01-01"},
        })
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "date" in str(e).lower()


# ── Profiling Agent ─────────────────────────────────────

def test_profiling_agent_detects_pii():
    """ProfilingAgent finds PII fields in the mock schema."""
    agent = ProfilingAgent()
    context = _make_context()
    result = agent.run(context)

    assert result.status == AgentStatus.COMPLETED
    assert result.data["pii_summary"]["total_pii_fields"] > 0


def test_profiling_agent_detects_relationships():
    """ProfilingAgent maps cross-table relationships."""
    agent = ProfilingAgent()
    context = _make_context()
    result = agent.run(context)

    assert len(result.data["relationships"]) > 0


def test_profiling_agent_fallback_mode():
    """ProfilingAgent works in rule-based mode (no API key)."""
    agent = ProfilingAgent()
    context = _make_context()
    result = agent.run(context)

    assert result.status == AgentStatus.COMPLETED
    assert "Rule-Based" in result.summary or "rule_based" in str(result.data)


# ── Subsetting Agent ────────────────────────────────────

def test_subsetting_agent_extracts_data():
    """SubsettingAgent extracts rows with referential integrity."""
    profiler = ProfilingAgent()
    context = _make_context(record_count=5)
    profile_result = profiler.run(context)
    context["profile_report"] = profile_result.data
    context["pii_summary"] = profile_result.data.get("pii_summary", {})

    agent = SubsettingAgent()
    result = agent.run(context)

    assert result.status == AgentStatus.COMPLETED
    assert result.data["total_rows"] > 0
    assert result.data["tables_extracted"] >= 1


def test_subsetting_agent_no_profile_fails():
    """SubsettingAgent fails gracefully without profile report."""
    agent = SubsettingAgent()
    result = agent.run({"record_count": 10})

    assert result.status == AgentStatus.FAILED
    assert len(result.errors) > 0


# ── Masking Agent ───────────────────────────────────────

def test_masking_agent_masks_pii():
    """MaskingAgent anonymizes PII values."""
    profiler = ProfilingAgent()
    context = _make_context(record_count=5)
    profile_result = profiler.run(context)
    context["profile_report"] = profile_result.data
    context["pii_summary"] = profile_result.data.get("pii_summary", {})

    subsetter = SubsettingAgent()
    subset_result = subsetter.run(context)
    context["extracted_data"] = subset_result.data.get("extracted_data", {})

    agent = MaskingAgent()
    result = agent.run(context)

    assert result.status == AgentStatus.COMPLETED
    assert result.data["total_values_masked"] > 0


def test_masking_agent_no_data_fails():
    """MaskingAgent fails gracefully with no extracted data."""
    agent = MaskingAgent()
    result = agent.run({})

    assert result.status == AgentStatus.FAILED
    assert len(result.errors) > 0


def test_masking_consistency():
    """Same input value produces same masked output (referential integrity)."""
    agent = MaskingAgent()
    masked1 = agent._mask_value("John Doe", "PERSON_NAME", "t1", "bus_nm")
    masked2 = agent._mask_value("John Doe", "PERSON_NAME", "t2", "bus_nm")

    assert masked1 == masked2
    assert masked1 != "John Doe"


# ── Provisioning Agent ──────────────────────────────────

def test_provisioning_agent_no_data_fails():
    """ProvisioningAgent fails gracefully with no masked data."""
    agent = ProvisioningAgent()
    result = agent.run({})

    assert result.status == AgentStatus.FAILED
    assert len(result.errors) > 0


# ── Engine Methods ──────────────────────────────────────

def test_engine_get_request_returns_none_for_unknown():
    """get_request returns None for unknown request ID."""
    engine = OrchestratorEngine()
    assert engine.get_request("nonexistent") is None


def test_engine_get_status_returns_error_for_unknown():
    """get_status returns error dict for unknown request ID."""
    engine = OrchestratorEngine()
    status = engine.get_status("nonexistent")
    assert "error" in status
