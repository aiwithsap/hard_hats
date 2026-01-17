"""Camera repository."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Camera, CameraStatus
from .base import TenantRepository


class CameraRepository(TenantRepository[Camera]):
    """Repository for camera operations within a tenant."""

    model = Camera

    async def get_active_cameras(self) -> List[Camera]:
        """Get all active cameras."""
        query = self._base_query().where(Camera.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: CameraStatus) -> List[Camera]:
        """Get cameras by status."""
        query = self._base_query().where(Camera.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_zone(self, zone: str) -> List[Camera]:
        """Get cameras in a specific zone."""
        query = self._base_query().where(Camera.zone == zone)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        camera_id: UUID,
        status: CameraStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update camera status."""
        camera = await self.get_by_id(camera_id)
        if camera:
            camera.status = status
            camera.error_message = error_message
            camera.last_seen = datetime.utcnow()
            await self.session.flush()
            return True
        return False

    async def update_last_seen(self, camera_id: UUID) -> bool:
        """Update camera last seen timestamp."""
        camera = await self.get_by_id(camera_id)
        if camera:
            camera.last_seen = datetime.utcnow()
            await self.session.flush()
            return True
        return False


class GlobalCameraRepository:
    """Repository for cross-organization camera lookups (worker only)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_cameras(self) -> List[Camera]:
        """Get all active cameras across all organizations (for worker)."""
        query = (
            select(Camera)
            .where(Camera.is_active == True)
            .order_by(Camera.organization_id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_id_global(self, camera_id: UUID) -> Optional[Camera]:
        """Get camera by ID across all organizations."""
        query = select(Camera).where(Camera.id == camera_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        camera_id: UUID,
        status: CameraStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update camera status (worker use)."""
        camera = await self.get_by_id_global(camera_id)
        if camera:
            camera.status = status
            camera.error_message = error_message
            camera.last_seen = datetime.utcnow()
            await self.session.flush()
            return True
        return False
