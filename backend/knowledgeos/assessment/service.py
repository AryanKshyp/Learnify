"""The Layer 4 boundary: generate Schema A, validate and ingest Schema B.

This module is where the clock lives. The engine is deliberately clock-free, so converting real
timestamps into the `days_elapsed` floats it consumes is this layer's job — the conversion
happens once, here, rather than being scattered through the formulas.

`now` is always an explicit argument rather than read from the system clock. Ingesting the same
Schema B with the same `now` must produce byte-identical state, which is what makes the whole
pipeline reproducible and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import ValidationError

from knowledgeos.curriculum import CurriculumGraph
from knowledgeos.engine import (
    DEFAULT_CONFIG,
    EngineConfig,
    EngineSnapshot,
    Observation,
    apply_session,
    recompute,
)
from knowledgeos.state import (
    KnowledgeState,
    SessionHistoryRepository,
    SessionRecord,
    StateOverlay,
)

from .errors import (
    SchemaValidationError,
    SessionMismatchError,
    UnknownNodeReferenceError,
    UnknownSessionError,
)
from .schemas import (
    AssessmentDirectives,
    CurrentState,
    PrerequisiteContext,
    RoleContext,
    SchemaA,
    SchemaB,
    TargetNode,
)

SECONDS_PER_DAY = 86_400.0


def days_between(earlier: datetime | None, later: datetime) -> float:
    """Elapsed days as a float, the unit the engine consumes.

    A node never assessed has no elapsed time to speak of, so it returns 0.0 — its retention is
    already 0 by virtue of having no stability, and inventing an interval would be noise.
    Clock skew (a `later` before `earlier`) clamps to 0 rather than producing negative decay.
    """
    if earlier is None:
        return 0.0
    return max((later - earlier).total_seconds() / SECONDS_PER_DAY, 0.0)


@runtime_checkable
class PendingSessionStore(Protocol):
    """Schema A payloads awaiting their Schema B.

    Needed because the two halves of a session are separated by a copy-paste into another
    tool — the app must remember what it asked. Kept apart from session history, which stays
    append-only and only ever receives *completed* sessions.
    """

    def open(self, schema_a: SchemaA) -> None: ...
    def take(self, session_id: UUID) -> SchemaA | None:
        """Retrieve and remove. A session is ingested exactly once."""
        ...

    def peek(self, session_id: UUID) -> SchemaA | None: ...
    def all(self) -> tuple[SchemaA, ...]: ...


class InMemoryPendingSessionStore:
    def __init__(self) -> None:
        self._open: dict[UUID, SchemaA] = {}

    def open(self, schema_a: SchemaA) -> None:
        self._open[schema_a.session_id] = schema_a

    def take(self, session_id: UUID) -> SchemaA | None:
        return self._open.pop(session_id, None)

    def peek(self, session_id: UUID) -> SchemaA | None:
        return self._open.get(session_id)

    def all(self) -> tuple[SchemaA, ...]:
        return tuple(self._open[key] for key in sorted(self._open, key=str))


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Everything one ingestion produced."""

    record: SessionRecord
    state_before: KnowledgeState
    state_after: KnowledgeState
    snapshot: EngineSnapshot

    @property
    def mastery_delta(self) -> float:
        return self.state_after.intrinsic_mastery - self.state_before.intrinsic_mastery


