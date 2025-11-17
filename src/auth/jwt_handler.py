"""JWT token handling."""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    """Token data model."""
    username: Optional[str] = None
    user_id: Optional[str] = None


class JWTHandler:
    """Handle JWT token creation and validation."""

    def __init__(self, secret_key: str, algorithm: str = "HS256", expiration_minutes: int = 60):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expiration_minutes = expiration_minutes

    def create_access_token(self, data: dict) -> str:
        """
        Create JWT access token.

        Args:
            data: Data to encode in the token

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.expiration_minutes)
        to_encode.update({"exp": expire})

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        logger.info("jwt_token_created", username=data.get("sub"))

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[TokenData]:
        """
        Verify JWT token.

        Args:
            token: JWT token to verify

        Returns:
            TokenData if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")

            if username is None:
                logger.warning("jwt_verification_failed", reason="missing_username")
                return None

            return TokenData(username=username, user_id=user_id)

        except JWTError as e:
            logger.error("jwt_verification_error", error=str(e))
            return None

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password."""
        return pwd_context.hash(password)
