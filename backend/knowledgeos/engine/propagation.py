"""Pipeline stages 5-6 — prerequisite confidence and effective mastery.

CALC_ENGINE_SPEC.md §7, §8. This is where the governing principle earns its complexity.

When `Probability` decays, `Naive Bayes` becomes less *trustworthy* — but the user has not
forgotten Naive Bayes, and the system has no evidence that they have. So intrinsic mastery is
left completely alone and only `EM = M · R · PC` falls. Restudying `Probability` restores every
dependent automatically, with zero reassessment, because nothing was ever destroyed.

Computed in topological order with prerequisites resolved first, which the curriculum graph
already guarantees (`CurriculumGraph.topological_order()`).
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph

from .config import DEFAULT_CONFIG, EngineConfig
from .observation import clamp


@dataclass(frozen=True, slots=True)
class PrerequisiteInput:
    """One prerequisite's contribution: its effective mastery and the edge's strength."""

    node_id: str
    effective_mastery: float
    weight: float


def prerequisite_confidence(
    prerequisites: tuple[PrerequisiteInput, ...],
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """PC — how far this node can be trusted given the state of what it rests on.

    A node with no prerequisites is fully trusted (PC = 1): there is nothing upstream to
    undermine it.

    Otherwise a bottleneck-leaning blend of the weighted average (breadth) and the weakest
    single prerequisite (depth):

        PC = γ·min(EM) + (1−γ)·weighted_avg(EM)

    γ = 0.6 leans toward the minimum because understanding does not average. If one hard
    prerequisite is missing, being solid on the other four does not repair the gap — you still
    cannot follow the derivation.
    """
    if not prerequisites:
        return 1.0

    total_weight = sum(p.weight for p in prerequisites)
    if total_weight <= 0.0:
        # every edge is weightless: no dependency strength to propagate through
        return 1.0

    weighted_average = (
        sum(p.weight * p.effective_mastery for p in prerequisites) / total_weight
    )
    weakest = min(p.effective_mastery for p in prerequisites)
    gamma = config.gamma
    return clamp(gamma * weakest + (1.0 - gamma) * weighted_average)


def effective_mastery(
    intrinsic_mastery: float, retention: float, prerequisite_confidence: float
) -> float:
    """EM = M · R · PC — the only score that reflects time and prerequisites.

    M is passed in and returned untouched. This function cannot modify evidence; it only
    reports how much of it the system can currently rely on.
    """
    return clamp(intrinsic_mastery * retention * prerequisite_confidence)


def propagate(
    curriculum: CurriculumGraph,
    intrinsic: dict[str, float],
    retentions: dict[str, float],
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute PC and EM for every node, in topological order.

    Returns `(prerequisite_confidence, effective_mastery)` keyed by node_id.

    Ordering is what makes a single pass sufficient: every prerequisite's EM is final before
    any dependent reads it. Termination is guaranteed because the prerequisite subgraph is
    acyclic, which Layer 1 refuses to load without.

    Missing entries in `intrinsic`/`retentions` are treated as 0.0 — an unassessed node
    contributes no evidence, and its dependents' trust must reflect that rather than assuming
    competence nobody has demonstrated.
    """
    confidence: dict[str, float] = {}
    effective: dict[str, float] = {}

    for node_id in curriculum.topological_order():
        edges = curriculum.prerequisite_edges_of(node_id)
        inputs = tuple(
            PrerequisiteInput(
                node_id=edge.prerequisite_id,
                effective_mastery=effective[edge.prerequisite_id],
                weight=edge.weight,
            )
            for edge in edges
        )
        node_confidence = prerequisite_confidence(inputs, config)
        confidence[node_id] = node_confidence
        effective[node_id] = effective_mastery(
            intrinsic.get(node_id, 0.0),
            retentions.get(node_id, 0.0),
            node_confidence,
        )

    return confidence, effective
