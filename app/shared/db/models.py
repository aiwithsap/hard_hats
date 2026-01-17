"""SQLAlchemy ORM models with multi-tenancy support."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Date,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# Enums

class UserRole(str, PyEnum):
    """User role within an organization."""
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"


class CameraStatus(str, PyEnum):
    """Camera operational status."""
    online = "online"
    offline = "offline"
    error = "error"
    connecting = "connecting"


class SourceType(str, PyEnum):
    """Camera source type."""
    rtsp = "rtsp"
    file = "file"


class DetectionMode(str, PyEnum):
    """Detection mode for camera."""
    ppe = "ppe"
    zone = "zone"


class EventType(str, PyEnum):
    """Type of event."""
    PPE_VIOLATION = "ppe_violation"
    ZONE_VIOLATION = "zone_violation"
    SYSTEM_ALERT = "system_alert"


class ViolationType(str, PyEnum):
    """Type of safety violation."""
    NO_HARDHAT = "no_hardhat"
    NO_VEST = "no_vest"
    NO_MASK = "no_mask"
    ZONE_BREACH = "zone_breach"
    OTHER = "other"


class Severity(str, PyEnum):
    """Event severity level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PlanType(str, PyEnum):
    """Organization subscription plan."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# Models

class Organization(Base):
    """Organization (tenant) for multi-tenancy."""
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType, values_callable=lambda x: [e.value for e in x]),
        default=PlanType.FREE, nullable=False
    )
    max_cameras: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera", back_populates="organization", cascade="all, delete-orphan"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="organization", cascade="all, delete-orphan"
    )
    daily_stats: Mapped[List["DailyStat"]] = relationship(
        "DailyStat", back_populates="organization", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="organization", cascade="all, delete-orphan"
    )


class User(Base):
    """User account within an organization."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.OPERATOR, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="users"
    )
    acknowledged_events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="acknowledged_by_user", foreign_keys="Event.acknowledged_by"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_user_org_email"),
        Index("ix_users_email", "email"),
        Index("ix_users_org_id", "organization_id"),
    )


class Camera(Base):
    """Camera configuration for an organization."""
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone: Mapped[str] = mapped_column(String(100), default="Common", nullable=False)

    # Source configuration
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, values_callable=lambda x: [e.value for e in x]),
        default=SourceType.file, nullable=False
    )
    rtsp_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    placeholder_video: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    use_placeholder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Processing settings
    inference_width: Mapped[int] = mapped_column(Integer, default=640, nullable=False)
    inference_height: Mapped[int] = mapped_column(Integer, default=640, nullable=False)
    target_fps: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)

    # Floor plan position (0-100 percentage)
    position_x: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    position_y: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)

    # Detection mode
    detection_mode: Mapped[DetectionMode] = mapped_column(
        Enum(DetectionMode, values_callable=lambda x: [e.value for e in x]),
        default=DetectionMode.ppe, nullable=False
    )
    zone_polygon: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[CameraStatus] = mapped_column(
        Enum(CameraStatus, values_callable=lambda x: [e.value for e in x]),
        default=CameraStatus.offline, nullable=False
    )
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="cameras"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="camera", cascade="all, delete-orphan"
    )
    daily_stats: Mapped[List["DailyStat"]] = relationship(
        "DailyStat", back_populates="camera", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cameras_org_id", "organization_id"),
        Index("ix_cameras_status", "status"),
    )


class Event(Base):
    """Detection or violation event."""
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )

    # Event details
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    violation_type: Mapped[Optional[ViolationType]] = mapped_column(
        Enum(ViolationType, values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, values_callable=lambda x: [e.value for e in x]),
        default=Severity.MEDIUM, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Bounding box
    bbox_x1: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_y1: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_x2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_y2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Media
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    frame_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Acknowledgment
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="events"
    )
    camera: Mapped["Camera"] = relationship(
        "Camera", back_populates="events"
    )
    acknowledged_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="acknowledged_events", foreign_keys=[acknowledged_by]
    )

    __table_args__ = (
        Index("ix_events_org_id", "organization_id"),
        Index("ix_events_camera_id", "camera_id"),
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_type", "event_type", "violation_type"),
    )


class EventTracking(Base):
    """Event deduplication tracking."""
    __tablename__ = "event_tracking"

    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    track_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        Index("ix_tracking_last_seen", "last_seen"),
    )


class DailyStat(Base):
    """Daily statistics aggregation."""
    __tablename__ = "daily_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    camera_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True
    )
    date: Mapped[datetime] = mapped_column(Date, nullable=False)

    # Counts
    total_violations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    no_hardhat_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    no_vest_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    zone_breach_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frames_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="daily_stats"
    )
    camera: Mapped[Optional["Camera"]] = relationship(
        "Camera", back_populates="daily_stats"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "camera_id", "date", name="uq_daily_stats"),
        Index("ix_daily_stats_org_date", "organization_id", "date"),
    )


class AuditLog(Base):
    """Audit log for tracking user actions."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="audit_logs"
    )

    __table_args__ = (
        Index("ix_audit_logs_org_id", "organization_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
