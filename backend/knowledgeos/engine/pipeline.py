"""The canonical pipeline. CALC_ENGINE_SPEC.md §1.

Two entry points:

* `apply_session` — stages 1-4, for the one node that was assessed.
* `recompute` — stages 5-14, for the assessed node plus everything whose value could change.
  This is also the read path answering "what should I study next?" with no new assessment.

Ordering is not negotiable: PC before EM, EM before readiness, readiness before priority. Each
stage is a pure function of the previous, and every produced value carries a
`computation_trace` so any score can answer "how was this calculated?" from stored evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from knowledgeos.curriculum import CurriculumGraph, Depth
from knowledgeos.state import KnowledgeState, Status

from .config import DEFAULT_CONFIG, EngineConfig
from .health import KnowledgeHealth, knowledge_health
from .observation import (
    EvidenceQuality,
    Observation,
    SessionAbility,
    evidence_quality,
    session_ability,
    update_intrinsic_mastery,
)
from .position import (
    critical_path_values,
    current_importance,
    intrinsic_importance,
    is_frontier,
    leverage_values,
)
from .propagation import propagate
from .readiness import RoleReadiness, all_role_readiness
from .recommend import (
    Candidate,
    cold_start_queue,
    diversify,
    expected_readiness_gain,
    learning_cost,
    score_candidates,
)
from .retention import (
    adjust_difficulty,
    days_until_review,
    initial_difficulty,
    retention,
    update_stability,
)
from .status import derive_status


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
        previous_variance_raw=state.assessment_variance * config.variance_normalizer,
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


@dataclass(frozen=True, slots=True)
class EngineSnapshot:
    """Everything stages 5-14 produce, for the whole graph."""

    prerequisite_confidence: dict[str, float]
    effective_mastery: dict[str, float]
    retention: dict[str, float]
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
            variance=state_of(node_id).assessment_variance,
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
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[Candidate, ...]:
    """Stages 11-12 — build the candidate set, rank it, diversify it.

    Candidates are `frontier ∪ high-CPV`, never every node: searching the frontier is both
    faster and the reason a recommendation can always explain itself.
    """
    candidate_ids = {n for n, on in snapshot.frontier.items() if on}
    candidate_ids |= {
        n
        for n, cpv in snapshot.critical_path_value.items()
        if cpv >= config.high_cpv_threshold and snapshot.effective_mastery[n] < snapshot.targets[n]
    }
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
    return diversify(curriculum, score_candidates(candidates, config), limit, config)


def unexplored(
    curriculum: CurriculumGraph,
    states: dict[str, KnowledgeState],
    snapshot: EngineSnapshot,
) -> tuple[str, ...]:
    """The cold-start backlog — nodes with no evidence, ranked by CurImp · (1 + Lev)."""
    ids = tuple(
        n.node_id
        for n in curriculum
        if states.get(n.node_id, KnowledgeState.cold(n.node_id)).session_count == 0
    )
    return cold_start_queue(
        ids,
        current_importance=snapshot.current_importance,
        leverage=snapshot.leverage,
    )


__all__ = [
    "EngineSnapshot",
    "SessionUpdate",
    "apply_session",
    "intrinsic_importance",
    "recommend",
    "recompute",
    "target_for_node",
    "unexplored",
]
