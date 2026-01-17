"""Thread-safe frame buffer for camera streams."""

import threading
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FrameData:
    """Container for frame and associated metadata."""
    frame: np.ndarray
    fps: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    frame_number: int = 0
    detections: List[Dict[str, Any]] = field(default_factory=list)


class FrameBuffer:
    """Thread-safe buffer for storing the latest frame from a camera."""

    def __init__(self):
        self._frame: Optional[np.ndarray] = None
        self._fps: float = 0.0
        self._timestamp: datetime = datetime.utcnow()
        self._frame_number: int = 0
        self._detections: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def update(
        self,
        frame: np.ndarray,
        fps: float = 0.0,
        detections: Optional[List[Dict[str, Any]]] = None,
        frame_number: int = 0,
    ):
        """Update the buffer with a new frame and metadata."""
        with self._lock:
            self._frame = frame.copy()
            self._fps = fps
            self._timestamp = datetime.utcnow()
            self._frame_number = frame_number
            self._detections = detections or []

    def get(self) -> Tuple[Optional[np.ndarray], float]:
        """Get the current frame and FPS (legacy interface)."""
        with self._lock:
            if self._frame is None:
                return None, 0.0
            return self._frame.copy(), self._fps

    def get_full(self) -> Optional[FrameData]:
        """Get full frame data with all metadata."""
        with self._lock:
            if self._frame is None:
                return None
            return FrameData(
                frame=self._frame.copy(),
                fps=self._fps,
                timestamp=self._timestamp,
                frame_number=self._frame_number,
                detections=self._detections.copy(),
            )

    def get_detections(self) -> List[Dict[str, Any]]:
        """Get the latest detections."""
        with self._lock:
            return self._detections.copy()

    @property
    def has_frame(self) -> bool:
        """Check if buffer has a frame."""
        with self._lock:
            return self._frame is not None

    @property
    def fps(self) -> float:
        """Get current FPS."""
        with self._lock:
            return self._fps

    @property
    def frame_number(self) -> int:
        """Get current frame number."""
        with self._lock:
            return self._frame_number
