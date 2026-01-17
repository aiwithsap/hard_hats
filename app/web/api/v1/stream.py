"""Video streaming API endpoints."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.db.database import get_db_session
from ....shared.db.repositories.cameras import CameraRepository
from ....shared.redis.pubsub import get_frame_subscriber
from ...auth.dependencies import CurrentUser

router = APIRouter()


async def generate_mjpeg_stream(camera_id: str):
    """
    Generate MJPEG stream from Redis frames.

    Yields:
        MJPEG frame bytes with boundary markers
    """
    try:
        subscriber = await get_frame_subscriber()

        async for frame_data in subscriber.subscribe(camera_id):
            # MJPEG boundary format
            yield b"--frame\r\n"
            yield b"Content-Type: image/jpeg\r\n\r\n"
            yield frame_data
            yield b"\r\n"

            # Small delay to prevent overwhelming
            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        # Client disconnected
        pass
    except Exception as e:
        # Log error but don't crash
        print(f"Stream error for camera {camera_id}: {e}")
    finally:
        if subscriber:
            await subscriber.unsubscribe()


async def generate_placeholder_frame():
    """Generate a placeholder frame when no video is available."""
    import cv2
    import numpy as np

    # Create a dark frame with "No Signal" text
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (30, 30, 40)  # Dark background

    cv2.putText(
        frame,
        "No Signal",
        (220, 230),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.5,
        (100, 100, 100),
        2,
    )
    cv2.putText(
        frame,
        "Waiting for video stream...",
        (170, 270),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (80, 80, 80),
        1,
    )

    _, jpeg = cv2.imencode(".jpg", frame)
    return jpeg.tobytes()


async def generate_placeholder_stream():
    """Generate a placeholder stream with periodic frame updates."""
    import cv2
    import numpy as np

    try:
        while True:
            # Create frame
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (30, 30, 40)

            cv2.putText(
                frame,
                "No Signal",
                (220, 230),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (100, 100, 100),
                2,
            )

            _, jpeg = cv2.imencode(".jpg", frame)
            frame_data = jpeg.tobytes()

            yield b"--frame\r\n"
            yield b"Content-Type: image/jpeg\r\n\r\n"
            yield frame_data
            yield b"\r\n"

            await asyncio.sleep(1.0)  # Update every second

    except asyncio.CancelledError:
        pass


@router.get("/stream/{camera_id}")
async def stream_camera(
    camera_id: UUID,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Stream video from a camera as MJPEG.

    The stream is fetched from Redis where the worker publishes frames.
    """
    # Verify camera belongs to organization
    camera_repo = CameraRepository(db, auth.organization_id)
    camera = await camera_repo.get_by_id(camera_id)

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    # Try to get frame from Redis first
    try:
        subscriber = await get_frame_subscriber()
        latest_frame = await subscriber.get_latest_frame(str(camera_id))

        if latest_frame:
            # Camera has active stream
            return StreamingResponse(
                generate_mjpeg_stream(str(camera_id)),
                media_type="multipart/x-mixed-replace; boundary=frame",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
    except Exception:
        pass  # Redis not available or no frames

    # Return placeholder stream
    return StreamingResponse(
        generate_placeholder_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/snapshot/{camera_id}")
async def get_snapshot(
    camera_id: UUID,
    auth: CurrentUser,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a single frame snapshot from a camera.
    """
    # Verify camera belongs to organization
    camera_repo = CameraRepository(db, auth.organization_id)
    camera = await camera_repo.get_by_id(camera_id)

    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    # Try to get frame from Redis
    try:
        subscriber = await get_frame_subscriber()
        frame_data = await subscriber.get_latest_frame(str(camera_id))

        if frame_data:
            return StreamingResponse(
                iter([frame_data]),
                media_type="image/jpeg",
                headers={"Cache-Control": "no-cache"},
            )
    except Exception:
        pass

    # Return placeholder
    placeholder = await generate_placeholder_frame()
    return StreamingResponse(
        iter([placeholder]),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )
