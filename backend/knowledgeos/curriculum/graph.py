"""The in-memory curriculum graph and its query surface (Layer 1).

## Edge direction — read this before touching traversal

The JSON contract (C.2) stores an edge as **dependent → prerequisite** (`from` requires `to`).
The networkx DiGraph built here is deliberately the **reverse**: an arc runs
**prerequisite → dependent**.

That inversion buys three things, and every one of them is load-bearing:

    nx.ancestors(G, X)      -> everything X transitively depends on   (its prerequisites)
    nx.descendants(G, X)    -> everything that transitively depends on X (its dependents)
    nx.topological_sort(G)  -> prerequisites BEFORE dependents

The third is required by CALC_ENGINE_SPEC.md §7: prerequisite confidence must be computed in
topological order with prerequisites resolved first. Getting this backwards would still
produce a valid-looking DAG and silently wrong propagation, so it is asserted in the tests.

`part_of` edges are hierarchy, not dependency. They are kept out of the prerequisite DAG
entirely — mixing them would corrupt every traversal above — and are exposed separately.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import networkx as nx

from .errors import NodeNotFoundError, RoleNotFoundError
from .models import Edge, EdgeType, Node, Role


class CurriculumGraph:
    """An immutable, validated curriculum.

    Construct via `knowledgeos.curriculum.loader.load_curriculum`, which validates first —
    this class assumes its inputs are already known-good.
    """

    def __init__(
        self,
        roles: Iterable[Role],
        nodes: Iterable[Node],
        edges: Iterable[Edge],
    ) -> None:
        self._roles: dict[str, Role] = {role.role_id: role for role in roles}
        self._nodes: dict[str, Node] = {node.node_id: node for node in nodes}
        self._edges: tuple[Edge, ...] = tuple(edges)

        self._prerequisite_edges = tuple(
            edge for edge in self._edges if edge.type is EdgeType.PREREQUISITE
        )
        self._part_of_edges = tuple(
            edge for edge in self._edges if edge.type is EdgeType.PART_OF
        )

        # prerequisite -> dependent (see module docstring)
        self._dag = nx.DiGraph()
        self._dag.add_nodes_from(self._nodes)
        for edge in self._prerequisite_edges:
            self._dag.add_edge(edge.prerequisite_id, edge.dependent_id, weight=edge.weight)

    # ------------------------------------------------------------------ basics

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def __iter__(self) -> Iterator[Node]:
        return iter(self._nodes.values())

    @property
    def dag(self) -> nx.DiGraph:
        """The prerequisite DAG, oriented prerequisite → dependent. Read-only by convention."""
        return self._dag

    @property
    def nodes(self) -> tuple[Node, ...]:
        return tuple(self._nodes.values())

    @property
    def edges(self) -> tuple[Edge, ...]:
        return self._edges

    @property
    def prerequisite_edges(self) -> tuple[Edge, ...]:
        return self._prerequisite_edges

    @property
    def part_of_edges(self) -> tuple[Edge, ...]:
        """Hierarchy edges. Deliberately excluded from the prerequisite DAG."""
        return self._part_of_edges

    @property
    def roles(self) -> tuple[Role, ...]:
        """Roles in the user's priority order (rank 1 first)."""
        return tuple(sorted(self._roles.values(), key=lambda role: role.priority_rank))

    def node(self, node_id: str) -> Node:
        try:
            return self._nodes[node_id]
        except KeyError:
            raise NodeNotFoundError(node_id) from None

    def role(self, role_id: str) -> Role:
        try:
            return self._roles[role_id]
        except KeyError:
            raise RoleNotFoundError(role_id) from None

    def _require(self, node_id: str) -> str:
        if node_id not in self._nodes:
            raise NodeNotFoundError(node_id)
        return node_id

    # ------------------------------------------------------------- by-attribute

    def nodes_by_role(self, role_id: str) -> tuple[Node, ...]:
        """Every node serving `role_id`, most important to that role first."""
        if role_id not in self._roles:
            raise RoleNotFoundError(role_id)
        matching = [node for node in self._nodes.values() if node.serves_role(role_id)]
        matching.sort(
            key=lambda node: (
                -_importance(node, role_id),
                node.node_id,
            )
        )
        return tuple(matching)

    def nodes_by_section(self, section: str) -> tuple[Node, ...]:
        return tuple(
            node for node in self._nodes.values() if node.section == section
        )

    def nodes_by_competency(
        self, competency: str, *, section: str | None = None
    ) -> tuple[Node, ...]:
        """Nodes in a competency.

        `competency` is only unique *within* a section (e.g. "foundations" appears under both
        probability and linear-algebra), so pass `section` to disambiguate.
        """
        return tuple(
            node
            for node in self._nodes.values()
            if node.competency == competency and (section is None or node.section == section)
        )

    @property
    def sections(self) -> tuple[str, ...]:
        return tuple(sorted({node.section for node in self._nodes.values()}))

    def competencies(self, section: str | None = None) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    node.competency
                    for node in self._nodes.values()
                    if section is None or node.section == section
                }
            )
        )

    # ---------------------------------------------------------------- traversal

    def prerequisites_of(self, node_id: str) -> tuple[Node, ...]:
        """DIRECT prerequisites — the nodes `node_id` immediately requires."""
        self._require(node_id)
        return tuple(self._nodes[p] for p in sorted(self._dag.predecessors(node_id)))

    def dependents_of(self, node_id: str) -> tuple[Node, ...]:
        """DIRECT dependents — the nodes that immediately require `node_id`."""
        self._require(node_id)
        return tuple(self._nodes[d] for d in sorted(self._dag.successors(node_id)))

    def ancestors(self, node_id: str) -> frozenset[str]:
        """ALL transitive prerequisites of `node_id` (excluding itself)."""
        self._require(node_id)
        return frozenset(nx.ancestors(self._dag, node_id))

    def descendants(self, node_id: str) -> frozenset[str]:
        """ALL transitive dependents of `node_id` (excluding itself).

        This is the set CALC_ENGINE_SPEC.md §9 sums over for critical-path value.
        """
        self._require(node_id)
        return frozenset(nx.descendants(self._dag, node_id))

    def prerequisite_edges_of(self, node_id: str) -> tuple[Edge, ...]:
        """Direct prerequisite edges of `node_id`, carrying their weights.

        Prerequisite confidence (CALC_ENGINE_SPEC.md §7) is a weighted blend over exactly
        these, so the weight must travel with the edge rather than be looked up separately.
        """
        self._require(node_id)
        return tuple(
            sorted(
                (e for e in self._prerequisite_edges if e.dependent_id == node_id),
                key=lambda e: e.prerequisite_id,
            )
        )

    def edge_weight(self, dependent_id: str, prerequisite_id: str) -> float:
        """Weight of the prerequisite edge `dependent → prerequisite`."""
        self._require(dependent_id)
        self._require(prerequisite_id)
        if not self._dag.has_edge(prerequisite_id, dependent_id):
            raise NodeNotFoundError(f"{dependent_id} -> {prerequisite_id} (no such edge)")
        return float(self._dag.edges[prerequisite_id, dependent_id]["weight"])

    def topological_order(self) -> tuple[str, ...]:
        """Node ids with every prerequisite before every node that depends on it.

        Deterministic: ties are broken lexicographically, so identical input always yields an
        identical order. The engine's propagation depends on this being reproducible.
        """
        return tuple(nx.lexicographical_topological_sort(self._dag))

    def roots(self) -> tuple[Node, ...]:
        """Nodes with no prerequisites — the places a learner can start unblocked."""
        return tuple(
            self._nodes[n] for n in sorted(self._dag.nodes) if self._dag.in_degree(n) == 0
        )

    def leaves(self) -> tuple[Node, ...]:
        """Nodes nothing else depends on."""
        return tuple(
            self._nodes[n] for n in sorted(self._dag.nodes) if self._dag.out_degree(n) == 0
        )


def _importance(node: Node, role_id: str) -> float:
    requirement = node.requirement_for(role_id)
    return requirement.importance if requirement else 0.0
