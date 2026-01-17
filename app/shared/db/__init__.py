"""Database module with PostgreSQL async support."""

from .database import (
    get_db,
    get_db_session,
    init_db,
    close_db,
    get_session_factory,
    async_session_factory,
)
from .models import (
    Base,
    Organization,
    User,
    Camera,
    Event,
    DailyStat,
    AuditLog,
    EventTracking,
    UserRole,
    CameraStatus,
    SourceType,
    DetectionMode,
    EventType,
    ViolationType,
    Severity,
    PlanType,
)

__all__ = [
    # Database functions
    "get_db",
    "get_db_session",
    "init_db",
    "close_db",
    "get_session_factory",
    "async_session_factory",
    # Models
    "Base",
    "Organization",
    "User",
    "Camera",
    "Event",
    "DailyStat",
    "AuditLog",
    "EventTracking",
    # Enums
    "UserRole",
    "CameraStatus",
    "SourceType",
    "DetectionMode",
    "EventType",
    "ViolationType",
    "Severity",
    "PlanType",
]
