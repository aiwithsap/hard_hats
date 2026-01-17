"""JWT token handling."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import jwt, JWTError

from ..config import config


class TokenData:
    """Parsed token data."""

    def __init__(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: str,
        exp: datetime,
    ):
        self.user_id = user_id
        self.organization_id = organization_id
        self.role = role
        self.exp = exp

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.exp


def create_access_token(
    user_id: UUID,
    organization_id: UUID,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID
        organization_id: Organization's UUID
        role: User's role (admin, manager, operator)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            config.SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM],
        )

        user_id = payload.get("sub")
        organization_id = payload.get("org")
        role = payload.get("role")
        exp = payload.get("exp")

        if not all([user_id, organization_id, role, exp]):
            return None

        return TokenData(
            user_id=UUID(user_id),
            organization_id=UUID(organization_id),
            role=role,
            exp=datetime.fromtimestamp(exp),
        )

    except (JWTError, ValueError):
        return None


def get_token_expiry_seconds() -> int:
    """Get token expiry time in seconds."""
    return config.JWT_EXPIRE_MINUTES * 60