class AssessmentService:
    """Generates Schema A and ingests Schema B. The whole Layer 4 boundary."""

    def __init__(
        self,
        curriculum: CurriculumGraph,
        overlay: StateOverlay,
        history: SessionHistoryRepository,
        pending: PendingSessionStore | None = None,
        config: EngineConfig = DEFAULT_CONFIG,
    ) -> None:
        self._curriculum = curriculum
        self._overlay = overlay
        self._history = history
        self._pending = pending or InMemoryPendingSessionStore()
        self._config = config

    @property
    def curriculum(self) -> CurriculumGraph:
        return self._curriculum

    @property
    def overlay(self) -> StateOverlay:
        return self._overlay

    @property
    def history(self) -> SessionHistoryRepository:
        return self._history

    @property
    def pending(self) -> PendingSessionStore:
        return self._pending

    # ------------------------------------------------------------- Schema A

    def select_role_context(self, node_id: str) -> RoleContext:
        """The highest-priority role tagging this node (C.7 selection rule).

        Deterministic even when several roles share a rank: ties break on role_id, so the same
        node always produces the same Schema A.
        """
        node = self._curriculum.node(node_id)
        if not node.roles:
            raise ValueError(f"node {node_id!r} serves no roles and cannot be assessed")

        best = min(
            node.roles,
            key=lambda r: (self._curriculum.role(r.role_id).priority_rank, r.role_id),
        )
        return RoleContext(
            role_id=best.role_id,
            importance=best.importance,
            required_depth=best.required_depth,
        )

    def generate(
        self,
        node_id: str,
        *,
        now: datetime,
        session_id: UUID | None = None,
        min_questions: int = 5,
    ) -> SchemaA:
        """Build the Schema A for a node and open the session.

        Prerequisite context carries each direct prerequisite's intrinsic mastery so the
        external engine can distinguish "does not understand this" from "never learned what it
        rests on", and flag the latter upstream.
        """
        node = self._curriculum.node(node_id)
        role_context = self.select_role_context(node_id)
        state = self._overlay.state_for(node_id)

        elapsed = days_between(state.last_assessed_at, now)
        from knowledgeos.engine import retention as retention_at

        prerequisites = tuple(
            PrerequisiteContext(
                node_id=prerequisite.node_id,
                name=prerequisite.name,
                intrinsic_mastery=self._overlay.state_for(
                    prerequisite.node_id
                ).intrinsic_mastery,
            )
            for prerequisite in self._curriculum.prerequisites_of(node_id)
        )

        schema_a = SchemaA(
            session_id=session_id or uuid4(),
            generated_at=now,
            target=TargetNode(
                node_id=node.node_id,
                name=node.name,
                section=node.section,
                competency=node.competency,
            ),
            role_context=role_context,
            current_state=CurrentState(
                intrinsic_mastery=state.intrinsic_mastery,
                retention=retention_at(elapsed, state.stability),
                session_count=state.session_count,
                last_gaps=state.last_gaps,
            ),
            prerequisite_context=prerequisites,
            assessment_directives=AssessmentDirectives(
                min_questions=min_questions,
                must_probe_depth=role_context.required_depth,
                focus_hints=self._focus_hints(state),
            ),
        )
        self._pending.open(schema_a)
        return schema_a

    def _focus_hints(self, state: KnowledgeState) -> tuple[str, ...]:
        hints = ["test transfer to an unseen framing"]
        if state.last_gaps:
            hints.insert(0, "target the previously identified gaps")
        return tuple(hints)

    # ------------------------------------------------------------- Schema B

    def parse(self, payload: dict[str, Any] | SchemaB) -> SchemaB:
        """Strict parse. Reports every violation at once, never coerces, never drops."""
        if isinstance(payload, SchemaB):
            return payload
        try:
            return SchemaB.model_validate(payload)
        except ValidationError as exc:
            problems = []
            for error in exc.errors():
                location = ".".join(str(part) for part in error["loc"]) or "<root>"
                problems.append(f"{location}: {error['msg']}")
            raise SchemaValidationError(problems) from exc

    def ingest(self, payload: dict[str, Any] | SchemaB, *, now: datetime) -> IngestResult:
        """Validate → run the engine → persist → append history → recompute.

        Ordering is deliberate. Validation happens entirely before any write, so a rejected
        Schema B leaves state exactly as it was — a partially-applied assessment would be worse
        than a refused one, because it would be invisible.
        """
        schema_b = self.parse(payload)

        schema_a = self._pending.peek(schema_b.session_id)
        if schema_a is None:
            raise UnknownSessionError(schema_b.session_id)
        if schema_b.node_id != schema_a.target.node_id:
            raise SessionMismatchError(
                field="node_id",
                expected=schema_a.target.node_id,
                received=schema_b.node_id,
            )
        self._validate_node_references(schema_b)

        # ---- validation complete; only now does anything change ----
        self._pending.take(schema_b.session_id)

        node_id = schema_b.node_id
        state_before = self._overlay.state_for(node_id)
        elapsed = days_between(state_before.last_assessed_at, schema_b.completed_at)

        update = apply_session(
            state=state_before,
            observation=Observation(
                recall=schema_b.observations.recall,
                depth=schema_b.observations.depth,
                transfer=schema_b.observations.transfer,
                response_time_rating=schema_b.response_time_rating,
                llm_confidence=schema_b.llm_confidence,
            ),
            required_depth=schema_a.role_context.required_depth,
            days_since_last_session=elapsed,
            previous_running_mean=state_before.observation_mean,
            config=self._config,
        )

        state_after = state_before.replace(
            intrinsic_mastery=update.intrinsic_mastery,
            retention=update.retention,
            stability=update.stability,
            difficulty=update.difficulty,
            assessment_variance=update.variance,
            engine_confidence=update.engine_confidence,
            observation_mean=update.running_mean,
            session_count=update.session_count,
            last_assessed_at=schema_b.completed_at,
            next_review_at=schema_b.completed_at
            + _days(update.days_until_review),
            last_gaps=schema_b.gaps_identified,
        )
        self._overlay.save(state_after)

        record = SessionRecord(
            session_id=schema_b.session_id,
            node_id=node_id,
            role_context=schema_a.role_context.role_id,
            created_at=schema_a.generated_at,
            completed_at=schema_b.completed_at,
            schema_a=schema_a.to_payload(),
            schema_b=schema_b.to_payload(),
            mastery_before=state_before.intrinsic_mastery,
            mastery_after=state_after.intrinsic_mastery,
            computation_trace=update.trace,
        )
        self._history.append(record)

        snapshot = self.recompute(now=now)
        self._apply_derived(snapshot)

        return IngestResult(
            record=record,
            state_before=state_before,
            state_after=self._overlay.state_for(node_id),
            snapshot=snapshot,
        )

    def _validate_node_references(self, schema_b: SchemaB) -> None:
        """Every referenced node must exist (C.8). Unknown ids are a hard failure."""
        for field, ids in (
            ("prerequisite_flags", schema_b.prerequisite_flags),
            ("recommended_next_concepts", schema_b.recommended_next_concepts),
        ):
            unknown = [n for n in ids if n not in self._curriculum]
            if unknown:
                raise UnknownNodeReferenceError(field, unknown)

    # ------------------------------------------------------------- recompute

    def recompute(
        self, *, now: datetime, active_role_id: str | None = None
    ) -> EngineSnapshot:
        """Run stages 5-14 over the whole graph, using real elapsed time per node."""
        states = {item.node_id: item.state for item in self._overlay.all()}
        elapsed = {
            node_id: days_between(state.last_assessed_at, now)
            for node_id, state in states.items()
        }
        return recompute(
            self._curriculum,
            states,
            days_elapsed=elapsed,
            active_role_id=active_role_id,
            config=self._config,
        )

    def _apply_derived(self, snapshot: EngineSnapshot) -> None:
        """Write the engine's derived values back onto knowledge state.

        These are all recomputed values, never authored — persisting them is a cache so the API
        can serve a node without re-running the pipeline, not a second source of truth.
        """
        updated = []
        for item in self._overlay.all():
            node_id = item.node_id
            updated.append(
                item.state.replace(
                    effective_mastery=snapshot.effective_mastery[node_id],
                    retention=snapshot.retention[node_id],
                    is_frontier=snapshot.frontier[node_id],
                    critical_path_value=snapshot.critical_path_value[node_id],
                    leverage=snapshot.leverage[node_id],
                    current_importance=snapshot.current_importance[node_id],
                    learning_cost=snapshot.learning_cost[node_id],
                    status=snapshot.status[node_id],
                )
            )
        self._overlay.save_many(tuple(updated))


def _days(value: float):
    """Days as a timedelta. Kept local so the import stays out of the engine's reach."""
    from datetime import timedelta

    return timedelta(days=value)
