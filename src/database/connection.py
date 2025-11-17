"""Database connection management."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import structlog

from src.database.models import Base

logger = structlog.get_logger()


class Database:
    """Database connection manager."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            poolclass=NullPool,
            echo=False,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        """Create all tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("database_tables_created")
        except Exception as e:
            logger.error("database_table_creation_error", error=str(e))
            raise

    async def drop_tables(self):
        """Drop all tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("database_tables_dropped")
        except Exception as e:
            logger.error("database_table_drop_error", error=str(e))
            raise

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        async with self.async_session() as session:
            yield session

    async def close(self):
        """Close database connection."""
        await self.engine.dispose()
        logger.info("database_connection_closed")
