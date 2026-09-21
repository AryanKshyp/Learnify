"""The canonical pipeline, and the stages it sequences. CALC_ENGINE_SPEC.md §1.

Two entry points:

* `apply_session` — stages 1-4, for the one node that was assessed.
* `recompute` — stages 5-14, for the assessed node plus everything whose value could change.
  This is also the read path answering "what should I study next?" with no new assessment.

Ordering is not negotiable: PC before EM, EM before readiness, readiness before priority. Each
stage is a pure function of the previous, and every produced value carries a
`computation_trace` so any score can answer "how was this calculated?" from stored evidence.

The stages with no consumer but this file live here rather than in a module each — frontier and
graph position (§9-10), status (§13) and knowledge health (§14). Splitting them out put one
number's derivation across four files without hiding anything: each interface was as wide as
its implementation, so there was nothing to read the small module *instead of*. The stages that
are genuinely shared stay separate and are imported above: `observation`, `retention`,
`propagation`, `readiness` and `recommend` all have callers besides this one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from knowledgeos.curriculum import CurriculumGraph, Depth
from knowledgeos.state import KnowledgeState, Status

from .config import DEFAULT_CONFIG, EngineConfig
from .observation import (
    EvidenceQuality,
    Observation,
    SessionAbility,
    clamp,
    evidence_quality,
    normalized_variance,
    session_ability,
    update_intrinsic_mastery,
)
from .propagation import propagate
from .readiness import RoleReadiness, all_role_readiness
from .recommend import (
    Candidate,
    cold_start_queue,
    diversify,
    expected_readiness_gain,
    learning_cost,
    min_max_normalize,
    score_candidates,
)
from .retention import (
    adjust_difficulty,
    days_until_review,
    initial_difficulty,
    retention,
    update_stability,
)


@dataclass(frozen=True, slots=True)
class SessionUpdate:
    """Result of stages 1-4 for the assessed node.

    `days_until_review` is a number of days, not a timestamp: the engine reads no clock, so the
    caller adds it to `last_assessed_at`.
    """

    node_id: str
    intrinsic_mastery: float
    intrinsic_mastery_before: float
    stability: float
    difficulty: float
    retention: float
    days_until_review: float
    variance_raw: float
    running_mean: float
    variance: float
    engine_confidence: float
    session_count: int
    ability: SessionAbility
    quality: EvidenceQuality
    trace: dict[str, Any] = field(default_factory=dict)


def apply_session(
    *,
    state: KnowledgeState,
    observation: Observation,
    required_depth: Depth,
    days_since_last_session: float = 0.0,
    previous_running_mean: float = 0.0,
    config: EngineConfig = DEFAULT_CONFIG,
) -> SessionUpdate:
    """Stages 1-4: observation → confidence/variance → intrinsic mastery → stability.

    Immediately after a session Δt = 0, so retention is 1.0 by definition.
    """
    ability = session_ability(observation, required_depth, config)
    quality = evidence_quality(
        ability,
        previous_mean=previous_running_mean,
        previous_variance_raw=state.assessment_variance_raw,
        session_count=state.session_count,
        days_since_last_session=days_since_last_session,
        llm_confidence=observation.llm_confidence,
        config=config,
    )

    mastery_before = state.intrinsic_mastery
    mastery = update_intrinsic_mastery(mastery_before, ability, quality.evidence_weight, config)

    difficulty = (
        initial_difficulty(required_depth, config)
        if state.difficulty is None
        else adjust_difficulty(state.difficulty, variance=quality.variance, config=config)
    )
    stability = update_stability(
        state.stability,
        quality=ability.quality,
        mastery=mastery,
        difficulty=difficulty,
        config=config,
    )

    return SessionUpdate(
        node_id=state.node_id,
        intrinsic_mastery=mastery,
        intrinsic_mastery_before=mastery_before,
        stability=stability,
        difficulty=difficulty,
        retention=1.0,  # Δt = 0 at the moment of assessment
        days_until_review=days_until_review(stability, config),
        variance_raw=quality.variance_raw,
        running_mean=quality.running_mean,
        variance=quality.variance,
        engine_confidence=quality.confidence,
        session_count=state.session_count + 1,
        ability=ability,
        quality=quality,
        trace={
            "stage_1_observation": {
                "inputs": {
                    "recall": observation.recall,
                    "depth": observation.depth,
                    "transfer": observation.transfer,
                    "response_time_rating": observation.response_time_rating,
                },
                "required_depth": required_depth.value,
                "weights": asdict(config.weights_for(required_depth)),
                "O_raw": ability.raw,
                "O": ability.value,
            },
            "stage_2_evidence": {
                "running_mean": quality.running_mean,
                "variance_raw": quality.variance_raw,
                "variance_normalized": quality.variance,
                "engine_confidence": quality.confidence,
                "evidence_weight": quality.evidence_weight,
                "llm_confidence_input": observation.llm_confidence,
                "llm_weight_cap": config.g_llm,
            },
            "stage_3_mastery": {
                "alpha": config.alpha_base * quality.evidence_weight,
                "before": mastery_before,
                "after": mastery,
            },
            "stage_4_stability": {
                "difficulty": difficulty,
                "stability_before": state.stability,
                "stability_after": stability,
                "days_until_review": days_until_review(stability, config),
            },
        },
    )


# Stages 7-8 — frontier, critical path, leverage, current importance. §9, §10.
#
# The frontier is the idea that makes recommendations both fast and explainable: a node is only
# worth suggesting if its prerequisites are actually ready. A weak node whose prerequisites are
# themselves weak is NOT on the frontier — the engine routes to the prerequisite instead, which
# is exactly the "your real problem is upstream" behaviour the product exists to provide.

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


# Stage 13 — status derivation. §13. Status is always derived from evidence, never set by hand.
#
# A deliberate deviation from the spec's stated evaluation order: the spec lists the tiers as
# `unassessed → learning → practiced → retained → mastered` and says "evaluate top-down; first
# match wins". Taken literally that is wrong: `retained` requires EM ≥ 0.70 and `mastered`
# requires EM ≥ 0.85, so a genuinely mastered node matches `retained` first and can never be
# reported as mastered. Resolved by evaluating **most demanding first** — plainly the intent,
# since the tiers are otherwise a ladder:
#
#     unassessed  (no evidence at all, so nothing else can apply)
#     learning    (evidence is weak OR too inconsistent to trust)
#     mastered
#     retained
#     practiced
#
# `learning` stays ahead of the strong tiers on purpose. Its σ² clause means "the observations
# disagree with each other"; a node whose evidence is self-contradictory should not be reported
# as retained regardless of how high the average looks. `mastered` already demands low variance,
# so it is unaffected.

def derive_status(
    *,
    effective_mastery: float,
    retention: float,
    variance: float,
    session_count: int,
    target: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> Status:
    """The node's status given its current evidence."""
    if session_count == 0:
        return Status.UNASSESSED

    if (
        effective_mastery < config.status_learning_em
        or variance > config.status_learning_variance
    ):
        return Status.LEARNING

    enough_sessions = session_count >= config.status_min_sessions

    if (
        effective_mastery >= max(config.status_mastered_em, target)
        and retention >= config.status_mastered_retention
        and variance <= config.status_mastered_variance
        and enough_sessions
    ):
        return Status.MASTERED

    if (
        effective_mastery >= config.status_practiced_em
        and retention >= config.status_retained_retention
        and enough_sessions
    ):
        return Status.RETAINED

    return Status.PRACTICED


