"""Database repositories for CRUD operations."""

from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from .database import get_db
from ..models.event import Event, EventType, ViolationType, Severity


class EventRepository:
    """Repository for event CRUD operations."""

    def __init__(self):
        self.db = get_db()

    def create(self, event: Event) -> Event:
        """Insert a new event."""
        bbox = event.bbox or (None, None, None, None)

        with self.db.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO events (
                    id, camera_id, camera_name, event_type, violation_type,
                    severity, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                    thumbnail_path, frame_number, timestamp, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.camera_id,
                    event.camera_name,
                    event.event_type.value,
                    event.violation_type.value if event.violation_type else None,
                    event.severity.value,
                    event.confidence,
                    bbox[0], bbox[1], bbox[2], bbox[3],
                    event.thumbnail_path,
                    event.frame_number,
                    event.timestamp.isoformat(),
                    1 if event.acknowledged else 0,
                ),
            )
        return event

    def get_by_id(self, event_id: str) -> Optional[Event]:
        """Get event by ID."""
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
        return None

    def get_all(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        violation_type: Optional[str] = None,
        severity: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Event], int]:
        """Get events with filtering and pagination."""
        conditions = []
        params = []

        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if violation_type:
            conditions.append("violation_type = ?")
            params.append(violation_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())
        if until:
            conditions.append("timestamp <= ?")
            params.append(until.isoformat())
        if acknowledged is not None:
            conditions.append("acknowledged = ?")
            params.append(1 if acknowledged else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self.db.get_cursor() as cursor:
            # Get total count
            cursor.execute(
                f"SELECT COUNT(*) FROM events WHERE {where_clause}",
                params,
            )
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor.execute(
                f"""
                SELECT * FROM events
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            )
            rows = cursor.fetchall()

        return [self._row_to_event(row) for row in rows], total

    def acknowledge(self, event_id: str) -> bool:
        """Mark event as acknowledged."""
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "UPDATE events SET acknowledged = 1 WHERE id = ?",
                (event_id,),
            )
            return cursor.rowcount > 0

    def delete(self, event_id: str) -> bool:
        """Delete event by ID."""
        with self.db.get_cursor() as cursor:
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            return cursor.rowcount > 0

    def cleanup_old(self, days: int = 7) -> int:
        """Delete events older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.db.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            return cursor.rowcount

    def _row_to_event(self, row) -> Event:
        """Convert database row to Event object."""
        bbox = None
        if row["bbox_x1"] is not None:
            # Convert bbox values to int (handles bytes/string/int types)
            def to_int(val):
                if val is None:
                    return None
                if isinstance(val, int):
                    return val
                if isinstance(val, bytes):
                    # Handle bytes stored by SQLite
                    return int.from_bytes(val[:4], byteorder='little', signed=False)
                return int(val)
            bbox = (to_int(row["bbox_x1"]), to_int(row["bbox_y1"]),
                    to_int(row["bbox_x2"]), to_int(row["bbox_y2"]))

        return Event(
            id=row["id"],
            camera_id=row["camera_id"],
            camera_name=row["camera_name"],
            event_type=EventType(row["event_type"]),
            violation_type=ViolationType(row["violation_type"]) if row["violation_type"] else None,
            severity=Severity(row["severity"]),
            confidence=row["confidence"] or 0.0,
            bbox=bbox,
            thumbnail_path=row["thumbnail_path"],
            frame_number=row["frame_number"] or 0,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            acknowledged=bool(row["acknowledged"]),
        )


class StatsRepository:
    """Repository for statistics operations."""

    def __init__(self):
        self.db = get_db()

    def get_violations_today(self) -> int:
        """Get count of violations today."""
        today = datetime.utcnow().date().isoformat()
        with self.db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM events
                WHERE event_type = 'violation'
                AND date(timestamp) = ?
                """,
                (today,),
            )
            return cursor.fetchone()[0]

    def get_violations_yesterday(self) -> int:
        """Get count of violations yesterday."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        with self.db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM events
                WHERE event_type = 'violation'
                AND date(timestamp) = ?
                """,
                (yesterday,),
            )
            return cursor.fetchone()[0]

    def get_daily_stats(self, days: int = 7) -> List[dict]:
        """Get daily violation statistics."""
        since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()

        with self.db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    date(timestamp) as date,
                    COUNT(*) as total_violations,
                    SUM(CASE WHEN violation_type = 'no_hardhat' THEN 1 ELSE 0 END) as no_hardhat_count,
                    SUM(CASE WHEN violation_type = 'no_vest' THEN 1 ELSE 0 END) as no_vest_count,
                    SUM(CASE WHEN violation_type = 'zone_breach' THEN 1 ELSE 0 END) as zone_breach_count
                FROM events
                WHERE event_type = 'violation'
                AND date(timestamp) >= ?
                GROUP BY date(timestamp)
                ORDER BY date(timestamp)
                """,
                (since,),
            )
            rows = cursor.fetchall()

        return [
            {
                "date": row["date"],
                "total_violations": row["total_violations"],
                "no_hardhat_count": row["no_hardhat_count"],
                "no_vest_count": row["no_vest_count"],
                "zone_breach_count": row["zone_breach_count"],
            }
            for row in rows
        ]

    def get_stats_by_camera(self) -> List[dict]:
        """Get violation counts by camera."""
        with self.db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    camera_id,
                    camera_name,
                    COUNT(*) as violation_count
                FROM events
                WHERE event_type = 'violation'
                AND date(timestamp) = date('now')
                GROUP BY camera_id
                ORDER BY violation_count DESC
                """,
            )
            rows = cursor.fetchall()

        return [
            {
                "camera_id": row["camera_id"],
                "camera_name": row["camera_name"],
                "violation_count": row["violation_count"],
            }
            for row in rows
        ]
