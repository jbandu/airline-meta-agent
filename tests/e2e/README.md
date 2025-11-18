# End-to-End Tests

Comprehensive end-to-end test suite for the Airline Meta Agent Orchestrator.

## Overview

These tests verify the complete system functionality including:
- **Authentication** - User registration, login, JWT tokens
- **Request Routing** - Intent classification, agent selection, orchestration
- **Session Management** - Session creation, persistence, context tracking
- **Agent Health** - Agent registration, health checks, monitoring

## Test Structure

```
tests/e2e/
├── conftest.py                    # Test fixtures and configuration
├── test_auth_flow.py              # Authentication tests (45 tests)
├── test_routing_flow.py           # Routing and orchestration tests (30+ tests)
├── test_session_management.py     # Session tests (20+ tests)
└── test_agent_health.py           # Agent health and monitoring tests (25+ tests)
```

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL (via Docker)
- Redis (via Docker)
- Anthropic API key (for intent classification)

## Quick Start

### 1. Setup Test Environment

```bash
# Run the setup script
./scripts/setup_test_environment.sh
```

This will:
- Start PostgreSQL and Redis containers
- Create test database and user
- Set up Python virtual environment
- Install dependencies
- Create `.env.test` configuration file

### 2. Run All Tests

```bash
# Run complete e2e test suite
./scripts/run_e2e_tests.sh
```

### 3. Run Specific Test Suites

```bash
# Run only authentication tests
./scripts/quick_test.sh auth

# Run only routing tests
./scripts/quick_test.sh routing

# Run only session tests
./scripts/quick_test.sh session

# Run only health check tests
./scripts/quick_test.sh health
```

## Manual Testing

### Activate Environment

```bash
source venv/bin/activate
export $(cat .env.test | grep -v '^#' | xargs)
```

### Run Specific Tests

```bash
# Run all e2e tests
pytest tests/e2e/ -v

# Run specific test file
pytest tests/e2e/test_auth_flow.py -v

# Run specific test class
pytest tests/e2e/test_auth_flow.py::TestAuthenticationFlow -v

# Run specific test
pytest tests/e2e/test_auth_flow.py::TestAuthenticationFlow::test_user_registration -v

# Run with coverage
pytest tests/e2e/ --cov=src --cov-report=html -v

# Run with detailed output
pytest tests/e2e/ -vv -s

# Run and stop at first failure
pytest tests/e2e/ -x

# Run with specific markers
pytest tests/e2e/ -v -m asyncio
```

## Test Suites

### Authentication Tests (`test_auth_flow.py`)

**TestAuthenticationFlow**
- ✅ User registration
- ✅ Duplicate registration handling
- ✅ User login
- ✅ Invalid credentials handling
- ✅ Protected endpoint access
- ✅ Token validation

**TestAuthenticationSecurity**
- ✅ Password hashing
- ✅ Weak password rejection
- ✅ Token security

**TestAuthenticationWorkflow**
- ✅ Complete registration-to-API flow
- ✅ Login after registration
- ✅ Multiple login sessions

### Routing Tests (`test_routing_flow.py`)

**TestBasicRouting**
- ✅ Chat endpoint basic functionality
- ✅ Session ID handling
- ✅ Authentication requirements

**TestIntentClassification**
- ✅ Baggage tracking intent
- ✅ Crew pay validation intent
- ✅ Analytics query intent

**TestExecutionModes**
- ✅ Sequential execution detection
- ✅ Parallel execution detection
- ✅ Single agent execution

**TestUrgencyDetection**
- ✅ High urgency detection
- ✅ Low urgency detection

**TestMultiAgentOrchestration**
- ✅ Multi-agent detection
- ✅ Context passing between agents

**TestErrorHandling**
- ✅ Empty message handling
- ✅ Very long message handling
- ✅ Malformed request handling
- ✅ Invalid session ID handling

**TestResponseStructure**
- ✅ Required fields verification
- ✅ Metadata validation
- ✅ Data type checking

### Session Tests (`test_session_management.py`)

**TestSessionCreation**
- ✅ Session creation on first chat
- ✅ Session persistence
- ✅ Session retrieval endpoint

**TestSessionHistory**
- ✅ Conversation history retrieval
- ✅ History limit parameter

**TestSessionDeletion**
- ✅ Session deletion
- ✅ Nonexistent session handling

**TestSessionSecurity**
- ✅ Cross-user access prevention
- ✅ Authentication requirements

**TestSessionContextVariables**
- ✅ Context variable storage

**TestAgentChainTracking**
- ✅ Agent chain recording

