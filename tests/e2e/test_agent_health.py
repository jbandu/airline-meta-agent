"""End-to-end tests for agent health checks and monitoring."""

import pytest


class TestAgentEndpoints:
    """Test agent listing and management endpoints."""

    @pytest.mark.asyncio
    async def test_list_all_agents(
        self, http_client, auth_headers
    ):
        """Test listing all registered agents."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "agents" in data
        assert "count" in data
        assert isinstance(data["agents"], list)
        assert data["count"] == len(data["agents"])

    @pytest.mark.asyncio
    async def test_agents_have_required_fields(
        self, http_client, auth_headers
    ):
        """Test that agent list includes required fields."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        data = response.json()

        if data["count"] > 0:
            agent = data["agents"][0]
            assert "name" in agent
            assert "domain" in agent
            assert "capabilities" in agent
            assert "status" in agent

    @pytest.mark.asyncio
    async def test_list_domains(
        self, http_client, auth_headers
    ):
        """Test listing all agent domains."""
        response = await http_client.get(
            "/api/v1/agents/domains",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "domains" in data
        assert isinstance(data["domains"], list)

    @pytest.mark.asyncio
    async def test_list_capabilities(
        self, http_client, auth_headers
    ):
        """Test listing all agent capabilities."""
        response = await http_client.get(
            "/api/v1/agents/capabilities",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)


class TestAgentHealthChecks:
    """Test individual agent health checks."""

    @pytest.mark.asyncio
    async def test_health_check_endpoint(
        self, http_client, auth_headers
    ):
        """Test health check for a specific agent."""
        # First get list of agents
        agents_response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        agents_data = agents_response.json()

        if agents_data["count"] > 0:
            agent_name = agents_data["agents"][0]["name"]

            # Check health of first agent
            health_response = await http_client.get(
                f"/api/v1/agents/{agent_name}/health",
                headers=auth_headers,
            )

            # Should return health status
            assert health_response.status_code in [200, 503]

            if health_response.status_code == 200:
                health_data = health_response.json()
                assert "agent_name" in health_data
                assert "status" in health_data

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_agent(
        self, http_client, auth_headers
    ):
        """Test health check for nonexistent agent."""
        response = await http_client.get(
            "/api/v1/agents/nonexistent_agent_xyz/health",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_health_check_requires_auth(
        self, http_client
    ):
        """Test that health check requires authentication."""
        response = await http_client.get(
            "/api/v1/agents/some_agent/health",
        )

        assert response.status_code == 403


class TestSystemHealth:
    """Test overall system health endpoints."""

    @pytest.mark.asyncio
    async def test_root_health_endpoint(
        self, http_client
    ):
        """Test root health check endpoint."""
        response = await http_client.get("/health")

        # Should return health status (doesn't require auth)
        assert response.status_code in [200, 503]

        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_root_endpoint(
        self, http_client
    ):
        """Test root endpoint returns service info."""
        response = await http_client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "service" in data
        assert "status" in data or "version" in data


class TestOrchestrator Statistics:
    """Test orchestrator statistics endpoints."""

    @pytest.mark.asyncio
    async def test_get_stats(
        self, http_client, auth_headers
    ):
        """Test getting orchestrator statistics."""
        response = await http_client.get(
            "/api/v1/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should include registry stats
        assert "registry" in data

    @pytest.mark.asyncio
    async def test_stats_require_auth(
        self, http_client
    ):
        """Test that stats endpoint requires authentication."""
        response = await http_client.get("/api/v1/stats")

        assert response.status_code == 403


class TestAgentRegistration:
    """Test agent registration and configuration."""

    @pytest.mark.asyncio
    async def test_baggage_operations_agents_registered(
        self, http_client, auth_headers
    ):
        """Test that baggage operations agents are registered."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        data = response.json()
        agents = data["agents"]

        # Should have baggage operations agents
        baggage_agents = [a for a in agents if a["domain"] == "baggage_operations"]
        assert len(baggage_agents) > 0

        # Expected baggage agents (from config)
        expected_agents = [
            "baggage_tracker_agent",
            "risk_assessment_agent",
            "exception_management_agent",
            "connection_protection_agent",
            "recovery_orchestration_agent",
            "communication_agent",
            "analytics_agent",
            "compliance_agent",
        ]

        baggage_agent_names = [a["name"] for a in baggage_agents]

        for expected in expected_agents:
            assert expected in baggage_agent_names, \
                f"Agent {expected} not found in registered agents"

    @pytest.mark.asyncio
    async def test_crew_operations_agents_registered(
        self, http_client, auth_headers
    ):
        """Test that crew operations agents are registered."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        data = response.json()
        agents = data["agents"]

        # Should have crew operations agents
        crew_agents = [a for a in agents if a["domain"] == "crew_operations"]
        assert len(crew_agents) > 0

        # Expected crew agents
        expected_agents = [
            "crew_pay_validator",
            "schedule_analyzer",
        ]

        crew_agent_names = [a["name"] for a in crew_agents]

        for expected in expected_agents:
            assert expected in crew_agent_names, \
                f"Agent {expected} not found in registered agents"

    @pytest.mark.asyncio
    async def test_agents_have_capabilities(
        self, http_client, auth_headers
    ):
        """Test that all agents have defined capabilities."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        data = response.json()
        agents = data["agents"]

        for agent in agents:
            assert "capabilities" in agent
            assert isinstance(agent["capabilities"], list)
            assert len(agent["capabilities"]) > 0


class TestAgentConfiguration:
    """Test agent configuration from YAML."""

    @pytest.mark.asyncio
    async def test_agent_capabilities_match_config(
        self, http_client, auth_headers
    ):
        """Test that agent capabilities match configuration."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        data = response.json()
        agents = data["agents"]

        # Check specific agents have expected capabilities
        tracker = next((a for a in agents if a["name"] == "baggage_tracker_agent"), None)
        if tracker:
            assert "track" in tracker["capabilities"]
            assert "locate" in tracker["capabilities"]

        risk_agent = next((a for a in agents if a["name"] == "risk_assessment_agent"), None)
        if risk_agent:
            assert "risk_analysis" in risk_agent["capabilities"]

    @pytest.mark.asyncio
    async def test_total_agent_count(
        self, http_client, auth_headers
    ):
        """Test that expected number of agents are registered."""
        response = await http_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        data = response.json()

        # Should have 10 agents total (8 baggage + 2 crew)
        assert data["count"] == 10


class TestMonitoringMetrics:
    """Test monitoring and metrics endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_exists(
        self, http_client
    ):
        """Test that metrics endpoint is available."""
        response = await http_client.get("/metrics")

        # Prometheus metrics endpoint should return text
        assert response.status_code == 200

        # Should contain Prometheus metrics format
        content = response.text
        assert "# HELP" in content or "# TYPE" in content or len(content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
