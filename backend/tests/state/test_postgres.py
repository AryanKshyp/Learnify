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

#: Skipping is only useful if it is fast. Without this, a machine with Docker stopped waits on
#: the OS connect timeout — minutes, twice — before the suite decides Postgres is unreachable,
#: which reads as a hang rather than as the documented skip.
CONNECT_TIMEOUT = {"connect_timeout": 3}


@pytest.fixture(scope="session")
def engine():
    """A connection to the **test** database, created if it does not exist.

    Deliberately not `settings.database_url`. The fixtures below truncate both tables around
    every test, so pointing this at the development database deletes real assessment history —
    which it did, unnoticed, on every full test run between 2026-08-01 and 2026-09-14. The
    guard below is the part that matters: it makes the mistake unrepeatable even if someone
    later edits the setting or exports the wrong env var.
    """
    url = sa.engine.make_url(settings.test_database_url)
    if not (url.database or "").endswith("_test"):
        pytest.fail(
            "refusing to run: test_database_url points at "
            f"{url.database!r}, which does not end in '_test'. These tests DELETE every row "
            "in knowledge_state and session_history."
        )
    if url.render_as_string(hide_password=False) == settings.database_url:
        pytest.fail("refusing to run: test_database_url equals database_url")

    try:
        _create_database_if_absent(url)
        engine = sa.create_engine(url, pool_pre_ping=True, connect_args=CONNECT_TIMEOUT)
        with engine.connect() as connection:
            connection.execute(sa.text("select 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Postgres unavailable ({exc.__class__.__name__}); run `docker compose up -d`")
    metadata.create_all(engine)  # the test database has no alembic history of its own
    return engine


def _create_database_if_absent(url) -> None:
    """`CREATE DATABASE` cannot run inside a transaction, hence AUTOCOMMIT.

    Connects to the `postgres` maintenance database, which always exists, so a fresh clone
    needs no manual setup step before `pytest` works.
    """
    admin = sa.create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args=CONNECT_TIMEOUT,
    )
    with admin.connect() as connection:
        exists = connection.execute(
            sa.text("select 1 from pg_database where datname = :name"),
            {"name": url.database},
        ).scalar()
        if not exists:
            connection.execute(sa.text(f'create database "{url.database}"'))
    admin.dispose()


@pytest.fixture
def states(engine):
    repo = PostgresKnowledgeStateRepository(engine)
    repo.clear()
    yield repo
    repo.clear()


@pytest.fixture
def history(engine, states):
    return PostgresSessionHistoryRepository(engine)


@pytest.fixture
def pending(engine):
    """Open Schema A payloads. Cleared around every test, like the other two stores.

    Not covered by `states.clear()`: pending sessions deliberately have no foreign key to
    knowledge_state, so nothing cascades to them.
    """
    from knowledgeos.assessment import PostgresPendingSessionStore

    store = PostgresPendingSessionStore(engine)
    store.clear()
    yield store
    store.clear()


def a_schema_a(node_id="prob-axioms", session_id=None):
    """A minimal but complete Schema A, built directly rather than through the service."""
    from knowledgeos.assessment import (
        AssessmentDirectives,
        CurrentState,
        PrerequisiteContext,
        RoleContext,
        SchemaA,
        TargetNode,
    )

    return SchemaA(
        session_id=session_id or uuid4(),
        generated_at=NOW,
        target=TargetNode(
            node_id=node_id, name="Axioms of probability", section="probability",
            competency="foundations",
        ),
        role_context=RoleContext(
            role_id="ai-research", importance=0.9, required_depth="derivation"
        ),
        current_state=CurrentState(
            intrinsic_mastery=0.0, retention=0.0, session_count=0, last_gaps=()
        ),
        prerequisite_context=(
            PrerequisiteContext(node_id="prob-bayes", name="Bayes", intrinsic_mastery=0.4),
        ),
        assessment_directives=AssessmentDirectives(
            min_questions=5, must_probe_depth="derivation", focus_hints=("probe transfer",)
        ),
    )


