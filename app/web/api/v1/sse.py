"""Server-Sent Events (SSE) API endpoints."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.redis.pubsub import get_event_subscriber
from ...auth.dependencies import CurrentUser

router = APIRouter()


async def event_generator(
    organization_id: str,
    request: Request,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events from Redis subscription.

    Yields:
        SSE event dictionaries
    """
    # Send connection confirmation
    yield {
        "event": "connected",
        "data": json.dumps({"status": "connected"}),
    }

    try:
        subscriber = await get_event_subscriber()

        async for event_data in subscriber.subscribe(organization_id):
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Forward event to client
            yield {
                "event": event_data.get("type", "message"),
                "data": json.dumps(event_data.get("data", event_data)),
            }

    except asyncio.CancelledError:
        pass
    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }
    finally:
        if subscriber:
            await subscriber.unsubscribe()


async def heartbeat_generator(
    organization_id: str,
    request: Request,
) -> AsyncGenerator[dict, None]:
    """
    Generate SSE events with periodic heartbeats.

    This is used when Redis is not available.
    """
    # Send connection confirmation
    yield {
        "event": "connected",
        "data": json.dumps({"status": "connected", "mode": "polling"}),
    }

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Send heartbeat
            yield {
                "event": "heartbeat",
                "data": json.dumps({"status": "ok"}),
            }

            await asyncio.sleep(30)  # Heartbeat every 30 seconds

    except asyncio.CancelledError:
        pass


@router.get("/sse/events")
async def sse_events(
    request: Request,
    auth: CurrentUser,
):
    """
    Subscribe to real-time events via Server-Sent Events.

    Events are pushed from the worker service via Redis pub/sub.

    Event types:
    - connected: Connection established
    - violation: Safety violation detected
    - heartbeat: Keep-alive ping
    - error: Error occurred
    """
    organization_id = str(auth.organization_id)

    # Try Redis-backed event stream
    try:
        return EventSourceResponse(
            event_generator(organization_id, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    except Exception:
        # Fallback to heartbeat-only mode
        return EventSourceResponse(
            heartbeat_generator(organization_id, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )


@router.get("/sse/camera/{camera_id}")
async def sse_camera_events(
    camera_id: str,
    request: Request,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Subscribe to events for a specific camera.

    This is a filtered version of /sse/events that only sends
    events related to the specified camera.
    """
    from ....shared.db.repositories.cameras import CameraRepository
    from uuid import UUID

    # Verify camera belongs to organization
    camera_repo = CameraRepository(db, auth.organization_id)
    camera = await camera_repo.get_by_id(UUID(camera_id))

    if not camera:
        # Return empty stream with error
        async def error_stream():
            yield {
                "event": "error",
                "data": json.dumps({"error": "Camera not found"}),
            }

        return EventSourceResponse(
            error_stream(),
            media_type="text/event-stream",
        )

    # Filter events for this camera
    async def camera_event_generator() -> AsyncGenerator[dict, None]:
        yield {
            "event": "connected",
            "data": json.dumps({"camera_id": camera_id, "status": "connected"}),
        }

        try:
            subscriber = await get_event_subscriber()

            async for event_data in subscriber.subscribe(str(auth.organization_id)):
                if await request.is_disconnected():
                    break

                # Filter for this camera
                data = event_data.get("data", {})
                if data.get("camera_id") == camera_id:
                    yield {
                        "event": event_data.get("type", "message"),
                        "data": json.dumps(data),
                    }

        except asyncio.CancelledError:
            pass
        finally:
            if subscriber:
                await subscriber.unsubscribe()

    return EventSourceResponse(
        camera_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
