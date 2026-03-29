"""Base agent class — defines the interface all agents must implement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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

    def run(self, context: dict) -> AgentResult:
        """Wrapper that handles timing and error catching."""
        start = datetime.now()
        self._status = AgentStatus.RUNNING

        try:
            result = self.execute(context)
            result.started_at = start.isoformat()
            result.completed_at = datetime.now().isoformat()
            result.duration_seconds = (datetime.now() - start).total_seconds()
            self._status = result.status
            return result

        except Exception as e:
            self._status = AgentStatus.FAILED
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                started_at=start.isoformat(),
                completed_at=datetime.now().isoformat(),
                duration_seconds=(datetime.now() - start).total_seconds(),
                errors=[f"Unhandled exception: {str(e)}"],
                summary=f"{self.name} failed with error: {str(e)}",
            )

    @property
    def status(self) -> AgentStatus:
        return self._status
