"""Orchestrator Engine — coordinates the full test data provisioning pipeline.

Accepts a request, plans execution, runs agents in sequence, and produces
a consolidated report.
"""

import json
import uuid
import sqlite3
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
        self.db_path = BASE_DIR / "metadata.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_jobs (
                    request_id TEXT PRIMARY KEY,
                    status TEXT,
                    submitted_at TEXT,
                    scenario TEXT,
                    payload_json TEXT
                )
            """)
            conn.commit()

    def _get_job(self, request_id: str) -> dict | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute("SELECT payload_json FROM pipeline_jobs WHERE request_id = ?", (request_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def _save_job(self, req: dict):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pipeline_jobs (request_id, status, submitted_at, scenario, payload_json) VALUES (?, ?, ?, ?, ?)",
                (req["request_id"], req["status"], req.get("submitted_at"), req["scenario"], json.dumps(req))
            )
            conn.commit()

    def submit_request(self, request: dict) -> dict:
        request_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Validate request
        scenario = request.get("scenario", "default")
        tables = request.get("tables", [])
        record_count = min(request.get("record_count", 100), 10000)
        date_range = request.get("date_range", {})
        
        # New flexibility flags
        skip_profiling = request.get("skip_profiling", False)
        skip_subsetting = request.get("skip_subsetting", False)
        skip_masking = request.get("skip_masking", False)
        skip_provisioning = request.get("skip_provisioning", False)

        if not tables and not skip_profiling:
            raise ValueError("At least one table must be specified unless skipping profiling")
        if date_range.get("start") and date_range.get("end"):
            if date_range["start"] > date_range["end"]:
                raise ValueError("Date range start must be before end")

        # Build execution plan conditionally
        execution_plan = []
        if not skip_profiling:
            execution_plan.append({"step": 1, "agent": "Data Profiling Agent", "action": "Analyze DML/DDL metadata, detect PII, map relationships"})
        if not skip_subsetting:
            execution_plan.append({"step": 2, "agent": "Smart Subsetting Agent", "action": f"Extract {record_count} records with referential integrity"})
        if not skip_masking:
            execution_plan.append({"step": 3, "agent": "Data Masking Agent", "action": "Anonymize PII fields (names, addresses, phones)"})
        if not skip_provisioning:
            execution_plan.append({"step": 4, "agent": "Data Provisioning Agent", "action": "Load masked data into target DB and validate"})

        req = {
            "request_id": request_id,
            "submitted_at": timestamp,
            "scenario": scenario,
            "tables": tables,
            "record_count": record_count,
            "date_range": date_range,
            "skip_profiling": skip_profiling,
            "skip_subsetting": skip_subsetting,
            "skip_masking": skip_masking,
            "skip_provisioning": skip_provisioning,
            "execution_plan": execution_plan,
            "status": "submitted",
            "agent_results": {},
        }
        self._save_job(req)

        return {
            "request_id": request_id,
            "status": "submitted",
            "submitted_at": timestamp,
            "execution_plan": execution_plan,
        }

    def execute_request(self, request_id: str) -> dict:
        req = self._get_job(request_id)
        if not req:
            return {"error": f"Request {request_id} not found"}

        req["status"] = "running"
        req["started_at"] = datetime.now().isoformat()
        self._save_job(req)

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

        status_flag = "completed"

        # ── Step 1: Profiling ──
        if not req.get("skip_profiling"):
            log.info("[1/4] Running Data Profiling Agent...")
            profile_result = self.agents["profiling"].run(context)
            req["agent_results"]["profiling"] = profile_result.to_dict()
            log.info(f"→ {profile_result.summary}")
            
            if profile_result.status == AgentStatus.FAILED:
                req["status"] = "failed"
                self._save_job(req)
                return self._build_report(req)
                
            context["profile_report"] = profile_result.data
            context["pii_summary"] = profile_result.data.get("pii_summary", {})
        else:
            log.info("[1/4] Skipping Data Profiling Agent...")

        self._save_job(req)

        # ── Step 2: Subsetting ──
        if not req.get("skip_subsetting"):
            log.info("[2/4] Running Smart Subsetting Agent...")
            subset_result = self.agents["subsetting"].run(context)
            req["agent_results"]["subsetting"] = subset_result.to_dict()
            log.info(f"→ {subset_result.summary}")

            if subset_result.status == AgentStatus.FAILED:
                req["status"] = "failed"
                self._save_job(req)
                return self._build_report(req)

            context["extracted_data"] = subset_result.data.get("extracted_data", {})
        else:
            log.info("[2/4] Skipping Smart Subsetting Agent...")

        self._save_job(req)

        # ── Step 3: Masking ──
        if not req.get("skip_masking"):
            log.info("[3/4] Running Data Masking Agent...")
            mask_result = self.agents["masking"].run(context)
            req["agent_results"]["masking"] = mask_result.to_dict()
            log.info(f"→ {mask_result.summary}")

            if mask_result.status == AgentStatus.FAILED:
                req["status"] = "failed"
                self._save_job(req)
                return self._build_report(req)

            context["masked_data"] = mask_result.data.get("masked_data", {})
        else:
            log.info("[3/4] Skipping Data Masking Agent...")

        self._save_job(req)

        # ── Step 4: Provisioning ──
        if not req.get("skip_provisioning"):
            log.info("[4/4] Running Data Provisioning Agent...")
            prov_result = self.agents["provisioning"].run(context)
            req["agent_results"]["provisioning"] = prov_result.to_dict()
            log.info(f"→ {prov_result.summary}")
            if prov_result.status != AgentStatus.COMPLETED:
                status_flag = "partial"
        else:
            log.info("[4/4] Skipping Data Provisioning Agent...")

        # Finalize
        req["status"] = status_flag
        req["completed_at"] = datetime.now().isoformat()
        self._save_job(req)

        report = self._build_report(req)
        self._save_report(request_id, report)

        log.info(f"Request {request_id}: {req['status'].upper()}")
        return report

    def process_request(self, request: dict) -> dict:
        receipt = self.submit_request(request)
        return self.execute_request(receipt["request_id"])

    def get_status(self, request_id: str) -> dict:
        req = self._get_job(request_id)
        if not req:
            return {"error": f"Request {request_id} not found"}

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
        return self._get_job(request_id)

    def _build_report(self, req: dict) -> dict:
        agent_results = req.get("agent_results", {})

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
        output_dir = KNOWLEDGE_BASE_DIR / "profiles"
        output_dir.mkdir(parents=True, exist_ok=True)

        report_file = output_dir / f"report_{request_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        log.info(f"Report saved: {report_file}")
