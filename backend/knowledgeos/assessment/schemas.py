"""Schema A and Schema B — the ONLY interface to the external assessment engine.

BUILD_SPEC.md C.7 and C.8.

These two shapes are the entire contract. KnowledgeOS knows nothing about how an assessment is
conducted and must work against any engine that honours them, which is why they are versioned
and validated strictly rather than parsed leniently.

Schema B is validated with `extra="forbid"`: an unknown field is a hard failure, never a silent
drop. A field the app does not recognise means the two sides disagree about the contract, and
quietly ignoring it would let that disagreement corrupt state invisibly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from knowledgeos.curriculum import Depth

Score = Annotated[float, Field(ge=0.0, le=1.0)]

SCHEMA_A_NAME = "knowledgeos.assessment.input"
SCHEMA_B_NAME = "knowledgeos.assessment.output"
SCHEMA_VERSION = 1

_STRICT = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------- A


class TargetNode(BaseModel):
    """Which concept is being assessed."""

    model_config = _STRICT

    node_id: str
    name: str
    section: str
    competency: str


class RoleContext(BaseModel):
    """The lens for this session.

    A concept matters differently to different roles, so the engine must be told which one it
    is probing for — Bayes at `derivation` for AI Research is a different session from Bayes at
    `working` for Software Engineering.
    """

    model_config = _STRICT

    role_id: str
    importance: Score
    required_depth: Depth


class CurrentState(BaseModel):
    """What the app already believes, so the engine can probe rather than re-cover ground."""

    model_config = _STRICT

    intrinsic_mastery: Score
    retention: Score
    session_count: int = Field(ge=0)
    last_gaps: tuple[str, ...] = ()


class PrerequisiteContext(BaseModel):
    """A prerequisite and its standing.

    Included so the assessment engine can tell "does not understand this" apart from "never
    learned what it rests on" — and report the difference via `prerequisite_flags`.
    """

    model_config = _STRICT

    node_id: str
    name: str
    intrinsic_mastery: Score


class AssessmentDirectives(BaseModel):
    """Advisory only. The engine may adapt; the app does not depend on compliance."""

    model_config = _STRICT

    min_questions: int = Field(default=5, ge=1)
    must_probe_depth: Depth
    focus_hints: tuple[str, ...] = ()


class SchemaA(BaseModel):
    """C.7 — assessment INPUT (application → assessment engine)."""

    model_config = _STRICT

    schema_name: Literal["knowledgeos.assessment.input"] = Field(
        default=SCHEMA_A_NAME, alias="schema"
    )
    schema_version: int = SCHEMA_VERSION
    session_id: UUID
    generated_at: datetime
    target: TargetNode
    role_context: RoleContext
    current_state: CurrentState
    prerequisite_context: tuple[PrerequisiteContext, ...] = ()
    assessment_directives: AssessmentDirectives

    def to_payload(self) -> dict:
        """JSON-ready mapping, using the wire field name `schema`."""
        return self.model_dump(mode="json", by_alias=True)


# --------------------------------------------------------------------------- B


class Observations(BaseModel):
    """The three signals the engine reports. All required, all bounded."""

    model_config = _STRICT

    recall: Score  # remembered the facts / definitions
    depth: Score  # understood the mechanism, not just the surface
    transfer: Score  # applied it to a novel framing


class SchemaB(BaseModel):
    """C.8 — assessment OUTPUT (assessment engine → application).

    The only way knowledge state ever changes.

    `llm_confidence` is accepted but capped downstream at ≤20% of update weight
    (CALC_ENGINE_SPEC.md §4). It is the engine's opinion of itself, and LLM self-report is
    miscalibrated; the KnowledgeOS engine computes its own confidence from evidence.

    `recommended_next_concepts` is likewise advisory — the app decides what to study next, and
    accepting the LLM's ranking would hand a protected calculation to the LLM.
    """

    model_config = _STRICT

    schema_name: Literal["knowledgeos.assessment.output"] = Field(
        default=SCHEMA_B_NAME, alias="schema"
    )
    schema_version: int = SCHEMA_VERSION
    session_id: UUID
    node_id: str
    completed_at: datetime

    observations: Observations
    response_time_rating: Score
    llm_confidence: Score

    gaps_identified: tuple[str, ...] = ()
    prerequisite_flags: tuple[str, ...] = ()
    recommended_next_concepts: tuple[str, ...] = ()
    evidence_summary: str = ""

    def to_payload(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)
