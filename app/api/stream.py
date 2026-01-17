"""Video streaming API endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
import cv2
import time
import numpy as np

from ..core.camera_manager import get_camera_manager

router = APIRouter()


def generate_mjpeg(camera_id: str):
    """Generate MJPEG stream for a camera."""
    manager = get_camera_manager()
    buffer = manager.get_buffer(camera_id)

    if not buffer:
        return

    while True:
        frame, fps = buffer.get()

        if frame is None:
            # No frame yet, send placeholder
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(
                placeholder,
                "Connecting...",
                (220, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (255, 255, 255),
                2,
            )
            frame = placeholder

        # Encode frame as JPEG
        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
        )

        time.sleep(0.033)  # ~30 FPS max


@router.get("/stream/{camera_id}")
async def stream_camera(camera_id: str):
    """Get MJPEG video stream for a camera."""
    manager = get_camera_manager()

    if not manager.get_camera(camera_id):
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    return StreamingResponse(
        generate_mjpeg(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/cameras/{camera_id}/snapshot")
async def get_snapshot(camera_id: str):
    """Get current frame as a single JPEG image."""
    manager = get_camera_manager()
    buffer = manager.get_buffer(camera_id)

    if not buffer:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    frame, _ = buffer.get()

    if frame is None:
        raise HTTPException(status_code=503, detail="No frame available yet")

    # Encode as JPEG
    ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ret:
        raise HTTPException(status_code=500, detail="Failed to encode frame")

    return Response(
        content=jpeg.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )
