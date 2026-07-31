"""Pipeline stages 10-12 — learning cost, expected readiness gain, priority.

CALC_ENGINE_SPEC.md §12.

The objective is **not** "close the biggest gap". It is *maximise expected readiness gain per
unit of learning effort*. Those differ sharply: a derivation-depth node sitting at 0.2 has an
enormous gap but costs 8 hours and may unlock nothing, while a working-depth prerequisite at
0.55 might cost 40 minutes and lift three downstream nodes at once.

Because readiness is bottleneck-based, improving a bottleneck produces a large ERG while
improving an already-strong node produces ≈0 — the ranking falls out of the readiness model
rather than needing separate rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph, Depth

from .config import DEFAULT_CONFIG, EngineConfig
from .position import min_max_normalize
from .readiness import all_role_readiness, role_priority_weights


def learning_cost(
    effective_mastery: float,
    *,
    target: float,
    difficulty: float,
    depth: Depth,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """Estimated hours to lift a node from where it is to its depth target τ.

        Cost = base_cost(depth) · D · (τ − EM)₊ / τ

    Already-sufficient nodes cost 0. Frontier membership means prerequisites are already met,
    so no upstream cost is added here.
    """
    if target <= 0.0:
        return 0.0
    remaining = max(target - effective_mastery, 0.0)
    return config.base_cost_for(depth) * difficulty * (remaining / target)


def expected_readiness_gain(
    curriculum: CurriculumGraph,
    node_id: str,
    *,
    effective_mastery: dict[str, float],
    target: float,
    baseline: dict[str, float] | None = None,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """ERG — how much overall readiness would rise if this node reached its target.

    Simulates lifting EM(node) to τ, then aggregates the per-role readiness deltas weighted by
    the user's role priority:

        ERG = Σ_r π_r · max(ERG_r, 0)

    Negative per-role deltas are clipped: making one node stronger cannot genuinely harm a
    role, so a negative value would be numerical noise rather than signal.

    Simplification worth stating: this raises the node's own EM and re-runs readiness, but does
    NOT re-propagate the improvement into its dependents' PC. Full propagation would be the
    stricter reading of the spec; it costs a full graph pass per candidate, and since readiness
    already counts every dependent node directly, the ranking it produces is very close. If
    recommendations ever look wrong for deep chains, this is the first thing to revisit.
    """
    weights = role_priority_weights(curriculum)
    before = baseline if baseline is not None else effective_mastery
    current = all_role_readiness(curriculum, before, config)

    simulated = dict(effective_mastery)
    if simulated.get(node_id, 0.0) >= target:
        return 0.0
    simulated[node_id] = target
    after = all_role_readiness(curriculum, simulated, config)

    return sum(
        weights.get(role_id, 0.0) * max(after[role_id].readiness - current[role_id].readiness, 0.0)
        for role_id in after
    )


@dataclass(frozen=True, slots=True)
class Candidate:
    """A node under consideration, with the factors that rank it."""

    node_id: str
    expected_readiness_gain: float
    learning_cost: float
    leverage: float
    current_importance: float
    priority: float = 0.0

    def with_priority(self, value: float) -> Candidate:
        return Candidate(
            node_id=self.node_id,
            expected_readiness_gain=self.expected_readiness_gain,
            learning_cost=self.learning_cost,
            leverage=self.leverage,
            current_importance=self.current_importance,
            priority=value,
        )


def score_candidates(
    candidates: tuple[Candidate, ...], config: EngineConfig = DEFAULT_CONFIG
) -> tuple[Candidate, ...]:
    """Priority = (ERG / Cost) · (1 + Lev) · CurImp, min-max normalised per factor.

    Each factor is normalised across the candidate set *before* combining, so no single term
    dominates purely because of its units — ERG is a small readiness delta while cost is in
    hours, and multiplying them raw would let hours decide everything.

    Zero-cost candidates (already at target) score 0 rather than dividing by zero: there is
    nothing to gain by studying something already sufficient.
    """
    if not candidates:
        return ()

    efficiency = {
        c.node_id: (c.expected_readiness_gain / c.learning_cost if c.learning_cost > 0 else 0.0)
        for c in candidates
    }
    normalized_efficiency = min_max_normalize(efficiency)
    normalized_leverage = min_max_normalize({c.node_id: c.leverage for c in candidates})
    normalized_importance = min_max_normalize(
        {c.node_id: c.current_importance for c in candidates}
    )

    scored = tuple(
        c.with_priority(
            normalized_efficiency[c.node_id]
            * (1.0 + normalized_leverage[c.node_id])
            * normalized_importance[c.node_id]
        )
        for c in candidates
    )
    return tuple(sorted(scored, key=lambda c: (-c.priority, c.node_id)))


def similarity(curriculum: CurriculumGraph, left: str, right: str) -> float:
    """Overlap between two nodes, for diversification.

    Shared competency plus Jaccard overlap of direct prerequisites — two nodes in the same
    competency that depend on the same things are near-duplicates from a study perspective,
    even when their ids look unrelated.
    """
    if left == right:
        return 1.0

    a, b = curriculum.node(left), curriculum.node(right)
    same_competency = (
        1.0 if (a.section, a.competency) == (b.section, b.competency) else 0.0
    )

    left_prereqs = {e.prerequisite_id for e in curriculum.prerequisite_edges_of(left)}
    right_prereqs = {e.prerequisite_id for e in curriculum.prerequisite_edges_of(right)}
    union = left_prereqs | right_prereqs
    overlap = len(left_prereqs & right_prereqs) / len(union) if union else 0.0

    return max(same_competency, overlap)


def diversify(
    curriculum: CurriculumGraph,
    candidates: tuple[Candidate, ...],
    limit: int,
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[Candidate, ...]:
    """Maximal marginal relevance — top-N that is not five variations of one topic.

        pick = argmax [ δ·priority − (1−δ)·max similarity to something already picked ]

    δ = 0.7 keeps priority dominant while still breaking up clusters. Without this a user who
    is weak in one competency gets a list entirely from that competency, which is both boring
    and fragile — one bad session invalidates the whole plan.
    """
    if limit <= 0 or not candidates:
        return ()

    remaining = list(candidates)
    selected: list[Candidate] = [remaining.pop(0)]  # highest priority always leads

    delta = config.mmr_lambda
    while remaining and len(selected) < limit:
        best_index, best_score = 0, float("-inf")
        for index, candidate in enumerate(remaining):
            closest = max(
                similarity(curriculum, candidate.node_id, chosen.node_id)
                for chosen in selected
            )
            score = delta * candidate.priority - (1.0 - delta) * closest
            if score > best_score:
                best_index, best_score = index, score
        selected.append(remaining.pop(best_index))

    return tuple(selected)


def cold_start_queue(
    unassessed_node_ids: tuple[str, ...],
    *,
    current_importance: dict[str, float],
    leverage: dict[str, float],
) -> tuple[str, ...]:
    """The unexplored backlog, ranked by CurImp · (1 + Lev).

    Kept deliberately separate from the main recommendations. A node nobody has been assessed
    on is not the same thing as a node the user demonstrably struggles with, and letting the
    two mix would make "you're weak here" indistinguishable from "we've never looked here".
    """
    return tuple(
        sorted(
            unassessed_node_ids,
            key=lambda node_id: (
                -(current_importance.get(node_id, 0.0) * (1.0 + leverage.get(node_id, 0.0))),
                node_id,
            ),
        )
    )
