"""Organization repository."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Organization


class OrganizationRepository:
    """Repository for organization operations (not tenant-scoped)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[Organization]:
        """Get organization by ID."""
        query = select(Organization).where(Organization.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug."""
        query = select(Organization).where(Organization.slug == slug)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, organization: Organization) -> Organization:
        """Create a new organization."""
        self.session.add(organization)
        await self.session.flush()
        await self.session.refresh(organization)
        return organization

    async def update(self, organization: Organization) -> Organization:
        """Update an organization."""
        await self.session.flush()
        await self.session.refresh(organization)
        return organization

    async def slug_exists(self, slug: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if slug already exists."""
        query = select(Organization.id).where(Organization.slug == slug)
        if exclude_id:
            query = query.where(Organization.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_camera_count(self, org_id: UUID) -> int:
        """Get count of cameras for organization."""
        from ..models import Camera
        from sqlalchemy import func

        query = (
            select(func.count())
            .select_from(Camera)
            .where(Camera.organization_id == org_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_user_count(self, org_id: UUID) -> int:
        """Get count of users for organization."""
        from ..models import User
        from sqlalchemy import func

        query = (
            select(func.count())
            .select_from(User)
            .where(User.organization_id == org_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()
