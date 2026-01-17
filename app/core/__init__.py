"""Core business logic for safety video analytics."""

from .frame_buffer import FrameBuffer
from .deduplication import ViolationDeduplicator
from .event_processor import EventProcessor, event_processor
from .camera_manager import CameraManager, camera_manager

__all__ = [
    "FrameBuffer",
    "ViolationDeduplicator",
    "EventProcessor",
    "event_processor",
    "CameraManager",
    "camera_manager",
]
