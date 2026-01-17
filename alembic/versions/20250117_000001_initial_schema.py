"""Initial schema for Hard Hats Detection System.

Revision ID: 0001
Revises:
Create Date: 2025-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE plantype AS ENUM ('free', 'starter', 'professional', 'enterprise')")
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'manager', 'operator')")
    op.execute("CREATE TYPE camerastatus AS ENUM ('online', 'offline', 'error', 'connecting')")
    op.execute("CREATE TYPE sourcetype AS ENUM ('rtsp', 'file')")
    op.execute("CREATE TYPE detectionmode AS ENUM ('ppe', 'zone')")
    op.execute("CREATE TYPE eventtype AS ENUM ('ppe_violation', 'zone_violation', 'system_alert')")
    op.execute("CREATE TYPE violationtype AS ENUM ('no_hardhat', 'no_vest', 'no_mask', 'zone_breach', 'other')")
    op.execute("CREATE TYPE severity AS ENUM ('low', 'medium', 'high', 'critical')")

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('plan', postgresql.ENUM('free', 'starter', 'professional', 'enterprise', name='plantype', create_type=False), nullable=False, server_default='free'),
        sa.Column('max_cameras', sa.Integer, nullable=False, server_default='5'),
        sa.Column('max_users', sa.Integer, nullable=False, server_default='3'),
        sa.Column('settings', postgresql.JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'manager', 'operator', name='userrole', create_type=False), nullable=False, server_default='operator'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('organization_id', 'email', name='uq_users_org_email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])

    # Create cameras table
    op.create_table(
        'cameras',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('zone', sa.String(255), nullable=True),
        sa.Column('source_type', postgresql.ENUM('rtsp', 'file', name='sourcetype', create_type=False), nullable=False, server_default='file'),
        sa.Column('rtsp_url', sa.String(512), nullable=True),
        sa.Column('credentials_encrypted', sa.Text, nullable=True),
        sa.Column('placeholder_video', sa.String(512), nullable=True),
        sa.Column('use_placeholder', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('inference_width', sa.Integer, nullable=False, server_default='640'),
        sa.Column('inference_height', sa.Integer, nullable=False, server_default='640'),
        sa.Column('target_fps', sa.Float, nullable=False, server_default='0.5'),
        sa.Column('position_x', sa.Integer, nullable=False, server_default='0'),
        sa.Column('position_y', sa.Integer, nullable=False, server_default='0'),
        sa.Column('detection_mode', postgresql.ENUM('ppe', 'zone', name='detectionmode', create_type=False), nullable=False, server_default='ppe'),
        sa.Column('zone_polygon', postgresql.JSONB, nullable=True),
        sa.Column('confidence_threshold', sa.Float, nullable=False, server_default='0.25'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('status', postgresql.ENUM('online', 'offline', 'error', 'connecting', name='camerastatus', create_type=False), nullable=False, server_default='offline'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_cameras_organization_id', 'cameras', ['organization_id'])
    op.create_index('ix_cameras_status', 'cameras', ['status'])

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', postgresql.ENUM('ppe_violation', 'zone_violation', 'system_alert', name='eventtype', create_type=False), nullable=False),
        sa.Column('violation_type', postgresql.ENUM('no_hardhat', 'no_vest', 'no_mask', 'zone_breach', 'other', name='violationtype', create_type=False), nullable=True),
        sa.Column('severity', postgresql.ENUM('low', 'medium', 'high', 'critical', name='severity', create_type=False), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('bbox_x1', sa.Integer, nullable=True),
        sa.Column('bbox_y1', sa.Integer, nullable=True),
        sa.Column('bbox_x2', sa.Integer, nullable=True),
        sa.Column('bbox_y2', sa.Integer, nullable=True),
        sa.Column('thumbnail_path', sa.String(512), nullable=True),
        sa.Column('acknowledged', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_events_organization_id', 'events', ['organization_id'])
    op.create_index('ix_events_camera_id', 'events', ['camera_id'])
    op.create_index('ix_events_created_at', 'events', ['created_at'])
    op.create_index('ix_events_severity', 'events', ['severity'])
    op.create_index('ix_events_acknowledged', 'events', ['acknowledged'])

    # Create daily_stats table
    op.create_table(
        'daily_stats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=True),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('total_violations', sa.Integer, nullable=False, server_default='0'),
        sa.Column('no_hardhat_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('no_vest_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('zone_breach_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('frames_processed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('organization_id', 'camera_id', 'date', name='uq_daily_stats_org_camera_date'),
    )
    op.create_index('ix_daily_stats_organization_id', 'daily_stats', ['organization_id'])
    op.create_index('ix_daily_stats_date', 'daily_stats', ['date'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_audit_logs_organization_id', 'audit_logs', ['organization_id'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # Create event_tracking table for deduplication
    op.create_table(
        'event_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('violation_key', sa.String(255), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('camera_id', 'violation_key', name='uq_event_tracking_camera_key'),
    )
    op.create_index('ix_event_tracking_camera_id', 'event_tracking', ['camera_id'])
    op.create_index('ix_event_tracking_last_seen', 'event_tracking', ['last_seen'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('event_tracking')
    op.drop_table('audit_logs')
    op.drop_table('daily_stats')
    op.drop_table('events')
    op.drop_table('cameras')
    op.drop_table('users')
    op.drop_table('organizations')

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS severity")
    op.execute("DROP TYPE IF EXISTS violationtype")
    op.execute("DROP TYPE IF EXISTS eventtype")
    op.execute("DROP TYPE IF EXISTS detectionmode")
    op.execute("DROP TYPE IF EXISTS sourcetype")
    op.execute("DROP TYPE IF EXISTS camerastatus")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS plantype")
