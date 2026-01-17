"""RTSP stream handler with retry logic and health checks."""

import asyncio
import time
from typing import Optional, Tuple
from dataclasses import dataclass
import cv2
import numpy as np

from ..shared.encryption import decrypt_credentials, safe_decrypt
from .config import config


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
        Open a video file.

        Args:
            path: Path to video file

        Returns:
            Tuple of (VideoCapture or None, error message or None)
        """
        try:
            cap = cv2.VideoCapture(path)

            if not cap.isOpened():
                return None, f"Failed to open video file: {path}"

            return cap, None

        except Exception as e:
            return None, str(e)


# Global handler instance
_rtsp_handler: Optional[RTSPHandler] = None


def get_rtsp_handler() -> RTSPHandler:
    """Get or create the RTSP handler."""
    global _rtsp_handler
    if _rtsp_handler is None:
        _rtsp_handler = RTSPHandler()
    return _rtsp_handler
