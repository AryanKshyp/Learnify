"""Layer 2 data contracts — BUILD_SPEC.md C.5 (knowledge state), C.6 (session history).

Both models are frozen. Knowledge state changes only by the engine producing a *new* value
from a validated Schema B, never by something mutating a record in place; making that a
type-level guarantee removes a whole class of accidental-write bug before it can happen.

Nothing here computes anything. Every derived field is stored exactly as the engine (Stage 3)
hands it over, and carries its cold default until then.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Score = Annotated[float, Field(ge=0.0, le=1.0)]

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class Status(StrEnum):
    """The status ladder — DERIVED by the engine, never user-set, never stored.

    Layer 2 owns the vocabulary; the engine owns the value. The thresholds that produce it live
    in CALC_ENGINE_SPEC.md §13 and are applied at Stage 3, and the result lives in
    `EngineSnapshot.status` rather than on `KnowledgeState` — status is a function of retention
    and effective mastery, so it changes with the clock even when no evidence has. A cold node
    is `unassessed` because it has no evidence, not because anyone chose that.
    """

    UNASSESSED = "unassessed"
    LEARNING = "learning"
    PRACTICED = "practiced"
    RETAINED = "retained"
    MASTERED = "mastered"


class KnowledgeState(BaseModel):
    """C.5 — the user's state for one curriculum node.

    Field groups, so the intent survives:

    * **Evidence** — `intrinsic_mastery` (M). What the user actually knows. NEVER modified by
      prerequisites, decay, or time. This is the governing invariant of the whole system.
    * **Forgetting** — `stability` (S), `difficulty` (D), `next_review_at`.
    * **Evidence quality** — `assessment_variance_raw` (σ²_raw), `engine_confidence` (C),
      `session_count`, `observation_mean` (μ). Engine-owned; `llm_confidence` never dominates.

    **Derived values are deliberately absent.** `effective_mastery`, `retention`, `is_frontier`,
    `critical_path_value`, `leverage`, `current_importance`, `learning_cost` and `status` are
    NOT stored here. Every one of them is a function of the clock — retention decays by the
    hour, and effective mastery and status decay with it — so a stored copy is wrong the moment
    it is written and drifts further every hour after. They live in `EngineSnapshot`, which is
    recomputed per request from evidence, and that is the only place they exist.

    What remains is exactly the evidence the engine needs to reproduce them. C.5 originally
    specified all of them as stored columns; see PROJECT_STATE.md issue #17 for why that was
    a cache nothing read.
    """

    model_config = _FROZEN

    node_id: str

    # evidence — never touched by prerequisites, decay, or time
    intrinsic_mastery: Score = 0.0

    # forgetting
    stability: float | None = Field(default=None, gt=0.0)  # days; None until first session
    difficulty: Score | None = None  # defaults by depth tier at Stage 3

    # evidence quality (engine-owned)
    #: σ²_raw — running variance of observed ability, in the engine's own units, UNBOUNDED.
    #:
    #: Stored raw rather than normalised (changed 2026-09-16). σ² is EWMA state: the next
    #: session's update needs the previous raw value back. Persisting the 0..1 form meant
    #: dividing by `variance_normalizer` and clamping on write, then rescaling on read, which
    #: coupled two things that should not be coupled — the engine had to know the storage
    #: format, and `variance_normalizer` was retroactive, silently reinterpreting every row
    #: already written the moment it was retuned.
    #:
    #: At the shipped κ = 0.5 the EWMA ceiling is ≈0.0625, below the 0.10 normalizer, so the
    #: clamp never actually fired and nothing stored was ever truncated. It was a latent trap
    #: rather than a live bug: one change to κ or the normalizer and the loss becomes silent.
    #: The 0..1 lens is derived on read; see `engine.observation.normalized_variance` and
    #: `EngineSnapshot.variance`.
    assessment_variance_raw: float = Field(default=0.0, ge=0.0)
    engine_confidence: Score = 0.0
    session_count: int = Field(default=0, ge=0)

    #: μ — running mean of observed session ability.
    #:
    #: DOCUMENTED EXTENSION TO C.5. CALC_ENGINE_SPEC.md §4 maintains μ as EWMA state alongside
    #: σ², but the §16 field-addition list names only `assessment_variance`. Without persisting
    #: μ the variance calculation silently restarts every session, so every assessment would
    #: look perfectly consistent with itself and σ² would never reflect real disagreement
    #: between sessions. Stored rather than replayed because replay would mean re-running the
    #: whole history on every ingest.
    observation_mean: Score = 0.0

    last_assessed_at: datetime | None = None
    next_review_at: datetime | None = None

    last_gaps: tuple[str, ...] = ()
    schema_version: int = 1

    @classmethod
    def cold(cls, node_id: str) -> KnowledgeState:
        """The ground truth for a node with no evidence at all.

        Explicitly *not* "mastery unknown" — a node nobody has been assessed on contributes
        zero, so readiness reflects the absence of evidence rather than assuming competence.
        Its status is `unassessed`, but the engine derives that from `session_count == 0`
        rather than reading it from here.
        """
        return cls(node_id=node_id)

    @property
    def is_assessed(self) -> bool:
        return self.session_count > 0

    def replace(self, **changes: Any) -> KnowledgeState:
        """A new state with `changes` applied, revalidated. The original is untouched.

        Deliberately not `model_copy(update=...)`, which is what this used to be.
        `model_copy` writes straight into the instance without validating: it accepted unknown
        field names as phantom attributes and let out-of-range scores through, so
        `replace(intrinsic_mastery=99.0)` produced a `Score` of 99.0 and `replace(status=...)`
        silently attached a field this model no longer has.

        That matters because `replace` is the *only* way state is ever written — Layer 4 builds
        every post-session record with it. Validation here is the boundary that made
        `extra="forbid"` and the `Score` bounds mean something; without it the sole check on an
        engine-produced value was a Postgres constraint the in-memory repository does not have.
        """
        return self.model_validate({**self.model_dump(), **changes})


class SessionRecord(BaseModel):
    """C.6 — one assessment session. Append-only.

    `schema_a` and `schema_b` are stored verbatim as opaque mappings: Layer 2's job is to keep
    the evidence, and Stage 4 owns their validation. Storing them whole is what makes state
    reproducible by replay — the raw evidence survives even if the engine's formulas change.

    `mastery_before` / `mastery_after` snapshot intrinsic mastery around the update, so an
    audit can answer "what did this session actually change?" without re-running anything.
    """

    model_config = _FROZEN

    session_id: UUID
    node_id: str
    role_context: str

    created_at: datetime  # when Schema A was generated
    completed_at: datetime | None = None  # when Schema B was ingested

    schema_a: dict[str, Any] = Field(default_factory=dict)
    schema_b: dict[str, Any] | None = None

    mastery_before: Score = 0.0
    mastery_after: Score = 0.0

    computation_trace: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1

    @property
    def is_complete(self) -> bool:
        """True once a Schema B has been ingested for this session."""
        return self.schema_b is not None and self.completed_at is not None


class DocumentRecord(BaseModel):
    """One document the user wants to prepare for, with its extraction kept verbatim.

    Only the *extraction* is stored — never the computed plan. A plan is a function of the
    extraction and the user's current mastery, and mastery moves every time they assess
    something. Storing the plan would freeze it at the moment of ingestion, so reopening a
    paper three weeks later would show a readiness number that stopped being true the day
    after it was written. Recomputing on every read is cheap and is the only way the readiness
    number stays honest.

    The document itself is never stored, and never uploaded here: KnowledgeOS holds what the
    document *requires*, not its contents.
    """

    model_config = _FROZEN

    document_id: UUID
    title: str
    kind: str
    source: str | None = None
    summary: str = ""

    created_at: datetime

    #: The Schema D payload exactly as validated, so a plan can always be replayed and
    #: audited against what the extraction actually claimed.
    extraction: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1

