"""Tests for AgentCoordinator and StatusTracker."""

import pytest

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from orchestrator.coordinator import AgentCoordinator
from orchestrator.status import StatusTracker


# ── Helpers ──────────────────────────────────────────────

class _MockAgent(BaseAgent):
    """Agent that always succeeds with a predictable result."""

    def __init__(self, name="mock_agent"):
        super().__init__(name)

    def execute(self, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            summary=f"{self.name} completed",
            data={"mock": True},
        )


# ── AgentCoordinator Tests ───────────────────────────────

def test_coordinator_assign_succeeds():
    """assign() runs the agent and returns a completed result."""
    agents = {"profiling": _MockAgent("profiling")}
    coord = AgentCoordinator(agents)
    result = coord.assign("profiling", {})

    assert result.status == AgentStatus.COMPLETED
    assert result.summary == "profiling completed"


def test_coordinator_assign_unknown_raises():
    """assign() with unknown agent name raises KeyError."""
    coord = AgentCoordinator({})
    with pytest.raises(KeyError, match="Unknown agent"):
        coord.assign("nonexistent", {})


def test_coordinator_progress_tracking():
    """progress property reflects step advancement."""
    agents = {"a": _MockAgent("a"), "b": _MockAgent("b")}
    coord = AgentCoordinator(agents)
    assert coord.progress["current_step"] == 0
    assert coord.progress["percent_complete"] == 0.0

    coord.assign("a", {})
    assert coord.progress["current_step"] == 1
    assert coord.progress["percent_complete"] == 50.0

    coord.assign("b", {})
    assert coord.progress["current_step"] == 2
    assert coord.progress["percent_complete"] == 100.0


def test_coordinator_task_log_recording():
    """Task log captures entries with timing and status."""
    agents = {"profiling": _MockAgent("profiling")}
    coord = AgentCoordinator(agents)
    coord.assign("profiling", {})

    task_log = coord.get_task_log()
    assert len(task_log) == 1
    entry = task_log[0]
    assert entry["agent"] == "profiling"
    assert entry["status"] == "completed"
    assert "started_at" in entry
    assert "completed_at" in entry
    assert "duration_seconds" in entry


def test_coordinator_reset_clears_state():
    """reset() clears task log and resets step counter."""
    agents = {"a": _MockAgent("a")}
    coord = AgentCoordinator(agents)
    coord.assign("a", {})
    assert coord.progress["current_step"] == 1
    assert len(coord.get_task_log()) == 1

    coord.reset()
    assert coord.progress["current_step"] == 0
    assert len(coord.get_task_log()) == 0


# ── StatusTracker Tests ──────────────────────────────────

def test_tracker_register():
    """register() creates a tracked request with initial state."""
    tracker = StatusTracker()
    tracker.register("req-1", {"scenario": "test", "tables": ["t1"], "record_count": 10})
    status = tracker.get_status("req-1")
    assert status is not None
    assert status["status"] == "submitted"
    assert status["scenario"] == "test"


def test_tracker_mark_running():
    """mark_running() updates status and sets started_at."""
    tracker = StatusTracker()
    tracker.register("req-1", {})
    tracker.mark_running("req-1")
    status = tracker.get_status("req-1")
    assert status["status"] == "running"
    assert status["started_at"] is not None


def test_tracker_update_agent_status():
    """update_agent_status() records per-agent status."""
    tracker = StatusTracker()
    tracker.register("req-1", {})
    tracker.update_agent_status("req-1", "profiling", "completed", summary="Done", duration_seconds=1.5)
    status = tracker.get_status("req-1")
    assert "profiling" in status["agent_statuses"]
    assert status["agent_statuses"]["profiling"]["status"] == "completed"
    assert status["agent_statuses"]["profiling"]["duration_seconds"] == 1.5


def test_tracker_mark_completed():
    """mark_completed() finalizes the request status."""
    tracker = StatusTracker()
    tracker.register("req-1", {})
    tracker.mark_completed("req-1", final_status="completed")
    status = tracker.get_status("req-1")
    assert status["status"] == "completed"
    assert status["completed_at"] is not None


def test_tracker_get_status_unknown_returns_none():
    """get_status() returns None for unregistered request."""
    tracker = StatusTracker()
    assert tracker.get_status("nonexistent") is None


def test_tracker_get_summary():
    """get_summary() returns a concise status dict."""
    tracker = StatusTracker()
    tracker.register("req-1", {"scenario": "test"})
    tracker.update_agent_status("req-1", "profiling", "completed")
    summary = tracker.get_summary("req-1")
    assert summary["request_id"] == "req-1"
    assert "1/1 agents completed" in summary["progress"]


def test_tracker_get_summary_unknown_returns_error():
    """get_summary() returns error dict for unknown request."""
    tracker = StatusTracker()
    result = tracker.get_summary("nonexistent")
    assert "error" in result


def test_tracker_list_requests():
    """list_requests() returns all tracked requests."""
    tracker = StatusTracker()
    tracker.register("req-1", {"scenario": "a"})
    tracker.register("req-2", {"scenario": "b"})
    requests = tracker.list_requests()
    assert len(requests) == 2
    ids = [r["request_id"] for r in requests]
    assert "req-1" in ids
    assert "req-2" in ids


def test_tracker_add_error():
    """add_error() appends errors to the request."""
    tracker = StatusTracker()
    tracker.register("req-1", {})
    tracker.add_error("req-1", "Something went wrong")
    status = tracker.get_status("req-1")
    assert "Something went wrong" in status["errors"]
