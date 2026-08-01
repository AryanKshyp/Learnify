"""SQLAlchemy table definitions for Layer 2.

Storage representation only. `BUILD_SPEC.md` Part C is explicit that tables are an
implementation detail chosen here, but they must round-trip the contracts losslessly — so every
C.5 and C.6 field has a column, and the Pydantic models remain the source of truth for shape
and validation.

Postgres rather than SQLite because the deployment target is Supabase. That choice pays off
directly here: `jsonb` stores the Schema A/B payloads and computation traces natively and makes
them queryable, and `timestamptz` keeps the UTC contract at the database level instead of
trusting every caller.
"""

from __future__ import annotations

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()


knowledge_state = Table(
    "knowledge_state",
    metadata,
    Column("node_id", String, primary_key=True),
    # evidence — never modified by prerequisites, decay, or time
    Column("intrinsic_mastery", Float, nullable=False, server_default="0"),
    # trust
    Column("effective_mastery", Float, nullable=False, server_default="0"),
    Column("retention", Float, nullable=False, server_default="0"),
    # forgetting. NULL until the first session: a node with no evidence has no
    # forgetting curve, which is different from having a curve that is flat.
    Column("stability", Float, nullable=True),
    Column("difficulty", Float, nullable=True),
    # evidence quality (engine-owned)
    Column("assessment_variance", Float, nullable=False, server_default="0"),
    Column("engine_confidence", Float, nullable=False, server_default="0"),
    Column("session_count", Integer, nullable=False, server_default="0"),
    Column("observation_mean", Float, nullable=False, server_default="0"),
    Column("last_assessed_at", DateTime(timezone=True), nullable=True),
    Column("next_review_at", DateTime(timezone=True), nullable=True),
    # position in the graph — recomputed every pass, cached here for reads
    Column("is_frontier", Boolean, nullable=False, server_default="false"),
    Column("critical_path_value", Float, nullable=False, server_default="0"),
    Column("leverage", Float, nullable=False, server_default="0"),
    Column("current_importance", Float, nullable=False, server_default="0"),
    Column("learning_cost", Float, nullable=False, server_default="0"),
    Column("status", String, nullable=False, server_default="unassessed"),
    Column("last_gaps", ARRAY(Text), nullable=False, server_default="{}"),
    Column("schema_version", Integer, nullable=False, server_default="1"),
    # The engine clamps these, but a bad migration or a hand-written UPDATE should not be able
    # to introduce an out-of-range score that silently corrupts every downstream calculation.
    CheckConstraint(
        "intrinsic_mastery BETWEEN 0 AND 1 AND effective_mastery BETWEEN 0 AND 1 "
        "AND retention BETWEEN 0 AND 1 AND assessment_variance BETWEEN 0 AND 1 "
        "AND engine_confidence BETWEEN 0 AND 1 AND observation_mean BETWEEN 0 AND 1",
        name="ck_knowledge_state_scores_in_range",
    ),
    CheckConstraint("session_count >= 0", name="ck_knowledge_state_session_count"),
    CheckConstraint(
        "stability IS NULL OR stability > 0", name="ck_knowledge_state_stability_positive"
    ),
)


session_history = Table(
    "session_history",
    metadata,
    Column("session_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "node_id",
        String,
        ForeignKey("knowledge_state.node_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("role_context", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("schema_a", JSONB, nullable=False),
    Column("schema_b", JSONB, nullable=True),
    Column("mastery_before", Float, nullable=False),
    Column("mastery_after", Float, nullable=False),
    Column("computation_trace", JSONB, nullable=False, server_default="{}"),
    Column("schema_version", Integer, nullable=False, server_default="1"),
    CheckConstraint(
        "mastery_before BETWEEN 0 AND 1 AND mastery_after BETWEEN 0 AND 1",
        name="ck_session_history_mastery_in_range",
    ),
)
