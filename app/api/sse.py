"""Server-Sent Events (SSE) endpoint for real-time notifications."""

import asyncio
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..core.event_processor import get_event_processor
from ..models.event import Event

router = APIRouter()


async def event_generator():
    """Generate SSE events for new violations."""
    processor = get_event_processor()
    event_queue = asyncio.Queue()

    def on_event(event: Event):
        """Callback for new events."""
        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                event_queue.put_nowait, event
            )
        except Exception:
            pass

    # Subscribe to events
    processor.subscribe(on_event)

    try:
        # Send initial heartbeat
        yield {
            "event": "connected",
            "data": json.dumps({"status": "connected"}),
        }

        while True:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)

                yield {
                    "event": event.event_type.value,
                    "data": json.dumps(event.to_dict()),
                }

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"status": "alive"}),
                }

    finally:
        # Unsubscribe on disconnect
        processor.unsubscribe(on_event)


@router.get("/sse/events")
async def sse_events():
    """
    Server-Sent Events stream for real-time event notifications.

    Event types:
    - connected: Initial connection confirmation
    - violation: New safety violation detected
    - heartbeat: Keep-alive signal (every 30s)

    Usage (JavaScript):
    ```
    const eventSource = new EventSource('/api/sse/events');
    eventSource.addEventListener('violation', (e) => {
        const data = JSON.parse(e.data);
        console.log('New violation:', data);
    });
    ```
    """
    return EventSourceResponse(event_generator())
