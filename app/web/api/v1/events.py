"""Events API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.models import EventType, ViolationType, Severity, Camera
from ....shared.db.repositories.events import EventRepository
from ....shared.db.repositories.cameras import CameraRepository
from ....shared.schemas.event import (
    EventResponse,
    EventListResponse,
    AcknowledgeRequest,
)
from ...auth.dependencies import CurrentUser

router = APIRouter()


def event_to_response(event, camera_name: str = "") -> EventResponse:
    """Convert Event model to EventResponse."""
    bbox = None
    if event.bbox_x1 is not None:
        bbox = [event.bbox_x1, event.bbox_y1, event.bbox_x2, event.bbox_y2]

    # Generate human-readable message
    violation_messages = {
        ViolationType.NO_HARDHAT: "Worker detected without hardhat",
        ViolationType.NO_VEST: "Worker detected without safety vest",
        ViolationType.ZONE_BREACH: "Unauthorized zone entry detected",
    }
    if event.violation_type:
        message = f"{violation_messages.get(event.violation_type, 'Violation detected')} on {camera_name}"
    else:
        message = f"Detection on {camera_name}"

    # Generate thumbnail URL
    thumbnail_url = None
    if event.thumbnail_path:
        thumbnail_url = f"/thumbnails/{event.id}.jpg"

    return EventResponse(
        id=event.id,
        camera_id=event.camera_id,
        camera_name=camera_name,
        event_type=event.event_type.value,
        violation_type=event.violation_type.value if event.violation_type else None,
        severity=event.severity.value,
        confidence=event.confidence,
        bbox=bbox,
        thumbnail_path=event.thumbnail_path,
        thumbnail_url=thumbnail_url,
        frame_number=event.frame_number,
        acknowledged=event.acknowledged,
        acknowledged_by=event.acknowledged_by,
        acknowledged_at=event.acknowledged_at,
        timestamp=event.timestamp,
        message=message,
    )


@router.get("", response_model=EventListResponse)
async def list_events(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    camera_id: Optional[UUID] = None,
    event_type: Optional[str] = None,
    violation_type: Optional[str] = None,
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """
    List events with filtering and pagination.
    """
    event_repo = EventRepository(db, auth.organization_id)
    camera_repo = CameraRepository(db, auth.organization_id)

    offset = (page - 1) * page_size

    events, total = await event_repo.get_filtered(
        camera_id=camera_id,
        event_type=EventType(event_type) if event_type else None,
        violation_type=ViolationType(violation_type) if violation_type else None,
        severity=Severity(severity) if severity else None,
        acknowledged=acknowledged,
        limit=page_size,
        offset=offset,
    )

    # Get camera names
    camera_names = {}
    for event in events:
        if event.camera_id not in camera_names:
            camera = await camera_repo.get_by_id(event.camera_id)
            camera_names[event.camera_id] = camera.name if camera else "Unknown"

    return EventListResponse(
        events=[
            event_to_response(e, camera_names.get(e.camera_id, "Unknown"))
            for e in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/live", response_model=EventListResponse)
async def get_live_events(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Get most recent events for live feed.
    """
    event_repo = EventRepository(db, auth.organization_id)
    camera_repo = CameraRepository(db, auth.organization_id)

    events = await event_repo.get_recent(limit=limit)

    # Get camera names
    camera_names = {}
    for event in events:
        if event.camera_id not in camera_names:
            camera = await camera_repo.get_by_id(event.camera_id)
            camera_names[event.camera_id] = camera.name if camera else "Unknown"

    return EventListResponse(
        events=[
            event_to_response(e, camera_names.get(e.camera_id, "Unknown"))
            for e in events
        ],
        total=len(events),
        page=1,
        page_size=limit,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a single event by ID.
    """
    event_repo = EventRepository(db, auth.organization_id)
    camera_repo = CameraRepository(db, auth.organization_id)

    event = await event_repo.get_by_id(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    camera = await camera_repo.get_by_id(event.camera_id)
    camera_name = camera.name if camera else "Unknown"

    return event_to_response(event, camera_name)


@router.post("/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: UUID,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Acknowledge an event.
    """
    event_repo = EventRepository(db, auth.organization_id)

    success = await event_repo.acknowledge(event_id, auth.user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return {"message": "Event acknowledged"}


@router.post("/acknowledge-all")
async def acknowledge_all_events(
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Acknowledge all unacknowledged events.
    """
    event_repo = EventRepository(db, auth.organization_id)
    count = await event_repo.acknowledge_all(auth.user_id)

    return {"message": f"Acknowledged {count} events"}


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete an event.
    """
    event_repo = EventRepository(db, auth.organization_id)
    deleted = await event_repo.delete(event_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
