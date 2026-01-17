"""Organization schemas."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    """Organization response schema."""
    id: UUID
    name: str
    slug: str
    plan: str
    max_cameras: int
    max_users: int
    settings: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime

    # Usage stats
    camera_count: int = 0
    user_count: int = 0

    class Config:
        from_attributes = True


class OrganizationUpdate(BaseModel):
    """Organization update request schema."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    settings: Optional[Dict[str, Any]] = None
