#!/bin/bash

# Quick test runner - runs specific test suites
# Usage: ./scripts/quick_test.sh [auth|routing|session|health|all]

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load test environment
if [ -f ".env.test" ]; then
    export $(cat .env.test | grep -v '^#' | xargs)
fi

TEST_SUITE=${1:-all}

echo -e "${BLUE}Running tests: ${YELLOW}$TEST_SUITE${NC}\n"

case $TEST_SUITE in
    auth)
        pytest tests/e2e/test_auth_flow.py -v
        ;;
    routing)
        pytest tests/e2e/test_routing_flow.py -v
        ;;
    session)
        pytest tests/e2e/test_session_management.py -v
        ;;
    health)
        pytest tests/e2e/test_agent_health.py -v
        ;;
    all)
        pytest tests/e2e/ -v
        ;;
    *)
        echo -e "${YELLOW}Usage: $0 [auth|routing|session|health|all]${NC}"
        exit 1
        ;;
esac

TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}✓ Tests passed!${NC}\n"
else
    echo -e "\n${YELLOW}✗ Some tests failed${NC}\n"
fi

exit $TEST_EXIT_CODE
