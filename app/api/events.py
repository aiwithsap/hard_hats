"""Events API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from ..models.schemas import EventResponse, EventListResponse
from ..db.repositories import EventRepository
from ..core.event_processor import get_event_processor

router = APIRouter()


@router.get("/events", response_model=EventListResponse)
async def list_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    since: Optional[datetime] = Query(None, description="Events since timestamp"),
    until: Optional[datetime] = Query(None, description="Events until timestamp"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Get list of events with optional filtering."""
    repo = EventRepository()
    events, total = repo.get_all(
        camera_id=camera_id,
        event_type=event_type,
        violation_type=violation_type,
        severity=severity,
        since=since,
        until=until,
        acknowledged=acknowledged,
        limit=limit,
        offset=offset,
    )

    return EventListResponse(
        events=[EventResponse(**e.to_dict()) for e in events],
        total=total,
        page=(offset // limit) + 1 if limit > 0 else 1,
        page_size=limit,
    )


@router.get("/events/live")
async def get_live_events(limit: int = Query(50, ge=1, le=100)):
    """Get recent live events from memory (faster than database)."""
    processor = get_event_processor()
    events = processor.get_live_events(limit=limit)

    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
    }


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    """Get details for a specific event."""
    repo = EventRepository()
    event = repo.get_by_id(event_id)

    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return EventResponse(**event.to_dict())


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_event(event_id: str):
    """Mark an event as acknowledged."""
    repo = EventRepository()

    if not repo.acknowledge(event_id):
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return {"status": "acknowledged", "event_id": event_id}


@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    """Delete an event."""
    repo = EventRepository()

    if not repo.delete(event_id):
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return {"status": "deleted", "event_id": event_id}
