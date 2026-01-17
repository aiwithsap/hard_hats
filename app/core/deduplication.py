"""Violation deduplication using spatial-temporal hashing."""

from hashlib import md5
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import threading


@dataclass
class DetectionSignature:
    """Signature for a detection used in deduplication."""
    camera_id: str
    class_id: int  # Violation class (e.g., CLASS_NO_HARDHAT)
    bbox_region: str  # Quantized region: "R1C2" (row 1, col 2)

    def hash(self) -> str:
        """Generate hash for this signature."""
        data = f"{self.camera_id}:{self.class_id}:{self.bbox_region}"
        return md5(data.encode()).hexdigest()[:16]


class ViolationDeduplicator:
    """
    Prevents duplicate violation events using spatial-temporal deduplication.

    Strategy:
    1. Quantize bbox into grid regions (3x3 by default)
    2. Create signature from (camera_id, violation_type, region)
    3. Track last occurrence of each signature
    4. Suppress duplicates within cooldown period (default: 30s)
    5. Allow re-trigger if same person returns after leaving
    """

    def __init__(
        self,
        cooldown_seconds: int = 30,
        grid_size: int = 3,
    ):
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.grid_size = grid_size

        # {signature_hash: (last_seen, event_id)}
        self._recent_violations: Dict[str, Tuple[datetime, str]] = {}
        self._lock = threading.Lock()

    def quantize_bbox(
        self,
        bbox: Tuple[int, int, int, int],
        frame_size: Tuple[int, int],
    ) -> str:
        """Convert bbox to grid region identifier."""
        x1, y1, x2, y2 = bbox
        w, h = frame_size

        # Get center point
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        # Quantize to grid cell
        col = min(int(cx / w * self.grid_size), self.grid_size - 1)
        row = min(int(cy / h * self.grid_size), self.grid_size - 1)

        return f"R{row}C{col}"

    def should_create_event(
        self,
        camera_id: str,
        violation_type: int,
        bbox: Tuple[int, int, int, int],
        frame_size: Tuple[int, int],
    ) -> Tuple[bool, str]:
        """
        Determine if this detection should create a new event.

        Returns:
            (should_create, signature_hash)
        """
        now = datetime.utcnow()

        # Create signature
        region = self.quantize_bbox(bbox, frame_size)
        sig = DetectionSignature(camera_id, violation_type, region)
        sig_hash = sig.hash()

        with self._lock:
            # Check recent violations
            if sig_hash in self._recent_violations:
                last_seen, event_id = self._recent_violations[sig_hash]

                if now - last_seen < self.cooldown:
                    # Update last seen but don't create new event
                    self._recent_violations[sig_hash] = (now, event_id)
                    return False, sig_hash

        # New violation - will create event
        return True, sig_hash

    def register_event(self, sig_hash: str, event_id: str):
        """Register a new event for tracking."""
        with self._lock:
            self._recent_violations[sig_hash] = (datetime.utcnow(), event_id)

    def cleanup_stale(self, max_age_seconds: int = 300):
        """Remove stale entries older than max_age."""
        cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)

        with self._lock:
            stale_keys = [
                k for k, (ts, _) in self._recent_violations.items()
                if ts < cutoff
            ]
            for k in stale_keys:
                del self._recent_violations[k]

    @property
    def active_signatures(self) -> int:
        """Get count of active signatures being tracked."""
        with self._lock:
            return len(self._recent_violations)
