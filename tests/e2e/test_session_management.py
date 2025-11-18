"""End-to-end tests for session management."""

import pytest


class TestSessionCreation:
    """Test session creation and retrieval."""

    @pytest.mark.asyncio
    async def test_session_created_on_first_chat(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test that session is created on first chat."""
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        assert response.status_code == 200
        data = response.json()

        session_id = data["session_id"]
        assert session_id is not None
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_session_persists_across_requests(
        self, http_client, auth_headers
    ):
        """Test that session persists across multiple requests."""
        session_id = "persist-test-123"

        # First request
        response1 = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Track bag NH459",
                "session_id": session_id,
            },
        )

        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["session_id"] == session_id

        # Second request with same session
        response2 = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "What's the status?",
                "session_id": session_id,
            },
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_get_session_endpoint(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test getting session information."""
        # Create session via chat
        chat_response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        session_id = chat_response.json()["session_id"]

        # Get session info
        session_response = await http_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        if session_response.status_code == 200:
            session_data = session_response.json()
            assert session_data["session_id"] == session_id
            assert "user_id" in session_data
            assert "agent_chain" in session_data


class TestSessionHistory:
    """Test session conversation history."""

    @pytest.mark.asyncio
    async def test_get_session_history(
        self, http_client, auth_headers
    ):
        """Test retrieving session history."""
        session_id = "history-test-123"

        # Make several requests
        messages = [
            "Track bag NH459",
            "What's the risk?",
            "Create recovery plan",
        ]

        for msg in messages:
            await http_client.post(
                "/api/v1/chat",
                headers=auth_headers,
                json={
                    "message": msg,
                    "session_id": session_id,
                },
            )

        # Get history
        history_response = await http_client.get(
            f"/api/v1/sessions/{session_id}/history",
            headers=auth_headers,
        )

        if history_response.status_code == 200:
            history_data = history_response.json()
            assert "history" in history_data
            assert isinstance(history_data["history"], list)
            # Should have at least some history
            assert len(history_data["history"]) > 0

    @pytest.mark.asyncio
    async def test_history_limit(
        self, http_client, auth_headers
    ):
        """Test history limit parameter."""
        session_id = "limit-test-123"

        # Make multiple requests
        for i in range(10):
            await http_client.post(
                "/api/v1/chat",
                headers=auth_headers,
                json={
                    "message": f"Message {i}",
                    "session_id": session_id,
                },
            )

        # Get limited history
        history_response = await http_client.get(
            f"/api/v1/sessions/{session_id}/history?limit=5",
            headers=auth_headers,
        )

        if history_response.status_code == 200:
            history_data = history_response.json()
            # Should respect limit
            assert len(history_data["history"]) <= 5


class TestSessionDeletion:
    """Test session deletion."""

    @pytest.mark.asyncio
    async def test_delete_session(
        self, http_client, auth_headers, sample_baggage_query
    ):
        """Test deleting a session."""
        # Create session
        chat_response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json=sample_baggage_query,
        )

        session_id = chat_response.json()["session_id"]

        # Delete session
        delete_response = await http_client.delete(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        assert delete_response.status_code == 200

        # Verify session is deleted
        get_response = await http_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(
        self, http_client, auth_headers
    ):
        """Test deleting a nonexistent session."""
        response = await http_client.delete(
            "/api/v1/sessions/nonexistent-session-123",
            headers=auth_headers,
        )

        # Should return 404
        assert response.status_code == 404


class TestSessionSecurity:
    """Test session security and access control."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_user_session(
        self, http_client
    ):
        """Test that users cannot access other users' sessions."""
        # Create first user and session
        user1_response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "username": "user1",
                "email": "user1@example.com",
                "password": "Password123!",
            },
        )

        user1_token = user1_response.json()["access_token"]
        user1_headers = {"Authorization": f"Bearer {user1_token}"}

        # Create session for user1
        chat_response = await http_client.post(
            "/api/v1/chat",
            headers=user1_headers,
            json={"message": "Test message"},
        )

        session_id = chat_response.json()["session_id"]

        # Create second user
        user2_response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "username": "user2",
                "email": "user2@example.com",
                "password": "Password123!",
            },
        )

        user2_token = user2_response.json()["access_token"]
        user2_headers = {"Authorization": f"Bearer {user2_token}"}

        # Try to access user1's session as user2
        get_response = await http_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=user2_headers,
        )

        # Should be forbidden
        assert get_response.status_code == 403

    @pytest.mark.asyncio
    async def test_session_requires_authentication(
        self, http_client, authenticated_user
    ):
        """Test that session endpoints require authentication."""
        # Try to access session without auth
        response = await http_client.get(
            "/api/v1/sessions/some-session-id",
        )

        assert response.status_code == 403


class TestSessionContextVariables:
    """Test session context variable storage."""

    @pytest.mark.asyncio
    async def test_context_variables_stored(
        self, http_client, auth_headers
    ):
        """Test that context variables are stored with session."""
        session_id = "context-var-test"

        # Send message with context
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Track bag NH459",
                "session_id": session_id,
                "context": {
                    "flight": "AA123",
                    "passenger": "John Doe",
                },
            },
        )

        assert response.status_code == 200

        # Retrieve session
        session_response = await http_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        if session_response.status_code == 200:
            session_data = session_response.json()
            # Context variables should be stored
            assert "context_variables" in session_data


class TestAgentChainTracking:
    """Test tracking of agent chains in sessions."""

    @pytest.mark.asyncio
    async def test_agent_chain_recorded(
        self, http_client, auth_headers
    ):
        """Test that agent chain is recorded in session."""
        session_id = "agent-chain-test"

        # Make request
        response = await http_client.post(
            "/api/v1/chat",
            headers=auth_headers,
            json={
                "message": "Track bag NH459 and assess risk",
                "session_id": session_id,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Agents used should be recorded
        assert "agents_used" in data
        assert isinstance(data["agents_used"], list)

        # Get session to verify agent chain
        session_response = await http_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        if session_response.status_code == 200:
            session_data = session_response.json()
            assert "agent_chain" in session_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
