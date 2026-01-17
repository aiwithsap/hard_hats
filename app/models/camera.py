"""Camera data model."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class CameraStatus(str, Enum):
    """Camera operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONNECTING = "connecting"


@dataclass
class Camera:
    """Represents a camera in the surveillance system."""

    id: str
    name: str
    zone: str  # "Warehouse", "Production", "Common", "Secure"
    source: str  # Video file path or RTSP URL

    # Floor plan position (0-100 percentage)
    position_x: float = 50.0
    position_y: float = 50.0

    # Status
    status: CameraStatus = CameraStatus.INACTIVE

    # Demo mode options
    start_offset: int = 0  # Seconds into video to start
    playback_speed: float = 1.0
    mirror: bool = False
    hue_shift: int = 0  # -180 to 180
    brightness: float = 1.0

    # Runtime stats
    fps: float = 0.0
    frame_count: int = 0
    last_detection_count: int = 0
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "zone": self.zone,
            "source": self.source,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "status": self.status.value,
            "fps": round(self.fps, 1),
            "frame_count": self.frame_count,
            "last_detection_count": self.last_detection_count,
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Camera":
        """Create Camera from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            zone=data.get("zone", "Common"),
            source=data["source"],
            position_x=data.get("position_x", 50.0),
            position_y=data.get("position_y", 50.0),
            start_offset=data.get("start_offset", 0),
            playback_speed=data.get("playback_speed", 1.0),
            mirror=data.get("mirror", False),
            hue_shift=data.get("hue_shift", 0),
            brightness=data.get("brightness", 1.0),
        )
