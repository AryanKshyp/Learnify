"""Pipeline stage 14 — knowledge health. CALC_ENGINE_SPEC.md §14.

One number for the home view, always reported alongside its four components. A single opaque
score invites the question "why is it 62?", so the parts that produced it travel with it.

"Critical" means intrinsic importance at or above the threshold for the active role — health
deliberately ignores peripheral nodes, so grinding low-importance material cannot inflate it.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph

from .config import DEFAULT_CONFIG, EngineConfig


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
