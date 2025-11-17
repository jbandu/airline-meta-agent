"""Application settings and configuration."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Anthropic API
    anthropic_api_key: str

    # Database Settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "airline_orchestrator"
    postgres_user: str = "orchestrator"
    postgres_password: str

    # Redis Settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    # JWT Settings
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Monitoring
    prometheus_port: int = 9090
    log_level: str = "INFO"

    # Environment
    environment: str = "development"

    # Agent Config
    agents_config_path: str = "src/config/agents_config.yaml"

    @property
    def database_url(self) -> str:
        """Get PostgreSQL database URL."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        """Get Redis URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
