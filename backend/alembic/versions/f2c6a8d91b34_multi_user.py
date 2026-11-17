"""multi-user: scope every table by user_id, add per-user LLM settings

Revision ID: f2c6a8d91b34
Revises: e7412ab9cc05
Create Date: 2026-11-18 00:00:00.000000

Existing rows are kept and assigned to the user ``local`` - the identity the application uses
when there is no authentication - so a single-user install upgrades in place and loses nothing.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'f2c6a8d91b34'
down_revision: str | Sequence[str] | None = 'e7412ab9cc05'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCAL = 'local'

# Every table the application owns. On Supabase, anything in the `public` schema is also exposed
# through its auto-generated REST API, which the PUBLIC anon key can call. Row level security
# with no policies denies that path entirely; the application is unaffected because it connects
# as the table owner, which bypasses RLS. Without this, anyone holding the (public) anon key
# could read every user's evidence and their encrypted API keys.
TABLES = (
    'knowledge_state', 'session_history', 'pending_sessions', 'document_plans',
    'user_llm_settings', 'alembic_version',
)


def upgrade() -> None:
    # session_history references knowledge_state, so drop that FK before touching the PK.
    op.drop_constraint('session_history_node_id_fkey', 'session_history', type_='foreignkey')

    op.add_column('knowledge_state', sa.Column(
        'user_id', sa.String(), server_default=LOCAL, nullable=False))
    op.drop_constraint('knowledge_state_pkey', 'knowledge_state', type_='primary')
    op.create_primary_key('knowledge_state_pkey', 'knowledge_state', ['user_id', 'node_id'])

    for table in ('session_history', 'pending_sessions', 'document_plans'):
        op.add_column(table, sa.Column(
            'user_id', sa.String(), server_default=LOCAL, nullable=False))
        op.create_index(op.f(f'ix_{table}_user_id'), table, ['user_id'], unique=False)

    op.create_foreign_key(
        'session_history_user_node_fkey', 'session_history', 'knowledge_state',
        ['user_id', 'node_id'], ['user_id', 'node_id'], ondelete='RESTRICT',
    )

    op.create_table(
        'user_llm_settings',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
    )

    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in TABLES:
        if table != 'user_llm_settings':
            op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
    op.drop_table('user_llm_settings')
    op.drop_constraint('session_history_user_node_fkey', 'session_history', type_='foreignkey')
    for table in ('document_plans', 'pending_sessions', 'session_history'):
        op.drop_index(op.f(f'ix_{table}_user_id'), table_name=table)
        op.drop_column(table, 'user_id')
    op.drop_constraint('knowledge_state_pkey', 'knowledge_state', type_='primary')
    op.drop_column('knowledge_state', 'user_id')
    op.create_primary_key('knowledge_state_pkey', 'knowledge_state', ['node_id'])
    op.create_foreign_key(
        'session_history_node_id_fkey', 'session_history', 'knowledge_state',
        ['node_id'], ['node_id'], ondelete='RESTRICT',
    )
