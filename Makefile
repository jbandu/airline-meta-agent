.PHONY: help install dev-install clean test coverage lint format docker-up docker-down docker-restart logs db-migrate

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev-install   - Install development dependencies"
	@echo "  make test          - Run tests"
	@echo "  make coverage      - Run tests with coverage"
	@echo "  make lint          - Run linters"
	@echo "  make format        - Format code"
	@echo "  make docker-up     - Start all services with Docker Compose"
	@echo "  make docker-down   - Stop all services"
	@echo "  make docker-restart - Restart all services"
	@echo "  make logs          - View docker logs"
	@echo "  make clean         - Clean up cache and temporary files"

install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black ruff mypy

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache

test:
	pytest -v

coverage:
	pytest --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src tests
	mypy src

format:
	black src tests
	ruff check --fix src tests

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-restart:
	docker-compose restart

docker-rebuild:
	docker-compose up -d --build

logs:
	docker-compose logs -f orchestrator

logs-all:
	docker-compose logs -f

db-shell:
	docker-compose exec postgres psql -U orchestrator -d airline_orchestrator

redis-shell:
	docker-compose exec redis redis-cli

run-local:
	python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
