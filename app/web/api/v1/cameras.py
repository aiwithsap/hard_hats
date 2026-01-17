"""Camera API endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.models import Camera, SourceType, DetectionMode, CameraStatus
from ....shared.db.repositories.cameras import CameraRepository
from ....shared.db.repositories.organizations import OrganizationRepository
from ....shared.encryption import encrypt_credentials, is_encryption_configured
from ....shared.schemas.camera import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    CameraListResponse,
    CameraTestRequest,
    CameraTestResponse,
)
from ...auth.dependencies import CurrentUser, AdminUser

router = APIRouter()


def camera_to_response(camera: Camera, fps: float = 0.0, detection_count: int = 0) -> CameraResponse:
    """Convert Camera model to CameraResponse."""
    return CameraResponse(
        id=camera.id,
        name=camera.name,
        zone=camera.zone,
        source_type=camera.source_type.value,
        rtsp_url=camera.rtsp_url,  # URL only, credentials are separate
        placeholder_video=camera.placeholder_video,
        use_placeholder=camera.use_placeholder,
        inference_width=camera.inference_width,
        inference_height=camera.inference_height,
        target_fps=camera.target_fps,
        confidence_threshold=camera.confidence_threshold,
        position_x=camera.position_x,
        position_y=camera.position_y,
        detection_mode=camera.detection_mode.value,
        zone_polygon=camera.zone_polygon,
        is_active=camera.is_active,
        status=camera.status.value,
        last_seen=camera.last_seen,
        error_message=camera.error_message,
        created_at=camera.created_at,
        updated_at=camera.updated_at,
        fps=fps,
        detection_count=detection_count,
    )


@router.get("", response_model=CameraListResponse)
async def list_cameras(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    zone: Optional[str] = None,
    status_filter: Optional[str] = None,
):
    """
    List all cameras in the organization.
    """
    camera_repo = CameraRepository(db, auth.organization_id)

    if zone:
        cameras = await camera_repo.get_by_zone(zone)
    elif status_filter:
        cameras = await camera_repo.get_by_status(CameraStatus(status_filter))
    else:
        cameras, _ = await camera_repo.get_all(limit=1000)

    # TODO: Get real-time fps/detection count from Redis
    return CameraListResponse(
        cameras=[camera_to_response(c) for c in cameras],
        total=len(cameras),
    )


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    request: CameraCreate,
    auth: AdminUser,  # Admin only
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new camera (admin only).
    """
    camera_repo = CameraRepository(db, auth.organization_id)
    org_repo = OrganizationRepository(db)

    # Check camera limit
    org = await org_repo.get_by_id(auth.organization_id)
    camera_count = await org_repo.get_camera_count(auth.organization_id)
    if camera_count >= org.max_cameras:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera limit reached ({org.max_cameras}). Upgrade your plan.",
        )

    # Encrypt RTSP credentials if provided
    credentials_encrypted = None
    if request.rtsp_username and request.rtsp_password:
        if not is_encryption_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption not configured. Set ENCRYPTION_KEY.",
            )
        credentials_encrypted = encrypt_credentials(
            request.rtsp_username,
            request.rtsp_password,
        )

    # Create camera
    camera = Camera(
        organization_id=auth.organization_id,
        name=request.name,
        zone=request.zone,
        source_type=SourceType(request.source_type),
        rtsp_url=request.rtsp_url,
        credentials_encrypted=credentials_encrypted,
        placeholder_video=request.placeholder_video,
        use_placeholder=request.use_placeholder,
        inference_width=request.inference_width,
        inference_height=request.inference_height,
        target_fps=request.target_fps,
        confidence_threshold=request.confidence_threshold,
        position_x=request.position_x,
        position_y=request.position_y,
        detection_mode=DetectionMode(request.detection_mode),
        zone_polygon=request.zone_polygon,
    )
    camera = await camera_repo.create(camera)

    return camera_to_response(camera)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: UUID,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a camera by ID.
    """
    camera_repo = CameraRepository(db, auth.organization_id)
    camera = await camera_repo.get_by_id(camera_id)

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    return camera_to_response(camera)


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: UUID,
    request: CameraUpdate,
    auth: AdminUser,  # Admin only
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update a camera (admin only).
    """
    camera_repo = CameraRepository(db, auth.organization_id)
    camera = await camera_repo.get_by_id(camera_id)

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    # Update fields
    if request.name is not None:
        camera.name = request.name
    if request.zone is not None:
        camera.zone = request.zone
    if request.source_type is not None:
        camera.source_type = SourceType(request.source_type)
    if request.rtsp_url is not None:
        camera.rtsp_url = request.rtsp_url
    if request.rtsp_username and request.rtsp_password:
        if not is_encryption_configured():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption not configured. Set ENCRYPTION_KEY.",
            )
        camera.credentials_encrypted = encrypt_credentials(
            request.rtsp_username,
            request.rtsp_password,
        )
    if request.placeholder_video is not None:
        camera.placeholder_video = request.placeholder_video
    if request.use_placeholder is not None:
        camera.use_placeholder = request.use_placeholder
    if request.inference_width is not None:
        camera.inference_width = request.inference_width
    if request.inference_height is not None:
        camera.inference_height = request.inference_height
    if request.target_fps is not None:
        camera.target_fps = request.target_fps
    if request.confidence_threshold is not None:
        camera.confidence_threshold = request.confidence_threshold
    if request.position_x is not None:
        camera.position_x = request.position_x
    if request.position_y is not None:
        camera.position_y = request.position_y
    if request.detection_mode is not None:
        camera.detection_mode = DetectionMode(request.detection_mode)
    if request.zone_polygon is not None:
        camera.zone_polygon = request.zone_polygon
    if request.is_active is not None:
        camera.is_active = request.is_active

    await camera_repo.update(camera)
    return camera_to_response(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: UUID,
    auth: AdminUser,  # Admin only
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete a camera (admin only).
    """
    camera_repo = CameraRepository(db, auth.organization_id)
    deleted = await camera_repo.delete(camera_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )


@router.post("/{camera_id}/test", response_model=CameraTestResponse)
async def test_camera_connection(
    camera_id: UUID,
    auth: AdminUser,  # Admin only
    db: AsyncSession = Depends(get_db_session),
):
    """
    Test camera RTSP connection (admin only).
    """
    camera_repo = CameraRepository(db, auth.organization_id)
    camera = await camera_repo.get_by_id(camera_id)

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    if camera.source_type != SourceType.rtsp:
        return CameraTestResponse(
            success=True,
            message="Camera uses file source, no connection test needed",
        )

    # TODO: Implement actual RTSP connection test
    # This would be done by the worker service
    return CameraTestResponse(
        success=True,
        message="Connection test not yet implemented. Camera will be tested when worker starts.",
    )


@router.get("/presets", response_model=dict)
async def get_presets():
    """
    Get available resolution and FPS presets.
    """
    return {
        "resolution_presets": [
            {"name": "Low", "width": 640, "height": 640, "description": "Fast processing, ~174ms/frame"},
            {"name": "Medium", "width": 720, "height": 720, "description": "Balanced accuracy/speed"},
            {"name": "High", "width": 1080, "height": 1080, "description": "Better accuracy, ~400ms/frame"},
        ],
        "fps_presets": [
            {"name": "Low", "fps": 0.25, "description": "15 frames/min, very low CPU"},
            {"name": "Default", "fps": 0.5, "description": "30 frames/min, good balance"},
            {"name": "Medium", "fps": 1.0, "description": "60 frames/min, active areas"},
            {"name": "High", "fps": 2.0, "description": "120 frames/min, near real-time"},
        ],
    }
