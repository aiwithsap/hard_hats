"""Base repository with tenant filtering."""

from typing import TypeVar, Generic, Optional, List, Type
from uuid import UUID

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Base

T = TypeVar("T", bound=Base)


class TenantRepository(Generic[T]):
    """
    Base repository that automatically filters by organization_id.

    All queries are scoped to the current tenant (organization).
    """

    model: Type[T]

    def __init__(self, session: AsyncSession, organization_id: UUID):
        self.session = session
        self.organization_id = organization_id

    def _base_query(self):
        """Get base query filtered by organization."""
        return select(self.model).where(
            self.model.organization_id == self.organization_id
        )

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get entity by ID within the tenant."""
        query = self._base_query().where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[T], int]:
        """Get all entities with pagination."""
        # Get total count
        count_query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.organization_id == self.organization_id)
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = self._base_query().limit(limit).offset(offset)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        entity.organization_id = self.organization_id
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID."""
        query = (
            delete(self.model)
            .where(self.model.id == id)
            .where(self.model.organization_id == self.organization_id)
        )
        result = await self.session.execute(query)
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        """Check if entity exists."""
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.id == id)
            .where(self.model.organization_id == self.organization_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one() > 0

    async def count(self) -> int:
        """Get total count of entities."""
        query = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.organization_id == self.organization_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()
