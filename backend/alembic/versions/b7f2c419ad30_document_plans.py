"""document plans

Revision ID: b7f2c419ad30
Revises: 4a03a162964b
Create Date: 2026-09-15 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7f2c419ad30'
down_revision: str | Sequence[str] | None = '4a03a162964b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document_plans',
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('summary', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('extraction', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
        sa.PrimaryKeyConstraint('document_id'),
    )
    op.create_index(
        op.f('ix_document_plans_created_at'), 'document_plans', ['created_at'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_document_plans_created_at'), table_name='document_plans')
    op.drop_table('document_plans')
