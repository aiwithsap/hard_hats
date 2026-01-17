"""Statistics API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.repositories.stats import StatsRepository
from ....shared.schemas.stats import (
    StatsSummaryResponse,
    DailyStatsResponse,
    DailyStatsItem,
    CameraStatsResponse,
    CameraStatsItem,
    ViolationBreakdownResponse,
)
from ...auth.dependencies import CurrentUser

router = APIRouter()


@router.get("/summary", response_model=StatsSummaryResponse)
async def get_stats_summary(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get summary statistics for the dashboard.
    """
    stats_repo = StatsRepository(db, auth.organization_id)

    violations_today = await stats_repo.get_violations_today()
    violations_yesterday = await stats_repo.get_violations_yesterday()
    active_cameras = await stats_repo.get_active_cameras_count()
    total_cameras = await stats_repo.get_total_cameras_count()

    # Calculate change percentage
    if violations_yesterday > 0:
        change_percent = ((violations_today - violations_yesterday) / violations_yesterday) * 100
    elif violations_today > 0:
        change_percent = 100.0
    else:
        change_percent = 0.0

    # TODO: Get actual frames processed from Redis/worker
    ai_scanned = 0

    return StatsSummaryResponse(
        violations_today=violations_today,
        violations_yesterday=violations_yesterday,
        violations_change_percent=round(change_percent, 1),
        active_cameras=active_cameras,
        total_cameras=total_cameras,
        ai_scanned=ai_scanned,
    )


@router.get("/daily", response_model=DailyStatsResponse)
async def get_daily_stats(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    days: int = Query(default=7, ge=1, le=90),
):
    """
    Get daily violation statistics for the past N days.
    """
    stats_repo = StatsRepository(db, auth.organization_id)
    stats = await stats_repo.get_daily_stats(days=days)

    return DailyStatsResponse(
        stats=[DailyStatsItem(**s) for s in stats],
        period_days=days,
    )


@router.get("/by-camera", response_model=CameraStatsResponse)
async def get_stats_by_camera(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get violation counts by camera for today.
    """
    stats_repo = StatsRepository(db, auth.organization_id)
    camera_stats = await stats_repo.get_stats_by_camera()

    return CameraStatsResponse(
        cameras=[CameraStatsItem(**s) for s in camera_stats],
    )


@router.get("/breakdown", response_model=ViolationBreakdownResponse)
async def get_violation_breakdown(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get breakdown of violations by type for today.
    """
    stats_repo = StatsRepository(db, auth.organization_id)
    breakdown = await stats_repo.get_violation_breakdown()

    return ViolationBreakdownResponse(
        no_hardhat=breakdown["no_hardhat"],
        no_vest=breakdown["no_vest"],
        zone_breach=breakdown["zone_breach"],
        total=sum(breakdown.values()),
    )
