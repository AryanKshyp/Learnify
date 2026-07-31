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
    """C.5 `status` — DERIVED by the engine, never user-set.

    Layer 2 only stores it. The thresholds that produce it live in CALC_ENGINE_SPEC.md §13 and
    are applied at Stage 3; a cold node is `unassessed` because it has no evidence, not
    because anyone chose that.
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
    * **Trust** — `effective_mastery` (EM = M · R · PC). The only score reflecting time and
      prerequisites, and the one recommendations act on.
    * **Forgetting** — `retention` (R), `stability` (S), `next_review_at`.
    * **Evidence quality** — `assessment_variance` (σ²), `engine_confidence` (C),
      `session_count`. Engine-owned; `llm_confidence` never dominates these.
    * **Position in the graph** — `is_frontier`, `critical_path_value`, `leverage`,
      `current_importance`, `learning_cost`. Recomputed each pass, never authored.
    """

    model_config = _FROZEN

    node_id: str

    # evidence — never touched by prerequisites, decay, or time
    intrinsic_mastery: Score = 0.0

    # trust — the only score that reflects time and prerequisites
    effective_mastery: Score = 0.0

    # forgetting
    retention: Score = 0.0
    stability: float | None = Field(default=None, gt=0.0)  # days; None until first session
    difficulty: Score | None = None  # defaults by depth tier at Stage 3

    # evidence quality (engine-owned)
    assessment_variance: Score = 0.0
    engine_confidence: Score = 0.0
    session_count: int = Field(default=0, ge=0)

    last_assessed_at: datetime | None = None
    next_review_at: datetime | None = None

    # graph position — derived every recompute
    is_frontier: bool = False
    critical_path_value: Score = 0.0
    leverage: Score = 0.0
    current_importance: float = Field(default=0.0, ge=0.0)
    learning_cost: float = Field(default=0.0, ge=0.0)

    status: Status = Status.UNASSESSED
    last_gaps: tuple[str, ...] = ()
    schema_version: int = 1

    @classmethod
    def cold(cls, node_id: str) -> KnowledgeState:
        """The ground truth for a node with no evidence at all.

        Explicitly *not* "mastery unknown" — a node nobody has been assessed on contributes
        zero, so readiness reflects the absence of evidence rather than assuming competence.
        """
        return cls(node_id=node_id)

    @property
    def is_assessed(self) -> bool:
        return self.session_count > 0

    def replace(self, **changes: Any) -> KnowledgeState:
        """A new state with `changes` applied. The original is untouched."""
        return self.model_copy(update=changes)


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
