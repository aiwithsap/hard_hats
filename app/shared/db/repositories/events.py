"""Event repository."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, EventType, ViolationType, Severity
from .base import TenantRepository


class EventRepository(TenantRepository[Event]):
    """Repository for event operations within a tenant."""

    model = Event

    async def get_by_camera(
        self,
        camera_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Event], int]:
        """Get events for a specific camera."""
        # Count
        count_query = (
            select(func.count())
            .select_from(Event)
            .where(Event.organization_id == self.organization_id)
            .where(Event.camera_id == camera_id)
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Data
        query = (
            self._base_query()
            .where(Event.camera_id == camera_id)
            .order_by(Event.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        events = list(result.scalars().all())

        return events, total

    async def get_filtered(
        self,
        camera_id: Optional[UUID] = None,
        event_type: Optional[EventType] = None,
        violation_type: Optional[ViolationType] = None,
        severity: Optional[Severity] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Event], int]:
        """Get events with filters."""
        conditions = [Event.organization_id == self.organization_id]

        if camera_id:
            conditions.append(Event.camera_id == camera_id)
        if event_type:
            conditions.append(Event.event_type == event_type)
        if violation_type:
            conditions.append(Event.violation_type == violation_type)
        if severity:
            conditions.append(Event.severity == severity)
        if since:
            conditions.append(Event.timestamp >= since)
        if until:
            conditions.append(Event.timestamp <= until)
        if acknowledged is not None:
            conditions.append(Event.acknowledged == acknowledged)

        # Count
        count_query = (
            select(func.count())
            .select_from(Event)
            .where(and_(*conditions))
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Data
        query = (
            select(Event)
            .where(and_(*conditions))
            .order_by(Event.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        events = list(result.scalars().all())

        return events, total

    async def get_recent(self, limit: int = 10) -> List[Event]:
        """Get most recent events."""
        query = (
            self._base_query()
            .order_by(Event.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_unacknowledged(self, limit: int = 50) -> List[Event]:
        """Get unacknowledged events."""
        query = (
            self._base_query()
            .where(Event.acknowledged == False)
            .order_by(Event.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def acknowledge(
        self,
        event_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Acknowledge an event."""
        event = await self.get_by_id(event_id)
        if event:
            event.acknowledged = True
            event.acknowledged_by = user_id
            event.acknowledged_at = datetime.utcnow()
            await self.session.flush()
            return True
        return False

    async def acknowledge_all(self, user_id: UUID) -> int:
        """Acknowledge all unacknowledged events."""
        events = await self.get_unacknowledged(limit=1000)
        count = 0
        for event in events:
            event.acknowledged = True
            event.acknowledged_by = user_id
            event.acknowledged_at = datetime.utcnow()
            count += 1
        await self.session.flush()
        return count

    async def cleanup_old(self, days: int = 30) -> int:
        """Delete events older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = (
            delete(Event)
            .where(Event.organization_id == self.organization_id)
            .where(Event.timestamp < cutoff)
        )
        result = await self.session.execute(query)
        return result.rowcount

    async def count_today(self) -> int:
        """Count violations today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = (
            select(func.count())
            .select_from(Event)
            .where(Event.organization_id == self.organization_id)
            .where(Event.event_type.in_([EventType.PPE_VIOLATION, EventType.ZONE_VIOLATION]))
            .where(Event.timestamp >= today_start)
        )
        result = await self.session.execute(query)
        return result.scalar_one()


class GlobalEventRepository:
    """Repository for cross-organization event creation (worker only)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: Event) -> Event:
        """Create an event (worker use)."""
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def create_event(self, event_data: dict) -> Event:
        """Create an event from a dictionary (worker use)."""
        from datetime import datetime

        event = Event(
            id=event_data["id"],
            organization_id=event_data["organization_id"],
            camera_id=event_data["camera_id"],
            event_type=event_data["event_type"],
            violation_type=event_data.get("violation_type"),
            severity=event_data["severity"],
            confidence=event_data["confidence"],
            bbox_x1=event_data.get("bbox_x1"),
            bbox_y1=event_data.get("bbox_y1"),
            bbox_x2=event_data.get("bbox_x2"),
            bbox_y2=event_data.get("bbox_y2"),
            thumbnail_path=event_data.get("thumbnail_path"),
            timestamp=datetime.utcnow(),
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event
