"""Frame processing and Redis publishing."""

import cv2
import numpy as np
from typing import Optional

from ..shared.redis.pubsub import FramePublisher
from .config import config


class FrameProcessor:
    """
    Processes frames and publishes to Redis for web service consumption.

    Features:
    - JPEG encoding with configurable quality
    - Frame rate limiting
    - Watermark overlay for demo mode
    """

    def __init__(
        self,
        publisher: FramePublisher,
        jpeg_quality: int = config.THUMBNAIL_QUALITY,
    ):
        self.publisher = publisher
        self.jpeg_quality = jpeg_quality
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]

    async def publish_frame(
        self,
        camera_id: str,
        frame: np.ndarray,
        is_demo: bool = False,
    ) -> bool:
        """
        Encode and publish a frame to Redis.

        Args:
            camera_id: Camera identifier
            frame: OpenCV frame (BGR format)
            is_demo: If True, adds "DEMO MODE" watermark

        Returns:
            True if published successfully
        """
        try:
            # Add demo watermark if needed
            if is_demo:
                frame = self._add_demo_watermark(frame)

            # Encode to JPEG
            success, encoded = cv2.imencode(".jpg", frame, self._encode_params)

            if not success:
                return False

            # Publish to Redis
            await self.publisher.publish_frame(camera_id, encoded.tobytes())

            return True

        except Exception as e:
            print(f"[FRAME_PROCESSOR] Error publishing frame: {e}")
            return False

    def _add_demo_watermark(self, frame: np.ndarray) -> np.ndarray:
        """Add a "DEMO MODE" watermark to the frame."""
        frame = frame.copy()
        height, width = frame.shape[:2]

        # Watermark text
        text = "DEMO MODE"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2

        # Get text size
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )

        # Position in top-right corner
        x = width - text_w - 20
        y = text_h + 20

        # Draw background rectangle
        cv2.rectangle(
            frame,
            (x - 10, y - text_h - 10),
            (x + text_w + 10, y + 10),
            (0, 0, 0),
            -1,
        )

        # Draw text
        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            font_scale,
            (0, 255, 255),  # Yellow
            thickness,
        )

        return frame

    async def close(self) -> None:
        """Close the publisher connection."""
        await self.publisher.close()


class ThumbnailGenerator:
    """
    Generates and saves thumbnail images for events.
    """

    def __init__(
        self,
        output_dir: str = config.THUMBNAIL_DIR,
        quality: int = config.THUMBNAIL_QUALITY,
    ):
        self.output_dir = output_dir
        self.quality = quality
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]

        # Ensure output directory exists
        import os
        os.makedirs(output_dir, exist_ok=True)

    def generate(
        self,
        frame: np.ndarray,
        event_id: str,
        bbox: Optional[tuple] = None,
    ) -> Optional[str]:
        """
        Generate a thumbnail for an event.

        Args:
            frame: Source frame
            event_id: Event identifier for filename
            bbox: Optional bounding box to crop around

        Returns:
            Path to saved thumbnail or None on error
        """
        try:
            import os

            # Crop to region if bbox provided
            if bbox:
                x1, y1, x2, y2 = bbox
                # Add padding
                h, w = frame.shape[:2]
                pad = 50
                x1 = max(0, x1 - pad)
                y1 = max(0, y1 - pad)
                x2 = min(w, x2 + pad)
                y2 = min(h, y2 + pad)
                frame = frame[y1:y2, x1:x2]

            # Resize if too large
            max_dim = 640
            h, w = frame.shape[:2]
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                frame = cv2.resize(
                    frame,
                    (int(w * scale), int(h * scale)),
                )

            # Save thumbnail
            filename = f"{event_id}.jpg"
            filepath = os.path.join(self.output_dir, filename)

            cv2.imwrite(filepath, frame, self._encode_params)

            return filepath

        except Exception as e:
            print(f"[THUMBNAIL] Error generating thumbnail: {e}")
            return None
