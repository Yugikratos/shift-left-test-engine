"""Smoke test — runs the full pipeline and checks the result."""

from orchestrator.engine import OrchestratorEngine


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
