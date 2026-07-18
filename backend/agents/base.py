"""Base agent class for all AI agents."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all AI agents."""

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        """
        Initialize the agent.

        Args:
            name: Agent name
            config: Agent configuration
        """
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def execute(self, task: str) -> dict[str, Any]:
        """
        Execute a task.

        Args:
            task: Task description

        Returns:
            Task result
        """
        pass
