"""Agent registry for dynamic agent discovery and management."""

import asyncio
import yaml
import structlog
from typing import Dict, List, Optional
from pathlib import Path

from src.agents.base_agent import AgentMetadata, AgentStatus
from src.agents.agent_client import AgentClient

logger = structlog.get_logger()


class AgentRegistry:
    """Registry for managing and discovering agents."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.agents: Dict[str, AgentClient] = {}
        self.agents_by_domain: Dict[str, List[str]] = {}
        self.agents_by_capability: Dict[str, List[str]] = {}

    async def load_agents(self):
        """Load agents from configuration file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            agents_config = config.get("agents", {})

            for domain, agents in agents_config.items():
                self.agents_by_domain[domain] = []

                for agent_name, agent_config in agents.items():
                    metadata = AgentMetadata(
                        name=agent_name,
                        domain=domain,
                        url=agent_config["url"],
                        capabilities=agent_config["capabilities"],
                        description=agent_config["description"],
                        health_check_endpoint=agent_config.get(
                            "health_check_endpoint", "/health"
                        ),
                        timeout=agent_config.get("timeout", 30),
                        retry_count=agent_config.get("retry_count", 3),
                    )

                    agent_client = AgentClient(metadata)
                    self.agents[agent_name] = agent_client
                    self.agents_by_domain[domain].append(agent_name)

                    # Index by capabilities
                    for capability in metadata.capabilities:
                        if capability not in self.agents_by_capability:
                            self.agents_by_capability[capability] = []
                        self.agents_by_capability[capability].append(agent_name)

                    logger.info(
                        "agent_registered",
                        agent=agent_name,
                        domain=domain,
                        capabilities=metadata.capabilities,
                    )

            logger.info(
                "agents_loaded",
                total_agents=len(self.agents),
                domains=list(self.agents_by_domain.keys()),
            )

        except Exception as e:
            logger.error("failed_to_load_agents", error=str(e))
            raise

    async def health_check_all(self):
        """Perform health checks on all agents."""
        tasks = []
        for agent_name, agent in self.agents.items():
            tasks.append(self._check_agent_health(agent_name, agent))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        healthy_count = sum(1 for r in results if r is True)
        logger.info(
            "health_check_complete",
            total_agents=len(self.agents),
            healthy=healthy_count,
            unhealthy=len(self.agents) - healthy_count,
        )

    async def _check_agent_health(self, agent_name: str, agent: AgentClient) -> bool:
        """Check health of a single agent."""
        try:
            return await agent.health_check()
        except Exception as e:
            logger.error(
                "health_check_error",
                agent=agent_name,
                error=str(e),
            )
            return False

    def get_agent(self, agent_name: str) -> Optional[AgentClient]:
        """Get agent by name."""
        return self.agents.get(agent_name)

    def get_agents_by_domain(self, domain: str) -> List[AgentClient]:
        """Get all agents in a domain."""
        agent_names = self.agents_by_domain.get(domain, [])
        return [self.agents[name] for name in agent_names if name in self.agents]

    def get_agents_by_capability(self, capability: str) -> List[AgentClient]:
        """Get all agents with a specific capability."""
        agent_names = self.agents_by_capability.get(capability, [])
        return [self.agents[name] for name in agent_names if name in self.agents]

    def get_all_agents(self) -> List[AgentClient]:
        """Get all registered agents."""
        return list(self.agents.values())

    def get_healthy_agents(self) -> List[AgentClient]:
        """Get all healthy agents."""
        return [
            agent
            for agent in self.agents.values()
            if agent.metadata.status == AgentStatus.HEALTHY
        ]

    def get_agent_metadata(self, agent_name: str) -> Optional[AgentMetadata]:
        """Get metadata for an agent."""
        agent = self.agents.get(agent_name)
        return agent.metadata if agent else None

    def list_domains(self) -> List[str]:
        """List all available domains."""
        return list(self.agents_by_domain.keys())

    def list_capabilities(self) -> List[str]:
        """List all available capabilities."""
        return list(self.agents_by_capability.keys())

    def get_registry_stats(self) -> Dict:
        """Get registry statistics."""
        status_counts = {}
        for agent in self.agents.values():
            status = agent.metadata.status
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_agents": len(self.agents),
            "domains": len(self.agents_by_domain),
            "capabilities": len(self.agents_by_capability),
            "status_breakdown": status_counts,
            "agents_by_domain": {
                domain: len(agents) for domain, agents in self.agents_by_domain.items()
            },
        }

    async def close_all(self):
        """Close all agent connections."""
        tasks = [agent.close() for agent in self.agents.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("all_agent_connections_closed")
