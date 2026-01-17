"""Statistics schemas."""

from typing import List, Dict
from pydantic import BaseModel


class StatsSummaryResponse(BaseModel):
    """Summary statistics response schema."""
    violations_today: int
    violations_yesterday: int
    violations_change_percent: float
    active_cameras: int
    total_cameras: int
    ai_scanned: int  # Total frames processed


class DailyStatsItem(BaseModel):
    """Single day statistics."""
    date: str
    total_violations: int
    no_hardhat_count: int
    no_vest_count: int
    zone_breach_count: int
    frames_processed: int


class DailyStatsResponse(BaseModel):
    """Daily statistics response schema."""
    stats: List[DailyStatsItem]
    period_days: int


class CameraStatsItem(BaseModel):
    """Statistics for a single camera."""
    camera_id: str
    camera_name: str
    violation_count: int


class CameraStatsResponse(BaseModel):
    """Statistics by camera response schema."""
    cameras: List[CameraStatsItem]


class ViolationBreakdownResponse(BaseModel):
    """Violation breakdown response schema."""
    no_hardhat: int
    no_vest: int
    zone_breach: int
    total: int
