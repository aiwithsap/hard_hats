"""User repository."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User, UserRole
from .base import TenantRepository


class UserRepository(TenantRepository[User]):
    """Repository for user operations within a tenant."""

    model = User

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email within the organization."""
        query = self._base_query().where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_role(self, role: UserRole) -> List[User]:
        """Get all users with a specific role."""
        query = self._base_query().where(User.role == role)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_users(self) -> List[User]:
        """Get all active users."""
        query = self._base_query().where(User.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_last_login(self, user_id: UUID) -> bool:
        """Update user's last login timestamp."""
        user = await self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            await self.session.flush()
            return True
        return False

    async def email_exists(
        self, email: str, exclude_id: Optional[UUID] = None
    ) -> bool:
        """Check if email exists within the organization."""
        query = (
            select(func.count())
            .select_from(User)
            .where(User.organization_id == self.organization_id)
            .where(User.email == email)
        )
        if exclude_id:
            query = query.where(User.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one() > 0


class GlobalUserRepository:
    """Repository for cross-organization user lookups (auth only)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email_global(self, email: str) -> Optional[User]:
        """Get user by email across all organizations (for login)."""
        query = select(User).where(User.email == email).where(User.is_active == True)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_global(self, user_id: UUID) -> Optional[User]:
        """Get user by ID across all organizations."""
        query = select(User).where(User.id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
