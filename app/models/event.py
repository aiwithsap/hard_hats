"""Event data model for violations and detections."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple
from datetime import datetime
import uuid


class EventType(str, Enum):
    """Type of event."""
    VIOLATION = "violation"
    DETECTION = "detection"
    STATUS = "status"


class ViolationType(str, Enum):
    """Type of safety violation."""
    NO_HARDHAT = "no_hardhat"
    NO_VEST = "no_vest"
    ZONE_BREACH = "zone_breach"


class Severity(str, Enum):
    """Event severity level."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Event:
    """Represents a detection or violation event."""

    camera_id: str
    camera_name: str
    event_type: EventType

    # Violation details
    violation_type: Optional[ViolationType] = None
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.0

    # Bounding box (x1, y1, x2, y2)
    bbox: Optional[Tuple[int, int, int, int]] = None

    # Metadata
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    frame_number: int = 0
    thumbnail_path: Optional[str] = None
    acknowledged: bool = False

    @property
    def message(self) -> str:
        """Generate human-readable event message."""
        if self.event_type == EventType.VIOLATION:
            violation_messages = {
                ViolationType.NO_HARDHAT: "Worker detected without hardhat",
                ViolationType.NO_VEST: "Worker detected without safety vest",
                ViolationType.ZONE_BREACH: "Unauthorized zone entry detected",
            }
            msg = violation_messages.get(self.violation_type, "Safety violation detected")
            return f"{msg} on {self.camera_name}"
        elif self.event_type == EventType.STATUS:
            return f"Camera status update: {self.camera_name}"
        else:
            return f"Detection on {self.camera_name}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "event_type": self.event_type.value,
            "violation_type": self.violation_type.value if self.violation_type else None,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 2),
            "bbox": list(self.bbox) if self.bbox else None,
            "timestamp": self.timestamp.isoformat(),
            "frame_number": self.frame_number,
            "thumbnail_path": self.thumbnail_path,
            "acknowledged": self.acknowledged,
            "message": self.message,
        }

    def to_sse_dict(self) -> dict:
        """Convert to SSE-friendly dictionary."""
        return {
            "type": self.event_type.value,
            "data": self.to_dict(),
        }
