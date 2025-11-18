"""End-to-end test fixtures and configuration."""

import pytest
import asyncio
from typing import AsyncGenerator, Dict
import httpx
from fastapi.testclient import TestClient
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.api.main import app
from src.database.models import Base
from src.auth.jwt_handler import JWTHandler


# Test configuration
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_airline_orchestrator"
TEST_REDIS_URL = "redis://localhost:6379/1"
API_BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_db_engine):
    """Create database session for tests."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest.fixture
async def redis_client():
    """Create Redis client for tests."""
    client = redis.from_url(TEST_REDIS_URL, decode_responses=True)

    # Clear test database
    await client.flushdb()

    yield client

    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def http_client():
    """Create async HTTP client."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def jwt_handler():
    """Create JWT handler for tests."""
    return JWTHandler(
        secret_key="test_secret_key_12345",
        algorithm="HS256",
        expiration_minutes=60,
    )


@pytest.fixture
def test_user_credentials():
    """Test user credentials."""
    return {
        "username": "test_user",
        "email": "test@example.com",
        "password": "TestPassword123!",
    }


@pytest.fixture
async def authenticated_user(http_client, test_user_credentials):
    """Create and authenticate a test user."""
    # Register user
    register_response = await http_client.post(
        "/api/v1/auth/register",
        json=test_user_credentials,
    )

    if register_response.status_code == 201:
        data = register_response.json()
        return {
            "token": data["access_token"],
            "user_id": data["user_id"],
            "username": data["username"],
        }

    # If user already exists, login
    login_response = await http_client.post(
        "/api/v1/auth/login",
        json={
            "username": test_user_credentials["username"],
            "password": test_user_credentials["password"],
        },
    )

    data = login_response.json()
    return {
        "token": data["access_token"],
        "user_id": data["user_id"],
        "username": data["username"],
    }


@pytest.fixture
def auth_headers(authenticated_user):
    """Get authorization headers with JWT token."""
    return {"Authorization": f"Bearer {authenticated_user['token']}"}


@pytest.fixture
def sample_baggage_query():
    """Sample baggage tracking query."""
    return {
        "message": "Where is bag NH459 and what's the risk it will miss the connection?",
    }


@pytest.fixture
def sample_crew_query():
    """Sample crew pay validation query."""
    return {
        "message": "Validate crew member pay for trip 2847",
    }


@pytest.fixture
def sample_analytics_query():
    """Sample analytics query."""
    return {
        "message": "What's causing high baggage mishandling on route PTY-MIA?",
    }


# Mock agent responses for testing
@pytest.fixture
def mock_agent_response():
    """Mock successful agent response."""
    return {
        "success": True,
        "data": {
            "bag_id": "NH459",
            "location": "Gate 14",
            "status": "in_transit",
        },
        "message": "Bag located successfully",
    }


@pytest.fixture
def mock_agent_error_response():
    """Mock error agent response."""
    return {
        "success": False,
        "error": "Agent temporarily unavailable",
        "message": "Failed to process request",
    }


# Helper functions
def assert_successful_response(response_data: Dict):
    """Assert response is successful."""
    assert response_data["success"] is True
    assert "message" in response_data
    assert "agents_used" in response_data
    assert len(response_data["agents_used"]) > 0


def assert_failed_response(response_data: Dict):
    """Assert response failed."""
    assert response_data["success"] is False
    assert "error" in response_data or "message" in response_data


def assert_valid_jwt_response(response_data: Dict):
    """Assert JWT response is valid."""
    assert "access_token" in response_data
    assert "token_type" in response_data
    assert response_data["token_type"] == "bearer"
    assert "user_id" in response_data
    assert "username" in response_data
