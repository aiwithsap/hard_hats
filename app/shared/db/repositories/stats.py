"""Statistics repository."""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, date

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, EventType, ViolationType, DailyStat, Camera, CameraStatus


class StatsRepository:
    """Repository for statistics operations within a tenant."""

    def __init__(self, session: AsyncSession, organization_id: UUID):
        self.session = session
        self.organization_id = organization_id

    async def get_violations_today(self) -> int:
        """Get count of violations today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = (
            select(func.count())
            .select_from(Event)
            .where(Event.organization_id == self.organization_id)
            .where(or_(
                Event.event_type == EventType.PPE_VIOLATION,
                Event.event_type == EventType.ZONE_VIOLATION
            ))
            .where(Event.timestamp >= today_start)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_violations_yesterday(self) -> int:
        """Get count of violations yesterday."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        query = (
            select(func.count())
            .select_from(Event)
            .where(Event.organization_id == self.organization_id)
            .where(or_(
                Event.event_type == EventType.PPE_VIOLATION,
                Event.event_type == EventType.ZONE_VIOLATION
            ))
            .where(Event.timestamp >= yesterday_start)
            .where(Event.timestamp < today_start)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_active_cameras_count(self) -> int:
        """Get count of active (online) cameras."""
        query = (
            select(func.count())
            .select_from(Camera)
            .where(Camera.organization_id == self.organization_id)
            .where(Camera.status == CameraStatus.online)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_total_cameras_count(self) -> int:
        """Get total count of cameras."""
        query = (
            select(func.count())
            .select_from(Camera)
            .where(Camera.organization_id == self.organization_id)
            .where(Camera.is_active == True)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_daily_stats(self, days: int = 7) -> List[dict]:
        """Get daily violation statistics."""
        since = datetime.utcnow().date() - timedelta(days=days)
        query = (
            select(DailyStat)
            .where(DailyStat.organization_id == self.organization_id)
            .where(DailyStat.date >= since)
            .where(DailyStat.camera_id == None)  # Org-level stats
            .order_by(DailyStat.date)
        )
        result = await self.session.execute(query)
        stats = list(result.scalars().all())

        return [
            {
                "date": str(s.date),
                "total_violations": s.total_violations,
                "no_hardhat_count": s.no_hardhat_count,
                "no_vest_count": s.no_vest_count,
                "zone_breach_count": s.zone_breach_count,
                "frames_processed": s.frames_processed,
            }
            for s in stats
        ]

    async def get_stats_by_camera(self) -> List[dict]:
        """Get violation counts by camera for today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = (
            select(
                Camera.id,
                Camera.name,
                func.count(Event.id).label("violation_count"),
            )
            .join(Event, Event.camera_id == Camera.id, isouter=True)
            .where(Camera.organization_id == self.organization_id)
            .where(
                (Event.timestamp >= today_start) | (Event.id == None)
            )
            .group_by(Camera.id, Camera.name)
            .order_by(func.count(Event.id).desc())
        )
        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "camera_id": str(row.id),
                "camera_name": row.name,
                "violation_count": row.violation_count or 0,
            }
            for row in rows
        ]

    async def get_violation_breakdown(self) -> dict:
        """Get breakdown of violations by type for today."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = (
            select(
                Event.violation_type,
                func.count(Event.id).label("count"),
            )
            .where(Event.organization_id == self.organization_id)
            .where(or_(
                Event.event_type == EventType.PPE_VIOLATION,
                Event.event_type == EventType.ZONE_VIOLATION
            ))
            .where(Event.timestamp >= today_start)
            .group_by(Event.violation_type)
        )
        result = await self.session.execute(query)
        rows = result.all()

        breakdown = {
            "no_hardhat": 0,
            "no_vest": 0,
            "zone_breach": 0,
        }
        for row in rows:
            if row.violation_type:
                breakdown[row.violation_type.value] = row.count

        return breakdown

    async def upsert_daily_stat(
        self,
        stat_date: date,
        camera_id: Optional[UUID] = None,
        total_violations: int = 0,
        no_hardhat_count: int = 0,
        no_vest_count: int = 0,
        zone_breach_count: int = 0,
        frames_processed: int = 0,
    ) -> DailyStat:
        """Update or insert daily statistics."""
        # Try to find existing
        conditions = [
            DailyStat.organization_id == self.organization_id,
            DailyStat.date == stat_date,
        ]
        if camera_id:
            conditions.append(DailyStat.camera_id == camera_id)
        else:
            conditions.append(DailyStat.camera_id == None)

        query = select(DailyStat).where(and_(*conditions))
        result = await self.session.execute(query)
        stat = result.scalar_one_or_none()

        if stat:
            stat.total_violations += total_violations
            stat.no_hardhat_count += no_hardhat_count
            stat.no_vest_count += no_vest_count
            stat.zone_breach_count += zone_breach_count
            stat.frames_processed += frames_processed
        else:
            stat = DailyStat(
                organization_id=self.organization_id,
                camera_id=camera_id,
                date=stat_date,
                total_violations=total_violations,
                no_hardhat_count=no_hardhat_count,
                no_vest_count=no_vest_count,
                zone_breach_count=zone_breach_count,
                frames_processed=frames_processed,
            )
            self.session.add(stat)

        await self.session.flush()
        return stat
