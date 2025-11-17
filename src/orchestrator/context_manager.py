"""Context manager for maintaining conversation state across agents."""

import json
import structlog
from typing import Any, Dict, List, Optional
from datetime import datetime
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.models import ConversationHistory

logger = structlog.get_logger()


class SessionContext:
    """Session context model."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        agent_chain: Optional[List[str]] = None,
        context_variables: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_chain = agent_chain or []
        self.context_variables = context_variables or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_chain": self.agent_chain,
            "context_variables": self.context_variables,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionContext":
        """Create from dictionary."""
        context = cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            agent_chain=data.get("agent_chain", []),
            context_variables=data.get("context_variables", {}),
        )
        if "created_at" in data:
            context.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            context.updated_at = datetime.fromisoformat(data["updated_at"])
        return context


class ContextManager:
    """Manages conversation context using Redis and PostgreSQL."""

    def __init__(
        self,
        redis_client: redis.Redis,
        db_session: AsyncSession,
        ttl: int = 3600,
    ):
        self.redis = redis_client
        self.db_session = db_session
        self.ttl = ttl

    async def create_session(
        self, session_id: str, user_id: str
    ) -> SessionContext:
        """Create a new session."""
        context = SessionContext(session_id=session_id, user_id=user_id)
        await self._save_to_redis(context)

        logger.info(
            "session_created",
            session_id=session_id,
            user_id=user_id,
        )

        return context

    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session from Redis."""
        try:
            data = await self.redis.get(f"session:{session_id}")
            if data:
                context = SessionContext.from_dict(json.loads(data))
                logger.debug("session_retrieved", session_id=session_id)
                return context

            logger.warning("session_not_found", session_id=session_id)
            return None

        except Exception as e:
            logger.error(
                "session_retrieval_error",
                session_id=session_id,
                error=str(e),
            )
            return None

    async def update_session(
        self,
        session_id: str,
        agent_name: Optional[str] = None,
        context_variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[SessionContext]:
        """Update session context."""
        context = await self.get_session(session_id)
        if not context:
            logger.warning("session_not_found_for_update", session_id=session_id)
            return None

        if agent_name:
            context.agent_chain.append(agent_name)

        if context_variables:
            context.context_variables.update(context_variables)

        context.updated_at = datetime.utcnow()
        await self._save_to_redis(context)

        logger.info(
            "session_updated",
            session_id=session_id,
            agent=agent_name,
        )

        return context

    async def _save_to_redis(self, context: SessionContext):
        """Save session to Redis with TTL."""
        key = f"session:{context.session_id}"
        value = json.dumps(context.to_dict())
        await self.redis.setex(key, self.ttl, value)

    async def save_conversation(
        self,
        session_id: str,
        user_id: str,
        agent_name: str,
        user_message: str,
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Save conversation to PostgreSQL for history."""
        try:
            conversation = ConversationHistory(
                session_id=session_id,
                user_id=user_id,
                agent_name=agent_name,
                user_message=user_message,
                agent_response=agent_response,
                metadata=metadata or {},
            )

            self.db_session.add(conversation)
            await self.db_session.commit()

            logger.info(
                "conversation_saved",
                session_id=session_id,
                agent=agent_name,
            )

        except Exception as e:
            await self.db_session.rollback()
            logger.error(
                "conversation_save_error",
                session_id=session_id,
                error=str(e),
            )

    async def get_conversation_history(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get conversation history from PostgreSQL."""
        try:
            result = await self.db_session.execute(
                select(ConversationHistory)
                .where(ConversationHistory.session_id == session_id)
                .order_by(ConversationHistory.created_at.desc())
                .limit(limit)
            )

            conversations = result.scalars().all()

            history = [
                {
                    "agent_name": conv.agent_name,
                    "user_message": conv.user_message,
                    "agent_response": conv.agent_response,
                    "created_at": conv.created_at.isoformat(),
                    "metadata": conv.metadata,
                }
                for conv in reversed(conversations)
            ]

            logger.info(
                "conversation_history_retrieved",
                session_id=session_id,
                count=len(history),
            )

            return history

        except Exception as e:
            logger.error(
                "conversation_history_error",
                session_id=session_id,
                error=str(e),
            )
            return []

    async def delete_session(self, session_id: str):
        """Delete session from Redis."""
        try:
            await self.redis.delete(f"session:{session_id}")
            logger.info("session_deleted", session_id=session_id)
        except Exception as e:
            logger.error(
                "session_deletion_error",
                session_id=session_id,
                error=str(e),
            )

    async def extend_session(self, session_id: str):
        """Extend session TTL."""
        try:
            key = f"session:{session_id}"
            await self.redis.expire(key, self.ttl)
            logger.debug("session_ttl_extended", session_id=session_id)
        except Exception as e:
            logger.error(
                "session_ttl_extension_error",
                session_id=session_id,
                error=str(e),
            )
