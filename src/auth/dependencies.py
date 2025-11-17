"""Authentication dependencies for FastAPI."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from src.auth.jwt_handler import JWTHandler, TokenData
from src.database.models import User
from src.database.connection import Database

logger = structlog.get_logger()

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    jwt_handler: JWTHandler = Depends(),
    db: AsyncSession = Depends(),
) -> User:
    """
    Get current authenticated user.

    Args:
        credentials: HTTP authorization credentials
        jwt_handler: JWT handler instance
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    token_data = jwt_handler.verify_token(token)

    if token_data is None or token_data.username is None:
        logger.warning("authentication_failed", reason="invalid_token")
        raise credentials_exception

    # Get user from database
    result = await db.execute(
        select(User).where(User.username == token_data.username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("authentication_failed", reason="user_not_found", username=token_data.username)
        raise credentials_exception

    if not user.is_active:
        logger.warning("authentication_failed", reason="inactive_user", username=token_data.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    logger.info("user_authenticated", username=user.username, user_id=str(user.id))

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        User object

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
