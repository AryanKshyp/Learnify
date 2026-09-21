"""pending sessions

Revision ID: c3d81e5f07a2
Revises: b7f2c419ad30
Create Date: 2026-09-16 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d81e5f07a2'
down_revision: str | Sequence[str] | None = 'b7f2c419ad30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pending_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('schema_a', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
        sa.PrimaryKeyConstraint('session_id'),
    )
    op.create_index(
        op.f('ix_pending_sessions_node_id'), 'pending_sessions', ['node_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_pending_sessions_node_id'), table_name='pending_sessions')
    op.drop_table('pending_sessions')
