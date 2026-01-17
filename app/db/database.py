"""SQLite database connection and schema management."""

import sqlite3
import threading
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# Database path
DB_PATH = Path("data/db/events.db")


class Database:
    """Thread-safe SQLite database manager."""

    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self):
        """Ensure database directory exists."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @contextmanager
    def get_cursor(self):
        """Get a database cursor with automatic commit/rollback."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_schema(self):
        """Initialize database schema."""
        schema = """
        -- Events table (violations/detections)
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            camera_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            violation_type TEXT,
            severity TEXT DEFAULT 'warning',
            confidence REAL,
            bbox_x1 INTEGER,
            bbox_y1 INTEGER,
            bbox_x2 INTEGER,
            bbox_y2 INTEGER,
            thumbnail_path TEXT,
            frame_number INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged INTEGER DEFAULT 0
        );

        -- Event deduplication tracking
        CREATE TABLE IF NOT EXISTS event_tracking (
            camera_id TEXT NOT NULL,
            track_hash TEXT NOT NULL,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            event_id TEXT,
            PRIMARY KEY (camera_id, track_hash)
        );

        -- Daily stats aggregation
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT NOT NULL,
            camera_id TEXT,
            total_violations INTEGER DEFAULT 0,
            no_hardhat_count INTEGER DEFAULT 0,
            no_vest_count INTEGER DEFAULT 0,
            zone_breach_count INTEGER DEFAULT 0,
            PRIMARY KEY (date, camera_id)
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, violation_type);
        CREATE INDEX IF NOT EXISTS idx_tracking_last_seen ON event_tracking(last_seen);
        """

        with self.get_cursor() as cursor:
            cursor.executescript(schema)

    def close(self):
        """Close the database connection."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection


# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
