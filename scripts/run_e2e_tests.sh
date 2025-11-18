#!/bin/bash

# Script to run end-to-end tests for Airline Meta Agent Orchestrator
# This script starts the necessary services and runs the full e2e test suite

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ENV_FILE="$PROJECT_ROOT/.env.test"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Airline Meta Agent E2E Test Runner${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}\n"

# Setup test environment
echo -e "${YELLOW}Setting up test environment...${NC}"

# Create test .env file if it doesn't exist
if [ ! -f "$TEST_ENV_FILE" ]; then
    echo -e "${YELLOW}Creating test environment file...${NC}"
    cat > "$TEST_ENV_FILE" << EOF
# Test Environment Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Anthropic API (required for intent classification)
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-your_test_api_key_here}

# Test Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=test_airline_orchestrator
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_pass

# Test Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# JWT Settings
JWT_SECRET_KEY=test_secret_key_12345
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Environment
ENVIRONMENT=test
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✓ Test environment file created${NC}"
else
    echo -e "${GREEN}✓ Test environment file already exists${NC}"
fi

# Start test services
echo -e "\n${YELLOW}Starting test services (PostgreSQL, Redis)...${NC}"

# Check if services are already running
if docker ps | grep -q "airline-orchestrator-db"; then
    echo -e "${BLUE}PostgreSQL already running${NC}"
else
    docker-compose up -d postgres
    echo -e "${GREEN}✓ PostgreSQL started${NC}"
    sleep 5  # Wait for PostgreSQL to be ready
fi

if docker ps | grep -q "airline-orchestrator-redis"; then
    echo -e "${BLUE}Redis already running${NC}"
else
    docker-compose up -d redis
    echo -e "${GREEN}✓ Redis started${NC}"
    sleep 2
fi

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
for i in {1..30}; do
    if docker exec airline-orchestrator-db pg_isready -U test_user >/dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Error: PostgreSQL did not become ready${NC}"
        exit 1
    fi
    sleep 1
done

if docker exec airline-orchestrator-redis redis-cli ping >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis is ready${NC}"
else
    echo -e "${RED}Error: Redis is not responding${NC}"
    exit 1
fi

# Install Python dependencies if needed
echo -e "\n${YELLOW}Checking Python dependencies...${NC}"
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    cd "$PROJECT_ROOT"
    python3 -m venv venv
fi

echo -e "${YELLOW}Installing/updating dependencies...${NC}"
source "$PROJECT_ROOT/venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$PROJECT_ROOT/requirements.txt"
echo -e "${GREEN}✓ Dependencies ready${NC}"

# Run tests
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}Running E2E Tests${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Export test environment variables
export $(cat "$TEST_ENV_FILE" | grep -v '^#' | xargs)

# Run pytest with coverage
cd "$PROJECT_ROOT"
pytest tests/e2e/ \
    -v \
    --tb=short \
    --maxfail=5 \
    --capture=no \
    --log-cli-level=INFO

TEST_EXIT_CODE=$?

# Cleanup (optional - comment out if you want to keep services running)
echo -e "\n${YELLOW}Tests complete. Cleaning up...${NC}"
# docker-compose down

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All E2E tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}\n"
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}✗ Some tests failed${NC}"
    echo -e "${RED}========================================${NC}\n"
fi

exit $TEST_EXIT_CODE
