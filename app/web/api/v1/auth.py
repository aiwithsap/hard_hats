"""Authentication API endpoints."""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.models import Organization, User, UserRole
from ....shared.db.repositories.organizations import OrganizationRepository
from ....shared.db.repositories.users import GlobalUserRepository, UserRepository
from ....shared.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
)
from ...auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from ...auth.dependencies import AuthContext
from ...auth.jwt import get_token_expiry_seconds
from ...config import config

router = APIRouter()


def create_slug(name: str) -> str:
    """Create a URL-friendly slug from organization name."""
    # Convert to lowercase, replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:50]  # Limit length


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the authentication cookie on response."""
    response.set_cookie(
        key=config.COOKIE_NAME,
        value=token,
        httponly=config.COOKIE_HTTPONLY,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        max_age=get_token_expiry_seconds(),
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie."""
    response.delete_cookie(
        key=config.COOKIE_NAME,
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Register a new organization and admin user.

    Creates a new organization with the given name and a user with admin role.
    Sets authentication cookie on success.
    """
    if not config.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled",
        )

    org_repo = OrganizationRepository(db)
    user_repo = GlobalUserRepository(db)

    # Check if email already exists
    existing_user = await user_repo.get_by_email_global(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create slug and check uniqueness
    base_slug = create_slug(request.organization_name)
    slug = base_slug
    counter = 1
    while await org_repo.slug_exists(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create organization
    org = Organization(
        name=request.organization_name,
        slug=slug,
        max_cameras=config.MAX_CAMERAS_DEFAULT,
        max_users=config.MAX_USERS_DEFAULT,
    )
    org = await org_repo.create(org)

    # Create admin user
    user = User(
        organization_id=org.id,
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Create token and set cookie
    token = create_access_token(
        user_id=user.id,
        organization_id=org.id,
        role=user.role.value,
    )
    set_auth_cookie(response, token)

    return UserResponse.model_validate(user)


@router.post("/login", response_model=UserResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Login with email and password.

    Sets authentication cookie on success.
    """
    user_repo = GlobalUserRepository(db)

    # Find user by email
    user = await user_repo.get_by_email_global(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.flush()

    # Create token and set cookie
    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role.value,
    )
    set_auth_cookie(response, token)

    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(response: Response):
    """
    Logout by clearing the authentication cookie.
    """
    clear_auth_cookie(response)
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    auth: AuthContext = Depends(get_current_user),
):
    """
    Refresh the authentication token.

    Requires a valid existing token.
    """
    token = create_access_token(
        user_id=auth.user_id,
        organization_id=auth.organization_id,
        role=auth.role.value,
    )
    set_auth_cookie(response, token)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=get_token_expiry_seconds(),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    auth: AuthContext = Depends(get_current_user),
):
    """
    Get current authenticated user.
    """
    return UserResponse.model_validate(auth.user)


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Change current user's password.
    """
    # Verify current password
    if not verify_password(request.current_password, auth.user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    auth.user.password_hash = hash_password(request.new_password)
    await db.flush()

    return {"message": "Password changed successfully"}
