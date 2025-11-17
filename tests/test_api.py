"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import uuid

from src.api.main import app
from src.database.models import User
from src.auth.jwt_handler import JWTHandler


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Create test user."""
    return User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password=JWTHandler.hash_password("testpassword"),
        is_active=1,
    )


@pytest.fixture
def auth_token():
    """Create test auth token."""
    jwt_handler = JWTHandler(
        secret_key="test_secret_key",
        algorithm="HS256",
        expiration_minutes=60,
    )
    return jwt_handler.create_access_token(
        data={"sub": "testuser", "user_id": str(uuid.uuid4())}
    )


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Airline Meta Agent Orchestrator"
        assert data["status"] == "running"


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""

    @patch('src.api.routes.get_app_state')
    def test_register_endpoint(self, mock_get_app_state, client):
        """Test user registration endpoint."""
        # Mock app state and database
        mock_app_state = Mock()
        mock_db_session = AsyncMock()
        mock_app_state.db.get_session = AsyncMock(return_value=mock_db_session)
        mock_app_state.jwt_handler = JWTHandler(
            secret_key="test_secret",
            algorithm="HS256",
            expiration_minutes=60,
        )
        mock_get_app_state.return_value = mock_app_state

        # Note: This is a basic test structure. Full implementation would require
        # more complex mocking of database operations

    @patch('src.api.routes.get_app_state')
    def test_login_endpoint(self, mock_get_app_state, client):
        """Test login endpoint."""
        # Similar structure to registration test
        # Would require mocking database and JWT operations
        pass


class TestChatEndpoints:
    """Test chat endpoints."""

    def test_chat_requires_authentication(self, client):
        """Test that chat endpoint requires authentication."""
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello"},
        )
        assert response.status_code == 403  # Forbidden without auth


class TestAgentEndpoints:
    """Test agent management endpoints."""

    def test_list_agents_requires_authentication(self, client):
        """Test that listing agents requires authentication."""
        response = client.get("/api/v1/agents")
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
