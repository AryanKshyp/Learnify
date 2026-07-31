"""Pipeline stage 9 — readiness. CALC_ENGINE_SPEC.md §11.

Readiness is a **weighted harmonic mean**, not an average, because interviews punish
bottlenecks. A candidate scoring 100/100/15 across three areas fails; an arithmetic mean calls
that 72 and looks fine. The harmonic mean collapses toward the weakest term, which is what
actually predicts the outcome.

Every readiness value is reported with the node that is holding it back, so the number is
always explainable as "held back by X" rather than being an opaque score.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph

from .config import DEFAULT_CONFIG, EngineConfig


@dataclass(frozen=True, slots=True)
class RoleReadiness:
    """Readiness for one role, with the reason it is not higher."""

    role_id: str
    readiness: float
    bottleneck_node_id: str | None
    node_count: int

    @property
    def is_explainable(self) -> bool:
        return self.bottleneck_node_id is not None


def role_readiness(
    curriculum: CurriculumGraph,
    role_id: str,
    effective_mastery: dict[str, float],
    config: EngineConfig = DEFAULT_CONFIG,
) -> RoleReadiness:
    """Weighted harmonic mean of effective mastery over the role's nodes.

        Readiness = Σ I_n  /  Σ (I_n / max(EM_n, ε))

    ε floors the denominator so one completely unknown node cannot drive the whole score to
    zero — otherwise readiness would stop distinguishing "one gap" from "nothing known", and
    every role would read 0 until the very last node was assessed.

    The binding bottleneck is the node contributing most to the denominator (largest
    `I_n / max(EM_n, ε)`), which is the node whose improvement would raise readiness most —
    a more useful answer than simply the lowest EM, since it accounts for importance.
    """
    nodes = curriculum.nodes_by_role(role_id)
    if not nodes:
        return RoleReadiness(role_id=role_id, readiness=0.0, bottleneck_node_id=None, node_count=0)

    epsilon = config.readiness_epsilon
    numerator = 0.0
    denominator = 0.0
    worst_contribution = -1.0
    bottleneck: str | None = None

    for node in nodes:
        requirement = node.requirement_for(role_id)
        if requirement is None:  # pragma: no cover - nodes_by_role guarantees this
            continue
        importance = requirement.importance
        mastery = max(effective_mastery.get(node.node_id, 0.0), epsilon)
        contribution = importance / mastery

        numerator += importance
        denominator += contribution

        # ties break on node_id so the reported bottleneck is deterministic
        if contribution > worst_contribution or (
            contribution == worst_contribution
            and bottleneck is not None
            and node.node_id < bottleneck
        ):
            worst_contribution = contribution
            bottleneck = node.node_id

    if denominator <= 0.0:  # pragma: no cover - importances are positive
        return RoleReadiness(role_id, 0.0, bottleneck, len(nodes))

    return RoleReadiness(
        role_id=role_id,
        readiness=numerator / denominator,
        bottleneck_node_id=bottleneck,
        node_count=len(nodes),
    )


def all_role_readiness(
    curriculum: CurriculumGraph,
    effective_mastery: dict[str, float],
    config: EngineConfig = DEFAULT_CONFIG,
) -> dict[str, RoleReadiness]:
    """Readiness for every role, keyed by role_id."""
    return {
        role.role_id: role_readiness(curriculum, role.role_id, effective_mastery, config)
        for role in curriculum.roles
    }


def role_priority_weights(curriculum: CurriculumGraph) -> dict[str, float]:
    """π_r ∝ 1/priority_rank, normalised to sum to 1.

    The user's #1 role gets roughly twice the weight of their #2, so recommendations follow
    stated priority without ever fully abandoning the lower-ranked tracks.
    """
    inverse = {role.role_id: 1.0 / role.priority_rank for role in curriculum.roles}
    total = sum(inverse.values())
    if total <= 0.0:  # pragma: no cover - ranks are >= 1
        return dict.fromkeys(inverse, 0.0)
    return {role_id: value / total for role_id, value in inverse.items()}
