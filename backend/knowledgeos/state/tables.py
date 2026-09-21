"""SQLAlchemy table definitions for Layer 2.

Storage representation only. `BUILD_SPEC.md` Part C is explicit that tables are an
implementation detail chosen here, but they must round-trip the contracts losslessly — so every
*stored* C.5 and C.6 field has a column, and the Pydantic models remain the source of truth for
shape and validation. C.5's derived values are not stored at all; see `knowledge_state` below.

Postgres rather than SQLite because the deployment target is Supabase. That choice pays off
directly here: `jsonb` stores the Schema A/B payloads and computation traces natively and makes
them queryable, and `timestamptz` keeps the UTC contract at the database level instead of
trusting every caller.
"""

from __future__ import annotations

from sqlalchemy import (
    ARRAY,
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
    # Evidence only. Derived values (effective_mastery, retention, is_frontier,
    # critical_path_value, leverage, current_importance, learning_cost, status) are NOT columns
    # here: every one of them is a function of elapsed time, so a stored copy is stale the hour
    # after it is written. They are recomputed into `EngineSnapshot` on read.
    Column("intrinsic_mastery", Float, nullable=False, server_default="0"),
    # forgetting. NULL until the first session: a node with no evidence has no
    # forgetting curve, which is different from having a curve that is flat.
    Column("stability", Float, nullable=True),
    Column("difficulty", Float, nullable=True),
    # evidence quality (engine-owned)
    # σ²_raw, unbounded on purpose — it is EWMA state, not a score. See models.py.
    Column("assessment_variance_raw", Float, nullable=False, server_default="0"),
    Column("engine_confidence", Float, nullable=False, server_default="0"),
    Column("session_count", Integer, nullable=False, server_default="0"),
    Column("observation_mean", Float, nullable=False, server_default="0"),
    Column("last_assessed_at", DateTime(timezone=True), nullable=True),
    Column("next_review_at", DateTime(timezone=True), nullable=True),
    Column("last_gaps", ARRAY(Text), nullable=False, server_default="{}"),
    Column("schema_version", Integer, nullable=False, server_default="1"),
    # The engine clamps these, but a bad migration or a hand-written UPDATE should not be able
    # to introduce an out-of-range score that silently corrupts every downstream calculation.
    CheckConstraint(
        "intrinsic_mastery BETWEEN 0 AND 1 "
        "AND engine_confidence BETWEEN 0 AND 1 AND observation_mean BETWEEN 0 AND 1",
        name="ck_knowledge_state_scores_in_range",
    ),
    CheckConstraint("session_count >= 0", name="ck_knowledge_state_session_count"),
    # Not a 0..1 score, but a variance can never be negative.
    CheckConstraint(
        "assessment_variance_raw >= 0", name="ck_knowledge_state_variance_non_negative"
    ),
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


pending_sessions = Table(
    "pending_sessions",
    metadata,
    Column("session_id", UUID(as_uuid=True), primary_key=True),
    # Deliberately no foreign key to knowledge_state, unlike session_history. A session can be
    # opened on a node that has never been assessed, and that node has no state row until the
    # first Schema B lands — an FK here would refuse to open exactly the sessions that matter
    # most, the first one on every concept.
    Column("node_id", String, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # The Schema A verbatim, as it was handed to the external engine. Stored whole rather than
    # normalised because it is a contract payload: the Schema B that comes back is validated
    # against this exact object, so reassembling it from columns would risk a drift that the
    # round-trip check is supposed to catch.
    Column("schema_a", JSONB, nullable=False),
    Column("schema_version", Integer, nullable=False, server_default="1"),
)


document_plans = Table(
    "document_plans",
    metadata,
    Column("document_id", UUID(as_uuid=True), primary_key=True),
    Column("title", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("source", String, nullable=True),
    Column("summary", Text, nullable=False, server_default=""),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    # The Schema D verbatim. No column per concept: the plan is recomputed from this on every
    # read against current mastery, so normalising the concept list would buy nothing and
    # would quietly become a second, staler copy of the contract.
    Column("extraction", JSONB, nullable=False),
    Column("schema_version", Integer, nullable=False, server_default="1"),
)

