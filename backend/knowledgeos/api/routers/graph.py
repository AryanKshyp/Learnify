"""Browsing the knowledge graph.

Role, competency, and concept are **lenses over one graph**, not separate datasets
(`BUILD_SPEC.md` Part E). Filtering by role narrows which nodes come back and re-weights
importance through that role's eyes; it never produces a different graph.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from knowledgeos.api.dependencies import Context, Curriculum
from knowledgeos.api.schemas import AdvancedMetrics as Advanced
from knowledgeos.api.schemas import (
    EdgeOut,
    GraphOut,
    NodeDetail,
    NodeSummary,
    RoleOut,
    RoleRequirementOut,
)

router = APIRouter(tags=["graph"])


@router.get("/roles", response_model=tuple[RoleOut, ...])
def list_roles(curriculum: Curriculum):
    """The six roles, in the user's priority order."""
    return tuple(
        RoleOut(role_id=r.role_id, name=r.name, priority_rank=r.priority_rank)
        for r in curriculum.roles
    )


@router.get("/sections", response_model=tuple[str, ...])
def list_sections(curriculum: Curriculum):
    return curriculum.sections


@router.get("/sections/{section}/competencies", response_model=tuple[str, ...])
def list_competencies(section: str, curriculum: Curriculum):
    return curriculum.competencies(section)


@router.get("/graph", response_model=GraphOut)
def get_graph(
    context: Context,
    role: str | None = Query(
        None, description="filter to one role AND use it as the importance lens"
    ),
    section: str | None = Query(None, description="filter to one section"),
    competency: str | None = Query(None, description="filter to one competency"),
):
    """The graph, optionally viewed through a role or narrowed to a section/competency.

    Edges are filtered to those whose endpoints both survive the node filter, so the response
    is always internally consistent — a client never receives an edge pointing at a node it
    was not given.
    """
    curriculum = context.curriculum
    snapshot = context.snapshot(active_role_id=role)

    if role is not None:
        nodes = curriculum.nodes_by_role(role)
    elif competency is not None:
        nodes = curriculum.nodes_by_competency(competency, section=section)
    elif section is not None:
        nodes = curriculum.nodes_by_section(section)
    else:
        nodes = curriculum.nodes

    if role is not None and section is not None:
        nodes = tuple(n for n in nodes if n.section == section)
    if role is not None and competency is not None:
        nodes = tuple(n for n in nodes if n.competency == competency)

    included = {n.node_id for n in nodes}
    states = context.states()

    return GraphOut(
        nodes=tuple(NodeSummary.build(n, snapshot, states[n.node_id]) for n in nodes),
        edges=tuple(
            EdgeOut(
                edge_id=e.edge_id,
                from_node_id=e.from_node_id,
                to_node_id=e.to_node_id,
                type=e.type.value,
                weight=e.weight,
            )
            for e in curriculum.edges
            if e.from_node_id in included and e.to_node_id in included
        ),
        roles=tuple(
            RoleOut(role_id=r.role_id, name=r.name, priority_rank=r.priority_rank)
            for r in curriculum.roles
        ),
        sections=tuple(sorted({n.section for n in nodes})),
    )


@router.get("/nodes/{node_id}", response_model=NodeDetail)
def get_node(node_id: str, context: Context, role: str | None = Query(None)):
    """One node in full, including its neighbours and the Advanced metrics.

    `prerequisites` and `dependents` are included because a node's standing is rarely
    explainable on its own — a low effective mastery usually means an upstream problem, and the
    answer should be one response away rather than several.
    """
    curriculum = context.curriculum
    node = curriculum.node(node_id)  # raises NodeNotFoundError -> 404
    snapshot = context.snapshot(active_role_id=role)
    states = context.states()
    state = states[node_id]

    return NodeDetail(
        node_id=node.node_id,
        name=node.name,
        section=node.section,
        competency=node.competency,
        type=node.type.value,
        description=node.description,
        tags=node.tags,
        roles=tuple(
            RoleRequirementOut(
                role_id=r.role_id, importance=r.importance, required_depth=r.required_depth
            )
            for r in node.roles
        ),
        mastery=snapshot.effective_mastery[node_id],
        importance=snapshot.current_importance[node_id],
        status=snapshot.status[node_id],
        is_frontier=snapshot.frontier[node_id],
        prerequisites=tuple(
            NodeSummary.build(p, snapshot, states[p.node_id])
            for p in curriculum.prerequisites_of(node_id)
        ),
        dependents=tuple(
            NodeSummary.build(d, snapshot, states[d.node_id])
            for d in curriculum.dependents_of(node_id)
        ),
        advanced=Advanced(
            intrinsic_mastery=state.intrinsic_mastery,
            effective_mastery=snapshot.effective_mastery[node_id],
            retention=snapshot.retention[node_id],
            prerequisite_confidence=snapshot.prerequisite_confidence[node_id],
            stability=state.stability,
            difficulty=state.difficulty,
            assessment_variance=snapshot.variance[node_id],
            engine_confidence=state.engine_confidence,
            session_count=state.session_count,
            last_assessed_at=state.last_assessed_at,
            next_review_at=state.next_review_at,
            critical_path_value=snapshot.critical_path_value[node_id],
            leverage=snapshot.leverage[node_id],
            learning_cost=snapshot.learning_cost[node_id],
            target=snapshot.targets[node_id],
        ),
        last_gaps=state.last_gaps,
    )
