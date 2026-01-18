"""Event processing for violation detection and storage."""

import time
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID
import numpy as np
from dataclasses import dataclass, field

from ..shared.db.database import async_session_factory
from ..shared.db.models import EventType, ViolationType, Severity
from ..shared.db.repositories.events import GlobalEventRepository
from ..shared.redis.pubsub import EventPublisher
from .config import config
from .vision import (
    CLASS_PERSON, CLASS_HARDHAT, CLASS_NO_HARDHAT,
    CLASS_SAFETY_VEST, CLASS_NO_SAFETY_VEST,
    head_region, box_overlap, get_centroid, point_in_polygon,
)
from .frame_publisher import ThumbnailGenerator


@dataclass
class ViolationTracker:
    """Tracks violations per camera for deduplication."""
    camera_id: UUID
    last_violations: Dict[str, float] = field(default_factory=dict)
    cooldown_seconds: int = config.COOLDOWN_SECONDS

    def should_emit(self, violation_key: str) -> bool:
        """Check if violation should be emitted (not in cooldown)."""
        now = time.time()
        last_time = self.last_violations.get(violation_key, 0)

        if now - last_time >= self.cooldown_seconds:
            self.last_violations[violation_key] = now
            return True
        return False


class EventProcessor:
    """
    Processes detections to identify violations and create events.

    Features:
    - PPE violation detection (hardhat, safety vest)
    - Zone intrusion detection
    - Event deduplication with cooldown
    - Thumbnail generation
    - Redis event publishing for SSE
    - Database persistence
    """

    def __init__(self, event_publisher: EventPublisher):
        self.event_publisher = event_publisher
        self.thumbnail_generator = ThumbnailGenerator()
        self.trackers: Dict[UUID, ViolationTracker] = {}

    def _get_tracker(self, camera_id: UUID) -> ViolationTracker:
        """Get or create a violation tracker for a camera."""
        if camera_id not in self.trackers:
            self.trackers[camera_id] = ViolationTracker(camera_id=camera_id)
        return self.trackers[camera_id]

    async def process_detections(
        self,
        camera_id: UUID,
        organization_id: UUID,
        detections: List[Dict[str, Any]],
        mode: str,
        polygon: Optional[List[List[int]]],
        frame: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Process detections and create events for violations.

        Args:
            camera_id: Camera identifier
            organization_id: Organization identifier
            detections: List of detection dicts from YOLO
            mode: Detection mode ("ppe" or "zone")
            polygon: Zone polygon for zone mode
            frame: Current frame for thumbnail generation

        Returns:
            List of created events
        """
        tracker = self._get_tracker(camera_id)
        events = []

        if mode == "ppe":
            events = await self._process_ppe_violations(
                camera_id, organization_id, detections, frame, tracker
            )
        elif mode == "zone":
            events = await self._process_zone_violations(
                camera_id, organization_id, detections, polygon, frame, tracker
            )

        return events

    async def _process_ppe_violations(
        self,
        camera_id: UUID,
        organization_id: UUID,
        detections: List[Dict[str, Any]],
        frame: np.ndarray,
        tracker: ViolationTracker,
    ) -> List[Dict[str, Any]]:
        """Process PPE violations (missing hardhat or safety vest)."""
        events = []

        # Separate detections by class
        persons = [d for d in detections if d["class_id"] == CLASS_PERSON]
        hardhats = [d for d in detections if d["class_id"] == CLASS_HARDHAT]
        no_hardhats = [d for d in detections if d["class_id"] == CLASS_NO_HARDHAT]
        safety_vests = [d for d in detections if d["class_id"] == CLASS_SAFETY_VEST]
        no_safety_vests = [d for d in detections if d["class_id"] == CLASS_NO_SAFETY_VEST]

        for person in persons:
            person_box = person["box"]
            head_box = head_region(person_box, frac=0.30)
            centroid = get_centroid(person_box)

            # Check for missing hardhat
            has_no_hardhat = any(
                box_overlap(head_box, d["box"]) > 0.1
                for d in no_hardhats
            )

            if has_no_hardhat:
                violation_key = f"no_hardhat_{centroid[0]//50}_{centroid[1]//50}"

                if tracker.should_emit(violation_key):
                    event = await self._create_event(
                        camera_id=camera_id,
                        organization_id=organization_id,
                        event_type=EventType.PPE_VIOLATION,
                        violation_type=ViolationType.NO_HARDHAT,
                        severity=Severity.HIGH,
                        confidence=person["confidence"],
                        bbox=person_box,
                        frame=frame,
                    )
                    if event:
                        events.append(event)

            # Check for missing safety vest
            has_no_vest = any(
                box_overlap(person_box, d["box"]) > 0.1
                for d in no_safety_vests
            )

            if has_no_vest:
                violation_key = f"no_vest_{centroid[0]//50}_{centroid[1]//50}"

                if tracker.should_emit(violation_key):
                    event = await self._create_event(
                        camera_id=camera_id,
                        organization_id=organization_id,
                        event_type=EventType.PPE_VIOLATION,
                        violation_type=ViolationType.NO_VEST,
                        severity=Severity.MEDIUM,
                        confidence=person["confidence"],
                        bbox=person_box,
                        frame=frame,
                    )
                    if event:
                        events.append(event)

        return events

    async def _process_zone_violations(
        self,
        camera_id: UUID,
        organization_id: UUID,
        detections: List[Dict[str, Any]],
        polygon: Optional[List[List[int]]],
        frame: np.ndarray,
        tracker: ViolationTracker,
    ) -> List[Dict[str, Any]]:
        """Process zone intrusion violations."""
        if not polygon:
            return []

        events = []
        persons = [d for d in detections if d["class_id"] == CLASS_PERSON]

        # Convert polygon format
        polygon_tuples = [(p[0], p[1]) for p in polygon]

        for person in persons:
            person_box = person["box"]
            centroid = get_centroid(person_box)

            if point_in_polygon(centroid, polygon_tuples):
                violation_key = f"zone_{centroid[0]//50}_{centroid[1]//50}"

                if tracker.should_emit(violation_key):
                    event = await self._create_event(
                        camera_id=camera_id,
                        organization_id=organization_id,
                        event_type=EventType.ZONE_VIOLATION,
                        violation_type=ViolationType.ZONE_BREACH,
                        severity=Severity.CRITICAL,
                        confidence=person["confidence"],
                        bbox=person_box,
                        frame=frame,
                    )
                    if event:
                        events.append(event)

        return events

    async def _create_event(
        self,
        camera_id: UUID,
        organization_id: UUID,
        event_type: EventType,
        violation_type: ViolationType,
        severity: Severity,
        confidence: float,
        bbox: Tuple[int, int, int, int],
        frame: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """Create and persist an event."""
        try:
            # Generate event ID
            import uuid
            event_id = uuid.uuid4()

            # Generate thumbnail
            thumbnail_path = self.thumbnail_generator.generate(
                frame=frame,
                event_id=str(event_id),
                bbox=bbox,
            )

            # Create event data
            event_data = {
                "id": event_id,
                "organization_id": organization_id,
                "camera_id": camera_id,
                "event_type": event_type,
                "violation_type": violation_type,
                "severity": severity,
                "confidence": confidence,
                "bbox_x1": bbox[0],
                "bbox_y1": bbox[1],
                "bbox_x2": bbox[2],
                "bbox_y2": bbox[3],
                "thumbnail_path": thumbnail_path,
            }

            # Persist to database
            async with async_session_factory() as session:
                repo = GlobalEventRepository(session)
                db_event = await repo.create_event(event_data)

            # Publish to Redis for SSE
            await self._publish_event(
                organization_id=organization_id,
                event_id=event_id,
                camera_id=camera_id,
                event_type=event_type,
                violation_type=violation_type,
                severity=severity,
                confidence=confidence,
                thumbnail_path=thumbnail_path,
            )

            print(
                f"[EVENT] {violation_type.value} detected - "
                f"camera={camera_id}, severity={severity.value}"
            )

            return event_data

        except Exception as e:
            print(f"[EVENT] Error creating event: {e}")
            return None

    async def _publish_event(
        self,
        organization_id: UUID,
        event_id: UUID,
        camera_id: UUID,
        event_type: EventType,
        violation_type: ViolationType,
        severity: Severity,
        confidence: float,
        thumbnail_path: Optional[str],
    ) -> None:
        """Publish event to Redis for SSE consumption."""
        from datetime import datetime

        event_data = {
            "id": str(event_id),
            "camera_id": str(camera_id),
            "event_type": event_type.value,
            "violation_type": violation_type.value,
            "severity": severity.value,
            "confidence": round(confidence, 2),
            "thumbnail_path": thumbnail_path,
            "created_at": datetime.utcnow().isoformat(),
        }

        await self.event_publisher.publish_event(
            str(organization_id),
            event_data,
        )

    async def close(self) -> None:
        """Clean up resources."""
        self.trackers.clear()
