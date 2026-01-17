"""Database repositories with tenant isolation."""

from .base import TenantRepository
from .users import UserRepository, GlobalUserRepository
from .organizations import OrganizationRepository
from .cameras import CameraRepository, GlobalCameraRepository
from .events import EventRepository, GlobalEventRepository
from .stats import StatsRepository

__all__ = [
    # Base
    "TenantRepository",
    # Tenant-scoped repositories
    "UserRepository",
    "OrganizationRepository",
    "CameraRepository",
    "EventRepository",
    "StatsRepository",
    # Global repositories (for worker/auth)
    "GlobalUserRepository",
    "GlobalCameraRepository",
    "GlobalEventRepository",
]
