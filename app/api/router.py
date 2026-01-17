"""Main API router combining all endpoint modules."""

from fastapi import APIRouter

from .cameras import router as cameras_router
from .events import router as events_router
from .stream import router as stream_router
from .stats import router as stats_router
from .sse import router as sse_router

# Create main API router
router = APIRouter(prefix="/api")

# Include sub-routers
router.include_router(cameras_router, tags=["cameras"])
router.include_router(events_router, tags=["events"])
router.include_router(stream_router, tags=["streaming"])
router.include_router(stats_router, tags=["statistics"])
router.include_router(sse_router, tags=["sse"])
