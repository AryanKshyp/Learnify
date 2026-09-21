"""drop derived knowledge state columns

Revision ID: d5b90c4a1e73
Revises: c3d81e5f07a2
Create Date: 2026-09-16 00:00:00.000000

Every column dropped here was a cache of an engine-derived value. Seven of the eight had no
reader at all — the API served them from `EngineSnapshot` — and all eight are functions of
elapsed time, so the stored copy was stale the hour after it was written. `EngineSnapshot`
is now the only place they exist.

Dropping them loses nothing: they are reproducible from the evidence columns that remain,
which is what the downgrade relies on. It restores the columns at their cold defaults, and
the next recompute re-derives the real values.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5b90c4a1e73'
down_revision: str | Sequence[str] | None = 'c3d81e5f07a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DERIVED = (
    'effective_mastery',
    'retention',
    'is_frontier',
    'critical_path_value',
    'leverage',
    'current_importance',
    'learning_cost',
    'status',
)


def upgrade() -> None:
    """Upgrade schema."""
    # the range check names two of the columns being dropped, so it goes first
    op.drop_constraint(
        'ck_knowledge_state_scores_in_range', 'knowledge_state', type_='check'
    )
    for column in DERIVED:
        op.drop_column('knowledge_state', column)
    op.create_check_constraint(
        'ck_knowledge_state_scores_in_range',
        'knowledge_state',
        'intrinsic_mastery BETWEEN 0 AND 1 AND assessment_variance BETWEEN 0 AND 1 '
        'AND engine_confidence BETWEEN 0 AND 1 AND observation_mean BETWEEN 0 AND 1',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_knowledge_state_scores_in_range', 'knowledge_state', type_='check'
    )
    op.add_column(
        'knowledge_state',
        sa.Column('effective_mastery', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('retention', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('is_frontier', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('critical_path_value', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('leverage', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('current_importance', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('learning_cost', sa.Float(), server_default='0', nullable=False),
    )
    op.add_column(
        'knowledge_state',
        sa.Column('status', sa.String(), server_default='unassessed', nullable=False),
    )
    op.create_check_constraint(
        'ck_knowledge_state_scores_in_range',
        'knowledge_state',
        'intrinsic_mastery BETWEEN 0 AND 1 AND effective_mastery BETWEEN 0 AND 1 '
        'AND retention BETWEEN 0 AND 1 AND assessment_variance BETWEEN 0 AND 1 '
        'AND engine_confidence BETWEEN 0 AND 1 AND observation_mean BETWEEN 0 AND 1',
    )
