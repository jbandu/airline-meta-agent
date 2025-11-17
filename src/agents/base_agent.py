"""Base agent interface and models."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class AgentStatus(str, Enum):
    """Agent health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class AgentCapability(BaseModel):
    """Agent capability model."""
    name: str
    description: Optional[str] = None


class AgentMetadata(BaseModel):
    """Agent metadata model."""
    name: str
    domain: str
    url: str
    capabilities: List[str]
    description: str
    health_check_endpoint: str = "/health"
    timeout: int = 30
    retry_count: int = 3
    status: AgentStatus = AgentStatus.UNAVAILABLE
    last_health_check: Optional[str] = None


class AgentRequest(BaseModel):
    """Request to an agent."""
    session_id: str
    user_id: str
    message: str
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Response from an agent."""
    agent_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None


class BaseAgent(ABC):
    """Base agent interface that all agents must implement."""

    def __init__(self, metadata: AgentMetadata):
        self.metadata = metadata

    @abstractmethod
    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute the agent's main logic.

        Args:
            request: The agent request containing message and context

        Returns:
            AgentResponse with the result
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the agent is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    def get_capabilities(self) -> List[str]:
        """Get list of agent capabilities."""
        return self.metadata.capabilities

    def get_name(self) -> str:
        """Get agent name."""
        return self.metadata.name

    def get_domain(self) -> str:
        """Get agent domain."""
        return self.metadata.domain
