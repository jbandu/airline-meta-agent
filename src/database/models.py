"""Database models for PostgreSQL."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class ConversationHistory(Base):
    """Conversation history table."""

    __tablename__ = "conversation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False)
    user_message = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ConversationHistory(id={self.id}, session_id={self.session_id}, agent={self.agent_name})>"


class User(Base):
    """User table for authentication."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class AgentMetrics(Base):
    """Agent performance metrics table."""

    __tablename__ = "agent_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False)
    execution_time_ms = Column(Integer)
    success = Column(Integer, nullable=False)  # 1 for success, 0 for failure
    error_message = Column(Text)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<AgentMetrics(id={self.id}, agent={self.agent_name}, success={self.success})>"
