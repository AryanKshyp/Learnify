"""Parsing and validation for the curriculum (Layer 1).

Loading is all-or-nothing and reports every problem it finds, not just the first. A curriculum
that fails any check is refused outright rather than loaded in a degraded state — downstream
layers are entitled to assume the graph is sound.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx
from pydantic import ValidationError

from .errors import CurriculumValidationError, CyclicPrerequisiteError
from .graph import CurriculumGraph
from .models import Edge, EdgeType, Node, Role


def load_curriculum(source: Path | str | dict[str, Any]) -> CurriculumGraph:
    """Load, validate, and return a curriculum.

    Accepts a path to a JSON file or an already-parsed mapping (handy for tests that inject a
    deliberate defect).

    Raises:
        CurriculumValidationError: schema, referential-integrity, or duplication problems.
        CyclicPrerequisiteError: the prerequisite subgraph is cyclic; the path is named.
    """
    payload = _read(source)
    roles, nodes, edges = _parse(payload)
    _validate(roles, nodes, edges)
    _assert_acyclic(nodes, edges)
    return CurriculumGraph(roles=roles, nodes=nodes, edges=edges)


def _read(source: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    path = Path(source)
    if not path.is_file():
        raise CurriculumValidationError([f"curriculum file not found: {path}"])
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CurriculumValidationError([f"{path} is not valid JSON: {exc}"]) from exc
    if not isinstance(payload, dict):
        raise CurriculumValidationError([f"{path}: top level must be an object"])
    return payload


def _parse(payload: dict[str, Any]) -> tuple[list[Role], list[Node], list[Edge]]:
    """Turn raw JSON into models, collecting *all* schema errors before giving up."""
    problems: list[str] = []

    for key in ("roles", "nodes", "edges"):
        if key not in payload:
            problems.append(f"missing top-level key: {key!r}")
        elif not isinstance(payload[key], list):
            problems.append(f"top-level {key!r} must be a list")
    if problems:
        raise CurriculumValidationError(problems)

    roles: list[Role] = []
    nodes: list[Node] = []
    edges: list[Edge] = []

    for index, raw in enumerate(payload["roles"]):
        try:
            roles.append(Role.model_validate(raw))
        except ValidationError as exc:
            problems.extend(_describe(exc, "role", index, raw.get("role_id")))

    for index, raw in enumerate(payload["nodes"]):
        try:
            nodes.append(Node.model_validate(raw))
        except ValidationError as exc:
            problems.extend(_describe(exc, "node", index, raw.get("node_id")))

    for index, raw in enumerate(payload["edges"]):
        try:
            edges.append(Edge.model_validate(raw))
        except ValidationError as exc:
            label = f"{raw.get('from_node_id')} -> {raw.get('to_node_id')}"
            problems.extend(_describe(exc, "edge", index, label))

    if problems:
        raise CurriculumValidationError(problems)
    return roles, nodes, edges


def _describe(exc: ValidationError, kind: str, index: int, label: str | None) -> list[str]:
    name = label or f"index {index}"
    out = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        out.append(f"{kind} {name}: {location}: {error['msg']}")
    return out


def _validate(roles: list[Role], nodes: list[Node], edges: list[Edge]) -> None:
    """Uniqueness, referential integrity, and the shared-concept rule."""
    problems: list[str] = []

    role_ids = {role.role_id for role in roles}
    for role_id, count in Counter(role.role_id for role in roles).items():
        if count > 1:
            problems.append(f"duplicate role_id: {role_id!r} ({count} times)")
    for rank, count in Counter(role.priority_rank for role in roles).items():
        if count > 1:
            problems.append(f"duplicate priority_rank: {rank} ({count} roles share it)")

    node_ids = {node.node_id for node in nodes}
    for node_id, count in Counter(node.node_id for node in nodes).items():
        if count > 1:
            problems.append(f"duplicate node_id: {node_id!r} ({count} times)")

    for node in nodes:
        seen: set[str] = set()
        for requirement in node.roles:
            if requirement.role_id not in role_ids:
                problems.append(
                    f"node {node.node_id!r}: unknown role_id {requirement.role_id!r}"
                )
            if requirement.role_id in seen:
                problems.append(
                    f"node {node.node_id!r}: role {requirement.role_id!r} tagged more than once"
                )
            seen.add(requirement.role_id)

    # A concept must exist exactly once (A.5.4). Two nodes sharing a name is the signature of
    # the duplicate-concept mistake this rule exists to prevent.
    by_name: dict[str, list[str]] = {}
    for node in nodes:
        by_name.setdefault(node.name.strip().casefold(), []).append(node.node_id)
    for name, ids in by_name.items():
        if len(ids) > 1:
            problems.append(
                f"duplicate concept name {name!r} on nodes {sorted(ids)} - "
                "a shared concept must be ONE node with multiple role tags"
            )

    for edge in edges:
        if edge.from_node_id not in node_ids:
            problems.append(
                f"edge {edge.edge_id!r}: from_node_id {edge.from_node_id!r} does not exist"
            )
        if edge.to_node_id not in node_ids:
            problems.append(
                f"edge {edge.edge_id!r}: to_node_id {edge.to_node_id!r} does not exist"
            )
        if edge.from_node_id == edge.to_node_id:
            problems.append(f"edge {edge.edge_id!r}: self-loop on {edge.from_node_id!r}")

    for edge_id, count in Counter(edge.edge_id for edge in edges).items():
        if count > 1:
            problems.append(f"duplicate edge: {edge_id!r} ({count} times)")

    if problems:
        raise CurriculumValidationError(problems)


def _assert_acyclic(nodes: list[Node], edges: list[Edge]) -> None:
    """Reject a cyclic prerequisite subgraph, naming the offending path.

    Built in the same orientation as CurriculumGraph (prerequisite → dependent) so the
    reported path reads in dependency order.
    """
    dag = nx.DiGraph()
    dag.add_nodes_from(node.node_id for node in nodes)
    for edge in edges:
        if edge.type is EdgeType.PREREQUISITE:
            dag.add_edge(edge.prerequisite_id, edge.dependent_id)

    if nx.is_directed_acyclic_graph(dag):
        return

    cycle_edges = nx.find_cycle(dag, orientation="original")
    path = [source for source, _target, *_ in cycle_edges]
    path.append(path[0])  # close the loop so the report reads as a cycle
    raise CyclicPrerequisiteError(path)
