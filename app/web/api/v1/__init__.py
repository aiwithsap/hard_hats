"""API v1 module."""

from fastapi import APIRouter

from .auth import router as auth_router
from .cameras import router as cameras_router
from .events import router as events_router
from .stats import router as stats_router
from .stream import router as stream_router
from .sse import router as sse_router
from .users import router as users_router
from .organizations import router as organizations_router

# Create main API router
router = APIRouter(prefix="/api/v1")

# Include sub-routers
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(organizations_router, prefix="/organization", tags=["organization"])
router.include_router(cameras_router, prefix="/cameras", tags=["cameras"])
router.include_router(events_router, prefix="/events", tags=["events"])
router.include_router(stats_router, prefix="/stats", tags=["stats"])
router.include_router(stream_router, tags=["streaming"])
router.include_router(sse_router, tags=["sse"])