# Stage 14 — knowledge health. §14.
#
# One number for the home view, always reported alongside its four components. A single opaque
# score invites the question "why is it 62?", so the parts that produced it travel with it.
#
# "Critical" means intrinsic importance at or above the threshold for the active role — health
# deliberately ignores peripheral nodes, so grinding low-importance material cannot inflate it.

@dataclass(frozen=True, slots=True)
class KnowledgeHealth:
    """The score, and the four components that produced it."""

    score: float  # 0..100
    coverage: float
    mean_effective_mastery: float
    mean_retention: float
    critical_gap_ratio: float
    critical_node_count: int
    frontier_size: int


def knowledge_health(
    curriculum: CurriculumGraph,
    *,
    effective_mastery: dict[str, float],
    retention: dict[str, float],
    session_counts: dict[str, int],
    targets: dict[str, float],
    frontier_size: int,
    active_role_id: str | None = None,
    config: EngineConfig = DEFAULT_CONFIG,
) -> KnowledgeHealth:
    """Health = 100·(h1·coverage + h2·mean_EM + h3·mean_R + h4·(1 − gap_ratio)).

    All three means are importance-weighted, so a weak node that matters counts for more than
    a weak node that does not.
    """
    role_id = active_role_id or curriculum.roles[0].role_id
    threshold = config.critical_importance_threshold

    critical: list[tuple[str, float]] = []
    for node in curriculum.nodes_by_role(role_id):
        requirement = node.requirement_for(role_id)
        if requirement and requirement.importance >= threshold:
            critical.append((node.node_id, requirement.importance))

    if not critical:
        return KnowledgeHealth(0.0, 0.0, 0.0, 0.0, 0.0, 0, frontier_size)

    total_importance = sum(importance for _, importance in critical)
    assessed = sum(1 for node_id, _ in critical if session_counts.get(node_id, 0) > 0)

    coverage = assessed / len(critical)
    mean_em = (
        sum(importance * effective_mastery.get(nid, 0.0) for nid, importance in critical)
        / total_importance
    )
    mean_retention = (
        sum(importance * retention.get(nid, 0.0) for nid, importance in critical)
        / total_importance
    )
    gaps = sum(
        1
        for node_id, _ in critical
        if effective_mastery.get(node_id, 0.0) < targets.get(node_id, 0.0)
    )
    gap_ratio = gaps / len(critical)

    score = 100.0 * (
        config.health_coverage * coverage
        + config.health_mean_em * mean_em
        + config.health_mean_retention * mean_retention
        + config.health_gap * (1.0 - gap_ratio)
    )

    return KnowledgeHealth(
        score=score,
        coverage=coverage,
        mean_effective_mastery=mean_em,
        mean_retention=mean_retention,
        critical_gap_ratio=gap_ratio,
        critical_node_count=len(critical),
        frontier_size=frontier_size,
    )


