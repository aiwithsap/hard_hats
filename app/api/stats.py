"""Statistics API endpoints."""

from fastapi import APIRouter

from ..models.schemas import StatsResponse, DailyStats
from ..db.repositories import StatsRepository
from ..core.camera_manager import get_camera_manager
from ..core.event_processor import get_event_processor

router = APIRouter()


@router.get("/stats/summary", response_model=StatsResponse)
async def get_stats_summary():
    """Get dashboard statistics summary."""
    stats_repo = StatsRepository()
    manager = get_camera_manager()
    processor = get_event_processor()

    # Get violation counts
    violations_today = stats_repo.get_violations_today()
    violations_yesterday = stats_repo.get_violations_yesterday()

    # Calculate change percentage
    if violations_yesterday > 0:
        change_percent = ((violations_today - violations_yesterday) / violations_yesterday) * 100
    else:
        change_percent = 100.0 if violations_today > 0 else 0.0

    # Get camera counts
    cameras = manager.get_cameras()
    total_cameras = len(cameras)
    active_cameras = manager.get_active_count()

    # AI metrics (mock data for demo)
    ai_scanned = sum(c.frame_count for c in cameras)
    ai_recognized = int(ai_scanned * 0.85)  # ~85% recognition rate

    # Get daily stats for chart
    daily_stats = stats_repo.get_daily_stats(days=7)

    return StatsResponse(
        violations_today=violations_today,
        violations_change_percent=round(change_percent, 1),
        active_cameras=active_cameras,
        total_cameras=total_cameras,
        ai_scanned=ai_scanned,
        ai_recognized=ai_recognized,
        daily_stats=[DailyStats(**s) for s in daily_stats],
    )


@router.get("/stats/by-camera")
async def get_stats_by_camera():
    """Get violation statistics grouped by camera."""
    stats_repo = StatsRepository()
    stats = stats_repo.get_stats_by_camera()

    return {
        "stats": stats,
        "count": len(stats),
    }
