"""Layer 1 model contracts (BUILD_SPEC.md C.1-C.4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from knowledgeos.curriculum import Depth, Edge, EdgeType, Node, NodeType, Role, RoleRequirement


class TestDepthLadder:
    def test_ladder_is_ordered_low_to_high(self):
        assert Depth.AWARENESS < Depth.WORKING < Depth.DEEP < Depth.DERIVATION

    def test_ordering_supports_max(self):
        assert max([Depth.WORKING, Depth.DERIVATION, Depth.AWARENESS]) is Depth.DERIVATION

    def test_values_match_the_contract(self):
        assert [d.value for d in Depth] == ["awareness", "working", "deep", "derivation"]

    def test_comparison_with_non_depth_is_not_implemented(self):
        with pytest.raises(TypeError):
            _ = Depth.DEEP < "working"


class TestEdgeIdentity:
    def test_edge_id_is_derived_from_its_endpoints(self):
        edge = Edge(
            from_node_id="dl-attention",
            to_node_id="linalg-dot-product",
            type=EdgeType.PREREQUISITE,
            weight=1.0,
        )
        assert edge.edge_id == "dl-attention__requires__linalg-dot-product"

    def test_part_of_edges_use_their_own_infix(self):
        edge = Edge(
            from_node_id="a", to_node_id="b", type=EdgeType.PART_OF, weight=1.0
        )
        assert edge.edge_id == "a__part_of__b"

    def test_dependent_and_prerequisite_read_in_the_contract_direction(self):
        edge = Edge(
            from_node_id="ml-naive-bayes",
            to_node_id="prob-bayes",
            type=EdgeType.PREREQUISITE,
            weight=1.0,
        )
        assert edge.dependent_id == "ml-naive-bayes"
        assert edge.prerequisite_id == "prob-bayes"


class TestNodeRoleLookup:
    @pytest.fixture
    def node(self) -> Node:
        return Node(
            node_id="prob-bayes",
            type=NodeType.ASSESSABLE,
            name="Bayes' Theorem",
            section="probability",
            competency="bayesian",
            description="...",
            roles=(
                RoleRequirement(
                    role_id="ai-research", importance=0.92, required_depth=Depth.DERIVATION
                ),
                RoleRequirement(
                    role_id="software-engineering",
                    importance=0.60,
                    required_depth=Depth.WORKING,
                ),
            ),
        )

    def test_same_concept_carries_different_depth_per_role(self, node):
        assert node.requirement_for("ai-research").required_depth is Depth.DERIVATION
        assert node.requirement_for("software-engineering").required_depth is Depth.WORKING

    def test_unknown_role_returns_none(self, node):
        assert node.requirement_for("finance-quant") is None
        assert not node.serves_role("finance-quant")

    def test_max_required_depth_takes_the_most_demanding(self, node):
        assert node.max_required_depth is Depth.DERIVATION

    def test_untagged_node_has_no_max_depth(self):
        bare = Node(
            node_id="x",
            type=NodeType.CONCEPT,
            name="X",
            section="s",
            competency="c",
            description="d",
        )
        assert bare.max_required_depth is None
        assert bare.role_ids == frozenset()


class TestImmutabilityAndStrictness:
    """The curriculum must never be mutated as a side effect of user activity."""

    def test_nodes_are_frozen(self):
        node = Node(
            node_id="x",
            type=NodeType.CONCEPT,
            name="X",
            section="s",
            competency="c",
            description="d",
        )
        with pytest.raises(ValidationError):
            node.name = "mutated"

    def test_roles_are_frozen(self):
        role = Role(role_id="r", name="R", priority_rank=1)
        with pytest.raises(ValidationError):
            role.priority_rank = 2

    def test_unknown_fields_are_rejected_rather_than_ignored(self):
        with pytest.raises(ValidationError):
            Role.model_validate(
                {"role_id": "r", "name": "R", "priority_rank": 1, "typo_field": 1}
            )

    @pytest.mark.parametrize("bad", [-0.01, 1.01])
    def test_importance_must_be_a_score(self, bad):
        with pytest.raises(ValidationError):
            RoleRequirement(role_id="r", importance=bad, required_depth=Depth.DEEP)

    @pytest.mark.parametrize("bad", [-0.5, 1.5])
    def test_edge_weight_must_be_a_score(self, bad):
        with pytest.raises(ValidationError):
            Edge(from_node_id="a", to_node_id="b", type=EdgeType.PREREQUISITE, weight=bad)

    def test_depth_outside_the_ladder_is_rejected(self):
        with pytest.raises(ValidationError):
            RoleRequirement(role_id="r", importance=0.5, required_depth="implementation")

    def test_schema_version_defaults_when_absent_from_json(self):
        node = Node.model_validate(
            {
                "node_id": "x",
                "type": "concept",
                "name": "X",
                "section": "s",
                "competency": "c",
                "description": "d",
                "roles": [],
                "tags": [],
            }
        )
        assert node.schema_version == 1
