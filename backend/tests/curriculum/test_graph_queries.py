"""Traversal and query surface (BUILD_SPEC.md Stage 1).

Assertions use the real fixture rather than a synthetic graph, so a regression in
`make_fixture.py` surfaces here too.

The `TestEdgeOrientation` class is the important one: the DAG is built inverted relative to
the JSON, and getting that backwards would still yield a valid-looking acyclic graph while
silently reversing every propagation the engine performs.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import NodeNotFoundError, RoleNotFoundError, load_curriculum


@pytest.fixture(scope="module")
def graph(fixture_curriculum_path):
    return load_curriculum(fixture_curriculum_path)


class TestEdgeOrientation:
    """The single easiest thing to get backwards in this layer."""

    def test_prerequisites_of_returns_what_the_node_depends_on(self, graph):
        assert {n.node_id for n in graph.prerequisites_of("ml-naive-bayes")} == {
            "prob-bayes",
            "prob-independence",
        }

    def test_dependents_of_returns_what_depends_on_the_node(self, graph):
        assert {n.node_id for n in graph.dependents_of("prob-conditional")} == {
            "prob-bayes",
            "prob-independence",
        }

    def test_ancestors_are_prerequisites_not_dependents(self, graph):
        ancestors = graph.ancestors("ml-naive-bayes")
        assert "prob-conditional" in ancestors, "must reach upstream through prob-bayes"
        assert "prob-axioms" in ancestors, "must reach the root of the chain"
        assert "dl-attention" not in ancestors, "dependents must NOT appear as ancestors"

    def test_descendants_are_dependents_not_prerequisites(self, graph):
        descendants = graph.descendants("prob-conditional")
        assert "ml-naive-bayes" in descendants
        assert "prob-axioms" not in descendants, "a prerequisite is not a descendant"

    def test_ancestors_and_descendants_are_inverses(self, graph):
        for node in graph:
            for ancestor in graph.ancestors(node.node_id):
                assert node.node_id in graph.descendants(ancestor)

    def test_topological_order_puts_prerequisites_first(self, graph):
        """CALC_ENGINE_SPEC.md §7 propagates in this order; reversed, it computes garbage."""
        order = graph.topological_order()
        position = {node_id: i for i, node_id in enumerate(order)}
        assert len(order) == len(graph)
        for edge in graph.prerequisite_edges:
            assert position[edge.prerequisite_id] < position[edge.dependent_id], (
                f"{edge.prerequisite_id} must be resolved before {edge.dependent_id}"
            )

    def test_topological_order_is_deterministic(self, graph):
        assert graph.topological_order() == graph.topological_order()

    def test_golden_chain_is_ordered_correctly(self, graph):
        """The CALC_ENGINE_SPEC.md §15 chain, in the order propagation must visit it."""
        order = graph.topological_order()
        chain = ["prob-conditional", "prob-bayes", "ml-naive-bayes"]
        positions = [order.index(node_id) for node_id in chain]
        assert positions == sorted(positions)


class TestTransitiveClosure:
    def test_multi_hop_ancestors(self, graph):
        # dl-attention -> dl-perceptron -> opt-gradient-descent -> ... -> opt-derivatives
        assert "opt-derivatives" in graph.ancestors("dl-attention")

    def test_leaf_has_no_descendants(self, graph):
        assert graph.descendants("dl-attention") == frozenset()

    def test_root_has_no_ancestors(self, graph):
        assert graph.ancestors("prob-axioms") == frozenset()

    def test_node_is_not_its_own_ancestor_or_descendant(self, graph):
        for node in graph:
            assert node.node_id not in graph.ancestors(node.node_id)
            assert node.node_id not in graph.descendants(node.node_id)

    def test_roots_have_no_incoming_prerequisites(self, graph):
        for node in graph.roots():
            assert graph.prerequisites_of(node.node_id) == ()

    def test_leaves_have_no_dependents(self, graph):
        for node in graph.leaves():
            assert graph.dependents_of(node.node_id) == ()


class TestEdgeWeights:
    def test_weight_travels_with_the_prerequisite_edge(self, graph):
        edges = {e.prerequisite_id: e.weight for e in graph.prerequisite_edges_of("prob-bayes")}
        assert edges == {"prob-conditional": 1.0, "prob-counting": 0.4}

    def test_edge_weight_lookup(self, graph):
        assert graph.edge_weight("ml-naive-bayes", "prob-bayes") == 1.0
        assert graph.edge_weight("ml-logistic-regression", "prob-bayes") == 0.4

    def test_edge_weight_for_a_missing_edge_raises(self, graph):
        with pytest.raises(NodeNotFoundError):
            graph.edge_weight("prob-axioms", "dl-attention")


class TestByAttributeQueries:
    def test_nodes_by_role_returns_only_tagged_nodes(self, graph):
        for node in graph.nodes_by_role("finance-quant"):
            assert node.serves_role("finance-quant")

    def test_nodes_by_role_is_sorted_by_importance_to_that_role(self, graph):
        nodes = graph.nodes_by_role("ai-research")
        scores = [n.requirement_for("ai-research").importance for n in nodes]
        assert scores == sorted(scores, reverse=True)

    def test_role_filter_is_a_lens_not_a_different_graph(self, graph):
        """The same node serves several roles at different importance (A.5.4)."""
        research = {n.node_id for n in graph.nodes_by_role("ai-research")}
        quant = {n.node_id for n in graph.nodes_by_role("finance-quant")}
        assert research & quant, "shared concepts must appear under both roles"

    def test_nodes_by_section(self, graph):
        probability = graph.nodes_by_section("probability")
        assert len(probability) == 9
        assert all(n.section == "probability" for n in probability)

    def test_unknown_section_returns_empty(self, graph):
        assert graph.nodes_by_section("astrology") == ()

    def test_competency_is_scoped_by_section(self, graph):
        """"foundations" exists in several sections; unscoped it must span them."""
        unscoped = graph.nodes_by_competency("foundations")
        scoped = graph.nodes_by_competency("foundations", section="probability")
        assert len(scoped) < len(unscoped)
        assert {n.section for n in scoped} == {"probability"}

    def test_sections_and_competencies_are_sorted_and_unique(self, graph):
        assert list(graph.sections) == sorted(set(graph.sections))
        assert list(graph.competencies()) == sorted(set(graph.competencies()))

    def test_sections_matches_the_fixture(self, graph):
        assert set(graph.sections) == {
            "probability",
            "statistics",
            "linear-algebra",
            "calculus-optimization",
            "classical-ml",
            "deep-learning",
        }


class TestLookupsAndErrors:
    def test_node_lookup(self, graph):
        assert graph.node("prob-bayes").name == "Bayes' Theorem"

    def test_role_lookup(self, graph):
        assert graph.role("ai-research").priority_rank == 1

    def test_membership(self, graph):
        assert "prob-bayes" in graph
        assert "nope" not in graph

    @pytest.mark.parametrize(
        "call",
        [
            lambda g: g.node("nope"),
            lambda g: g.prerequisites_of("nope"),
            lambda g: g.dependents_of("nope"),
            lambda g: g.ancestors("nope"),
            lambda g: g.descendants("nope"),
            lambda g: g.prerequisite_edges_of("nope"),
        ],
    )
    def test_unknown_node_raises(self, graph, call):
        with pytest.raises(NodeNotFoundError, match="nope"):
            call(graph)

    def test_unknown_role_raises(self, graph):
        with pytest.raises(RoleNotFoundError, match="astronaut"):
            graph.nodes_by_role("astronaut")


class TestCrossSectionStructure:
    """Cross-section prerequisites are expected and are what make the graph a DAG, not a tree."""

    def test_fixture_contains_cross_section_prerequisites(self, graph):
        crossing = [
            e
            for e in graph.prerequisite_edges
            if graph.node(e.dependent_id).section != graph.node(e.prerequisite_id).section
        ]
        assert len(crossing) >= 10

    def test_a_node_may_have_multiple_parents(self, graph):
        multi = [n for n in graph if len(graph.prerequisites_of(n.node_id)) >= 2]
        assert multi, "a tree would have none; this must be a DAG"

    def test_ml_logistic_regression_has_three_parents_across_two_sections(self, graph):
        parents = graph.prerequisites_of("ml-logistic-regression")
        assert len(parents) == 3
        assert len({p.section for p in parents}) >= 2