def a_state(node_id="prob-bayes", **overrides) -> KnowledgeState:
    base = KnowledgeState.cold(node_id).replace(
        intrinsic_mastery=0.62,
        stability=12.5,
        difficulty=0.6,
        assessment_variance_raw=0.18,
        engine_confidence=0.55,
        session_count=3,
        observation_mean=0.6,
        last_assessed_at=NOW,
        next_review_at=NOW + timedelta(days=2),
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
        assert overlay.state_for("prob-bayes").session_count == 0


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
        assert result.status_after is not Status.UNASSESSED, (
            "status is derived from the snapshot, never read back off the row"
        )

        stored = PostgresSessionHistoryRepository(states._engine).all()
        assert len(stored) == 1
        assert stored[0].computation_trace["stage_2_evidence"]["llm_weight_cap"] == 0.20


class TestPendingSessions:
    """Open Schema A payloads, persisted.

    The half of the session loop that used to live in a process dict. A learner opens a
    session, copies the Schema A into another tool, and comes back forty minutes later — the
    server has no business forgetting what it asked in the meantime.
    """

    def test_schema_a_round_trips(self, pending):
        schema_a = a_schema_a()
        pending.open(schema_a)
        assert pending.peek(schema_a.session_id) == schema_a

    def test_peek_leaves_it_open_and_take_removes_it(self, pending):
        schema_a = a_schema_a()
        pending.open(schema_a)
        assert pending.peek(schema_a.session_id) is not None
        assert pending.take(schema_a.session_id) == schema_a
        assert pending.take(schema_a.session_id) is None, "a session is ingested exactly once"
        assert pending.peek(schema_a.session_id) is None

    def test_unknown_session_is_none_not_an_error(self, pending):
        assert pending.peek(uuid4()) is None
        assert pending.take(uuid4()) is None

    def test_reopening_the_same_session_replaces_it(self, pending):
        """Asking for the Schema A again is legitimate — the learner lost the paste."""
        session_id = uuid4()
        pending.open(a_schema_a(session_id=session_id))
        pending.open(a_schema_a(session_id=session_id))
        assert len(pending.all()) == 1

    def test_satisfies_the_protocol(self, pending):
        from knowledgeos.assessment import PendingSessionStore

        assert isinstance(pending, PendingSessionStore)

    def test_a_session_survives_a_restart(self, engine, states, history, pending):
        """The failure this store exists to prevent.

        Open a session, throw away every object holding it — a deploy, a crash, an autoscale —
        and rebuild the whole stack from the database. The Schema B must still land. With the
        in-memory store this raised UnknownSessionError and the assessment was unrecoverable,
        with no history row recording that it ever happened.
        """
        from knowledgeos.assessment import AssessmentService, PostgresPendingSessionStore

        curriculum = fixture_repository().get()
        opening = AssessmentService(
            curriculum, StateOverlay(curriculum, states), history, pending=pending
        )
        schema_a = opening.generate("prob-axioms", now=NOW)
        del opening

        # a completely fresh stack over the same database
        restarted = AssessmentService(
            curriculum,
            StateOverlay(curriculum, PostgresKnowledgeStateRepository(engine)),
            PostgresSessionHistoryRepository(engine),
            pending=PostgresPendingSessionStore(engine),
        )
        result = restarted.ingest(
            {
                "schema": "knowledgeos.assessment.output",
                "schema_version": 1,
                "session_id": str(schema_a.session_id),
                "node_id": "prob-axioms",
                "completed_at": (NOW + timedelta(minutes=45)).isoformat(),
                "observations": {"recall": 0.85, "depth": 0.7, "transfer": 0.55},
                "response_time_rating": 0.7,
                "llm_confidence": 0.8,
                "gaps_identified": [],
                "prerequisite_flags": [],
                "recommended_next_concepts": [],
                "evidence_summary": "Good recall.",
            },
            now=NOW,
        )
        assert result.state_after.intrinsic_mastery > 0
        assert pending.peek(schema_a.session_id) is None, "ingested sessions stop being open"

    def test_pending_stores_agree(self, pending):
        """Parity, the same as for state and history — the protocol is only worth having if
        everything above Layer 4 can be tested against the in-memory one."""
        from knowledgeos.assessment import InMemoryPendingSessionStore

        memory = InMemoryPendingSessionStore()
        written = [a_schema_a() for _ in range(3)]
        for store in (pending, memory):
            for schema_a in written:
                store.open(schema_a)

        assert pending.all() == memory.all()
        assert pending.peek(written[0].session_id) == memory.peek(written[0].session_id)
        assert pending.take(written[0].session_id) == memory.take(written[0].session_id)
        assert pending.all() == memory.all()
        assert pending.peek(uuid4()) == memory.peek(uuid4())
