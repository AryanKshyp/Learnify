"""The document-prep endpoints over HTTP.

The loop these tests walk is the one a user actually performs: fetch the catalogue and prompt,
paste the JSON that comes back from a chat window, read the plan. The clock is injected the
same way the rest of the API tests inject it, so `created_at` is asserted rather than assumed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from knowledgeos.api import create_app
from knowledgeos.api.dependencies import get_now
from knowledgeos.curriculum import fixture_repository

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def curriculum():
    return fixture_repository().get()


@pytest.fixture
def client(curriculum):
    app = create_app(curriculum=curriculum)
    app.dependency_overrides[get_now] = lambda: NOW
    return TestClient(app)


@pytest.fixture
def node_id(curriculum):
    """A concept with prerequisites, so the closure has something to contribute."""
    return next(n.node_id for n in curriculum if curriculum.ancestors(n.node_id))


def extraction(node_id, **overrides) -> dict:
    payload = {
        "schema": "knowledgeos.document.extraction",
        "schema_version": 1,
        "document": {"title": "A Paper", "kind": "paper", "source": "arXiv:0000.00000"},
        "summary": "A paper about something.",
        "concepts": [
            {
                "node_id": node_id,
                "required_depth": "deep",
                "document_weight": 0.9,
                "evidence": "Section 3.",
            }
        ],
        "out_of_curriculum": [{"label": "Byte-pair encoding", "evidence": "Section 5.1."}],
    }
    payload.update(overrides)
    return payload


class TestCatalogue:
    def test_returns_the_prompt_and_the_catalogue_together(self, client, curriculum):
        body = client.get("/documents/catalogue").json()
        assert body["concept_count"] == len(curriculum)
        assert body["prompt"]
        assert body["catalogue"]
        assert body["catalogue_filename"].endswith(".txt")
        assert body["approx_tokens"] > 0

    def test_can_be_scoped_to_a_section(self, client, curriculum):
        section = curriculum.sections[0]
        body = client.get("/documents/catalogue", params={"section": section}).json()
        assert body["sections"] == [section]
        assert body["concept_count"] < len(curriculum)

    def test_can_be_scoped_to_a_role(self, client, curriculum):
        role = curriculum.roles[0].role_id
        body = client.get("/documents/catalogue", params={"role": role}).json()
        assert body["role_id"] == role
        assert body["concept_count"] == len(curriculum.nodes_by_role(role))

    def test_an_unknown_role_is_a_404(self, client):
        response = client.get("/documents/catalogue", params={"role": "nope"})
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "RoleNotFoundError"


class TestIngest:
    def test_a_valid_extraction_returns_a_plan(self, client, node_id):
        response = client.post("/documents/ingest", json=extraction(node_id))
        assert response.status_code == 201
        body = response.json()

        assert body["title"] == "A Paper"
        assert body["created_at"].startswith("2026-09-15T12:00")
        assert body["concept_count"] > 1, "the closure must add to the one stated concept"
        assert body["steps"]
        assert body["total_hours"] > 0

    def test_the_plan_separates_what_the_document_said_from_what_it_assumed(
        self, client, node_id
    ):
        body = client.post("/documents/ingest", json=extraction(node_id)).json()
        stated = [r for r in body["requirements"] if r["stated"]]
        implied = [r for r in body["requirements"] if not r["stated"]]

        assert [r["node_id"] for r in stated] == [node_id]
        assert implied, "prerequisites the document never named"
        for requirement in implied:
            assert requirement["required_for_name"]
            assert requirement["distance"] >= 1

    def test_every_step_explains_itself(self, client, node_id):
        """A recommendation that cannot say why it is there is indistinguishable from a guess."""
        body = client.post("/documents/ingest", json=extraction(node_id)).json()
        for step in body["steps"]:
            assert step["reason"]
            assert step["learning_cost_hours"] >= 0

    def test_out_of_curriculum_concepts_survive_untouched(self, client, node_id):
        body = client.post("/documents/ingest", json=extraction(node_id)).json()
        assert [c["label"] for c in body["out_of_curriculum"]] == ["Byte-pair encoding"]

    def test_an_invented_concept_id_is_a_422_that_names_it(self, client, node_id):
        payload = extraction(node_id)
        payload["concepts"].append(
            {
                "node_id": "totally-made-up",
                "required_depth": "deep",
                "document_weight": 0.5,
                "evidence": "Section 4.",
            }
        )
        response = client.post("/documents/ingest", json=payload)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["type"] == "UnknownConceptError"
        assert error["node_ids"] == ["totally-made-up"]

    def test_an_unknown_field_is_a_422(self, client, node_id):
        response = client.post("/documents/ingest", json=extraction(node_id, extra="nope"))
        assert response.status_code == 422
        assert response.json()["error"]["problems"]

    def test_an_empty_extraction_is_a_422(self, client, node_id):
        response = client.post("/documents/ingest", json=extraction(node_id, concepts=[]))
        assert response.status_code == 422
        assert response.json()["error"]["type"] == "EmptyExtractionError"

    def test_a_rejected_extraction_stores_nothing(self, client, node_id):
        client.post("/documents/ingest", json=extraction(node_id, concepts=[]))
        assert client.get("/documents").json() == []


class TestListAndDelete:
    def test_documents_are_listed_newest_first(self, client, curriculum, node_id):
        client.post("/documents/ingest", json=extraction(node_id, document={"title": "Older"}))

        app = client.app
        app.dependency_overrides[get_now] = lambda: NOW + timedelta(hours=1)
        client.post("/documents/ingest", json=extraction(node_id, document={"title": "Newer"}))

        titles = [d["title"] for d in client.get("/documents").json()]
        assert titles == ["Newer", "Older"]

    def test_the_list_carries_live_readiness(self, client, node_id):
        client.post("/documents/ingest", json=extraction(node_id))
        entry = client.get("/documents").json()[0]
        assert 0.0 <= entry["readiness"] <= 1.0
        assert entry["bottleneck_name"]
        assert entry["stated_count"] == 1
        assert entry["implied_count"] >= 1
        assert entry["gap_count"] == entry["concept_count"], "nothing assessed yet"

    def test_one_document_can_be_fetched_in_full(self, client, node_id):
        created = client.post("/documents/ingest", json=extraction(node_id)).json()
        fetched = client.get(f"/documents/{created['document_id']}").json()
        assert fetched["document_id"] == created["document_id"]
        assert len(fetched["requirements"]) == len(created["requirements"])

    def test_an_unknown_document_is_a_404(self, client):
        response = client.get("/documents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "DocumentNotFoundError"

    def test_a_document_can_be_deleted(self, client, node_id):
        created = client.post("/documents/ingest", json=extraction(node_id)).json()
        assert client.delete(f"/documents/{created['document_id']}").status_code == 204
        assert client.get("/documents").json() == []

    def test_deleting_twice_is_a_404(self, client, node_id):
        created = client.post("/documents/ingest", json=extraction(node_id)).json()
        client.delete(f"/documents/{created['document_id']}")
        assert client.delete(f"/documents/{created['document_id']}").status_code == 404


class TestReadinessTracksAssessment:
    def test_assessing_a_prerequisite_raises_the_document_readiness(self, client, curriculum):
        """The payoff for recomputing plans instead of storing them.

        One assessment of a concept the paper never mentioned must move that paper's readiness,
        with no re-extraction — otherwise the number is a souvenir of the day it was pasted.
        """
        target = next(n.node_id for n in curriculum if curriculum.ancestors(n.node_id))
        created = client.post("/documents/ingest", json=extraction(target)).json()
        before = created["readiness"]

        # assess one implied prerequisite, through the normal session loop
        prerequisite = next(
            r["node_id"] for r in created["requirements"] if not r["stated"]
        )
        schema_a = client.post(
            "/sessions", json={"node_id": prerequisite, "min_questions": 5}
        ).json()
        client.post(
            "/sessions/ingest",
            json={
                "schema": "knowledgeos.assessment.output",
                "schema_version": 1,
                "session_id": schema_a["session_id"],
                "node_id": prerequisite,
                "completed_at": (NOW + timedelta(minutes=45)).isoformat(),
                "observations": {"recall": 0.95, "depth": 0.9, "transfer": 0.85},
                "response_time_rating": 0.9,
                "llm_confidence": 0.9,
                "gaps_identified": [],
                "prerequisite_flags": [],
                "recommended_next_concepts": [],
                "evidence_summary": "Strong throughout.",
            },
        )

        after = client.get(f"/documents/{created['document_id']}").json()
        assert after["readiness"] > before

        # The assessed concept closed part of its gap. Not necessarily all of it — one session
        # from cold rarely reaches a document's target outright, and `gap_count` only falls
        # when sufficiency hits 1.0. Partial progress is still progress, and it must show.
        moved = next(r for r in after["requirements"] if r["node_id"] == prerequisite)
        was = next(r for r in created["requirements"] if r["node_id"] == prerequisite)
        assert moved["sufficiency"] > was["sufficiency"]
        assert moved["mastery"] > was["mastery"]
