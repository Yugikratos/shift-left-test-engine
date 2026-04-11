"""Demo script — runs the full test data provisioning pipeline end-to-end.

Usage:
    python -m orchestrator.demo
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db_setup import setup_all, SOURCE_DB_PATH
from orchestrator.engine import OrchestratorEngine


def run_demo():
    """Execute a full demo scenario."""

    print("\n" + "=" * 60)
    print("  SHIFT-LEFT TEST DATA ENGINE — POC DEMO")
    print("  Agentic Test Data Setup Engine")
    print("=" * 60)

    # Step 0: Setup databases if needed
    if not SOURCE_DB_PATH.exists():
        print("\n  Source database not found. Running setup...")
        setup_all()
    else:
        print(f"\n  Source database found: {SOURCE_DB_PATH}")

    # Step 1: Create orchestrator
    engine = OrchestratorEngine()

    # Step 2: Submit a test data request
    request = {
        "scenario": "business_entity_flow",
        "tables": [
            "stg_business_entity",
            "business_credit_score",
            "business_address_match",
        ],
        "record_count": 50,
        "date_range": {
            "start": "2024-01-01",
            "end": "2024-12-31",
        },
    }

    print(f"\n  Submitting request:")
    print(f"    Scenario:     {request['scenario']}")
    print(f"    Tables:       {', '.join(request['tables'])}")
    print(f"    Record Count: {request['record_count']}")
    print(f"    Date Range:   {request['date_range']['start']} to {request['date_range']['end']}")

    # Step 3: Process request through the full pipeline
    report = engine.process_request(request)

    # Step 4: Display results
    print("\n" + "=" * 60)
    print("  EXECUTION REPORT")
    print("=" * 60)

    summary = report.get("summary", {})
    print(f"\n  Status:              {report['status'].upper()}")
    print(f"  LLM Mode:            {report.get('llm_mode', 'N/A')}")
    print(f"  Tables Profiled:     {summary.get('tables_profiled', 0)}")
    print(f"  Total Fields:        {summary.get('total_fields', 0)}")
    print(f"  PII Fields Detected: {summary.get('pii_fields_detected', 0)}")
    print(f"  Relationships Found: {summary.get('relationships_found', 0)}")
    print(f"  Rows Extracted:      {summary.get('rows_extracted', 0)}")
    print(f"  Values Masked:       {summary.get('values_masked', 0)}")
    print(f"  Rows Loaded:         {summary.get('rows_loaded', 0)}")
    print(f"  Validation:          {summary.get('validation_status', 'N/A')}")

    # Agent details
    print(f"\n  {'Agent':<30} {'Status':<12} {'Duration':<12} {'Summary'}")
    print(f"  {'-'*90}")
    for agent_name, agent_info in report.get("agent_results", {}).items():
        duration = f"{agent_info.get('duration_seconds', 0):.2f}s"
        agent_summary = agent_info.get("summary", "")[:60]
        print(f"  {agent_name:<30} {agent_info['status']:<12} {duration:<12} {agent_summary}")

    # Before/After masking samples
    masking_detail = report.get("detailed_data", {}).get("masking", {})
    samples = masking_detail.get("before_after_samples", {})
    if samples:
        print(f"\n  MASKING BEFORE/AFTER SAMPLES:")
        print(f"  {'-'*70}")
        for table, fields in samples.items():
            print(f"\n  Table: {table}")
            for col, vals in list(fields.items())[:5]:
                print(f"    {col:<25} {str(vals['before'])[:20]:<22} -> {str(vals['after'])[:20]}")

    # Validation details
    prov_detail = report.get("detailed_data", {}).get("provisioning", {})
    validation = prov_detail.get("validation", {})
    if validation:
        print(f"\n  VALIDATION RESULTS:")
        print(f"  {'-'*70}")
        print(f"  Overall: {validation.get('overall_status', 'N/A')} "
              f"({validation.get('passed', 0)}/{validation.get('total_checks', 0)} checks passed)")

        for table_name, table_val in validation.get("by_table", {}).items():
            status_icon = "[PASS]" if table_val.get("passed") else "[FAIL]"
            print(f"    {status_icon} {table_name}: {table_val.get('total_checks', 0)} checks")

    print(f"\n{'='*60}")
    print(f"  Demo complete. Full report saved to knowledge_base/profiles/")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    run_demo()
