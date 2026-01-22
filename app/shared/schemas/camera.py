"""Camera schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    """Create camera request schema."""
    name: str = Field(..., min_length=1, max_length=255)
    zone: str = Field(default="Common", max_length=100)

    # Source configuration
    source_type: str = Field(default="file", pattern="^(rtsp|file)$")
    rtsp_url: Optional[str] = None
    rtsp_username: Optional[str] = None  # Encrypted before storage
    rtsp_password: Optional[str] = None  # Encrypted before storage
    placeholder_video: Optional[str] = None
    use_placeholder: bool = False

    # Processing settings
    inference_width: int = Field(default=640, ge=320, le=1920)
    inference_height: int = Field(default=640, ge=320, le=1920)
    target_fps: float = Field(default=0.5, ge=0.1, le=5.0)
    confidence_threshold: float = Field(default=0.25, ge=0.1, le=1.0)

    # Floor plan position
    position_x: float = Field(default=50.0, ge=0, le=100)
    position_y: float = Field(default=50.0, ge=0, le=100)

    # Detection mode
    detection_mode: str = Field(default="ppe", pattern="^(ppe|zone)$")
    zone_polygon: Optional[List[List[int]]] = None  # [[x,y], ...]

    # Inference control
    inference_enabled: bool = True


class CameraUpdate(BaseModel):
    """Update camera request schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    zone: Optional[str] = Field(None, max_length=100)

    # Source configuration
    source_type: Optional[str] = Field(None, pattern="^(rtsp|file)$")
    rtsp_url: Optional[str] = None
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None
    placeholder_video: Optional[str] = None
    use_placeholder: Optional[bool] = None

    # Processing settings
    inference_width: Optional[int] = Field(None, ge=320, le=1920)
    inference_height: Optional[int] = Field(None, ge=320, le=1920)
    target_fps: Optional[float] = Field(None, ge=0.1, le=5.0)
    confidence_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)

    # Floor plan position
    position_x: Optional[float] = Field(None, ge=0, le=100)
    position_y: Optional[float] = Field(None, ge=0, le=100)

    # Detection mode
    detection_mode: Optional[str] = Field(None, pattern="^(ppe|zone)$")
    zone_polygon: Optional[List[List[int]]] = None

    # Inference control
    inference_enabled: Optional[bool] = None

    # Status
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    """Camera response schema."""
    id: UUID
    name: str
    zone: str
    source_type: str
    rtsp_url: Optional[str] = None  # URL only, no credentials
    placeholder_video: Optional[str] = None
    use_placeholder: bool

    inference_width: int
    inference_height: int
    target_fps: float
    confidence_threshold: float

    position_x: float
    position_y: float

    detection_mode: str
    zone_polygon: Optional[List[List[int]]] = None

    inference_enabled: bool

    is_active: bool
    status: str
    last_seen: Optional[datetime] = None
    error_message: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    # Runtime stats (from Redis/worker)
    fps: float = 0.0
    infer_fps: float = 0.0
    detection_count: int = 0

    class Config:
        from_attributes = True


class CameraListResponse(BaseModel):
    """Camera list response schema."""
    cameras: List[CameraResponse]
    total: int


class CameraTestRequest(BaseModel):
    """Test camera connection request schema."""
    rtsp_url: str
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None


class CameraTestResponse(BaseModel):
    """Test camera connection response schema."""
    success: bool
    message: str
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    fps: Optional[float] = None
