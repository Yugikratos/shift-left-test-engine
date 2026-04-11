"""FastAPI REST API — endpoints for the Test Data Engine.

Endpoints:
    POST /api/v1/provision   — Submit a test data provisioning request
    GET  /api/v1/status/{id} — Check request status
    GET  /api/v1/results/{id}— Get full results
    GET  /api/v1/health      — Health check
"""

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config.settings import KNOWLEDGE_BASE_DIR
from orchestrator.engine import OrchestratorEngine
from utils.database import source_engine
from sqlalchemy import inspect
from utils.llm_client import llm_client
from utils.logger import get_logger

log = get_logger("api")


# ── Lifespan ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Setup removed from lifespan, rely on GitOps/Kubernetes init containers or manual migration
    print(f"LLM Mode: {llm_client.mode}")
    print("API ready.")
    yield


# ── App Setup ──────────────────────────────────────────

app = FastAPI(
    title="Shift-Left Test Data Engine",
    description="Agentic Test Data Setup Engine — POC API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator
engine = OrchestratorEngine()


# ── Request/Response Models ────────────────────────────

class DateRange(BaseModel):
    start: str = Field(default="2024-01-01", json_schema_extra={"example": "2024-01-01"})
    end: str = Field(default="2024-12-31", json_schema_extra={"example": "2024-12-31"})

class ProvisionRequest(BaseModel):
    scenario: str = Field(default="business_entity_flow", json_schema_extra={"example": "business_entity_flow"})
    tables: list[str] = Field(
        default=["stg_business_entity", "business_credit_score", "business_address_match"],
        json_schema_extra={"example": ["stg_business_entity", "business_credit_score"]}
    )
    record_count: int = Field(default=100, ge=1, le=10000, json_schema_extra={"example": 100})
    date_range: DateRange = Field(default_factory=DateRange)

class ProvisionResponse(BaseModel):
    request_id: str
    status: str
    message: str


# ── Endpoints ──────────────────────────────────────────

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Shift-Left Test Data Engine",
        "version": "1.0.0",
        "llm_mode": llm_client.mode,
        "database_ready": True, # Offloaded to Kubernetes Probes
    }


@app.post("/api/v1/provision", response_model=ProvisionResponse)
async def provision(request: ProvisionRequest):
    """Submit and execute a test data provisioning request.

    This runs the full pipeline: Profile → Subset → Mask → Provision.
    """
    try:
        report = engine.process_request(request.model_dump())
        return ProvisionResponse(
            request_id=report.get("request_id", "unknown"),
            status=report.get("status", "unknown"),
            message=f"Pipeline {report.get('status', 'completed')}. "
                    f"{report.get('summary', {}).get('rows_loaded', 0)} rows provisioned.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/provision/async")
async def provision_async(request: ProvisionRequest, background_tasks: BackgroundTasks):
    """Submit a request for async execution and get a receipt immediately.

    The pipeline runs in the background. Poll /api/v1/status/{request_id} for progress.
    """
    receipt = engine.submit_request(request.model_dump())

    def _run_pipeline(request_id: str):
        try:
            engine.execute_request(request_id)
        except Exception as e:
            log.error(f"Background pipeline failed for {request_id}: {e}")

    background_tasks.add_task(_run_pipeline, receipt["request_id"])
    return receipt


@app.get("/api/v1/status/{request_id}")
async def get_status(request_id: str):
    """Get the current status of a provisioning request."""
    status = engine.get_status(request_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@app.get("/api/v1/results/{request_id}")
async def get_results(request_id: str):
    """Get full results of a completed provisioning request."""
    req = engine.get_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")

    if req["status"] not in ("completed", "partial"):
        return {"request_id": request_id, "status": req["status"], "message": "Request not yet completed"}

    # Return the saved report from AWS S3
    from utils.storage_client import storage_client
    from config.settings import S3_REPORTS_BUCKET

    object_key = f"{request_id}/profile_report.json"
    report = storage_client.download_json(S3_REPORTS_BUCKET, object_key)
    
    if report is not None:
        return report

    return {"request_id": request_id, "status": req["status"], "message": "Report object not found in S3"}


@app.get("/api/v1/tables")
async def list_tables():
    """List available tables in the source database."""
    try:
        inspector = inspect(source_engine)
        tables = [t for t in inspector.get_table_names() if not t.startswith("sqlite_")]
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
