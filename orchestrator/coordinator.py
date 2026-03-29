"""Agent Coordinator — manages agent task assignment and lifecycle tracking.

Handles the mapping of execution plan steps to agents, tracks per-agent
status, and provides a centralized view of pipeline progress.
"""

from datetime import datetime

from agents.base_agent import BaseAgent, AgentResult, AgentStatus


class AgentCoordinator:
    """Coordinates agent task assignment and tracks execution progress."""

    def __init__(self, agents: dict[str, BaseAgent]):
        self._agents = agents
        self._task_log: list[dict] = []
        self._current_step: int = 0
        self._total_steps: int = len(agents)

    @property
    def progress(self) -> dict:
        """Return current pipeline progress."""
        return {
            "current_step": self._current_step,
            "total_steps": self._total_steps,
            "percent_complete": round(
                (self._current_step / self._total_steps * 100)
                if self._total_steps > 0
                else 0,
                1,
            ),
            "agent_statuses": {
                name: agent.status.value for name, agent in self._agents.items()
            },
        }

    def assign(self, agent_name: str, context: dict) -> AgentResult:
        """Assign a task to a named agent and track the result.

        Args:
            agent_name: Key in the agents dict (e.g. "profiling").
            context: Pipeline context dict passed to the agent.

        Returns:
            AgentResult from the agent's run.

        Raises:
            KeyError: If agent_name is not registered.
        """
        if agent_name not in self._agents:
            raise KeyError(f"Unknown agent: {agent_name}")

        agent = self._agents[agent_name]
        self._current_step += 1

        entry = {
            "step": self._current_step,
            "agent": agent_name,
            "started_at": datetime.now().isoformat(),
            "status": AgentStatus.RUNNING.value,
        }
        self._task_log.append(entry)

        result = agent.run(context)

        entry["completed_at"] = datetime.now().isoformat()
        entry["status"] = result.status.value
        entry["duration_seconds"] = result.duration_seconds
        entry["summary"] = result.summary

        return result

    def get_task_log(self) -> list[dict]:
        """Return the full task execution log."""
        return list(self._task_log)

    def reset(self):
        """Reset coordinator state for a new pipeline run."""
        self._task_log.clear()
        self._current_step = 0
