"""Pydantic schemas for API requests and responses."""

from .auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
)
from .camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraListResponse,
    CameraTestRequest,
    CameraTestResponse,
)
from .event import (
    EventResponse,
    EventListResponse,
    EventFilterParams,
)
from .organization import (
    OrganizationResponse,
    OrganizationUpdate,
)
from .stats import (
    StatsSummaryResponse,
    DailyStatsResponse,
    ViolationBreakdownResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "ChangePasswordRequest",
    # Camera
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "CameraListResponse",
    "CameraTestRequest",
    "CameraTestResponse",
    # Event
    "EventResponse",
    "EventListResponse",
    "EventFilterParams",
    # Organization
    "OrganizationResponse",
    "OrganizationUpdate",
    # Stats
    "StatsSummaryResponse",
    "DailyStatsResponse",
    "ViolationBreakdownResponse",
]
