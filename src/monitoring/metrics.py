"""Prometheus metrics for monitoring."""

from prometheus_client import Counter, Histogram, Gauge, Info
import structlog

logger = structlog.get_logger()

# Request metrics
request_count = Counter(
    "orchestrator_requests_total",
    "Total number of requests to the orchestrator",
    ["endpoint", "method", "status"]
)

request_duration = Histogram(
    "orchestrator_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint", "method"]
)

# Agent metrics
agent_requests = Counter(
    "agent_requests_total",
    "Total number of requests to agents",
    ["agent_name", "status"]
)

agent_duration = Histogram(
    "agent_request_duration_seconds",
    "Agent request duration in seconds",
    ["agent_name"]
)

agent_failures = Counter(
    "agent_failures_total",
    "Total number of agent failures",
    ["agent_name", "error_type"]
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["agent_name"]
)

circuit_breaker_failures = Counter(
    "circuit_breaker_failures_total",
    "Total number of circuit breaker failures",
    ["agent_name"]
)

# Agent health metrics
agent_health_status = Gauge(
    "agent_health_status",
    "Agent health status (1=healthy, 0=unhealthy)",
    ["agent_name", "domain"]
)

# Session metrics
active_sessions = Gauge(
    "active_sessions",
    "Number of active sessions"
)

session_duration = Histogram(
    "session_duration_seconds",
    "Session duration in seconds"
)

# Database metrics
db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"]
)

db_connection_pool = Gauge(
    "db_connection_pool_size",
    "Database connection pool size"
)

# Application info
app_info = Info(
    "orchestrator_app",
    "Airline Meta Agent Orchestrator application info"
)


class MetricsCollector:
    """Collect and update metrics."""

    @staticmethod
    def record_request(endpoint: str, method: str, status: int, duration: float):
        """Record HTTP request metrics."""
        request_count.labels(endpoint=endpoint, method=method, status=status).inc()
        request_duration.labels(endpoint=endpoint, method=method).observe(duration)

    @staticmethod
    def record_agent_request(agent_name: str, success: bool, duration: float):
        """Record agent request metrics."""
        status = "success" if success else "failure"
        agent_requests.labels(agent_name=agent_name, status=status).inc()
        agent_duration.labels(agent_name=agent_name).observe(duration / 1000)  # Convert ms to seconds

    @staticmethod
    def record_agent_failure(agent_name: str, error_type: str):
        """Record agent failure."""
        agent_failures.labels(agent_name=agent_name, error_type=error_type).inc()

    @staticmethod
    def update_agent_health(agent_name: str, domain: str, is_healthy: bool):
        """Update agent health status."""
        agent_health_status.labels(agent_name=agent_name, domain=domain).set(1 if is_healthy else 0)

    @staticmethod
    def update_circuit_breaker_state(agent_name: str, state: str):
        """Update circuit breaker state."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        circuit_breaker_state.labels(agent_name=agent_name).set(state_map.get(state, 0))

    @staticmethod
    def record_circuit_breaker_failure(agent_name: str):
        """Record circuit breaker failure."""
        circuit_breaker_failures.labels(agent_name=agent_name).inc()

    @staticmethod
    def update_active_sessions(count: int):
        """Update active sessions count."""
        active_sessions.set(count)

    @staticmethod
    def record_session_duration(duration: float):
        """Record session duration."""
        session_duration.observe(duration)

    @staticmethod
    def record_db_query(operation: str, duration: float):
        """Record database query duration."""
        db_query_duration.labels(operation=operation).observe(duration)

    @staticmethod
    def set_app_info(version: str, environment: str):
        """Set application info."""
        app_info.info({"version": version, "environment": environment})
