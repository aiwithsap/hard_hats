"""RTSP stream handler with retry logic and health checks."""

import asyncio
import hashlib
import os
import time
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
import cv2
import numpy as np
import requests

from ..shared.encryption import decrypt_credentials, safe_decrypt
from .config import config

# Cache directory for downloaded videos
VIDEO_CACHE_DIR = Path("data/videos")


@dataclass
class RTSPConnection:
    """RTSP connection state."""
    url: str
    username: Optional[str]
    password: Optional[str]
    cap: Optional[cv2.VideoCapture] = None
    retry_count: int = 0
    last_success: float = 0
    last_error: Optional[str] = None


class RTSPHandler:
    """
    Handles RTSP stream connections with retry logic.

    Features:
    - Exponential backoff on connection failures
    - Automatic reconnection
    - Health checking
    - Credential injection into URL
    """

    def __init__(
        self,
        max_retries: int = config.RTSP_MAX_RETRIES,
        base_delay: float = config.RTSP_BASE_DELAY,
        max_delay: float = config.RTSP_MAX_DELAY,
        health_check_interval: float = config.RTSP_HEALTH_CHECK_INTERVAL,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.health_check_interval = health_check_interval

    def build_rtsp_url(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> str:
        """
        Build RTSP URL with credentials.

        Input: rtsp://camera.local:554/stream
        Output: rtsp://user:pass@camera.local:554/stream
        """
        if not username or not password:
            return base_url

        # Parse URL
        if "://" in base_url:
            protocol, rest = base_url.split("://", 1)
        else:
            protocol = "rtsp"
            rest = base_url

        # Remove existing credentials if present
        if "@" in rest:
            rest = rest.split("@", 1)[1]

        return f"{protocol}://{username}:{password}@{rest}"

    async def connect(
        self,
        url: str,
        credentials_encrypted: Optional[str] = None,
    ) -> Tuple[Optional[cv2.VideoCapture], Optional[str]]:
        """
        Connect to RTSP stream with retry logic.

        Args:
            url: RTSP URL (without credentials)
            credentials_encrypted: Encrypted username:password

        Returns:
            Tuple of (VideoCapture or None, error message or None)
        """
        username = None
        password = None

        # Decrypt credentials
        if credentials_encrypted:
            try:
                username, password = decrypt_credentials(credentials_encrypted)
            except Exception as e:
                return None, f"Failed to decrypt credentials: {e}"

        # Build full URL
        full_url = self.build_rtsp_url(url, username, password)

        # Try to connect with retries
        for attempt in range(self.max_retries):
            try:
                cap = cv2.VideoCapture(full_url)

                if cap.isOpened():
                    # Test read
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return cap, None

                    cap.release()

            except Exception as e:
                pass  # Will retry

            # Calculate delay with exponential backoff
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)

            if attempt < self.max_retries - 1:
                await asyncio.sleep(delay)

        return None, f"Failed to connect after {self.max_retries} attempts"

    async def test_connection(
        self,
        url: str,
        credentials_encrypted: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Test RTSP connection and return stream info.

        Returns:
            Tuple of (success, message, info dict or None)
        """
        username = None
        password = None

        if credentials_encrypted:
            try:
                username, password = decrypt_credentials(credentials_encrypted)
            except Exception as e:
                return False, f"Failed to decrypt credentials: {e}", None

        full_url = self.build_rtsp_url(url, username, password)

        try:
            cap = cv2.VideoCapture(full_url)

            if not cap.isOpened():
                return False, "Failed to open stream", None

            # Read a test frame
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return False, "Failed to read frame", None

            # Get stream info
            info = {
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
            }

            cap.release()
            return True, "Connection successful", info

        except Exception as e:
            return False, str(e), None

    def open_file(self, path: str) -> Tuple[Optional[cv2.VideoCapture], Optional[str]]:
        """
        Open a video file or URL.

        Args:
            path: Path to video file or HTTP/HTTPS URL

        Returns:
            Tuple of (VideoCapture or None, error message or None)
        """
        try:
            # Check if path is a URL
            if path.startswith("http://") or path.startswith("https://"):
                local_path, error = self._download_video(path)
                if error:
                    return None, error
                path = local_path

            cap = cv2.VideoCapture(path)

            if not cap.isOpened():
                return None, f"Failed to open video file: {path}"

            return cap, None

        except Exception as e:
            return None, str(e)

    def _download_video(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Download a video from URL to local cache.

        Args:
            url: HTTP/HTTPS URL to video

        Returns:
            Tuple of (local path or None, error message or None)
        """
        try:
            # Create cache directory
            VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Generate cache filename from URL hash
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            ext = os.path.splitext(url.split("?")[0])[-1] or ".mp4"
            cache_path = VIDEO_CACHE_DIR / f"cached_{url_hash}{ext}"

            # Check if already cached
            if cache_path.exists() and cache_path.stat().st_size > 0:
                print(f"[RTSP_HANDLER] Using cached video: {cache_path}")
                return str(cache_path), None

            # Download video
            print(f"[RTSP_HANDLER] Downloading video from: {url}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # Save to cache
            with open(cache_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"[RTSP_HANDLER] Downloaded video to: {cache_path}")
            return str(cache_path), None

        except requests.RequestException as e:
            return None, f"Failed to download video: {e}"
        except Exception as e:
            return None, f"Error caching video: {e}"


class TestPatternCapture:
    """
    A cv2.VideoCapture-like class that generates test pattern frames.
    Used as a fallback when no video source is available.
    """

    def __init__(self, width: int = 640, height: int = 480, fps: float = 0.5):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = 0
        self._opened = True

    def isOpened(self) -> bool:
        return self._opened

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Generate a test pattern frame."""
        if not self._opened:
            return False, None

        # Create a frame with gradient background
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Add color gradient
        for y in range(self.height):
            color_val = int((y / self.height) * 128) + 64
            frame[y, :, 0] = color_val  # Blue channel
            frame[y, :, 2] = 192 - color_val  # Red channel

        # Add "DEMO MODE" text
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = "DEMO MODE"
        text_size = cv2.getTextSize(text, font, 1.5, 3)[0]
        text_x = (self.width - text_size[0]) // 2
        text_y = (self.height + text_size[1]) // 2
        cv2.putText(frame, text, (text_x, text_y), font, 1.5, (255, 255, 255), 3)

        # Add frame counter
        counter_text = f"Frame: {self.frame_count}"
        cv2.putText(frame, counter_text, (10, 30), font, 0.7, (200, 200, 200), 2)

        # Add instructions
        info_text = "Configure camera in Camera Setup"
        info_size = cv2.getTextSize(info_text, font, 0.6, 1)[0]
        cv2.putText(frame, info_text, ((self.width - info_size[0]) // 2, self.height - 20),
                    font, 0.6, (180, 180, 180), 1)

        self.frame_count += 1
        return True, frame

    def get(self, prop_id: int) -> float:
        """Get capture property."""
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self.width)
        elif prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self.height)
        elif prop_id == cv2.CAP_PROP_FPS:
            return self.fps
        return 0.0

    def release(self) -> None:
        """Release the capture."""
        self._opened = False


# Global handler instance
_rtsp_handler: Optional[RTSPHandler] = None


def get_rtsp_handler() -> RTSPHandler:
    """Get or create the RTSP handler."""
    global _rtsp_handler
    if _rtsp_handler is None:
        _rtsp_handler = RTSPHandler()
    return _rtsp_handler


def get_test_pattern_capture(width: int = 640, height: int = 480) -> TestPatternCapture:
    """Get a test pattern capture for demo mode."""
    return TestPatternCapture(width=width, height=height)
