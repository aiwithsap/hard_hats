"""Event processing pipeline for violations and detections."""

import threading
from collections import deque
from datetime import datetime
from typing import Optional, List, Callable, Dict, Any, Tuple
from pathlib import Path
import cv2
import numpy as np

from ..models.event import Event, EventType, ViolationType, Severity
from ..models.camera import Camera
from ..db.repositories import EventRepository
from .deduplication import ViolationDeduplicator


# Class IDs from the YOLO model
CLASS_HARDHAT = 0
CLASS_NO_HARDHAT = 2
CLASS_NO_SAFETY_VEST = 4
CLASS_PERSON = 5
CLASS_SAFETY_VEST = 7


class EventProcessor:
    """
    Processes detections and generates events.

    Responsibilities:
    - Convert detections to events
    - Apply deduplication
    - Store events in database
    - Broadcast events via SSE
    - Save thumbnails
    """

    def __init__(
        self,
        thumbnail_dir: str = "data/thumbnails",
        max_live_events: int = 100,
        cooldown_seconds: int = 30,
    ):
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

        self._deduplicator = ViolationDeduplicator(cooldown_seconds=cooldown_seconds)
        self._event_repo = EventRepository()

        # Live events for real-time feed (in-memory)
        self._live_events: deque = deque(maxlen=max_live_events)
        self._live_lock = threading.Lock()

        # SSE subscribers
        self._subscribers: List[Callable[[Event], None]] = []
        self._subscribers_lock = threading.Lock()

        # Stats counters
        self._events_today = 0
        self._last_date = datetime.utcnow().date()

    def process_detections(
        self,
        camera: Camera,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        frame_number: int,
    ) -> List[Event]:
        """
        Process detections from a camera and generate events.

        Args:
            camera: Camera object
            frame: Current video frame
            detections: List of detection dicts from YOLO
            frame_number: Current frame number

        Returns:
            List of new events created
        """
        events = []
        frame_size = (frame.shape[1], frame.shape[0])

        # Find persons and their PPE status
        persons = [d for d in detections if d["class_id"] == CLASS_PERSON]
        no_hardhats = [d for d in detections if d["class_id"] == CLASS_NO_HARDHAT]
        no_vests = [d for d in detections if d["class_id"] == CLASS_NO_SAFETY_VEST]

        for person in persons:
            person_box = person["box"]

            # Check for no hardhat violation
            for no_hat in no_hardhats:
                if self._boxes_overlap(person_box, no_hat["box"], threshold=0.1):
                    event = self._try_create_violation(
                        camera=camera,
                        frame=frame,
                        frame_number=frame_number,
                        frame_size=frame_size,
                        violation_type=ViolationType.NO_HARDHAT,
                        bbox=person_box,
                        confidence=no_hat["confidence"],
                    )
                    if event:
                        events.append(event)
                    break

            # Check for no vest violation
            for no_vest in no_vests:
                if self._boxes_overlap(person_box, no_vest["box"], threshold=0.1):
                    event = self._try_create_violation(
                        camera=camera,
                        frame=frame,
                        frame_number=frame_number,
                        frame_size=frame_size,
                        violation_type=ViolationType.NO_VEST,
                        bbox=person_box,
                        confidence=no_vest["confidence"],
                    )
                    if event:
                        events.append(event)
                    break

        return events

    def process_zone_violation(
        self,
        camera: Camera,
        frame: np.ndarray,
        person_box: Tuple[int, int, int, int],
        frame_number: int,
        confidence: float,
    ) -> Optional[Event]:
        """Process a zone breach violation."""
        frame_size = (frame.shape[1], frame.shape[0])

        return self._try_create_violation(
            camera=camera,
            frame=frame,
            frame_number=frame_number,
            frame_size=frame_size,
            violation_type=ViolationType.ZONE_BREACH,
            bbox=person_box,
            confidence=confidence,
        )

    def _try_create_violation(
        self,
        camera: Camera,
        frame: np.ndarray,
        frame_number: int,
        frame_size: Tuple[int, int],
        violation_type: ViolationType,
        bbox: Tuple[int, int, int, int],
        confidence: float,
    ) -> Optional[Event]:
        """Try to create a violation event with deduplication."""
        # Map violation type to class ID for deduplication
        class_id_map = {
            ViolationType.NO_HARDHAT: CLASS_NO_HARDHAT,
            ViolationType.NO_VEST: CLASS_NO_SAFETY_VEST,
            ViolationType.ZONE_BREACH: -1,  # Special ID for zone violations
        }
        class_id = class_id_map.get(violation_type, -1)

        # Check deduplication
        should_create, sig_hash = self._deduplicator.should_create_event(
            camera_id=camera.id,
            violation_type=class_id,
            bbox=bbox,
            frame_size=frame_size,
        )

        if not should_create:
            return None

        # Determine severity
        severity = Severity.CRITICAL if confidence > 0.8 else Severity.MEDIUM

        # Create event
        event = Event(
            camera_id=camera.id,
            camera_name=camera.name,
            event_type=EventType.VIOLATION,
            violation_type=violation_type,
            severity=severity,
            confidence=confidence,
            bbox=bbox,
            frame_number=frame_number,
        )

        # Save thumbnail
        thumbnail_path = self._save_thumbnail(event.id, frame, bbox)
        event.thumbnail_path = str(thumbnail_path) if thumbnail_path else None

        # Register for deduplication
        self._deduplicator.register_event(sig_hash, event.id)

        # Store in database
        self._event_repo.create(event)

        # Add to live events
        with self._live_lock:
            self._live_events.appendleft(event)

        # Update stats
        self._update_stats()

        # Broadcast to subscribers
        self._broadcast(event)

        return event

    def _save_thumbnail(
        self,
        event_id: str,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        padding: int = 20,
    ) -> Optional[Path]:
        """Save a cropped thumbnail of the violation."""
        try:
            x1, y1, x2, y2 = bbox
            h, w = frame.shape[:2]

            # Add padding
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)

            # Crop and save
            thumbnail = frame[y1:y2, x1:x2]
            thumbnail_path = self.thumbnail_dir / f"{event_id}.jpg"
            cv2.imwrite(str(thumbnail_path), thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85])

            return thumbnail_path
        except Exception:
            return None

    def _boxes_overlap(
        self,
        box1: Tuple[int, int, int, int],
        box2: Tuple[int, int, int, int],
        threshold: float = 0.1,
    ) -> bool:
        """Check if two boxes overlap by at least threshold."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x1 >= x2 or y1 >= y2:
            return False

        intersection = (x2 - x1) * (y2 - y1)
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

        if box2_area == 0:
            return False

        return (intersection / box2_area) >= threshold

    def _update_stats(self):
        """Update daily stats counter."""
        today = datetime.utcnow().date()
        if today != self._last_date:
            self._events_today = 0
            self._last_date = today
        self._events_today += 1

    def subscribe(self, callback: Callable[[Event], None]):
        """Subscribe to new events."""
        with self._subscribers_lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Event], None]):
        """Unsubscribe from events."""
        with self._subscribers_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _broadcast(self, event: Event):
        """Broadcast event to all subscribers."""
        with self._subscribers_lock:
            for callback in self._subscribers:
                try:
                    callback(event)
                except Exception:
                    pass  # Don't let subscriber errors break the pipeline

    def get_live_events(self, limit: int = 50) -> List[Event]:
        """Get recent live events."""
        with self._live_lock:
            return list(self._live_events)[:limit]

    @property
    def events_today(self) -> int:
        """Get count of events today."""
        return self._events_today

    def cleanup(self):
        """Run cleanup tasks."""
        self._deduplicator.cleanup_stale()


# Global event processor instance
event_processor: Optional[EventProcessor] = None


def get_event_processor() -> EventProcessor:
    """Get or create the global event processor."""
    global event_processor
    if event_processor is None:
        event_processor = EventProcessor()
    return event_processor
