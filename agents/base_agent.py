"""Base agent class — defines the interface all agents must implement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import time


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentResult:
    """Standard result object returned by every agent."""
    agent_name: str
    status: AgentStatus
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "summary": self.summary,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class BaseAgent(ABC):
    """Abstract base class for all agents in the pipeline."""

    def __init__(self, name: str):
        self.name = name
        self._status = AgentStatus.PENDING

    @abstractmethod
    def execute(self, context: dict) -> AgentResult:
        """Execute the agent's task.

        Args:
            context: Dictionary containing all inputs from the orchestrator
                     and results from previous agents in the pipeline.

        Returns:
            AgentResult with status, data, and any errors/warnings.
        """
        pass

    def run(self, context: dict, max_retries: int = 3, retry_delay_sec: int = 2) -> AgentResult:
        """Wrapper that handles timing, error catching, and resiliency retries."""
        start = datetime.now()
        self._status = AgentStatus.RUNNING

        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                result = self.execute(context)
                result.started_at = start.isoformat()
                result.completed_at = datetime.now().isoformat()
                result.duration_seconds = (datetime.now() - start).total_seconds()
                self._status = result.status
                return result

            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    time.sleep(retry_delay_sec)

        self._status = AgentStatus.FAILED
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.FAILED,
            started_at=start.isoformat(),
            completed_at=datetime.now().isoformat(),
            duration_seconds=(datetime.now() - start).total_seconds(),
            errors=[f"Failed after {max_retries} attempts. Last error: {str(last_exception)}"],
            summary=f"{self.name} failed after {max_retries} attempts: {str(last_exception)}",
        )

    @property
    def status(self) -> AgentStatus:
        return self._status
