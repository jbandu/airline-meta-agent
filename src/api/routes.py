"""API routes and endpoints."""

import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.database.models import User
from src.auth.jwt_handler import JWTHandler
from src.auth.dependencies import get_current_active_user
from src.api.main import get_app_state

logger = structlog.get_logger()
security = HTTPBearer()
router = APIRouter()


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message to process")
    session_id: Optional[str] = Field(None, description="Session ID for context continuity")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    agents_used: list[str]
    intent: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response model."""
    session_id: str
    user_id: str
    agent_chain: list[str]
    context_variables: Dict[str, Any]


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class RegisterRequest(BaseModel):
    """User registration request."""
    username: str
    email: str
    password: str


class AgentHealthResponse(BaseModel):
    """Agent health response."""
    agent_name: str
    domain: str
    status: str
    capabilities: list[str]


# Authentication Endpoints
@router.post("/auth/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    app_state=Depends(get_app_state),
):
    """Register a new user."""
    db_session = await anext(app_state.db.get_session())

    try:
        # Check if user exists
        result = await db_session.execute(
            select(User).where(User.username == request.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )

        # Check if email exists
        result = await db_session.execute(
            select(User).where(User.email == request.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create user
        hashed_password = JWTHandler.hash_password(request.password)
        user = User(
            username=request.username,
            email=request.email,
            hashed_password=hashed_password,
        )

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Generate token
        token = app_state.jwt_handler.create_access_token(
            data={"sub": user.username, "user_id": str(user.id)}
        )

        logger.info("user_registered", username=user.username, user_id=str(user.id))

        return LoginResponse(
            access_token=token,
            user_id=str(user.id),
            username=user.username,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db_session.rollback()
        logger.error("registration_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    app_state=Depends(get_app_state),
):
    """Authenticate user and return JWT token."""
    db_session = await anext(app_state.db.get_session())

    try:
        # Get user
        result = await db_session.execute(
            select(User).where(User.username == request.username)
        )
        user = result.scalar_one_or_none()

        if not user or not JWTHandler.verify_password(request.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )

        # Generate token
        token = app_state.jwt_handler.create_access_token(
            data={"sub": user.username, "user_id": str(user.id)}
        )

        logger.info("user_logged_in", username=user.username, user_id=str(user.id))

        return LoginResponse(
            access_token=token,
            user_id=str(user.id),
            username=user.username,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("login_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


# Chat Endpoints
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """Process chat message through agent orchestrator."""
    try:
        # Create or get session
        session_id = request.session_id or str(uuid.uuid4())

        # Get or create session context
        session = await app_state.context_manager.get_session(session_id)
        if not session:
            session = await app_state.context_manager.create_session(
                session_id=session_id,
                user_id=str(current_user.id),
            )

        # Route request through agents
        result = await app_state.router.route_request(
            session_id=session_id,
            user_id=str(current_user.id),
            message=request.message,
            context=request.context,
        )

        logger.info(
            "chat_processed",
            session_id=session_id,
            user_id=str(current_user.id),
            success=result.get("success", False),
        )

        return ChatResponse(
            session_id=session_id,
            success=result.get("success", False),
            message=result.get("message", ""),
            data=result.get("data"),
            agents_used=result.get("agents_used", []),
            intent=result.get("intent"),
        )

    except Exception as e:
        logger.error("chat_processing_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Session Endpoints
@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """Get session information."""
    session = await app_state.context_manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Verify session belongs to user
    if session.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return SessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        agent_chain=session.agent_chain,
        context_variables=session.context_variables,
    )


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """Get session conversation history."""
    history = await app_state.context_manager.get_conversation_history(
        session_id=session_id,
        limit=limit,
    )

    return {
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """Delete a session."""
    session = await app_state.context_manager.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Verify session belongs to user
    if session.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    await app_state.context_manager.delete_session(session_id)

    return {"message": "Session deleted successfully"}


# Agent Management Endpoints
@router.get("/agents")
async def list_agents(
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """List all registered agents."""
    agents = app_state.registry.get_all_agents()

    return {
        "agents": [
            {
                "name": agent.metadata.name,
                "domain": agent.metadata.domain,
                "capabilities": agent.metadata.capabilities,
                "status": agent.metadata.status,
                "description": agent.metadata.description,
            }
            for agent in agents
        ],
        "count": len(agents),
    }


@router.get("/agents/domains")
async def list_domains(
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """List all agent domains."""
    domains = app_state.registry.list_domains()
    return {"domains": domains}


@router.get("/agents/capabilities")
async def list_capabilities(
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """List all agent capabilities."""
    capabilities = app_state.registry.list_capabilities()
    return {"capabilities": capabilities}


@router.get("/agents/{agent_name}/health", response_model=AgentHealthResponse)
async def check_agent_health(
    agent_name: str,
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """Check health of a specific agent."""
    agent = app_state.registry.get_agent(agent_name)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    is_healthy = await agent.health_check()

    return AgentHealthResponse(
        agent_name=agent.metadata.name,
        domain=agent.metadata.domain,
        status=agent.metadata.status,
        capabilities=agent.metadata.capabilities,
    )


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_active_user),
    app_state=Depends(get_app_state),
):
    """Get orchestrator statistics."""
    stats = app_state.registry.get_registry_stats()

    return {
        "registry": stats,
        "environment": "production",
    }
