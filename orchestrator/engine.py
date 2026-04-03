"""Orchestrator Engine — coordinates the full test data provisioning pipeline.

Accepts a request, plans execution, runs agents in sequence, and produces
a consolidated report.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from agents.base_agent import AgentStatus
from agents.profiling_agent import ProfilingAgent
from agents.subsetting_agent import SubsettingAgent
from agents.masking_agent import MaskingAgent
from agents.provisioning_agent import ProvisioningAgent
from config.settings import BASE_DIR, KNOWLEDGE_BASE_DIR
from utils.llm_client import llm_client
from utils.logger import get_logger

log = get_logger("orchestrator")

class OrchestratorEngine:
    """Central orchestrator that manages the end-to-end test data provisioning pipeline."""

    def __init__(self):
        self.agents = {
            "profiling": ProfilingAgent(),
            "subsetting": SubsettingAgent(),
            "masking": MaskingAgent(),
            "provisioning": ProvisioningAgent(),
        }
        self._requests = {}  # In-memory request store

    def submit_request(self, request: dict) -> dict:
        """Submit a new test data provisioning request.

        Args:
            request: {
                "scenario": "business_entity_flow",
                "tables": ["stg_business_entity", "business_credit_score", ...],
                "record_count": 100,
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            }

        Returns:
            Request receipt with request_id and execution plan.
        """
        request_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Validate request
        scenario = request.get("scenario", "default")
        tables = request.get("tables", [])
        record_count = min(request.get("record_count", 100), 10000)
        date_range = request.get("date_range", {})

        if not tables:
            raise ValueError("At least one table must be specified")
        if date_range.get("start") and date_range.get("end"):
            if date_range["start"] > date_range["end"]:
                raise ValueError("Date range start must be before end")

        # Build execution plan
        execution_plan = self._build_execution_plan(scenario, tables, record_count)

        # Store request
        self._requests[request_id] = {
            "request_id": request_id,
            "submitted_at": timestamp,
            "scenario": scenario,
            "tables": tables,
            "record_count": record_count,
            "date_range": date_range,
            "execution_plan": execution_plan,
            "status": "submitted",
            "agent_results": {},
        }

        return {
            "request_id": request_id,
            "status": "submitted",
            "submitted_at": timestamp,
            "execution_plan": execution_plan,
        }

    def execute_request(self, request_id: str) -> dict:
        """Execute a submitted request through the full agent pipeline.

        Returns the consolidated result report.
        """
        if request_id not in self._requests:
            return {"error": f"Request {request_id} not found"}

        req = self._requests[request_id]
        req["status"] = "running"
        req["started_at"] = datetime.now().isoformat()

        context = {
            "request_id": request_id,
            "scenario": req["scenario"],
            "tables": req["tables"],
            "record_count": req["record_count"],
            "date_range": req["date_range"],
            "source_db": str(BASE_DIR / "source_data.db"),
            "target_db": str(BASE_DIR / "target_test.db"),
        }

        log.info(f"Executing Request: {request_id}")
        log.info(f"Scenario: {req['scenario']}")
        log.debug(f"Tables: {req['tables']}")
        log.info(f"Records: {req['record_count']}")
        log.debug(f"LLM Mode: {llm_client.mode}")

        # ── Step 1: Profiling ──
        log.info("[1/4] Running Data Profiling Agent...")
        profile_result = self.agents["profiling"].run(context)
        req["agent_results"]["profiling"] = profile_result.to_dict()
        log.info(f"→ {profile_result.summary}")

        if profile_result.status == AgentStatus.FAILED:
            req["status"] = "failed"
            return self._build_report(req)

        # Pass profiling output to next agents
        context["profile_report"] = profile_result.data
        context["pii_summary"] = profile_result.data.get("pii_summary", {})

        # ── Step 2: Subsetting ──
        log.info("[2/4] Running Smart Subsetting Agent...")
        subset_result = self.agents["subsetting"].run(context)
        req["agent_results"]["subsetting"] = subset_result.to_dict()
        log.info(f"→ {subset_result.summary}")

        if subset_result.status == AgentStatus.FAILED:
            req["status"] = "failed"
            return self._build_report(req)

        # Pass extracted data to masking
        context["extracted_data"] = subset_result.data.get("extracted_data", {})

        # ── Step 3: Masking ──
        log.info("[3/4] Running Data Masking Agent...")
        mask_result = self.agents["masking"].run(context)
        req["agent_results"]["masking"] = mask_result.to_dict()
        log.info(f"→ {mask_result.summary}")

        if mask_result.status == AgentStatus.FAILED:
            req["status"] = "failed"
            return self._build_report(req)

        # Pass masked data to provisioning
        context["masked_data"] = mask_result.data.get("masked_data", {})

        # ── Step 4: Provisioning ──
        log.info("[4/4] Running Data Provisioning Agent...")
        prov_result = self.agents["provisioning"].run(context)
        req["agent_results"]["provisioning"] = prov_result.to_dict()
        log.info(f"→ {prov_result.summary}")

        # Finalize
        req["status"] = "completed" if prov_result.status == AgentStatus.COMPLETED else "partial"
        req["completed_at"] = datetime.now().isoformat()

        report = self._build_report(req)

        # Save report
        self._save_report(request_id, report)

        log.info(f"Request {request_id}: {req['status'].upper()}")

        return report

    def process_request(self, request: dict) -> dict:
        """Convenience method — submit and execute in one call."""
        receipt = self.submit_request(request)
        return self.execute_request(receipt["request_id"])

    def get_status(self, request_id: str) -> dict:
        """Get current status of a request."""
        if request_id not in self._requests:
            return {"error": f"Request {request_id} not found"}

        req = self._requests[request_id]
        return {
            "request_id": request_id,
            "status": req["status"],
            "submitted_at": req.get("submitted_at"),
            "started_at": req.get("started_at"),
            "completed_at": req.get("completed_at"),
            "agent_statuses": {
                name: result.get("status", "pending")
                for name, result in req.get("agent_results", {}).items()
            },
        }

    def get_request(self, request_id: str) -> dict | None:
        """Get a request's full data by ID. Returns None if not found."""
        return self._requests.get(request_id)

    def _build_execution_plan(self, scenario: str, tables: list, record_count: int) -> list:
        """Build the execution plan (ordered list of agent steps)."""
        return [
            {"step": 1, "agent": "Data Profiling Agent", "action": "Analyze DML/DDL metadata, detect PII, map relationships"},
            {"step": 2, "agent": "Smart Subsetting Agent", "action": f"Extract {record_count} records with referential integrity"},
            {"step": 3, "agent": "Data Masking Agent", "action": "Anonymize PII fields (names, addresses, phones)"},
            {"step": 4, "agent": "Data Provisioning Agent", "action": "Load masked data into target DB and validate"},
        ]

    def _build_report(self, req: dict) -> dict:
        """Build consolidated report from all agent results."""
        agent_results = req.get("agent_results", {})

        # Extract key metrics
        profile_data = agent_results.get("profiling", {}).get("data", {})
        subset_data = agent_results.get("subsetting", {}).get("data", {})
        mask_data = agent_results.get("masking", {}).get("data", {})
        prov_data = agent_results.get("provisioning", {}).get("data", {})

        return {
            "request_id": req["request_id"],
            "status": req["status"],
            "scenario": req["scenario"],
            "submitted_at": req.get("submitted_at"),
            "completed_at": req.get("completed_at"),
            "llm_mode": llm_client.mode,
            "execution_plan": req.get("execution_plan", []),
            "summary": {
                "tables_profiled": profile_data.get("tables_profiled", 0),
                "total_fields": profile_data.get("total_fields", 0),
                "pii_fields_detected": profile_data.get("pii_summary", {}).get("total_pii_fields", 0),
                "relationships_found": len(profile_data.get("relationships", [])),
                "rows_extracted": subset_data.get("total_rows", 0),
                "values_masked": mask_data.get("total_values_masked", 0),
                "rows_loaded": prov_data.get("total_rows_loaded", 0),
                "validation_status": prov_data.get("validation", {}).get("overall_status", "N/A"),
            },
            "agent_results": {
                name: {
                    "status": result.get("status"),
                    "summary": result.get("summary"),
                    "duration_seconds": result.get("duration_seconds"),
                    "errors": result.get("errors", []),
                    "warnings": result.get("warnings", []),
                }
                for name, result in agent_results.items()
            },
            "detailed_data": {
                "profile": profile_data,
                "subsetting": subset_data,
                "masking": {
                    "stats": mask_data.get("masking_stats", {}),
                    "before_after_samples": mask_data.get("before_after_samples", {}),
                },
                "provisioning": {
                    "load_summary": prov_data.get("load_summary", {}),
                    "validation": prov_data.get("validation", {}),
                },
            },
        }

    def _save_report(self, request_id: str, report: dict):
        """Save report to knowledge base."""
        output_dir = KNOWLEDGE_BASE_DIR / "profiles"
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"report_{request_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        log.info(f"Report saved: {report_file}")