### Health Check Tests (`test_agent_health.py`)

**TestAgentEndpoints**
- ✅ List all agents
- ✅ Agent field validation
- ✅ List domains
- ✅ List capabilities

**TestAgentHealthChecks**
- ✅ Individual agent health
- ✅ Nonexistent agent handling
- ✅ Authentication requirements

**TestSystemHealth**
- ✅ Root health endpoint
- ✅ Service info endpoint

**TestOrchestratorStatistics**
- ✅ Statistics endpoint
- ✅ Registry stats

**TestAgentRegistration**
- ✅ Baggage operations agents
- ✅ Crew operations agents
- ✅ Agent capabilities

**TestAgentConfiguration**
- ✅ Capability matching
- ✅ Total agent count

**TestMonitoringMetrics**
- ✅ Prometheus metrics endpoint

## Configuration

### Test Environment Variables

Create `.env.test` file with:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Anthropic API (required for intent classification)
ANTHROPIC_API_KEY=your_api_key_here

# Test Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=test_airline_orchestrator
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_pass

# Test Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1  # Use DB 1 to separate from dev

# JWT Settings
JWT_SECRET_KEY=test_secret_key_12345
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Environment
ENVIRONMENT=test
LOG_LEVEL=INFO
```

### Test Database Setup

The test database is automatically created by the setup script, but you can manually create it:

```bash
# Connect to PostgreSQL
docker exec -it airline-orchestrator-db psql -U orchestrator

# Create test database
CREATE DATABASE test_airline_orchestrator;
CREATE USER test_user WITH PASSWORD 'test_pass';
GRANT ALL PRIVILEGES ON DATABASE test_airline_orchestrator TO test_user;
```

## Fixtures

### Available Fixtures (from `conftest.py`)

**Database & Storage**
- `test_db_engine` - Test database engine
- `db_session` - Database session
- `redis_client` - Redis client

**HTTP Clients**
- `test_client` - Synchronous TestClient
- `http_client` - Async HTTP client

**Authentication**
- `jwt_handler` - JWT token handler
- `test_user_credentials` - Test user credentials
- `authenticated_user` - Pre-authenticated user with token
- `auth_headers` - Authorization headers

**Sample Queries**
- `sample_baggage_query` - Baggage tracking query
- `sample_crew_query` - Crew pay validation query
- `sample_analytics_query` - Analytics query

**Helper Functions**
- `assert_successful_response()` - Verify successful response
- `assert_failed_response()` - Verify failed response
- `assert_valid_jwt_response()` - Verify JWT response

## Troubleshooting

### Tests Failing to Connect

```bash
# Check if services are running
docker ps | grep airline-orchestrator

# Restart services
docker-compose restart postgres redis

# Check service logs
docker logs airline-orchestrator-db
docker logs airline-orchestrator-redis
```

### Database Issues

```bash
# Reset test database
docker exec airline-orchestrator-db psql -U orchestrator -c "DROP DATABASE test_airline_orchestrator;"
docker exec airline-orchestrator-db psql -U orchestrator -c "CREATE DATABASE test_airline_orchestrator;"
```

### Redis Issues

```bash
# Clear Redis test database
docker exec airline-orchestrator-redis redis-cli -n 1 FLUSHDB
```

### Import Errors

```bash
# Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt
```

### Missing ANTHROPIC_API_KEY

Some tests require the Anthropic API key for intent classification. Set it:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Or add to `.env.test` file.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
          POSTGRES_DB: test_airline_orchestrator
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run E2E tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          pytest tests/e2e/ -v --cov=src
```

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures to ensure proper cleanup after tests
3. **Assertions**: Use descriptive assertions that explain what's being tested
4. **Async Tests**: Mark async tests with `@pytest.mark.asyncio`
5. **Test Data**: Use fixtures for reusable test data
6. **Error Handling**: Test both success and failure scenarios

## Contributing

When adding new tests:

1. Place tests in the appropriate test file
2. Use descriptive test names: `test_<what>_<condition>_<expected>`
3. Add docstrings explaining what the test does
4. Use existing fixtures where possible
5. Clean up test data in teardown
6. Run the full test suite before committing

## Performance

Test suite performance:
- **Full suite**: ~30-60 seconds
- **Auth tests**: ~5-10 seconds
- **Routing tests**: ~15-20 seconds
- **Session tests**: ~10-15 seconds
- **Health tests**: ~5-10 seconds

## Support

For issues with tests:
1. Check test logs for specific error messages
2. Verify all services are running
3. Check test environment configuration
4. Review recent code changes
5. Open an issue with test output and environment details
