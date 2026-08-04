"""Stage 8 — the Core User Flow, end to end (BUILD_SPEC.md Part D, Stage 8).

    Open app → browse graph → select a concept → generate Schema A →
    [external assessment] → paste Schema B → validate → recompute → re-recommend

Every other test file checks one layer. This one checks that the layers compose: that an
assessment entering through HTTP actually moves a number the recommendation engine reads, and
that the same mock Schema B always produces the same resulting state.

Runs against the API with a frozen, injected clock — which is what makes "three months pass"
an assertion rather than a comment.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from knowledgeos.api import create_app
from knowledgeos.api.dependencies import get_now
from knowledgeos.curriculum import fixture_repository

START = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class Clock:
    """A clock the test drives, so decay can be observed instead of waited for."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def advance(self, days: float) -> None:
        self.now += timedelta(days=days)


@pytest.fixture
def clock():
    return Clock(START)


@pytest.fixture
def client(clock):
    app = create_app(curriculum=fixture_repository().get())
    app.dependency_overrides[get_now] = lambda: clock.now
    return TestClient(app)


def assess(client, clock, node_id: str, *, recall: float, depth: float, transfer: float) -> dict:
    """One full session: generate Schema A, answer it, ingest the Schema B.

    Stands in for the external assessment engine — the app's half of the boundary is real, only
    the engine's answer is mocked.
    """
    schema_a = client.post("/sessions", json={"node_id": node_id}).json()
    payload = {
        "schema": "knowledgeos.assessment.output",
        "schema_version": 1,
        "session_id": schema_a["session_id"],
        "node_id": node_id,
        "completed_at": clock.now.isoformat(),
        "observations": {"recall": recall, "depth": depth, "transfer": transfer},
        "response_time_rating": 0.75,
        "llm_confidence": 0.8,
        "gaps_identified": [],
        "prerequisite_flags": [],
        "recommended_next_concepts": [],
        "evidence_summary": "mock session",
    }
    response = client.post("/sessions/ingest", json=payload)
    assert response.status_code == 200, response.json()
    return response.json()


class TestCoreUserFlow:
    def test_the_whole_loop(self, client, clock):
        """Part D, start to finish, in the order a user would actually do it."""
        # 1. open the app
        assert client.get("/health").json()["status"] == "ok"

        opening = client.get("/overview").json()
        assert opening["unexplored_count"] == opening["total_nodes"], "nothing known yet"
        assert opening["health"]["score"] == 0.0

        # 2. browse the graph
        graph = client.get("/graph").json()
        assert len(graph["nodes"]) == 26

        # 3. ask what to study
        first = client.get("/recommendations?limit=5").json()["recommendations"]
        assert first, "a cold graph must still have a starting point"
        assert all(r["reason"] for r in first), "and must say why"

        target = first[0]["node_id"]

        # 4-6. generate Schema A, assess externally, paste Schema B back
        result = assess(client, clock, target, recall=0.9, depth=0.85, transfer=0.75)
        assert result["intrinsic_mastery_after"] > result["intrinsic_mastery_before"]
        assert result["status_after"] != "unassessed"

        # 7. everything recomputes
        after = client.get("/overview").json()
        assert after["unexplored_count"] == opening["unexplored_count"] - 1
        assert after["health"]["score"] > opening["health"]["score"]

        # 8. and the next recommendation reflects it
        second = client.get("/recommendations?limit=5").json()["recommendations"]
        order = [r["node_id"] for r in second]
        assert order[0] != target, "the just-assessed node should no longer lead"
        # It may legitimately still appear: one session rarely reaches a `deep` or
        # `derivation` target, so the node stays a candidate — just a lower-priority one,
        # because its remaining gap (and therefore its expected readiness gain) shrank.
        if target in order:
            assert order.index(target) > 0

        # history is the audit trail
        sessions = client.get("/sessions").json()
        assert len(sessions) == 1
        assert sessions[0]["node_id"] == target

    def test_assessment_propagates_downstream(self, client, clock):
        """The point of the graph: learning a prerequisite lifts what depends on it."""
        before = client.get("/nodes/prob-bayes").json()["advanced"]["prerequisite_confidence"]

        assess(client, clock, "prob-axioms", recall=0.95, depth=0.9, transfer=0.85)
        assess(client, clock, "prob-conditional", recall=0.95, depth=0.9, transfer=0.85)

        after = client.get("/nodes/prob-bayes").json()["advanced"]["prerequisite_confidence"]
        assert after > before, "Bayes became more trustworthy without being assessed"

    def test_the_governing_invariant_over_http(self, client, clock):
        """Decay lowers what we can trust; it never touches what was demonstrated.

        This is the §15 golden case expressed through the real stack rather than in isolation.
        """
        assess(client, clock, "prob-axioms", recall=0.95, depth=0.9, transfer=0.9)
        fresh = client.get("/nodes/prob-axioms").json()["advanced"]

        clock.advance(365)
        stale = client.get("/nodes/prob-axioms").json()["advanced"]

        assert stale["intrinsic_mastery"] == fresh["intrinsic_mastery"], "evidence is preserved"
        assert stale["retention"] < fresh["retention"], "but it is no longer fresh"
        assert stale["effective_mastery"] < fresh["effective_mastery"], "so trust falls"

    def test_a_decayed_prerequisite_drags_its_dependents(self, client, clock):
        assess(client, clock, "prob-axioms", recall=0.95, depth=0.9, transfer=0.9)
        assess(client, clock, "prob-conditional", recall=0.95, depth=0.9, transfer=0.9)
        assess(client, clock, "prob-bayes", recall=0.95, depth=0.9, transfer=0.9)
        fresh = client.get("/nodes/prob-bayes").json()["advanced"]

        clock.advance(400)
        stale = client.get("/nodes/prob-bayes").json()["advanced"]

        assert stale["intrinsic_mastery"] == fresh["intrinsic_mastery"]
        assert stale["prerequisite_confidence"] < fresh["prerequisite_confidence"]

    def test_restudying_a_prerequisite_restores_dependents_with_no_reassessment(
        self, client, clock
    ):
        """The payoff the whole architecture exists for, proven through the API."""
        assess(client, clock, "prob-axioms", recall=0.95, depth=0.9, transfer=0.9)
        assess(client, clock, "prob-conditional", recall=0.95, depth=0.9, transfer=0.9)
        assess(client, clock, "prob-bayes", recall=0.95, depth=0.9, transfer=0.9)

        clock.advance(400)
        decayed = client.get("/nodes/prob-bayes").json()["advanced"]
        bayes_sessions_before = decayed["session_count"]

        # restudy ONLY the upstream nodes
        assess(client, clock, "prob-axioms", recall=0.95, depth=0.9, transfer=0.9)
        assess(client, clock, "prob-conditional", recall=0.95, depth=0.9, transfer=0.9)

        restored = client.get("/nodes/prob-bayes").json()["advanced"]
        assert restored["prerequisite_confidence"] > decayed["prerequisite_confidence"]
        assert restored["session_count"] == bayes_sessions_before, (
            "Bayes recovered without being reassessed even once"
        )


