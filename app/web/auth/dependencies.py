"""FastAPI authentication dependencies."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.db import get_db_session
from ...shared.db.models import User, UserRole
from ...shared.db.repositories.users import GlobalUserRepository
from ..config import config
from .jwt import decode_token, TokenData


class AuthContext:
    """Authentication context with user and organization info."""

    def __init__(self, user: User, token_data: TokenData):
        self.user = user
        self.token_data = token_data

    @property
    def user_id(self) -> UUID:
        return self.user.id

    @property
    def organization_id(self) -> UUID:
        return self.user.organization_id

    @property
    def role(self) -> UserRole:
        return self.user.role

    @property
    def is_admin(self) -> bool:
        return self.user.role == UserRole.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.user.role in (UserRole.ADMIN, UserRole.MANAGER)


async def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract token from HTTP-only cookie."""
    return request.cookies.get(config.COOKIE_NAME)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """
    Get current authenticated user from cookie.

    This is the main authentication dependency for protected routes.

    Raises:
        HTTPException 401: If not authenticated or token invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Get token from cookie
    token = await get_token_from_cookie(request)
    if not token:
        raise credentials_exception

    # Decode token
    token_data = decode_token(token)
    if not token_data:
        raise credentials_exception

    # Check expiry
    if token_data.is_expired:
        raise credentials_exception

    # Get user from database
    user_repo = GlobalUserRepository(db)
    user = await user_repo.get_by_id_global(token_data.user_id)

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Verify organization matches
    if user.organization_id != token_data.organization_id:
        raise credentials_exception

    return AuthContext(user, token_data)


async def get_current_active_user(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    """Alias for get_current_user (user is always active if returned)."""
    return auth


async def require_admin(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    """
    Require admin role.

    Raises:
        HTTPException 403: If user is not an admin
    """
    if not auth.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return auth


async def require_manager(
    auth: AuthContext = Depends(get_current_user),
) -> AuthContext:
    """
    Require manager or admin role.

    Raises:
        HTTPException 403: If user is not a manager or admin
    """
    if not auth.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return auth


async def get_organization_id(
    auth: AuthContext = Depends(get_current_user),
) -> UUID:
    """Get organization ID from authenticated user."""
    return auth.organization_id


# Type aliases for cleaner route signatures
CurrentUser = Annotated[AuthContext, Depends(get_current_user)]
AdminUser = Annotated[AuthContext, Depends(require_admin)]
ManagerUser = Annotated[AuthContext, Depends(require_manager)]
OrgId = Annotated[UUID, Depends(get_organization_id)]
