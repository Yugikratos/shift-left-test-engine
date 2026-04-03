"""Tests for features added by Gemini — skip flags, retry logic, persistent storage."""

import sqlite3
import time
from unittest.mock import patch, MagicMock

import pytest

from orchestrator.engine import OrchestratorEngine
from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from config.settings import BASE_DIR


# ── Helpers ─────────────────────────────────────────────

class _FailNTimesAgent(BaseAgent):
    """Test agent that raises a transient error N times, then succeeds."""

    def __init__(self, fail_count: int, error_cls=ConnectionError):
        super().__init__("FailNTimesAgent")
        self.fail_count = fail_count
        self.attempts = 0
        self.error_cls = error_cls

    def execute(self, context: dict) -> AgentResult:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise self.error_cls(f"Transient failure #{self.attempts}")
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            summary="Succeeded after retries",
        )


# ── Retry Logic ─────────────────────────────────────────

def test_retry_succeeds_after_transient_failure():
    """Agent recovers from transient errors within retry limit."""
    agent = _FailNTimesAgent(fail_count=2, error_cls=ConnectionError)
    result = agent.run({}, max_retries=3, retry_delay_sec=0.01)

    assert result.status == AgentStatus.COMPLETED
    assert agent.attempts == 3


def test_retry_exhausted_on_transient_failure():
    """Agent fails after exhausting all retries on transient errors."""
    agent = _FailNTimesAgent(fail_count=5, error_cls=TimeoutError)
    result = agent.run({}, max_retries=3, retry_delay_sec=0.01)

    assert result.status == AgentStatus.FAILED
    assert "3 retries" in result.errors[0]
    assert agent.attempts == 3


def test_no_retry_on_non_transient_error():
    """Non-transient errors (ValueError, KeyError, etc.) fail immediately."""
    agent = _FailNTimesAgent(fail_count=5, error_cls=ValueError)
    result = agent.run({}, max_retries=3, retry_delay_sec=0.01)

    assert result.status == AgentStatus.FAILED
    assert "Unhandled exception" in result.errors[0]
    assert agent.attempts == 1  # no retries


def test_retry_on_os_error():
    """OSError (file I/O, disk issues) is treated as transient."""
    agent = _FailNTimesAgent(fail_count=1, error_cls=OSError)
    result = agent.run({}, max_retries=2, retry_delay_sec=0.01)

    assert result.status == AgentStatus.COMPLETED
    assert agent.attempts == 2


# ── Skip Flag Validation ────────────────────────────────

def test_skip_subsetting_without_masking_raises():
    """Cannot skip subsetting if masking will still run."""
    engine = OrchestratorEngine()
    with pytest.raises(ValueError, match="skip subsetting"):
        engine.submit_request({
            "scenario": "test",
            "tables": ["stg_business_entity"],
            "skip_subsetting": True,
            "skip_masking": False,
        })


def test_skip_masking_without_provisioning_raises():
    """Cannot skip masking if provisioning will still run."""
    engine = OrchestratorEngine()
    with pytest.raises(ValueError, match="skip masking"):
        engine.submit_request({
            "scenario": "test",
            "tables": ["stg_business_entity"],
            "skip_masking": True,
            "skip_provisioning": False,
        })


def test_skip_profiling_only_is_allowed():
    """Skipping just profiling is valid — downstream agents can still run."""
    engine = OrchestratorEngine()
    receipt = engine.submit_request({
        "scenario": "test",
        "tables": ["stg_business_entity"],
        "skip_profiling": True,
    })
    assert receipt["status"] == "submitted"
    # Execution plan should omit profiling
    agent_names = [step["agent"] for step in receipt["execution_plan"]]
    assert "Data Profiling Agent" not in agent_names


def test_skip_all_downstream_is_allowed():
    """Skipping subsetting + masking + provisioning together is valid."""
    engine = OrchestratorEngine()
    receipt = engine.submit_request({
        "scenario": "test",
        "tables": ["stg_business_entity"],
        "skip_subsetting": True,
        "skip_masking": True,
        "skip_provisioning": True,
    })
    assert receipt["status"] == "submitted"
    assert len(receipt["execution_plan"]) == 1  # only profiling


def test_empty_tables_still_raises():
    """Empty tables raises ValueError regardless of skip flags."""
    engine = OrchestratorEngine()
    with pytest.raises(ValueError, match="table"):
        engine.submit_request({
            "scenario": "test",
            "tables": [],
            "skip_profiling": True,
        })


# ── Persistent Storage ──────────────────────────────────

def test_job_persists_across_engine_instances():
    """Jobs saved by one engine instance are readable by another."""
    engine1 = OrchestratorEngine()
    receipt = engine1.submit_request({
        "scenario": "persistence_test",
        "tables": ["stg_business_entity"],
        "record_count": 5,
    })
    request_id = receipt["request_id"]

    # New engine instance reads from same metadata.db
    engine2 = OrchestratorEngine()
    job = engine2.get_request(request_id)

    assert job is not None
    assert job["scenario"] == "persistence_test"
    assert job["status"] == "submitted"


def test_job_status_updates_persist():
    """Status changes during execution are persisted."""
    engine = OrchestratorEngine()
    report = engine.process_request({
        "scenario": "status_test",
        "tables": ["stg_business_entity"],
        "record_count": 5,
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    })
    request_id = report["request_id"]

    # Read back from a fresh engine
    engine2 = OrchestratorEngine()
    status = engine2.get_status(request_id)
    assert status["status"] in ("completed", "partial")
