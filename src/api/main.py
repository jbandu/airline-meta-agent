"""FastAPI main application."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
import structlog
import redis.asyncio as redis
import time

from src.config.settings import settings
from src.database.connection import Database
from src.orchestrator.registry import AgentRegistry
from src.orchestrator.context_manager import ContextManager
from src.orchestrator.router import RequestRouter
from src.auth.jwt_handler import JWTHandler
from src.monitoring.metrics import MetricsCollector
from src.api.routes import router

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


class AppState:
    """Application state container."""
    def __init__(self):
        self.db: Database = None
        self.redis_client: redis.Redis = None
        self.registry: AgentRegistry = None
        self.context_manager: ContextManager = None
        self.router: RequestRouter = None
        self.jwt_handler: JWTHandler = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("application_starting", environment=settings.environment)

    # Initialize database
    app_state.db = Database(settings.database_url)
    await app_state.db.create_tables()
    logger.info("database_initialized")

    # Initialize Redis
    app_state.redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    await app_state.redis_client.ping()
    logger.info("redis_connected")

    # Initialize agent registry
    app_state.registry = AgentRegistry(settings.agents_config_path)
    await app_state.registry.load_agents()
    logger.info("agent_registry_initialized")

    # Initialize context manager
    db_session = app_state.db.async_session()
    app_state.context_manager = ContextManager(
        redis_client=app_state.redis_client,
        db_session=await anext(app_state.db.get_session()),
        ttl=3600,
    )
    logger.info("context_manager_initialized")

    # Initialize router
    app_state.router = RequestRouter(
        registry=app_state.registry,
        context_manager=app_state.context_manager,
        anthropic_api_key=settings.anthropic_api_key,
    )
    logger.info("router_initialized")

    # Initialize JWT handler
    app_state.jwt_handler = JWTHandler(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expiration_minutes=settings.jwt_expiration_minutes,
    )
    logger.info("jwt_handler_initialized")

    # Start health check background task
    asyncio.create_task(health_check_task())

    # Set application metrics
    MetricsCollector.set_app_info(version="1.0.0", environment=settings.environment)

    logger.info("application_started")

    yield

    # Cleanup
    logger.info("application_shutting_down")
    await app_state.registry.close_all()
    await app_state.redis_client.close()
    await app_state.db.close()
    logger.info("application_shutdown_complete")


async def health_check_task():
    """Background task for periodic health checks."""
    while True:
        try:
            await app_state.registry.health_check_all()
            await asyncio.sleep(30)  # Check every 30 seconds
        except Exception as e:
            logger.error("health_check_task_error", error=str(e))
            await asyncio.sleep(30)


# Create FastAPI app
app = FastAPI(
    title="Airline Meta Agent Orchestrator",
    description="Production-ready orchestrator for airline domain agents",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time header and metrics."""
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    # Record metrics
    MetricsCollector.record_request(
        endpoint=request.url.path,
        method=request.method,
        status=response.status_code,
        duration=process_time,
    )

    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": str(exc) if settings.environment == "development" else "An error occurred",
        },
    )


# Include routers
app.include_router(router, prefix="/api/v1")

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Airline Meta Agent Orchestrator",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        # Check Redis
        await app_state.redis_client.ping()

        # Get registry stats
        stats = app_state.registry.get_registry_stats()

        return {
            "status": "healthy",
            "redis": "connected",
            "database": "connected",
            "agents": stats,
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
            },
        )


# Dependency providers
def get_app_state():
    """Get application state."""
    return app_state


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower(),
    )
