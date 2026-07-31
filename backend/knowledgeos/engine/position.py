"""Pipeline stages 7-8 — frontier, critical path, leverage, current importance.

CALC_ENGINE_SPEC.md §9, §10.

The frontier is the idea that makes recommendations both fast and explainable: a node is only
worth suggesting if its prerequisites are actually ready. A weak node whose prerequisites are
themselves weak is NOT on the frontier — the engine routes to the prerequisite instead, which
is exactly the "your real problem is upstream" behaviour the product exists to provide.
"""

from __future__ import annotations

from knowledgeos.curriculum import CurriculumGraph

from .config import DEFAULT_CONFIG, EngineConfig
from .observation import clamp


def min_max_normalize(values: dict[str, float]) -> dict[str, float]:
    """Scale to 0..1 across all nodes.

    A flat distribution maps to 0.0 rather than 1.0: if nothing differentiates the nodes, the
    factor should contribute nothing to ranking instead of maximally inflating everything.
    """
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if high - low <= 0.0:
        return dict.fromkeys(values, 0.0)
    span = high - low
    return {key: (value - low) / span for key, value in values.items()}


def is_frontier(
    effective_mastery: float,
    prerequisite_confidence: float,
    target: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> bool:
    """On the frontier = not yet sufficient, but ready to be learned.

    Both halves matter. Drop the first and you recommend things already known; drop the second
    and you recommend things the user cannot yet understand.
    """
    return (
        effective_mastery < target
        and prerequisite_confidence >= config.frontier_prerequisite_threshold
    )


def intrinsic_importance(curriculum: CurriculumGraph, node_id: str) -> float:
    """Highest static importance this node carries across the roles it serves."""
    node = curriculum.node(node_id)
    return max((r.importance for r in node.roles), default=0.0)


def critical_path_values(
    curriculum: CurriculumGraph, config: EngineConfig = DEFAULT_CONFIG
) -> dict[str, float]:
    """CPV — how much high-importance material sits downstream of each node.

        CPV_raw(X) = Σ over descendants d of  importance(d) · ζ^hops(X→d)

    ζ = 0.6 discounts per hop, so being a direct gateway to something critical counts for far
    more than being five steps upstream of it. Normalised across all nodes.

    This is a pure property of the curriculum: it depends on no user state, so it can be
    computed once per graph rather than per recompute.
    """
    import networkx as nx  # noqa: PLC0415 - graph algorithms only, no I/O

    dag = curriculum.dag
    discount = config.critical_path_discount
    raw: dict[str, float] = {}

    for node_id in dag.nodes:
        hops = nx.single_source_shortest_path_length(dag, node_id)
        total = 0.0
        for descendant, distance in hops.items():
            if descendant == node_id:
                continue
            total += intrinsic_importance(curriculum, descendant) * (discount**distance)
        raw[node_id] = total

    return min_max_normalize(raw)


def leverage_values(
    curriculum: CurriculumGraph,
    critical_path: dict[str, float],
    config: EngineConfig = DEFAULT_CONFIG,
) -> dict[str, float]:
    """Lev — breadth of impact of improving a node.

        Lev_raw = a·immediate_unlocks + b·indirect_unlocks + c·role_overlap + d·CPV

    Then min-max normalised across all nodes, exactly as the spec specifies.

    NOTE (flagged, not silently corrected): the four terms are on very different scales.
    `immediate_unlocks` and `indirect_unlocks` are unbounded counts while CPV and role_overlap
    are small, so in a large graph the count terms dominate and CPV contributes almost nothing
    before normalisation. The spec is explicit that normalisation happens AFTER combining, so
    that is what is implemented; see PROJECT_STATE.md for the observation. Normalising each
    term first would be a change to the spec's math, not an implementation detail.
    """
    raw: dict[str, float] = {}
    for node in curriculum:
        node_id = node.node_id
        immediate = len(curriculum.dependents_of(node_id))
        indirect = len(curriculum.descendants(node_id))
        role_overlap = sum(r.importance for r in node.roles)
        raw[node_id] = (
            config.leverage_immediate * immediate
            + config.leverage_indirect * indirect
            + config.leverage_role_overlap * role_overlap
            + config.leverage_critical_path * critical_path.get(node_id, 0.0)
        )
    return min_max_normalize(raw)


def current_importance(
    curriculum: CurriculumGraph,
    node_id: str,
    *,
    leverage: float,
    active_role_id: str | None = None,
    date_factor: float = 1.0,
    is_bottleneck: bool = False,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """CurImp — importance as of right now, derived rather than authored.

        CurImp = IntrinsicImp_r* · date_factor · bottleneck_factor · (1 + η·Lev)

    The static graph weights are never rewritten; this is recomputed each pass. `r*` is the
    active role, or the highest-priority role tagging the node when none is set.

    May exceed 1.0 by design — it is a ranking multiplier, not a probability.
    """
    node = curriculum.node(node_id)

    if active_role_id is not None:
        requirement = node.requirement_for(active_role_id)
        base = requirement.importance if requirement else 0.0
    else:
        ranked = sorted(
            (r for r in node.roles),
            key=lambda r: curriculum.role(r.role_id).priority_rank,
        )
        base = ranked[0].importance if ranked else 0.0

    bottleneck_factor = 1.0 + config.bottleneck_boost if is_bottleneck else 1.0
    return (
        base
        * date_factor
        * bottleneck_factor
        * (1.0 + config.leverage_importance_boost * clamp(leverage))
    )
