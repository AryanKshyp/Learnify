"""Postgres-backed repositories, against a real database.

These do not mock. A storage layer that only passes against a fake proves nothing about the
thing it is standing in for — type coercion, NULL handling, array round-tripping and constraint
enforcement are exactly what an in-memory double cannot tell you about.

Skipped (not failed) when Postgres is unreachable, so the suite still runs on a machine without
Docker. Everything above Layer 2 is storage-free by design and remains fully covered there.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from knowledgeos.config import settings
from knowledgeos.curriculum import fixture_repository
from knowledgeos.state import (
    DuplicateSessionError,
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    KnowledgeState,
    PostgresKnowledgeStateRepository,
    PostgresSessionHistoryRepository,
    SessionRecord,
    StateOverlay,
    Status,
)
from knowledgeos.state.tables import metadata

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def engine():
    try:
        engine = sa.create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(sa.text("select 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Postgres unavailable ({exc.__class__.__name__}); run `docker compose up -d`")
    metadata.create_all(engine)  # no-op when alembic has already run
    return engine


@pytest.fixture
def states(engine):
    repo = PostgresKnowledgeStateRepository(engine)
    repo.clear()
    yield repo
    repo.clear()


@pytest.fixture
def history(engine, states):
    return PostgresSessionHistoryRepository(engine)


def a_state(node_id="prob-bayes", **overrides) -> KnowledgeState:
    base = KnowledgeState.cold(node_id).replace(
        intrinsic_mastery=0.62,
        effective_mastery=0.41,
        retention=0.83,
        stability=12.5,
        difficulty=0.6,
        assessment_variance=0.18,
        engine_confidence=0.55,
        session_count=3,
        observation_mean=0.6,
        last_assessed_at=NOW,
        next_review_at=NOW + timedelta(days=2),
        is_frontier=True,
        critical_path_value=0.34,
        leverage=0.72,
        current_importance=0.88,
        learning_cost=1.9,
        status=Status.PRACTICED,
        last_gaps=("softmax scaling", "why divide by sqrt(d_k)"),
    )
    return base.replace(**overrides) if overrides else base


class TestKnowledgeStateRoundTrip:
    def test_every_field_survives_a_round_trip(self, states):
        original = a_state()
        states.save(original)
        assert states.get("prob-bayes") == original

    def test_cold_state_round_trips(self, states):
        cold = KnowledgeState.cold("prob-axioms")
        states.save(cold)
        assert states.get("prob-axioms") == cold

    def test_nulls_survive(self, states):
        """`stability`/`difficulty` are NULL until first assessment - not 0.0."""
        states.save(KnowledgeState.cold("prob-axioms"))
        loaded = states.get("prob-axioms")
        assert loaded.stability is None
        assert loaded.difficulty is None
        assert loaded.last_assessed_at is None

    def test_empty_gaps_round_trip_as_empty_tuple(self, states):
        states.save(a_state(last_gaps=()))
        assert states.get("prob-bayes").last_gaps == ()

    def test_timezone_is_preserved(self, states):
        states.save(a_state())
        loaded = states.get("prob-bayes")
        assert loaded.last_assessed_at.tzinfo is not None
        assert loaded.last_assessed_at == NOW

    def test_status_round_trips_as_enum(self, states):
        states.save(a_state(status=Status.MASTERED))
        assert states.get("prob-bayes").status is Status.MASTERED

    def test_missing_node_returns_none(self, states):
        assert states.get("nope") is None

    def test_save_upserts(self, states):
        states.save(a_state())
        states.save(a_state(intrinsic_mastery=0.91))
        assert states.get("prob-bayes").intrinsic_mastery == 0.91
        assert len(states.all()) == 1

    def test_save_many_and_all_is_ordered(self, states):
        states.save_many(
            [KnowledgeState.cold(n) for n in ("c-node", "a-node", "b-node")]
        )
        assert [s.node_id for s in states.all()] == ["a-node", "b-node", "c-node"]

    def test_save_many_with_nothing_is_a_no_op(self, states):
        states.save_many([])
        assert states.all() == ()


class TestDatabaseConstraints:
    """The schema refuses corrupt data even if something bypasses the models."""

    def test_out_of_range_score_is_rejected_by_the_database(self, engine, states):
        states.save(KnowledgeState.cold("prob-bayes"))
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "update knowledge_state set intrinsic_mastery = 1.5 "
                        "where node_id = 'prob-bayes'"
                    )
                )

    def test_negative_session_count_is_rejected(self, engine, states):
        states.save(KnowledgeState.cold("prob-bayes"))
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "update knowledge_state set session_count = -1 "
                        "where node_id = 'prob-bayes'"
                    )
                )

    def test_non_positive_stability_is_rejected(self, engine, states):
        states.save(KnowledgeState.cold("prob-bayes"))
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "update knowledge_state set stability = 0 where node_id = 'prob-bayes'"
                    )
                )


def a_record(node_id="prob-bayes", session_id=None, created=NOW) -> SessionRecord:
    return SessionRecord(
        session_id=session_id or uuid4(),
        node_id=node_id,
        role_context="ai-research",
        created_at=created,
        completed_at=created + timedelta(minutes=40),
        schema_a={"schema": "knowledgeos.assessment.input", "nested": {"depth": [1, 2]}},
        schema_b={"schema": "knowledgeos.assessment.output", "observations": {"recall": 0.7}},
        mastery_before=0.2,
        mastery_after=0.45,
        computation_trace={"stage_1_observation": {"O": 0.63}},
    )


class TestSessionHistory:
    def test_record_round_trips_including_json(self, states, history):
        states.save(KnowledgeState.cold("prob-bayes"))
        record = a_record()
        history.append(record)
        loaded = history.get(record.session_id)
        assert loaded == record
        assert loaded.schema_a["nested"]["depth"] == [1, 2]
        assert loaded.computation_trace["stage_1_observation"]["O"] == 0.63

    def test_history_is_append_only(self, states, history):
        states.save(KnowledgeState.cold("prob-bayes"))
        record = a_record()
        history.append(record)
        with pytest.raises(DuplicateSessionError):
            history.append(record)

    def test_there_is_no_update_or_delete_method(self, history):
        """Replay-based recalculation is only reproducible if history cannot be rewritten."""
        for forbidden in ("update", "delete", "remove", "save"):
            assert not hasattr(history, forbidden)

    def test_ordering_is_deterministic_under_identical_timestamps(self, states, history):
        states.save(KnowledgeState.cold("prob-bayes"))
        records = [a_record(created=NOW) for _ in range(5)]
        for record in records:
            history.append(record)
        first = [r.session_id for r in history.all()]
        second = [r.session_id for r in history.all()]
        assert first == second, "replay order must not vary between reads"

    def test_for_node_filters_and_orders(self, states, history):
        states.save_many(
            [KnowledgeState.cold("prob-bayes"), KnowledgeState.cold("prob-axioms")]
        )
        history.append(a_record("prob-bayes", created=NOW + timedelta(days=1)))
        history.append(a_record("prob-bayes", created=NOW))
        history.append(a_record("prob-axioms", created=NOW))

        for_bayes = history.for_node("prob-bayes")
        assert len(for_bayes) == 2
        assert [r.created_at for r in for_bayes] == sorted(r.created_at for r in for_bayes)

    def test_unknown_node_reference_is_rejected(self, states, history):
        """The FK stops history pointing at a node with no state row."""
        with pytest.raises(sa.exc.IntegrityError):
            history.append(a_record("node-that-does-not-exist"))


class TestParityWithInMemory:
    """The Postgres and in-memory repositories must be indistinguishable to callers.

    This is what makes the protocol worth having: everything above Layer 2 is tested against
    the fast in-memory implementation, and that only means something if the two agree.
    """

    def test_state_repositories_agree(self, states):
        memory = InMemoryKnowledgeStateRepository()
        written = [a_state("prob-bayes"), KnowledgeState.cold("prob-axioms")]
        for repo in (states, memory):
            repo.save_many(written)
        assert states.all() == memory.all()
        assert states.get("prob-bayes") == memory.get("prob-bayes")
        assert states.get("missing") == memory.get("missing")

    def test_history_repositories_agree(self, states, history):
        states.save(KnowledgeState.cold("prob-bayes"))
        memory = InMemorySessionHistoryRepository()
        records = [a_record(created=NOW + timedelta(minutes=i)) for i in range(3)]
        for repo in (history, memory):
            for record in records:
                repo.append(record)
        assert history.all() == memory.all()
        assert history.for_node("prob-bayes") == memory.for_node("prob-bayes")

    def test_overlay_works_against_postgres(self, states):
        curriculum = fixture_repository().get()
        overlay = StateOverlay(curriculum, states)
        assert len(overlay.all()) == len(curriculum)
        assert overlay.state_for("prob-bayes").status is Status.UNASSESSED


class TestFullFlowThroughPostgres:
    """The Core User Flow, persisted for real."""

    def test_assessment_round_trip_persists(self, states, history):
        from knowledgeos.assessment import AssessmentService

        curriculum = fixture_repository().get()
        overlay = StateOverlay(curriculum, states)
        service = AssessmentService(curriculum, overlay, history)

        schema_a = service.generate("prob-axioms", now=NOW)
        result = service.ingest(
            {
                "schema": "knowledgeos.assessment.output",
                "schema_version": 1,
                "session_id": str(schema_a.session_id),
                "node_id": "prob-axioms",
                "completed_at": (NOW + timedelta(minutes=45)).isoformat(),
                "observations": {"recall": 0.85, "depth": 0.7, "transfer": 0.55},
                "response_time_rating": 0.7,
                "llm_confidence": 0.8,
                "gaps_identified": ["shaky on countable additivity"],
                "prerequisite_flags": [],
                "recommended_next_concepts": ["prob-conditional"],
                "evidence_summary": "Good recall.",
            },
            now=NOW,
        )
        assert result.state_after.intrinsic_mastery > 0

        # reload from the database - nothing cached
        reloaded = PostgresKnowledgeStateRepository(states._engine).get("prob-axioms")
        assert reloaded.intrinsic_mastery == result.state_after.intrinsic_mastery
        assert reloaded.last_gaps == ("shaky on countable additivity",)
        assert reloaded.status is not Status.UNASSESSED

        stored = PostgresSessionHistoryRepository(states._engine).all()
        assert len(stored) == 1
        assert stored[0].computation_trace["stage_2_evidence"]["llm_weight_cap"] == 0.20