class TestDeterminism:
    """Same mock Schema B ⇒ same resulting state and same recommendations (Stage 8)."""

    def run(self) -> tuple[dict, list[str]]:
        clock = Clock(START)
        app = create_app(curriculum=fixture_repository().get())
        app.dependency_overrides[get_now] = lambda: clock.now
        client = TestClient(app)

        for node_id in ("prob-axioms", "linalg-vectors", "opt-derivatives"):
            assess(client, clock, node_id, recall=0.8, depth=0.7, transfer=0.6)

        state = client.get("/nodes/prob-axioms").json()["advanced"]
        picks = [
            r["node_id"]
            for r in client.get("/recommendations?limit=5").json()["recommendations"]
        ]
        return state, picks

    def test_identical_input_produces_identical_state(self):
        first, _ = self.run()
        second, _ = self.run()
        # session ids differ per run; everything the engine computes must not
        for key in first:
            assert first[key] == second[key], f"{key} is not reproducible"

    def test_identical_input_produces_identical_recommendations(self):
        _, first = self.run()
        _, second = self.run()
        assert first == second


class TestRejectionDoesNotCorrupt:
    def test_a_bad_paste_changes_nothing(self, client, clock):
        assess(client, clock, "prob-axioms", recall=0.8, depth=0.7, transfer=0.6)
        before = client.get("/nodes/prob-axioms").json()["advanced"]
        history_before = len(client.get("/sessions").json())

        schema_a = client.post("/sessions", json={"node_id": "prob-conditional"}).json()
        bad = {
            "schema": "knowledgeos.assessment.output",
            "schema_version": 1,
            "session_id": schema_a["session_id"],
            "node_id": "prob-conditional",
            "completed_at": clock.now.isoformat(),
            "observations": {"recall": 5.0, "depth": -1.0, "transfer": 0.5},
            "response_time_rating": 0.7,
            "llm_confidence": 9.9,
            "gaps_identified": [],
            "prerequisite_flags": ["does-not-exist"],
            "recommended_next_concepts": [],
            "evidence_summary": "",
        }
        response = client.post("/sessions/ingest", json=bad)
        assert response.status_code == 422
        assert len(response.json()["error"]["problems"]) >= 3

        assert client.get("/nodes/prob-axioms").json()["advanced"] == before
        assert len(client.get("/sessions").json()) == history_before
        assert client.get("/nodes/prob-conditional").json()["advanced"]["session_count"] == 0
