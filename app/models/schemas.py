"""Pydantic schemas for API request/response validation."""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# Camera schemas
class CameraResponse(BaseModel):
    """Camera details response."""
    id: str
    name: str
    zone: str
    source: str
    position_x: float
    position_y: float
    status: str
    fps: float
    frame_count: int
    last_detection_count: int
    last_error: Optional[str] = None


class CameraListResponse(BaseModel):
    """List of cameras response."""
    cameras: List[CameraResponse]
    total: int
    active: int


# Event schemas
class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x1: int
    y1: int
    x2: int
    y2: int


class EventResponse(BaseModel):
    """Event details response."""
    id: str
    camera_id: str
    camera_name: str
    event_type: str
    violation_type: Optional[str] = None
    severity: str
    confidence: float
    bbox: Optional[List[int]] = None
    timestamp: datetime
    frame_number: int
    thumbnail_path: Optional[str] = None
    acknowledged: bool
    message: str


class EventListResponse(BaseModel):
    """List of events response."""
    events: List[EventResponse]
    total: int
    page: int = 1
    page_size: int = 50


class EventQuery(BaseModel):
    """Query parameters for events."""
    camera_id: Optional[str] = None
    event_type: Optional[str] = None
    violation_type: Optional[str] = None
    severity: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    acknowledged: Optional[bool] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# Stats schemas
class DailyStats(BaseModel):
    """Daily statistics."""
    date: str
    total_violations: int
    no_hardhat_count: int
    no_vest_count: int
    zone_breach_count: int


class StatsResponse(BaseModel):
    """Dashboard statistics response."""
    violations_today: int
    violations_change_percent: float  # vs yesterday
    active_cameras: int
    total_cameras: int
    ai_scanned: int
    ai_recognized: int
    daily_stats: List[DailyStats] = []


# Floor plan schemas
class CameraPosition(BaseModel):
    """Camera position on floor plan."""
    id: str
    name: str
    zone: str
    x: float  # 0-100 percentage
    y: float  # 0-100 percentage
    status: str


class FloorPlanResponse(BaseModel):
    """Floor plan with camera positions."""
    cameras: List[CameraPosition]
    floor_plan_url: Optional[str] = None


# Config schemas
class ConfigUpdate(BaseModel):
    """Configuration update request."""
    mode: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    zone_polygon: Optional[List[List[int]]] = None


class ConfigResponse(BaseModel):
    """Current configuration response."""
    mode: str
    confidence: float
    zone_polygon: Optional[List[List[int]]] = None
    demo_mode: bool = False