@dataclass(frozen=True, slots=True)
class EngineSnapshot:
    """Everything stages 5-14 produce, for the whole graph."""

    prerequisite_confidence: dict[str, float]
    effective_mastery: dict[str, float]
    retention: dict[str, float]
    #: σ² on 0..1 — the lens on the stored raw variance, for thresholds and display.
    variance: dict[str, float]
    targets: dict[str, float]
    frontier: dict[str, bool]
    critical_path_value: dict[str, float]
    leverage: dict[str, float]
    current_importance: dict[str, float]
    learning_cost: dict[str, float]
    status: dict[str, Status]
    readiness: dict[str, RoleReadiness]
    health: KnowledgeHealth
    trace: dict[str, Any] = field(default_factory=dict)

    @property
    def frontier_ids(self) -> tuple[str, ...]:
        return tuple(sorted(n for n, on in self.frontier.items() if on))


def target_for_node(
    curriculum: CurriculumGraph, node_id: str, config: EngineConfig = DEFAULT_CONFIG
) -> float:
    """τ for absolute sufficiency — the max over the roles this node serves (§5)."""
    depth = curriculum.node(node_id).max_required_depth
    return config.target_for(depth) if depth else 0.0


def recompute(
    curriculum: CurriculumGraph,
    states: dict[str, KnowledgeState],
    *,
    days_elapsed: dict[str, float] | None = None,
    active_role_id: str | None = None,
    date_factor: float = 1.0,
    config: EngineConfig = DEFAULT_CONFIG,
) -> EngineSnapshot:
    """Stages 5-14 over the whole graph.

    `days_elapsed[node_id]` is days since that node was last assessed; absent means 0.
    """
    elapsed = days_elapsed or {}

    def state_of(node_id: str) -> KnowledgeState:
        return states.get(node_id, KnowledgeState.cold(node_id))

    intrinsic = {n.node_id: state_of(n.node_id).intrinsic_mastery for n in curriculum}
    retentions = {
        n.node_id: retention(elapsed.get(n.node_id, 0.0), state_of(n.node_id).stability)
        for n in curriculum
    }
    variances = {
        n.node_id: normalized_variance(state_of(n.node_id).assessment_variance_raw, config)
        for n in curriculum
    }

    # stages 5-6 — topological, prerequisites resolved first
    confidence, effective = propagate(curriculum, intrinsic, retentions, config)

    targets = {n.node_id: target_for_node(curriculum, n.node_id, config) for n in curriculum}

    # stage 7
    frontier = {
        node_id: is_frontier(effective[node_id], confidence[node_id], targets[node_id], config)
        for node_id in effective
    }
    critical_path = critical_path_values(curriculum, config)

    # stage 8
    leverage = leverage_values(curriculum, critical_path, config)

    # stage 9 — needed before CurImp, which depends on who the bottlenecks are
    readiness = all_role_readiness(curriculum, effective, config)
    bottlenecks = {r.bottleneck_node_id for r in readiness.values() if r.bottleneck_node_id}

    importance = {
        node_id: current_importance(
            curriculum,
            node_id,
            leverage=leverage[node_id],
            active_role_id=active_role_id,
            date_factor=date_factor,
            is_bottleneck=node_id in bottlenecks,
            config=config,
        )
        for node_id in effective
    }

    # stage 10
    costs = {}
    for node in curriculum:
        node_id = node.node_id
        state = state_of(node_id)
        depth = node.max_required_depth
        difficulty = state.difficulty
        if difficulty is None:
            difficulty = initial_difficulty(depth, config) if depth else 0.0
        costs[node_id] = (
            learning_cost(
                effective[node_id],
                target=targets[node_id],
                difficulty=difficulty,
                depth=depth,
                config=config,
            )
            if depth
            else 0.0
        )

    # stage 13
    statuses = {
        node_id: derive_status(
            effective_mastery=effective[node_id],
            retention=retentions[node_id],
            variance=variances[node_id],
            session_count=state_of(node_id).session_count,
            target=targets[node_id],
            config=config,
        )
        for node_id in effective
    }

    # stage 14
    health = knowledge_health(
        curriculum,
        effective_mastery=effective,
        retention=retentions,
        session_counts={n.node_id: state_of(n.node_id).session_count for n in curriculum},
        targets=targets,
        frontier_size=sum(1 for on in frontier.values() if on),
        active_role_id=active_role_id,
        config=config,
    )

    return EngineSnapshot(
        prerequisite_confidence=confidence,
        effective_mastery=effective,
        retention=retentions,
        variance=variances,
        targets=targets,
        frontier=frontier,
        critical_path_value=critical_path,
        leverage=leverage,
        current_importance=importance,
        learning_cost=costs,
        status=statuses,
        readiness=readiness,
        health=health,
        trace={
            "pipeline_order": [
                "prerequisite_confidence",
                "effective_mastery",
                "frontier_and_critical_path",
                "leverage_and_current_importance",
                "readiness",
                "learning_cost",
                "status",
                "knowledge_health",
            ],
            "topological_order": list(curriculum.topological_order()),
            "bottlenecks": sorted(b for b in bottlenecks),
            "active_role_id": active_role_id,
        },
    )


