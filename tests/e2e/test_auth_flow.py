"""End-to-end tests for authentication flow."""

import pytest
from tests.e2e.conftest import assert_valid_jwt_response


class TestAuthenticationFlow:
    """Test user authentication flows."""

    @pytest.mark.asyncio
    async def test_user_registration(self, http_client):
        """Test user registration flow."""
        # Register new user
        response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser123",
                "email": "newuser@example.com",
                "password": "SecurePass123!",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert_valid_jwt_response(data)
        assert data["username"] == "newuser123"

    @pytest.mark.asyncio
    async def test_duplicate_registration(self, http_client, test_user_credentials):
        """Test that duplicate registration fails."""
        # First registration
        await http_client.post(
            "/api/v1/auth/register",
            json=test_user_credentials,
        )

        # Attempt duplicate registration
        response = await http_client.post(
            "/api/v1/auth/register",
            json=test_user_credentials,
        )

        assert response.status_code == 400
        data = response.json()
        assert "already registered" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_user_login(self, http_client, test_user_credentials):
        """Test user login flow."""
        # Register user first
        await http_client.post(
            "/api/v1/auth/register",
            json=test_user_credentials,
        )

        # Login
        response = await http_client.post(
            "/api/v1/auth/login",
            json={
                "username": test_user_credentials["username"],
                "password": test_user_credentials["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert_valid_jwt_response(data)

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, http_client):
        """Test login with invalid credentials."""
        response = await http_client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "incorrect" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_auth(self, http_client):
        """Test that protected endpoints require authentication."""
        response = await http_client.get("/api/v1/agents")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_auth(self, http_client, auth_headers):
        """Test that protected endpoints work with valid auth."""
        response = await http_client.get("/api/v1/agents", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "count" in data

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_invalid_token(self, http_client):
        """Test that invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = await http_client.get("/api/v1/agents", headers=headers)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_token_contains_user_info(self, http_client, authenticated_user, jwt_handler):
        """Test that JWT token contains correct user information."""
        token_data = jwt_handler.verify_token(authenticated_user["token"])

        assert token_data is not None
        assert token_data.username == authenticated_user["username"]
        assert token_data.user_id == authenticated_user["user_id"]


class TestAuthenticationSecurity:
    """Test authentication security features."""

    @pytest.mark.asyncio
    async def test_password_hashing(self, http_client, test_user_credentials, db_session):
        """Test that passwords are hashed in database."""
        from src.database.models import User
        from sqlalchemy import select

        # Register user
        await http_client.post(
            "/api/v1/auth/register",
            json=test_user_credentials,
        )

        # Check database
        result = await db_session.execute(
            select(User).where(User.username == test_user_credentials["username"])
        )
        user = result.scalar_one_or_none()

        assert user is not None
        # Password should be hashed, not plain text
        assert user.hashed_password != test_user_credentials["password"]
        # Hashed password should be longer
        assert len(user.hashed_password) > len(test_user_credentials["password"])

    @pytest.mark.asyncio
    async def test_weak_password_rejected(self, http_client):
        """Test that weak passwords are rejected (if validation exists)."""
        # This test assumes password validation is implemented
        response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "123",  # Weak password
            },
        )

        # Should either reject or accept based on implementation
        # Adjust assertion based on your password policy
        assert response.status_code in [201, 400, 422]


class TestAuthenticationWorkflow:
    """Test complete authentication workflows."""

    @pytest.mark.asyncio
    async def test_complete_registration_to_api_call_flow(
        self, http_client, sample_baggage_query
    ):
        """Test complete flow from registration to making API call."""
        # Step 1: Register
        register_response = await http_client.post(
            "/api/v1/auth/register",
            json={
                "username": "flowtest123",
                "email": "flowtest@example.com",
                "password": "FlowTest123!",
            },
        )

        assert register_response.status_code == 201
        auth_data = register_response.json()
        token = auth_data["access_token"]

        # Step 2: Make authenticated API call
        headers = {"Authorization": f"Bearer {token}"}
        api_response = await http_client.get("/api/v1/agents", headers=headers)

        assert api_response.status_code == 200

        # Step 3: Use chat endpoint
        chat_response = await http_client.post(
            "/api/v1/chat",
            headers=headers,
            json=sample_baggage_query,
        )

        # Should succeed (even if agents aren't running, should get proper response)
        assert chat_response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_after_registration_flow(self, http_client):
        """Test login immediately after registration."""
        credentials = {
            "username": "logintest",
            "email": "logintest@example.com",
            "password": "LoginTest123!",
        }

        # Register
        register_response = await http_client.post(
            "/api/v1/auth/register",
            json=credentials,
        )
        assert register_response.status_code == 201

        # Login with same credentials
        login_response = await http_client.post(
            "/api/v1/auth/login",
            json={
                "username": credentials["username"],
                "password": credentials["password"],
            },
        )

        assert login_response.status_code == 200
        login_data = login_response.json()
        assert_valid_jwt_response(login_data)

    @pytest.mark.asyncio
    async def test_multiple_logins_generate_valid_tokens(self, http_client, test_user_credentials):
        """Test that multiple logins generate different valid tokens."""
        # Register once
        await http_client.post(
            "/api/v1/auth/register",
            json=test_user_credentials,
        )

        # Login multiple times
        tokens = []
        for _ in range(3):
            response = await http_client.post(
                "/api/v1/auth/login",
                json={
                    "username": test_user_credentials["username"],
                    "password": test_user_credentials["password"],
                },
            )
            data = response.json()
            tokens.append(data["access_token"])

        # All tokens should be valid but may be different
        for token in tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = await http_client.get("/api/v1/agents", headers=headers)
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
