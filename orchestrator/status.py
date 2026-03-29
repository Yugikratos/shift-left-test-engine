"""Status Tracker — centralized request status tracking and reporting.

Provides a structured view of request lifecycle, agent-level statuses,
and summary metrics for the API layer.
"""

from datetime import datetime


class StatusTracker:
    """Tracks request statuses and provides structured reporting."""

    def __init__(self):
        self._requests: dict[str, dict] = {}

    def register(self, request_id: str, metadata: dict):
        """Register a new request for tracking.

        Args:
            request_id: Unique request identifier.
            metadata: Initial request data (scenario, tables, record_count, etc.).
        """
        self._requests[request_id] = {
            "request_id": request_id,
            "status": "submitted",
            "submitted_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "scenario": metadata.get("scenario", "unknown"),
            "tables": metadata.get("tables", []),
            "record_count": metadata.get("record_count", 0),
            "agent_statuses": {},
            "errors": [],
        }

    def mark_running(self, request_id: str):
        """Mark a request as running."""
        if request_id in self._requests:
            self._requests[request_id]["status"] = "running"
            self._requests[request_id]["started_at"] = datetime.now().isoformat()

    def update_agent_status(
        self,
        request_id: str,
        agent_name: str,
        status: str,
        summary: str = "",
        duration_seconds: float = 0.0,
    ):
        """Update the status of a specific agent within a request.

        Args:
            request_id: The request being tracked.
            agent_name: Agent identifier (e.g. "profiling").
            status: Agent status string (pending, running, completed, failed).
            summary: One-line summary of agent result.
            duration_seconds: How long the agent took.
        """
        if request_id in self._requests:
            self._requests[request_id]["agent_statuses"][agent_name] = {
                "status": status,
                "summary": summary,
                "duration_seconds": round(duration_seconds, 2),
                "updated_at": datetime.now().isoformat(),
            }

    def mark_completed(self, request_id: str, final_status: str = "completed"):
        """Mark a request as completed (or partial/failed).

        Args:
            request_id: The request to finalize.
            final_status: One of "completed", "partial", "failed".
        """
        if request_id in self._requests:
            self._requests[request_id]["status"] = final_status
            self._requests[request_id]["completed_at"] = datetime.now().isoformat()

    def add_error(self, request_id: str, error: str):
        """Record an error against a request."""
        if request_id in self._requests:
            self._requests[request_id]["errors"].append(error)

    def get_status(self, request_id: str) -> dict | None:
        """Get full status for a request.

        Returns:
            Status dict or None if request not found.
        """
        return self._requests.get(request_id)

    def get_summary(self, request_id: str) -> dict:
        """Get a concise status summary suitable for API responses.

        Returns:
            Summary dict with key fields, or error dict if not found.
        """
        req = self._requests.get(request_id)
        if req is None:
            return {"error": f"Request {request_id} not found"}

        completed_agents = sum(
            1
            for a in req["agent_statuses"].values()
            if a["status"] == "completed"
        )
        total_agents = len(req["agent_statuses"]) or 4  # default pipeline length

        return {
            "request_id": request_id,
            "status": req["status"],
            "submitted_at": req["submitted_at"],
            "started_at": req["started_at"],
            "completed_at": req["completed_at"],
            "progress": f"{completed_agents}/{total_agents} agents completed",
            "agent_statuses": {
                name: info["status"]
                for name, info in req["agent_statuses"].items()
            },
            "errors": req["errors"],
        }

    def list_requests(self) -> list[dict]:
        """List all tracked requests with basic info."""
        return [
            {
                "request_id": r["request_id"],
                "status": r["status"],
                "scenario": r["scenario"],
                "submitted_at": r["submitted_at"],
            }
            for r in self._requests.values()
        ]