def recommend(
    curriculum: CurriculumGraph,
    snapshot: EngineSnapshot,
    *,
    limit: int = 5,
    role_id: str | None = None,
    section: str | None = None,
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[Candidate, ...]:
    """Stages 11-12 — build the candidate set, rank it, diversify it.

    Candidates are `frontier ∪ high-CPV`, never every node: searching the frontier is both
    faster and the reason a recommendation can always explain itself.

    `role_id` and `section` narrow the candidate set **before** scoring and diversification,
    which is the only placement that works. Filtering afterwards ranks and MMR-diversifies a
    set the caller is about to discard, so the diversity guarantee ends up applied to the wrong
    list — the survivors can all be near-duplicates of each other — and there is no way to know
    how far to over-fetch to still end up with `limit` of them. Both may be given; the
    candidate set is the intersection.

    The returned candidates carry their explanation factors. Those are computed here, after
    selection, because `unlocks` is a descendant traversal per node and the candidate set is
    much larger than the list.
    """
    candidate_ids = {n for n, on in snapshot.frontier.items() if on}
    candidate_ids |= {
        n
        for n, cpv in snapshot.critical_path_value.items()
        if cpv >= config.high_cpv_threshold and snapshot.effective_mastery[n] < snapshot.targets[n]
    }
    if role_id is not None:
        candidate_ids &= {n.node_id for n in curriculum.nodes_by_role(role_id)}
    if section is not None:
        candidate_ids &= {n.node_id for n in curriculum.nodes_by_section(section)}
    if not candidate_ids:
        return ()

    candidates = tuple(
        Candidate(
            node_id=node_id,
            expected_readiness_gain=expected_readiness_gain(
                curriculum,
                node_id,
                effective_mastery=snapshot.effective_mastery,
                target=snapshot.targets[node_id],
                config=config,
            ),
            learning_cost=snapshot.learning_cost[node_id],
            leverage=snapshot.leverage[node_id],
            current_importance=snapshot.current_importance[node_id],
        )
        for node_id in sorted(candidate_ids)
    )
    picks = diversify(curriculum, score_candidates(candidates, config), limit, config)
    return tuple(_with_reasons(curriculum, snapshot, c) for c in picks)


def _with_reasons(
    curriculum: CurriculumGraph, snapshot: EngineSnapshot, candidate: Candidate
) -> Candidate:
    """Attach the facts that answer "why was this recommended?" (A.5.6).

    Every one of them is already known here — the readiness stage computed the bottlenecks and
    the graph knows its own descendants — so a caller that re-derived them would be running
    graph algebra outside the engine against the same inputs.
    """
    node_id = candidate.node_id
    return candidate.with_reasons(
        blocking_roles=tuple(
            sorted(
                role_id
                for role_id, readiness in snapshot.readiness.items()
                if readiness.bottleneck_node_id == node_id
            )
        ),
        unlocks=len(curriculum.descendants(node_id)),
        is_frontier=snapshot.frontier[node_id],
    )


def unexplored(
    curriculum: CurriculumGraph,
    states: dict[str, KnowledgeState],
    snapshot: EngineSnapshot,
) -> tuple[str, ...]:
    """The cold-start backlog — nodes with no evidence, ranked by CurImp · (1 + Lev)."""
    # `is_assessed` rather than a second spelling of `session_count == 0`: Layer 2 owns what
    # counts as evidence, and the overlay used to carry a rival definition of the same set.
    ids = tuple(
        n.node_id
        for n in curriculum
        if not states.get(n.node_id, KnowledgeState.cold(n.node_id)).is_assessed
    )
    return cold_start_queue(
        ids,
        current_importance=snapshot.current_importance,
        leverage=snapshot.leverage,
    )


__all__ = [
    "EngineSnapshot",
    "KnowledgeHealth",
    "SessionUpdate",
    "apply_session",
    "critical_path_values",
    "current_importance",
    "derive_status",
    "intrinsic_importance",
    "is_frontier",
    "knowledge_health",
    "leverage_values",
    "recommend",
    "recompute",
    "target_for_node",
    "unexplored",
]
