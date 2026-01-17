"""Camera API endpoints."""

from fastapi import APIRouter, HTTPException
from typing import List

from ..models.schemas import CameraResponse, CameraListResponse, FloorPlanResponse, CameraPosition
from ..core.camera_manager import get_camera_manager

router = APIRouter()


@router.get("/cameras", response_model=CameraListResponse)
async def list_cameras():
    """Get list of all cameras with their status."""
    manager = get_camera_manager()
    cameras = manager.get_cameras()

    return CameraListResponse(
        cameras=[CameraResponse(**c.to_dict()) for c in cameras],
        total=len(cameras),
        active=manager.get_active_count(),
    )


@router.get("/cameras/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str):
    """Get details for a specific camera."""
    manager = get_camera_manager()
    camera = manager.get_camera(camera_id)

    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return CameraResponse(**camera.to_dict())


@router.get("/floorplan", response_model=FloorPlanResponse)
async def get_floorplan():
    """Get floor plan with camera positions."""
    manager = get_camera_manager()
    cameras = manager.get_cameras()

    positions = [
        CameraPosition(
            id=c.id,
            name=c.name,
            zone=c.zone,
            x=c.position_x,
            y=c.position_y,
            status=c.status.value,
        )
        for c in cameras
    ]

    return FloorPlanResponse(
        cameras=positions,
        floor_plan_url="/static/floorplan.svg",
    )
