"""The HTTP layer (BUILD_SPEC.md Stage 5).

Success criteria: endpoints return correct data against the fixture; submitting a Schema B via
the API updates state and changes subsequent recommendations; OpenAPI renders.

The clock is injected via `dependency_overrides`, which is what makes decay assertable over
HTTP — a test can advance a year between two requests and check that retention fell.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from knowledgeos.api import create_app
from knowledgeos.api.dependencies import get_now
from knowledgeos.curriculum import fixture_repository

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def app():
    application = create_app(curriculum=fixture_repository().get())
    application.dependency_overrides[get_now] = lambda: NOW
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def schema_b(schema_a: dict, **overrides) -> dict:
    payload = {
        "schema": "knowledgeos.assessment.output",
        "schema_version": 1,
        "session_id": schema_a["session_id"],
        "node_id": schema_a["target"]["node_id"],
        "completed_at": (NOW + timedelta(minutes=45)).isoformat(),
        "observations": {"recall": 0.85, "depth": 0.75, "transfer": 0.6},
        "response_time_rating": 0.7,
        "llm_confidence": 0.8,
        "gaps_identified": ["shaky on countable additivity"],
        "prerequisite_flags": [],
        "recommended_next_concepts": [],
        "evidence_summary": "Good recall.",
    }
    payload.update(overrides)
    return payload


class TestOpsAndDocs:
    def test_health(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["curriculum_nodes"] == 26

    def test_openapi_renders(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert len(response.json()["paths"]) == 17

    def test_docs_render(self, client):
        assert client.get("/docs").status_code == 200


class TestBrowsing:
    def test_roles_are_in_priority_order(self, client):
        roles = client.get("/roles").json()
        assert [r["priority_rank"] for r in roles] == [1, 2, 3, 4, 5, 6]
        assert roles[0]["role_id"] == "ai-research"

    def test_whole_graph(self, client):
        body = client.get("/graph").json()
        assert len(body["nodes"]) == 26
        assert len(body["edges"]) == 35

    def test_graph_by_role_is_a_lens_not_a_subset_of_data(self, client):
        body = client.get("/graph?role=finance-quant").json()
        assert 0 < len(body["nodes"]) < 26
        assert all("mastery" in n and "importance" in n for n in body["nodes"])

    def test_graph_edges_are_always_internally_consistent(self, client):
        """A client must never receive an edge pointing at a node it was not given."""
        queries = (
            "",
            "?role=finance-quant",
            "?section=probability",
            "?role=ai-research&section=probability",
        )
        for query in queries:
            body = client.get(f"/graph{query}").json()
            ids = {n["node_id"] for n in body["nodes"]}
            for edge in body["edges"]:
                assert edge["from_node_id"] in ids
                assert edge["to_node_id"] in ids

    def test_graph_by_section(self, client):
        body = client.get("/graph?section=probability").json()
        assert len(body["nodes"]) == 9

    def test_sections_and_competencies(self, client):
        assert "probability" in client.get("/sections").json()
        assert "foundations" in client.get("/sections/probability/competencies").json()

    def test_node_detail_defaults_to_mastery_and_importance(self, client):
        """Part E: only these two are surfaced by default; the rest sit under `advanced`."""
        body = client.get("/nodes/prob-bayes").json()
        assert body["mastery"] == 0.0
        assert "importance" in body
        assert "advanced" in body
        assert body["advanced"]["intrinsic_mastery"] == 0.0
        assert body["advanced"]["target"] > 0

    def test_node_detail_includes_neighbours(self, client):
        body = client.get("/nodes/ml-naive-bayes").json()
        assert {p["node_id"] for p in body["prerequisites"]} == {
            "prob-bayes",
            "prob-independence",
        }

    def test_unknown_node_is_404_with_the_error_envelope(self, client):
        response = client.get("/nodes/ghost")
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["type"] == "NodeNotFoundError"
        assert "ghost" in error["message"]

    def test_unknown_role_is_404(self, client):
        assert client.get("/graph?role=astronaut").status_code == 404


class TestRecommendations:
    def test_overall(self, client):
        body = client.get("/recommendations?limit=3").json()
        assert body["lens"] == "overall"
        assert 0 < len(body["recommendations"]) <= 3

    def test_every_recommendation_explains_itself(self, client):
        """A ranking nobody can interrogate is indistinguishable from a guess."""
        for rec in client.get("/recommendations").json()["recommendations"]:
            assert rec["reason"]
            assert "expected_readiness_gain" in rec
            assert "learning_cost_hours" in rec

    def test_grouped_by_role(self, client):
        body = client.get("/recommendations/role/finance-quant").json()
        assert body["lens"] == "role"
        assert body["key"] == "finance-quant"
        eligible = {
            n["node_id"] for n in client.get("/graph?role=finance-quant").json()["nodes"]
        }
        assert all(r["node_id"] in eligible for r in body["recommendations"])

    def test_grouped_by_competency(self, client):
        body = client.get("/recommendations/competency/probability").json()
        assert body["key"] == "probability"
        assert all(r["section"] == "probability" for r in body["recommendations"])

    def test_unknown_role_is_404(self, client):
        assert client.get("/recommendations/role/astronaut").status_code == 404

    def test_readiness_names_its_bottleneck(self, client):
        for readiness in client.get("/readiness").json():
            assert readiness["bottleneck_node_id"] is not None
            assert readiness["bottleneck_name"]

    def test_overview_is_one_call_for_the_home_view(self, client):
        body = client.get("/overview").json()
        assert body["total_nodes"] == 26
        assert body["unexplored_count"] == 26
        assert set(body["health"]) >= {"score", "coverage", "critical_gap_ratio"}
        assert len(body["readiness"]) == 6

    def test_unexplored_queue(self, client):
        body = client.get("/unexplored?limit=5").json()
        assert len(body) == 5


class TestSessionLoop:
    def test_generate_schema_a(self, client):
        response = client.post("/sessions", json={"node_id": "prob-axioms"})
        assert response.status_code == 201
        body = response.json()
        assert body["schema"] == "knowledgeos.assessment.input"
        assert body["target"]["node_id"] == "prob-axioms"
        # No role asked for, so the node's most important one: finance-quant at 0.90.
        assert body["role_context"]["role_id"] == "finance-quant"

    def test_generate_schema_a_for_an_explicit_role(self, client):
        response = client.post(
            "/sessions", json={"node_id": "prob-axioms", "role_id": "software-engineering"}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["role_context"]["role_id"] == "software-engineering"
        assert body["role_context"]["required_depth"] == "awareness"
        assert body["assessment_directives"]["must_probe_depth"] == "awareness"

    def test_prompt_follows_the_chosen_role(self, client):
        """The role decides the depth the prompt teaches and probes to."""
        prompts = {}
        for role_id in ("software-engineering", "finance-quant"):
            schema_a = client.post(
                "/sessions", json={"node_id": "prob-axioms", "role_id": role_id}
            ).json()
            prompts[role_id] = client.get(
                f"/sessions/open/{schema_a['session_id']}/prompt?phase=assess"
            ).json()["prompt"]
        assert "`awareness`" in prompts["software-engineering"]
        assert "`derivation`" in prompts["finance-quant"]
        assert "software-engineering" in prompts["software-engineering"]

    def test_role_the_node_does_not_serve_is_rejected(self, client):
        response = client.post(
            "/sessions", json={"node_id": "ml-naive-bayes", "role_id": "finance-quant"}
        )
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["type"] == "RoleNotApplicableError"
        assert "data-science" in error["valid_roles"]

    def test_unknown_role_is_a_404(self, client):
        response = client.post(
            "/sessions", json={"node_id": "prob-axioms", "role_id": "astronaut"}
        )
        assert response.status_code == 404

    def test_open_sessions_are_listed_and_retrievable(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        assert len(client.get("/sessions/open").json()) == 1
        again = client.get(f"/sessions/open/{schema_a['session_id']}").json()
        assert again == schema_a

    def test_full_round_trip_updates_state(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        response = client.post("/sessions/ingest", json=schema_b(schema_a))
        assert response.status_code == 200

        body = response.json()
        assert body["intrinsic_mastery_before"] == 0.0
        assert body["intrinsic_mastery_after"] > 0.0
        assert body["status_before"] == "unassessed"
        assert body["status_after"] != "unassessed"
        assert body["computation_trace"]

        detail = client.get("/nodes/prob-axioms").json()
        assert detail["advanced"]["intrinsic_mastery"] == body["intrinsic_mastery_after"]
        assert detail["advanced"]["session_count"] == 1
        assert detail["last_gaps"] == ["shaky on countable additivity"]

    def test_assessment_changes_subsequent_recommendations(self, client):
        """Stage 5 success criterion, stated exactly."""
        before = [r["node_id"] for r in client.get("/recommendations").json()["recommendations"]]
        assert "prob-axioms" in before

        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        client.post("/sessions/ingest", json=schema_b(schema_a))

        after = [r["node_id"] for r in client.get("/recommendations").json()["recommendations"]]
        assert before != after or client.get("/overview").json()["health"]["score"] > 0

    def test_assessment_lifts_downstream_trust(self, client):
        before = client.get("/nodes/prob-conditional").json()["advanced"][
            "prerequisite_confidence"
        ]
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        client.post("/sessions/ingest", json=schema_b(schema_a))
        after = client.get("/nodes/prob-conditional").json()["advanced"][
            "prerequisite_confidence"
        ]
        assert after > before

    def test_history_is_recorded(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        client.post("/sessions/ingest", json=schema_b(schema_a))
        records = client.get("/sessions").json()
        assert len(records) == 1
        assert records[0]["node_id"] == "prob-axioms"
        assert client.get("/sessions?node_id=prob-bayes").json() == []

    def test_a_session_can_only_be_ingested_once(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        payload = schema_b(schema_a)
        assert client.post("/sessions/ingest", json=payload).status_code == 200
        assert client.post("/sessions/ingest", json=payload).status_code == 404


class TestErrorContract:
    """One envelope for every failure."""

    def test_out_of_range_observation_is_422_with_all_problems(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        response = client.post(
            "/sessions/ingest",
            json=schema_b(
                schema_a,
                observations={"recall": 5.0, "depth": -1.0, "transfer": 0.5},
                llm_confidence=9.0,
            ),
        )
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["type"] == "SchemaValidationError"
        assert len(error["problems"]) >= 3, "a paste boundary must report every problem at once"

    def test_unknown_field_is_rejected_not_dropped(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        response = client.post(
            "/sessions/ingest", json=schema_b(schema_a, mastery_score=0.99)
        )
        assert response.status_code == 422
        assert any("mastery_score" in p for p in response.json()["error"]["problems"])

    def test_node_id_mismatch_is_409(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        response = client.post(
            "/sessions/ingest", json=schema_b(schema_a, node_id="prob-bayes")
        )
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["expected"] == "prob-axioms"
        assert error["received"] == "prob-bayes"

    def test_unknown_node_reference_is_422(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        response = client.post(
            "/sessions/ingest", json=schema_b(schema_a, prerequisite_flags=["ghost"])
        )
        assert response.status_code == 422
        assert response.json()["error"]["node_ids"] == ["ghost"]

    def test_rejected_payload_leaves_state_untouched_and_session_open(self, client):
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        client.post("/sessions/ingest", json=schema_b(schema_a, llm_confidence=3.0))

        assert client.get("/nodes/prob-axioms").json()["advanced"]["session_count"] == 0
        assert client.get("/sessions").json() == []
        # the session is still open, so the user can fix the paste and retry
        assert client.post("/sessions/ingest", json=schema_b(schema_a)).status_code == 200

    def test_every_error_uses_the_same_envelope(self, client):
        responses = [
            client.get("/nodes/ghost"),
            client.get("/recommendations/role/astronaut"),
            client.post("/sessions/ingest", json={"schema": "wrong"}),
        ]
        for response in responses:
            assert response.status_code >= 400
            body = response.json()
            assert set(body) == {"error"}
            assert {"type", "message"} <= set(body["error"])


class TestClockIsInjected:
    def test_decay_is_visible_over_http(self, app):
        """Advancing the injected clock must lower retention - untestable with a real clock."""
        client = TestClient(app)
        schema_a = client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        client.post("/sessions/ingest", json=schema_b(schema_a))
        fresh = client.get("/nodes/prob-axioms").json()["advanced"]["retention"]

        app.dependency_overrides[get_now] = lambda: NOW + timedelta(days=365)
        stale = client.get("/nodes/prob-axioms").json()["advanced"]["retention"]

        assert stale < fresh
