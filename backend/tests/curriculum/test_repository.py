"""Repository access, and a read-only check that the real 566-node curriculum is contract-valid.

Stage 1 says not to *seed* the real curriculum. Loading it read-only is not seeding — it is
the only way to know the loader holds up at full scale, and that the graph the four deepening
waves produced actually satisfies the C.1-C.3 contracts rather than merely `build_graph.py`'s
own validator.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import (
    DEFAULT_CURRICULUM_PATH,
    FIXTURE_CURRICULUM_PATH,
    CurriculumRepository,
    JsonCurriculumRepository,
    fixture_repository,
)


@pytest.fixture(scope="module")
def full():
    """The real 566-node curriculum, loaded once for this module."""
    return JsonCurriculumRepository(DEFAULT_CURRICULUM_PATH).get()


class TestJsonRepository:
    def test_fixture_repository_loads(self):
        assert len(fixture_repository().get()) == 26

    def test_result_is_cached(self):
        repo = fixture_repository()
        assert repo.get() is repo.get()

    def test_reload_rebuilds(self):
        repo = fixture_repository()
        first = repo.get()
        assert repo.reload() is not first

    def test_satisfies_the_protocol(self):
        assert isinstance(fixture_repository(), CurriculumRepository)

    def test_default_paths_resolve_to_the_repo_root(self):
        assert DEFAULT_CURRICULUM_PATH.name == "curriculum_graph.json"
        assert FIXTURE_CURRICULUM_PATH.name == "curriculum_fixture.json"
        assert DEFAULT_CURRICULUM_PATH.is_file()
        assert FIXTURE_CURRICULUM_PATH.is_file()


class TestRealCurriculumIsContractValid:
    def test_it_loads_and_validates(self, full):
        assert len(full) == 566
        assert len(full.edges) == 847
        assert len(full.sections) == 16
        assert len(full.roles) == 6

    def test_every_node_serves_at_least_one_role(self, full):
        assert [n.node_id for n in full if not n.roles] == []

    def test_prerequisite_graph_is_acyclic_at_full_scale(self, full):
        assert len(full.topological_order()) == len(full)

    def test_shared_concepts_are_single_nodes(self, full):
        """A.5.4 - the rule the whole curriculum design rests on."""
        multi_role = [n for n in full if len(n.roles) > 1]
        assert len(multi_role) > 200, "shared nodes are the point of the taxonomy"

    def test_golden_chain_survives_in_the_real_graph(self, full):
        assert "prob-bayes" in {n.node_id for n in full.prerequisites_of("ml-naive-bayes")}
        assert "prob-conditional" in full.ancestors("ml-naive-bayes")

    def test_fixture_is_a_subset_of_the_real_graph(self, full):
        """If these ever diverge, Stage 1-3 tests stop predicting Stage 6 behaviour."""
        fixture = fixture_repository().get()
        for node in fixture:
            assert full.node(node.node_id) == node
        real_edges = {e.edge_id for e in full.edges}
        for edge in fixture.edges:
            assert edge.edge_id in real_edges
