"""Recommendations, readiness, and the home-view overview.

Recommendations live on their own page grouped **Overall / Role / Competency**
(`BUILD_SPEC.md` Part E) so the user can follow interest without losing guidance — when one
section gets boring, pull the top item from another and stay on a sensible path either way.

Every recommendation carries the reason it was chosen. A ranking nobody can interrogate is
indistinguishable from a guess (A.5.6).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from knowledgeos.api.dependencies import Context
from knowledgeos.api.schemas import (
    KnowledgeHealthOut,
    NodeSummary,
    OverviewOut,
    ReadinessOut,
    RecommendationGroup,
    RecommendationOut,
    build_readiness,
)
from knowledgeos.engine import recommend, unexplored

router = APIRouter(tags=["recommendations"])


def _explain(context: Context, node_id: str, snapshot) -> str:
    """Why this node, in one sentence a human can check."""
    curriculum = context.curriculum
    reasons = []

    blocking = [
        role.role_id
        for role in curriculum.roles
        if snapshot.readiness[role.role_id].bottleneck_node_id == node_id
    ]
    if blocking:
        reasons.append(f"currently the bottleneck for {', '.join(blocking)}")

    unlocks = len(curriculum.descendants(node_id))
    if unlocks:
        reasons.append(f"unlocks {unlocks} downstream concept{'s' if unlocks != 1 else ''}")

    cost = snapshot.learning_cost[node_id]
    if cost:
        reasons.append(f"~{cost:.1f}h to reach its depth target")

    if snapshot.frontier[node_id]:
        reasons.append("prerequisites are already met")

    return "; ".join(reasons) or "on the learning frontier"


def _to_out(context: Context, candidate, snapshot) -> RecommendationOut:
    node = context.curriculum.node(candidate.node_id)
    return RecommendationOut(
        node_id=node.node_id,
        name=node.name,
        section=node.section,
        competency=node.competency,
        priority=candidate.priority,
        expected_readiness_gain=candidate.expected_readiness_gain,
        learning_cost_hours=candidate.learning_cost,
        leverage=candidate.leverage,
        current_importance=candidate.current_importance,
        reason=_explain(context, node.node_id, snapshot),
    )


@router.get("/recommendations", response_model=RecommendationGroup)
def overall(context: Context, limit: int = Query(5, ge=1, le=50)):
    """The Overall list — best next steps across everything, MMR-diversified."""
    snapshot = context.snapshot()
    picks = recommend(context.curriculum, snapshot, limit=limit)
    return RecommendationGroup(
        lens="overall",
        recommendations=tuple(_to_out(context, c, snapshot) for c in picks),
    )


@router.get("/recommendations/role/{role_id}", response_model=RecommendationGroup)
def by_role(role_id: str, context: Context, limit: int = Query(5, ge=1, le=50)):
    """Recommendations through one role's lens.

    The role changes both which nodes are eligible and how importance is weighted, so this is a
    genuinely different ranking rather than a filtered copy of Overall.
    """
    context.curriculum.role(role_id)  # 404 on unknown role
    snapshot = context.snapshot(active_role_id=role_id)
    eligible = {n.node_id for n in context.curriculum.nodes_by_role(role_id)}
    picks = [
        c
        for c in recommend(context.curriculum, snapshot, limit=limit * 4)
        if c.node_id in eligible
    ][:limit]
    return RecommendationGroup(
        lens="role",
        key=role_id,
        recommendations=tuple(_to_out(context, c, snapshot) for c in picks),
    )


@router.get("/recommendations/competency/{section}", response_model=RecommendationGroup)
def by_competency(section: str, context: Context, limit: int = Query(5, ge=1, le=50)):
    """Recommendations within one section."""
    snapshot = context.snapshot()
    eligible = {n.node_id for n in context.curriculum.nodes_by_section(section)}
    picks = [
        c
        for c in recommend(context.curriculum, snapshot, limit=limit * 8)
        if c.node_id in eligible
    ][:limit]
    return RecommendationGroup(
        lens="competency",
        key=section,
        recommendations=tuple(_to_out(context, c, snapshot) for c in picks),
    )


@router.get("/unexplored", response_model=tuple[NodeSummary, ...])
def unexplored_queue(context: Context, limit: int = Query(20, ge=1, le=200)):
    """The cold-start backlog — nodes with no evidence at all.

    Deliberately separate from recommendations: "we have never looked here" is a different
    statement from "you are weak here", and mixing them would make the second unreadable.
    """
    snapshot = context.snapshot()
    states = context.states()
    ids = unexplored(context.curriculum, states, snapshot)[:limit]
    return tuple(
        NodeSummary.build(context.curriculum.node(n), snapshot, states[n]) for n in ids
    )


@router.get("/readiness", response_model=tuple[ReadinessOut, ...])
def readiness(context: Context):
    """Readiness per role, each with the node holding it back."""
    return build_readiness(context.curriculum, context.snapshot())


@router.get("/overview", response_model=OverviewOut)
def overview(context: Context, role: str | None = Query(None)):
    """Everything the home view needs, in one call."""
    snapshot = context.snapshot(active_role_id=role)
    states = context.states()
    health = snapshot.health
    return OverviewOut(
        health=KnowledgeHealthOut(
            score=health.score,
            coverage=health.coverage,
            mean_effective_mastery=health.mean_effective_mastery,
            mean_retention=health.mean_retention,
            critical_gap_ratio=health.critical_gap_ratio,
            critical_node_count=health.critical_node_count,
            frontier_size=health.frontier_size,
        ),
        readiness=build_readiness(context.curriculum, snapshot),
        frontier_size=len(snapshot.frontier_ids),
        unexplored_count=len(unexplored(context.curriculum, states, snapshot)),
        total_nodes=len(context.curriculum),
    )
