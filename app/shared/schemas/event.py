"""Event schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class EventResponse(BaseModel):
    """Event response schema."""
    id: UUID
    camera_id: UUID
    camera_name: str  # Denormalized for convenience

    event_type: str
    violation_type: Optional[str] = None
    severity: str
    confidence: float

    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    thumbnail_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    frame_number: int

    acknowledged: bool
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None

    timestamp: datetime
    message: str  # Human-readable message

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Event list response schema."""
    events: List[EventResponse]
    total: int
    page: int
    page_size: int


class EventFilterParams(BaseModel):
    """Event filter parameters."""
    camera_id: Optional[UUID] = None
    event_type: Optional[str] = Field(None, pattern="^(violation|detection|status)$")
    violation_type: Optional[str] = Field(
        None, pattern="^(no_hardhat|no_vest|zone_breach)$"
    )
    severity: Optional[str] = Field(None, pattern="^(critical|warning|info)$")
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    acknowledged: Optional[bool] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AcknowledgeRequest(BaseModel):
    """Acknowledge event request schema."""
    event_ids: Optional[List[UUID]] = None  # If None, acknowledge all
