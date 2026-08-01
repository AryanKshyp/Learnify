"""Stage 6 — the real curriculum as the seeded graph (BUILD_SPEC.md Stage 6).

Success criteria: the full graph loads and passes DAG + referential validation; shared concepts
are single nodes referenced by multiple roles; role/competency traversal works on real data;
no duplication.

`tests/curriculum/test_repository.py` already proves it *loads*. This file proves the content
is shaped the way the taxonomy requires — which is a different claim, and the one that decides
whether readiness and recommendations mean anything.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import DEFAULT_CURRICULUM_PATH, JsonCurriculumRepository

#: sections named in CURRICULUM_BUILD_KIT.md Part 2
EXPECTED_SECTIONS = {
    "probability",
    "statistics",
    "linear-algebra",
    "calculus-optimization",
    "dsa",
    "cs-fundamentals",
    "system-design",
    "classical-ml",
    "deep-learning",
    "nlp-llms",
    "post-training-llms",
    "ml-systems-mlops",
    "data-science-analytics",
    "product-management",
    "finance-quant",
    "behavioral",
}

#: section -> abbreviation that must prefix every node_id in it
SECTION_ABBREV = {
    "probability": "prob",
    "statistics": "stat",
    "linear-algebra": "linalg",
    "calculus-optimization": "opt",
    "dsa": "dsa",
    "cs-fundamentals": "cs",
    "system-design": "sysd",
    "classical-ml": "ml",
    "deep-learning": "dl",
    "nlp-llms": "llm",
    "post-training-llms": "pt",
    "ml-systems-mlops": "mlops",
    "data-science-analytics": "ds",
    "product-management": "pm",
    "finance-quant": "fq",
    "behavioral": "beh",
}


@pytest.fixture(scope="module")
def graph():
    return JsonCurriculumRepository(DEFAULT_CURRICULUM_PATH).get()


class TestStructure:
    def test_all_sixteen_sections_are_present(self, graph):
        assert set(graph.sections) == EXPECTED_SECTIONS

    def test_all_six_roles_are_present_and_uniquely_ranked(self, graph):
        assert len(graph.roles) == 6
        assert [r.priority_rank for r in graph.roles] == [1, 2, 3, 4, 5, 6]

    def test_node_ids_are_prefixed_with_their_section_abbreviation(self, graph):
        """The slug convention from CURRICULUM_BUILD_KIT.md Part 4."""
        wrong = [
            node.node_id
            for node in graph
            if not node.node_id.startswith(SECTION_ABBREV[node.section] + "-")
        ]
        assert wrong == []

    def test_every_section_is_substantially_built(self, graph):
        """No section may be a stub - a thin section silently distorts readiness.

        Readiness is a harmonic mean over a role's nodes, so a section modelled with six nodes
        cannot express a bottleneck the user actually has.
        """
        counts = {s: len(graph.nodes_by_section(s)) for s in graph.sections}
        thin = {s: c for s, c in counts.items() if c < 25}
        assert thin == {}, f"under-built sections would distort readiness: {thin}"

    def test_prerequisite_graph_is_acyclic_at_full_scale(self, graph):
        assert len(graph.topological_order()) == len(graph)


class TestSharedConcepts:
    """A.5.4 — each concept exists exactly once, with per-role importance and depth."""

    def test_no_duplicate_concept_names(self, graph):
        """The loader rejects these outright, so reaching here means the rule held."""
        names = [node.name.strip().casefold() for node in graph]
        assert len(names) == len(set(names))

    def test_shared_nodes_are_the_norm_not_the_exception(self, graph):
        multi_role = [n for n in graph if len(n.roles) > 1]
        assert len(multi_role) / len(graph) > 0.4

    def test_the_leverage_sections_are_genuinely_shared(self, graph):
        """probability, dsa and behavioral are the taxonomy's stated leverage sections."""
        for section, minimum_roles in (
            ("probability", 4),
            ("dsa", 3),
            ("behavioral", 6),
        ):
            nodes = graph.nodes_by_section(section)
            best = max(len(n.roles) for n in nodes)
            assert best >= minimum_roles, (
                f"{section} should carry nodes shared across >= {minimum_roles} roles"
            )

    def test_behavioral_serves_every_role(self, graph):
        """The one section marked core for all six roles."""
        covered = set()
        for node in graph.nodes_by_section("behavioral"):
            covered |= node.role_ids
        assert covered == {r.role_id for r in graph.roles}

    def test_a_shared_concept_carries_different_depth_per_role(self, graph):
        """The whole point of per-role metadata (e.g. probability: derivation vs working)."""
        varied = [
            n for n in graph if len({r.required_depth for r in n.roles}) > 1
        ]
        assert len(varied) > 50


class TestTraversalOnRealData:
    def test_every_role_has_a_substantial_node_set(self, graph):
        for role in graph.roles:
            assert len(graph.nodes_by_role(role.role_id)) > 30

    def test_role_nodes_are_ordered_by_importance_to_that_role(self, graph):
        for role in graph.roles:
            nodes = graph.nodes_by_role(role.role_id)
            scores = [n.requirement_for(role.role_id).importance for n in nodes]
            assert scores == sorted(scores, reverse=True)

    def test_competency_traversal_works_in_every_section(self, graph):
        for section in graph.sections:
            competencies = graph.competencies(section)
            assert competencies, f"{section} has no competencies"
            for competency in competencies:
                found = graph.nodes_by_competency(competency, section=section)
                assert found
                assert all(n.section == section for n in found)

    def test_cross_section_prerequisites_are_common(self, graph):
        """Cross-section edges are what make this a DAG rather than 16 separate trees."""
        crossing = [
            e
            for e in graph.prerequisite_edges
            if graph.node(e.dependent_id).section != graph.node(e.prerequisite_id).section
        ]
        assert len(crossing) > 100

    def test_deep_chains_exist(self, graph):
        """Propagation only matters if knowledge actually stacks several levels deep."""
        deepest = max(len(graph.ancestors(n.node_id)) for n in graph)
        assert deepest > 15

    def test_the_golden_chain_is_intact(self, graph):
        assert "prob-bayes" in {n.node_id for n in graph.prerequisites_of("ml-naive-bayes")}
        assert "prob-conditional" in graph.ancestors("ml-naive-bayes")


class TestServedByTheApi:
    def test_the_app_defaults_to_the_real_curriculum(self):
        """Stage 6 in practice: no wiring change needed, the default IS the real graph."""
        from fastapi.testclient import TestClient

        from knowledgeos.api import create_app

        client = TestClient(create_app())
        body = client.get("/health").json()
        assert body["curriculum_nodes"] == 566
        assert body["curriculum_edges"] == 847

    def test_role_and_competency_lenses_work_over_http_on_real_data(self):
        from fastapi.testclient import TestClient

        from knowledgeos.api import create_app

        client = TestClient(create_app())
        for role in ("ai-research", "finance-quant", "product-management"):
            body = client.get(f"/graph?role={role}").json()
            assert len(body["nodes"]) > 30
            ids = {n["node_id"] for n in body["nodes"]}
            for edge in body["edges"]:
                assert edge["from_node_id"] in ids and edge["to_node_id"] in ids
