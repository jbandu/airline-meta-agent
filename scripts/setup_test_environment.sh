#!/bin/bash

# Script to set up the test environment for E2E tests
# This script prepares the database, Redis, and test data

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Start PostgreSQL and Redis
echo -e "${YELLOW}Starting PostgreSQL and Redis...${NC}"
docker-compose up -d postgres redis

echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 5

# Wait for PostgreSQL
for i in {1..30}; do
    if docker exec airline-orchestrator-db pg_isready -U orchestrator >/dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
        break
    fi
    sleep 1
done

# Create test database
echo -e "${YELLOW}Creating test database...${NC}"
docker exec airline-orchestrator-db psql -U orchestrator -c "CREATE DATABASE test_airline_orchestrator;" 2>/dev/null || echo -e "${BLUE}Test database already exists${NC}"

docker exec airline-orchestrator-db psql -U orchestrator -c "CREATE USER test_user WITH PASSWORD 'test_pass';" 2>/dev/null || echo -e "${BLUE}Test user already exists${NC}"

docker exec airline-orchestrator-db psql -U orchestrator -c "GRANT ALL PRIVILEGES ON DATABASE test_airline_orchestrator TO test_user;" >/dev/null 2>&1

echo -e "${GREEN}✓ Test database configured${NC}"

# Verify Redis
if docker exec airline-orchestrator-redis redis-cli ping >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis is ready${NC}"
fi

# Create Python virtual environment
echo -e "\n${YELLOW}Setting up Python environment...${NC}"
cd "$PROJECT_ROOT"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create test environment file
echo -e "\n${YELLOW}Creating test environment configuration...${NC}"

cat > .env.test << 'EOF'
# Test Environment Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Anthropic API
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-your_api_key_here}

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
LOG_LEVEL=DEBUG
EOF

echo -e "${GREEN}✓ Test environment file created${NC}"

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Test environment setup complete!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${BLUE}To run tests, use:${NC}"
echo -e "  ${YELLOW}./scripts/run_e2e_tests.sh${NC}\n"

echo -e "${BLUE}Or manually:${NC}"
echo -e "  ${YELLOW}source venv/bin/activate${NC}"
echo -e "  ${YELLOW}pytest tests/e2e/ -v${NC}\n"
