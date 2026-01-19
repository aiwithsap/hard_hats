"""Add inference_enabled column to cameras table.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'cameras',
        sa.Column('inference_enabled', sa.Boolean, nullable=False, server_default='true')
    )


def downgrade() -> None:
    op.drop_column('cameras', 'inference_enabled')
