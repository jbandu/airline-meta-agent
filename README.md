# Airline Meta Agent Orchestrator

Production-ready orchestrator for managing and coordinating specialized airline domain agents using FastAPI, LangGraph, and Claude AI.

> **📦 Deployment Branch**: `claude/airline-meta-agent-orchestrator-01BdVtd7nhkBpVdK6d45i8N1`
> **🏷️ Latest Release**: v1.0.0
> **📖 Deployment Guide**: See [DEPLOYMENT.md](DEPLOYMENT.md) for merge and deployment instructions

## Overview

The Airline Meta Agent Orchestrator is a sophisticated microservice that intelligently routes requests to specialized agents across different airline domains (baggage operations, crew management, etc.). It uses LLM-based intent classification, maintains conversation context, and provides comprehensive monitoring.

## Architecture

### Core Components

1. **Agent Registry** - Dynamic agent discovery and registration
2. **Request Router** - LLM-powered intent classification and routing via LangGraph
3. **Context Manager** - Session state management with Redis and PostgreSQL
4. **Response Aggregator** - Multi-agent response combination
5. **Monitoring Dashboard** - Real-time metrics via Prometheus/Grafana

### Tech Stack

- **Python 3.11**
- **FastAPI** - Async REST API framework
- **LangGraph** - Agent workflow orchestration
- **Anthropic Claude** - Intent classification
- **PostgreSQL** - Persistent storage
- **Redis** - Session caching
- **Prometheus/Grafana** - Monitoring

## Directory Structure

```
airline-meta-agent/
├── src/
│   ├── agents/
│   │   ├── base_agent.py          # Agent interface
│   │   └── agent_client.py        # HTTP client for agents
│   ├── orchestrator/
│   │   ├── router.py              # Request routing with LangGraph
│   │   ├── registry.py            # Agent registration
│   │   └── context_manager.py     # Session management
│   ├── api/
│   │   ├── main.py                # FastAPI application
│   │   └── routes.py              # REST endpoints
│   ├── auth/
│   │   ├── jwt_handler.py         # JWT authentication
│   │   └── dependencies.py        # Auth dependencies
│   ├── database/
│   │   ├── models.py              # SQLAlchemy models
│   │   └── connection.py          # Database connection
│   ├── monitoring/
│   │   └── metrics.py             # Prometheus metrics
│   └── config/
│       ├── settings.py            # Application settings
│       └── agents_config.yaml     # Agent definitions
├── tests/
│   ├── test_orchestrator.py      # Orchestrator tests
│   └── test_api.py                # API tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Anthropic API key

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd airline-meta-agent
git checkout claude/airline-meta-agent-orchestrator-01BdVtd7nhkBpVdK6d45i8N1
```

2. **Create environment file**

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```env
ANTHROPIC_API_KEY=your_api_key_here
JWT_SECRET_KEY=your_secure_secret_key
POSTGRES_PASSWORD=your_secure_password
```

3. **Start services with Docker Compose**

```bash
docker-compose up -d
```

This will start:
- PostgreSQL on port 5432
- Redis on port 6379
- Orchestrator API on port 8000
- Prometheus on port 9091
- Grafana on port 3000

4. **Initialize database**

The database tables are automatically created on startup.

### Local Development

1. **Create virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Start infrastructure**

```bash
docker-compose up -d postgres redis
```

4. **Run the application**

```bash
python -m uvicorn src.api.main:app --reload --port 8000
```

## API Usage

### Authentication

**Register a new user:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepassword"
  }'
```

**Login:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepassword"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "testuser"
}
```

### Chat with Agents

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "Track my baggage with tag number BA123456",
    "session_id": "optional-session-id"
  }'
```

Response:
```json
{
  "session_id": "abc123...",
  "success": true,
  "message": "Your baggage has been located...",
  "data": {
    "baggage_tracker_agent": {
      "tag_number": "BA123456",
      "status": "in_transit",
      "location": "JFK Airport"
    }
  },
  "agents_used": ["baggage_tracker_agent"],
  "intent": "track baggage"
}
```

### Agent Management

**List all agents:**

```bash
curl http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Check agent health:**

```bash
curl http://localhost:8000/api/v1/agents/baggage_tracker_agent/health \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**List domains:**

```bash
curl http://localhost:8000/api/v1/agents/domains \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Session Management

**Get session:**

```bash
curl http://localhost:8000/api/v1/sessions/SESSION_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Get conversation history:**

```bash
curl http://localhost:8000/api/v1/sessions/SESSION_ID/history \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Configuration

### Agent Configuration

Edit `src/config/agents_config.yaml` to add or modify agents:

```yaml
agents:
  baggage_operations:
    baggage_tracker_agent:
      url: "http://localhost:8001"
      capabilities:
        - "track"
        - "locate"
      description: "Tracks and locates baggage"
      health_check_endpoint: "/health"
      timeout: 30
      retry_count: 3
```

### Environment Variables

Key environment variables:

- `ANTHROPIC_API_KEY` - Anthropic API key for Claude
- `JWT_SECRET_KEY` - Secret key for JWT tokens
- `POSTGRES_HOST` - PostgreSQL host
- `POSTGRES_PASSWORD` - PostgreSQL password
- `REDIS_HOST` - Redis host
- `LOG_LEVEL` - Logging level (INFO, DEBUG, WARNING, ERROR)
- `ENVIRONMENT` - Environment (development, production)

## Monitoring

### Prometheus Metrics

Access Prometheus at: http://localhost:9091

Available metrics:
- `orchestrator_requests_total` - Total requests
- `agent_requests_total` - Agent requests by status
- `agent_request_duration_seconds` - Agent latency
- `circuit_breaker_state` - Circuit breaker status
- `agent_health_status` - Agent health

### Grafana Dashboards

Access Grafana at: http://localhost:3000
- Username: `admin`
- Password: `admin`

### Application Logs

Structured JSON logs are written to stdout and can be collected by your logging system.

## Testing

Run tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=src --cov-report=html
```

## Production Deployment

### Security Checklist

- [ ] Change default passwords in `.env`
- [ ] Use strong JWT secret key
- [ ] Enable HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Set up log aggregation
- [ ] Configure backup strategy
- [ ] Enable audit logging

### Scaling Considerations

1. **Horizontal Scaling**: Deploy multiple orchestrator instances behind a load balancer
2. **Redis Cluster**: Use Redis Cluster for high availability
3. **PostgreSQL**: Set up primary-replica configuration
4. **Agent Load Balancing**: Deploy multiple instances of each agent

### Health Checks

The orchestrator provides health check endpoints:

- `GET /health` - Overall system health
- `GET /api/v1/agents/{agent_name}/health` - Individual agent health

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

### Agent Communication Failures

1. Check agent URLs in `agents_config.yaml`
2. Verify agents are running and healthy
3. Check circuit breaker status in metrics
4. Review agent logs for errors

## API Documentation

Interactive API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [Your Repo URL]
- Email: [Your Support Email]

## Roadmap

- [ ] Add GraphQL API support
- [ ] Implement agent A/B testing
- [ ] Add multi-language support
- [ ] Enhanced analytics dashboard
- [ ] WebSocket support for real-time updates
- [ ] Machine learning-based routing optimization
