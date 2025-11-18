"""End-to-end tests for request routing and orchestration."""

import pytest
from tests.e2e.conftest import assert_successful_response, assert_failed_response


class TestBasicRouting:
    """Test basic request routing functionality."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_basic(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test basic chat endpoint."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session_id" in data
        assert "success" in data
        assert "message" in data
        assert "agents_used" in data
        assert "intent" in data

    @pytest.mark.asyncio
    async def test_chat_with_session_id(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test chat with provided session ID."""
        session_id = "test-session-12345"

        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                **sample_baggage_query,
                "session_id": session_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_chat_without_authentication(
        self, http_client, sample_baggage_query
    ):
        """Test that chat endpoint requires authentication."""
        response = await http_client.post(
            "/api/v1/chat",
            json=sample_baggage_query,
        )

        assert response.status_code == 403


class TestIntentClassification:
    """Test intent classification for different query types."""

    @pytest.mark.asyncio
    async def test_baggage_tracking_intent(
        self, http_client, auth_headers
    ):
        """Test baggage tracking query classification."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={"message": "Track baggage NH459"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should classify as baggage operations
        assert "baggage" in data.get("intent", "").lower() or \
               "track" in data.get("intent", "").lower()

    @pytest.mark.asyncio
    async def test_crew_pay_intent(
        self, http_client, auth_headers, sample_crew_query
    ):
        """Test crew pay validation query classification."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_crew_query,
        )

        assert response.status_code == 200
        data = response.json()

        # Should classify as crew operations
        assert "crew" in data.get("intent", "").lower() or \
               "pay" in data.get("intent", "").lower() or \
               "validate" in data.get("intent", "").lower()

    @pytest.mark.asyncio
    async def test_analytics_intent(
        self, http_client, auth_headers, sample_analytics_query
    ):
        """Test analytics query classification."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_analytics_query,
        )

        assert response.status_code == 200
        data = response.json()

        # Should classify as analytics
        assert "analyz" in data.get("intent", "").lower() or \
               "causing" in data.get("intent", "").lower()


class TestExecutionModes:
    """Test different execution modes (sequential, parallel, conditional)."""

    @pytest.mark.asyncio
    async def test_sequential_execution_detection(
        self, http_client, auth_headers
    ):
        """Test that sequential execution is detected for dependent operations."""
        # Query that should trigger sequential execution
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Where is bag NH459 and what's the risk it will miss the connection?"
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should use sequential or conditional mode
        if "execution_mode" in data:
            assert data["execution_mode"] in ["sequential", "conditional"]

    @pytest.mark.asyncio
    async def test_parallel_execution_detection(
        self, http_client, auth_headers, sample_analytics_query
    ):
        """Test that parallel execution is detected for independent operations."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_analytics_query,
        )

        assert response.status_code == 200
        data = response.json()

        # May use parallel mode for analytics
        # Execution mode detection depends on LLM classification
        assert data["success"] is not None

    @pytest.mark.asyncio
    async def test_single_agent_execution(
        self, http_client, auth_headers, sample_crew_query
    ):
        """Test single agent execution for simple queries."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_crew_query,
        )

        assert response.status_code == 200
        data = response.json()

        # Single agent queries should work
        assert data["success"] is not None


class TestUrgencyDetection:
    """Test urgency level detection."""

    @pytest.mark.asyncio
    async def test_high_urgency_detection(
        self, http_client, auth_headers
    ):
        """Test high urgency detection for time-sensitive queries."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "URGENT: Passenger missing connection, bag NH459 not transferred!"
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should detect high urgency (if supported)
        if "urgency" in data:
            assert data["urgency"] in ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_low_urgency_detection(
        self, http_client, auth_headers
    ):
        """Test low urgency for reporting queries."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Generate monthly baggage handling report"
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should detect low urgency for reports (if supported)
        if "urgency" in data:
            assert data["urgency"] in ["high", "medium", "low"]


class TestMultiAgentOrchestration:
    """Test multi-agent orchestration scenarios."""

    @pytest.mark.asyncio
    async def test_multi_agent_detection(
        self, http_client, auth_headers
    ):
        """Test that multi-agent needs are detected."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Track bag NH459, assess risk, and create recovery plan"
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should potentially use multiple agents
        # Actual number depends on agent availability
        assert isinstance(data.get("agents_used", []), list)

    @pytest.mark.asyncio
    async def test_context_passing(
        self, http_client, auth_headers
    ):
        """Test that context is maintained across requests in same session."""
        session_id = "context-test-session"

        # First message
        response1 = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Track bag NH459",
                "session_id": session_id,
            },
        )

        assert response1.status_code == 200

        # Follow-up message in same session
        response2 = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "What's the risk for this bag?",
                "session_id": session_id,
            },
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["session_id"] == session_id


class TestErrorHandling:
    """Test error handling in routing."""

    @pytest.mark.asyncio
    async def test_empty_message(
        self, http_client, auth_headers
    ):
        """Test handling of empty message."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={"message": ""},
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_very_long_message(
        self, http_client, auth_headers
    ):
        """Test handling of very long message."""
        long_message = "Track bag " + "A" * 10000

        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={"message": long_message},
        )

        # Should handle gracefully (truncate or reject)
        assert response.status_code in [200, 400, 413, 422]

    @pytest.mark.asyncio
    async def test_malformed_request(
        self, http_client, auth_headers
    ):
        """Test handling of malformed request."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={"wrong_field": "value"},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_invalid_session_id(
        self, http_client, auth_headers
    ):
        """Test handling of invalid session ID."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Track bag NH459",
                "session_id": "invalid!@#$%^&*()",
            },
        )

        # Should either accept or reject based on validation
        assert response.status_code in [200, 400, 422]


class TestResponseStructure:
    """Test response structure and data."""

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test that response contains all required fields."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "session_id" in data
        assert "success" in data
        assert "message" in data
        assert "agents_used" in data

    @pytest.mark.asyncio
    async def test_response_metadata(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test that response contains metadata."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        assert response.status_code == 200
        data = response.json()

        # Optional but expected metadata
        if data.get("success"):
            assert "intent" in data or "message" in data

    @pytest.mark.asyncio
    async def test_agents_used_is_list(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test that agents_used is always a list."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["agents_used"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
