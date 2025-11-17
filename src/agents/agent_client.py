"""HTTP client for communicating with agents."""

import httpx
import structlog
from typing import Optional
from pybreaker import CircuitBreaker, CircuitBreakerError
import time

from src.agents.base_agent import (
    BaseAgent,
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    AgentStatus,
)

logger = structlog.get_logger()


class AgentClient(BaseAgent):
    """HTTP client for remote agents with circuit breaker pattern."""

    def __init__(self, metadata: AgentMetadata):
        super().__init__(metadata)
        self.client = httpx.AsyncClient(timeout=metadata.timeout)
        self.circuit_breaker = CircuitBreaker(
            fail_max=5,
            timeout_duration=60,
            name=f"cb_{metadata.name}",
        )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        """
        Execute a request to the remote agent.

        Args:
            request: The agent request

        Returns:
            AgentResponse from the remote agent
        """
        start_time = time.time()

        try:
            response = await self._call_with_circuit_breaker(request)
            execution_time = (time.time() - start_time) * 1000

            response_data = AgentResponse(
                agent_name=self.metadata.name,
                success=True,
                data=response,
                execution_time_ms=execution_time,
            )

            logger.info(
                "agent_execution_success",
                agent=self.metadata.name,
                session_id=request.session_id,
                execution_time_ms=execution_time,
            )

            return response_data

        except CircuitBreakerError:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "circuit_breaker_open",
                agent=self.metadata.name,
                session_id=request.session_id,
            )
            return AgentResponse(
                agent_name=self.metadata.name,
                success=False,
                error="Circuit breaker is open - agent is temporarily unavailable",
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "agent_execution_error",
                agent=self.metadata.name,
                session_id=request.session_id,
                error=str(e),
            )
            return AgentResponse(
                agent_name=self.metadata.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
            )

    async def _call_with_circuit_breaker(self, request: AgentRequest) -> dict:
        """Call agent with circuit breaker protection."""

        @self.circuit_breaker
        async def _make_request():
            payload = {
                "session_id": request.session_id,
                "user_id": request.user_id,
                "message": request.message,
                "context": request.context,
                "metadata": request.metadata,
            }

            response = await self.client.post(
                f"{self.metadata.url}/execute",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        return await _make_request()

    async def health_check(self) -> bool:
        """
        Check if the agent is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(
                f"{self.metadata.url}{self.metadata.health_check_endpoint}",
                timeout=5.0,
            )

            is_healthy = response.status_code == 200

            self.metadata.status = (
                AgentStatus.HEALTHY if is_healthy else AgentStatus.DEGRADED
            )

            logger.info(
                "health_check",
                agent=self.metadata.name,
                status=self.metadata.status,
            )

            return is_healthy

        except Exception as e:
            logger.error(
                "health_check_failed",
                agent=self.metadata.name,
                error=str(e),
            )
            self.metadata.status = AgentStatus.UNAVAILABLE
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.close())
        except Exception:
            pass
