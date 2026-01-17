"""User management API endpoints (admin only)."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.models import User, UserRole
from ....shared.db.repositories.users import UserRepository
from ....shared.db.repositories.organizations import OrganizationRepository
from ....shared.schemas.auth import (
    UserResponse,
    UserCreateRequest,
    UserUpdateRequest,
)
from ...auth import hash_password
from ...auth.dependencies import AdminUser

router = APIRouter()


@router.get("", response_model=List[UserResponse])
async def list_users(
    auth: AdminUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all users in the organization (admin only).
    """
    user_repo = UserRepository(db, auth.organization_id)
    users, _ = await user_repo.get_all(limit=1000)
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    auth: AdminUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new user in the organization (admin only).
    """
    user_repo = UserRepository(db, auth.organization_id)
    org_repo = OrganizationRepository(db)

    # Check email uniqueness within org
    if await user_repo.email_exists(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists in this organization",
        )

    # Check user limit
    org = await org_repo.get_by_id(auth.organization_id)
    user_count = await org_repo.get_user_count(auth.organization_id)
    if user_count >= org.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User limit reached ({org.max_users}). Upgrade your plan.",
        )

    # Create user
    user = User(
        organization_id=auth.organization_id,
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role=UserRole(request.role),
    )
    user = await user_repo.create(user)

    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    auth: AdminUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a user by ID (admin only).
    """
    user_repo = UserRepository(db, auth.organization_id)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    auth: AdminUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update a user (admin only).
    """
    user_repo = UserRepository(db, auth.organization_id)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent demoting yourself
    if user_id == auth.user_id and request.role and request.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    # Update fields
    if request.full_name is not None:
        user.full_name = request.full_name
    if request.role is not None:
        user.role = UserRole(request.role)
    if request.is_active is not None:
        # Prevent deactivating yourself
        if user_id == auth.user_id and not request.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )
        user.is_active = request.is_active

    await user_repo.update(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    auth: AdminUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete a user (admin only).
    """
    # Prevent deleting yourself
    if user_id == auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    user_repo = UserRepository(db, auth.organization_id)
    deleted = await user_repo.delete(user_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
