"""store raw assessment variance

Revision ID: e7412ab9cc05
Revises: d5b90c4a1e73
Create Date: 2026-09-16 00:00:00.000000

σ² is EWMA state: each session's update needs the previous *raw* value back. It was persisted
in the 0..1 form — `raw / variance_normalizer`, clamped — which made `variance_normalizer`
retroactive: retuning it silently reinterpreted every row already written. The column now holds
the engine's own unbounded value and the 0..1 form is derived on read.

Existing rows are rescaled by the normalizer in force when they were written (0.10). That
recovers the true raw value exactly for every value below the clamp, which at the shipped
κ = 0.5 is all of them — the EWMA ceiling is ≈0.0625, so no stored value ever saturated. A row
sitting at exactly 1.0 would be one that had, and is not recoverable; none exist.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7412ab9cc05'
down_revision: str | Sequence[str] | None = 'd5b90c4a1e73'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The value in force while the old column was being written. Hard-coded rather than imported
#: from engine config: a migration must mean the same thing forever, and that constant is a
#: [TUNABLE] which may well have moved on by the time anyone runs this.
VARIANCE_NORMALIZER_AT_WRITE_TIME = 0.10


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        'ck_knowledge_state_scores_in_range', 'knowledge_state', type_='check'
    )
    op.alter_column(
        'knowledge_state', 'assessment_variance', new_column_name='assessment_variance_raw'
    )
    op.execute(
        'UPDATE knowledge_state SET assessment_variance_raw = '
        f'assessment_variance_raw * {VARIANCE_NORMALIZER_AT_WRITE_TIME}'
    )
    op.create_check_constraint(
        'ck_knowledge_state_scores_in_range',
        'knowledge_state',
        'intrinsic_mastery BETWEEN 0 AND 1 '
        'AND engine_confidence BETWEEN 0 AND 1 AND observation_mean BETWEEN 0 AND 1',
    )
    op.create_check_constraint(
        'ck_knowledge_state_variance_non_negative',
        'knowledge_state',
        'assessment_variance_raw >= 0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_knowledge_state_variance_non_negative', 'knowledge_state', type_='check'
    )
    op.drop_constraint(
        'ck_knowledge_state_scores_in_range', 'knowledge_state', type_='check'
    )
    op.execute(
        'UPDATE knowledge_state SET assessment_variance_raw = least('
        f'assessment_variance_raw / {VARIANCE_NORMALIZER_AT_WRITE_TIME}, 1.0)'
    )
    op.alter_column(
        'knowledge_state', 'assessment_variance_raw', new_column_name='assessment_variance'
    )
    op.create_check_constraint(
        'ck_knowledge_state_scores_in_range',
        'knowledge_state',
        'intrinsic_mastery BETWEEN 0 AND 1 AND assessment_variance BETWEEN 0 AND 1 '
        'AND engine_confidence BETWEEN 0 AND 1 AND observation_mean BETWEEN 0 AND 1',
    )
