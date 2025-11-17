"""Tests for orchestrator components."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import uuid

from src.agents.base_agent import AgentMetadata, AgentRequest, AgentResponse, AgentStatus
from src.agents.agent_client import AgentClient
from src.orchestrator.registry import AgentRegistry
from src.orchestrator.context_manager import SessionContext


class TestAgentClient:
    """Test AgentClient class."""

    @pytest.fixture
    def agent_metadata(self):
        """Create test agent metadata."""
        return AgentMetadata(
            name="test_agent",
            domain="test_domain",
            url="http://localhost:8001",
            capabilities=["test"],
            description="Test agent",
        )

    @pytest.fixture
    def agent_client(self, agent_metadata):
        """Create test agent client."""
        return AgentClient(agent_metadata)

    def test_agent_initialization(self, agent_client, agent_metadata):
        """Test agent client initialization."""
        assert agent_client.metadata.name == "test_agent"
        assert agent_client.metadata.domain == "test_domain"
        assert "test" in agent_client.metadata.capabilities

    @pytest.mark.asyncio
    async def test_health_check_success(self, agent_client):
        """Test successful health check."""
        with patch.object(agent_client.client, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = await agent_client.health_check()
            assert result is True
            assert agent_client.metadata.status == AgentStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_failure(self, agent_client):
        """Test failed health check."""
        with patch.object(agent_client.client, 'get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            result = await agent_client.health_check()
            assert result is False
            assert agent_client.metadata.status == AgentStatus.UNAVAILABLE


class TestSessionContext:
    """Test SessionContext class."""

    def test_session_context_creation(self):
        """Test session context creation."""
        session_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        context = SessionContext(
            session_id=session_id,
            user_id=user_id,
        )

        assert context.session_id == session_id
        assert context.user_id == user_id
        assert context.agent_chain == []
        assert context.context_variables == {}

    def test_session_context_to_dict(self):
        """Test session context serialization."""
        session_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            agent_chain=["agent1", "agent2"],
            context_variables={"key": "value"},
        )

        data = context.to_dict()

        assert data["session_id"] == session_id
        assert data["user_id"] == user_id
        assert data["agent_chain"] == ["agent1", "agent2"]
        assert data["context_variables"]["key"] == "value"

    def test_session_context_from_dict(self):
        """Test session context deserialization."""
        session_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        data = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_chain": ["agent1"],
            "context_variables": {"test": "value"},
        }

        context = SessionContext.from_dict(data)

        assert context.session_id == session_id
        assert context.user_id == user_id
        assert context.agent_chain == ["agent1"]
        assert context.context_variables["test"] == "value"


class TestAgentRegistry:
    """Test AgentRegistry class."""

    @pytest.fixture
    def config_file(self, tmp_path):
        """Create temporary config file."""
        config_content = """
agents:
  test_domain:
    test_agent:
      url: "http://localhost:8001"
      capabilities:
        - "test"
      description: "Test agent"
      health_check_endpoint: "/health"
      timeout: 30
      retry_count: 3
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.mark.asyncio
    async def test_load_agents(self, config_file):
        """Test loading agents from config."""
        registry = AgentRegistry(config_file)
        await registry.load_agents()

        assert len(registry.agents) == 1
        assert "test_agent" in registry.agents
        assert "test_domain" in registry.agents_by_domain

    @pytest.mark.asyncio
    async def test_get_agent(self, config_file):
        """Test getting agent by name."""
        registry = AgentRegistry(config_file)
        await registry.load_agents()

        agent = registry.get_agent("test_agent")
        assert agent is not None
        assert agent.metadata.name == "test_agent"

    @pytest.mark.asyncio
    async def test_get_agents_by_domain(self, config_file):
        """Test getting agents by domain."""
        registry = AgentRegistry(config_file)
        await registry.load_agents()

        agents = registry.get_agents_by_domain("test_domain")
        assert len(agents) == 1
        assert agents[0].metadata.name == "test_agent"

    @pytest.mark.asyncio
    async def test_get_agents_by_capability(self, config_file):
        """Test getting agents by capability."""
        registry = AgentRegistry(config_file)
        await registry.load_agents()

        agents = registry.get_agents_by_capability("test")
        assert len(agents) == 1
        assert agents[0].metadata.name == "test_agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
