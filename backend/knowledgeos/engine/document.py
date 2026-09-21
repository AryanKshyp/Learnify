"""Document prep — what a paper or report demands, measured against what you know.

This is a **lens over the same graph**, not a second model. An external LLM reads the document
and reports which curriculum concepts it requires and how deep; everything after that happens
here, deterministically, because it needs the prerequisite DAG and the user's mastery — neither
of which the LLM can see.

Three things this computes that the extraction cannot:

    requirement_closure()   the concepts the document silently assumes. A paper says
                            "multi-head attention"; it never says "softmax" or "matmul", and
                            those are exactly where a reader actually gets stuck.
    document_readiness()    one bottleneck-weighted number for "can I read this yet", plus the
                            concept holding it back.
    document_plan()         what to study, in an order that respects prerequisites.

No new mastery mathematics is introduced. Targets come from the same τ ladder, "a prerequisite
is satisfied" is the same φ used for frontier membership, the harmonic floor is the same ε, and
cost is the standard cost model. Only the closure attenuation constants are new, and they live
in `EngineConfig` like every other tunable.

Pure, like the rest of Layer 3: no I/O, no clock, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph, Depth

from .config import DEFAULT_CONFIG, EngineConfig
from .recommend import Candidate, learning_cost, score_candidates


@dataclass(frozen=True, slots=True)
class StatedConcept:
    """One concept the extraction says the document requires, as given.

    This is the engine-side view of a Schema D entry — deliberately a plain dataclass rather
    than the Pydantic model, so Layer 3 stays independent of the boundary's shape.
    """

    node_id: str
    depth: Depth
    weight: float


@dataclass(frozen=True, slots=True)
class Requirement:
    """One concept the document needs, stated or implied, with why and how deep."""

    node_id: str
    #: tau_doc — the mastery this document demands of this concept.
    target: float
    #: how much this concept matters *to this document*. Drives the readiness weighting.
    weight: float
    #: True if the document named it; False if the closure walk pulled it in.
    stated: bool
    #: For an implied concept, the stated concept that pulled it in most strongly. This is the
    #: whole explainability story: "Softmax — needed for Multi-Head Attention".
    required_for: str | None = None
    #: Prerequisite hops from the nearest stated concept. 0 for stated concepts.
    distance: int = 0


def requirement_closure(
    curriculum: CurriculumGraph,
    stated: tuple[StatedConcept, ...],
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[Requirement, ...]:
    """Expand the stated concepts into everything the document actually assumes.

    A single backward pass in reverse topological order — dependents are always finalised
    before the prerequisites they push onto, so each concept is visited once with its final
    demand rather than being revisited as new paths arrive.

    For a prerequisite `p` of a needed concept `n` across an edge of weight `w`:

        target[p] <- max(target[p],  phi * w * target[n] / tau_max)
        weight[p] <- max(weight[p],  weight[n] * w * decay)

    phi is the same "prerequisites are satisfied" threshold the frontier test uses, so the
    closure demands exactly what the rest of the engine considers sufficient support — no more.
    Scaling by `target[n] / tau_max` means a concept the document only needs at `awareness`
    asks less of its prerequisites than one it needs at `derivation`, which is the behaviour
    anyone would expect and the reason the chain attenuates instead of demanding mastery
    everywhere.

    `max` rather than sum: two stated concepts needing the same prerequisite does not make it
    twice as necessary. Chains terminate on `document_weight_floor`, not on a hop limit —
    a strongly-weighted chain should be allowed to run deep, a weak one should die in one hop.
    """
    tau_max = config.target_for(Depth.DERIVATION)
    phi = config.frontier_prerequisite_threshold
    floor = config.document_weight_floor
    decay = config.document_prerequisite_decay

    targets: dict[str, float] = {}
    weights: dict[str, float] = {}
    stated_ids: set[str] = set()
    # the stated concept each implied concept is serving, and how far away it is
    because_of: dict[str, str] = {}
    distance: dict[str, int] = {}

    # Ties on the same weight break on node_id, so an implied concept pulled in equally by two
    # stated concepts always reports the same one.
    def claim(node_id: str, owner: str, candidate_weight: float) -> bool:
        current = weights.get(node_id, 0.0)
        if candidate_weight > current:
            return True
        return candidate_weight == current and owner < because_of.get(node_id, owner)

    for concept in sorted(stated, key=lambda c: c.node_id):
        node_id = concept.node_id
        curriculum.node(node_id)  # raises NodeNotFoundError — closure never invents ids
        stated_ids.add(node_id)
        # A concept stated twice at different depths takes the stricter reading of both.
        targets[node_id] = max(targets.get(node_id, 0.0), config.target_for(concept.depth))
        weights[node_id] = max(weights.get(node_id, 0.0), concept.weight)
        because_of[node_id] = node_id
        distance[node_id] = 0

    # Reverse topological order: prerequisites come first in `topological_order()`, so walking
    # it backwards guarantees every dependent has already contributed before we read a node.
    for node_id in reversed(curriculum.topological_order()):
        if node_id not in weights:
            continue
        node_weight = weights[node_id]
        node_target = targets[node_id]
        owner = because_of[node_id]
        hops = distance[node_id]

        for edge in curriculum.prerequisite_edges_of(node_id):
            prerequisite = edge.to_node_id
            propagated = node_weight * edge.weight * decay
            if propagated < floor:
                continue
            if claim(prerequisite, owner, propagated):
                because_of[prerequisite] = owner
                distance[prerequisite] = hops + 1
            weights[prerequisite] = max(weights.get(prerequisite, 0.0), propagated)
            targets[prerequisite] = max(
                targets.get(prerequisite, 0.0), phi * edge.weight * (node_target / tau_max)
            )

    return tuple(
        sorted(
            (
                Requirement(
                    node_id=node_id,
                    target=targets[node_id],
                    weight=weights[node_id],
                    stated=node_id in stated_ids,
                    required_for=(None if node_id in stated_ids else because_of[node_id]),
                    distance=distance[node_id],
                )
                for node_id in weights
            ),
            key=lambda r: (-r.weight, r.node_id),
        )
    )


def sufficiency(requirement: Requirement, effective_mastery: float) -> float:
    """How much of what this document demands of this concept the user actually has, 0-1.

    Saturating at 1.0 is the point. Knowing a concept far beyond what the document needs does
    not make you more ready to read it — it just means that concept is not the problem. Without
    the cap, deep knowledge of something incidental would paper over a genuine gap elsewhere.
    """
    if requirement.target <= 0.0:
        return 1.0
    return min(effective_mastery / requirement.target, 1.0)


@dataclass(frozen=True, slots=True)
class DocumentReadiness:
    """How ready the user is for one document, and what is holding it back."""

    readiness: float
    bottleneck_node_id: str | None
    concept_count: int
    #: concepts whose sufficiency is below 1.0
    gap_count: int

    @property
    def is_explainable(self) -> bool:
        return self.bottleneck_node_id is not None


def document_readiness(
    requirements: tuple[Requirement, ...],
    effective_mastery: dict[str, float],
    config: EngineConfig = DEFAULT_CONFIG,
) -> DocumentReadiness:
    """Weighted harmonic mean of sufficiency over the document's concepts (§11's shape).

        Readiness = sum(w_i) / sum(w_i / max(suff_i, epsilon))

    Harmonic and not arithmetic for the same reason role readiness is: reading a paper is
    gated by the thing you do not know, not helped by the nine you do. An arithmetic mean of
    nine 1.0s and one 0.0 reads 0.90 and tells you to go ahead; the harmonic mean collapses
    toward the zero, which is what actually happens when you hit that paragraph.

    The bottleneck is the largest `w_i / max(suff_i, epsilon)` — the concept whose improvement
    would lift this document's readiness most, which accounts for centrality rather than just
    reporting whatever you happen to know least.
    """
    if not requirements:
        return DocumentReadiness(0.0, None, 0, 0)

    epsilon = config.readiness_epsilon
    numerator = 0.0
    denominator = 0.0
    worst = -1.0
    bottleneck: str | None = None
    gaps = 0

    for requirement in requirements:
        got = sufficiency(requirement, effective_mastery.get(requirement.node_id, 0.0))
        if got < 1.0:
            gaps += 1
        contribution = requirement.weight / max(got, epsilon)
        numerator += requirement.weight
        denominator += contribution

        if contribution > worst or (
            contribution == worst and bottleneck is not None and requirement.node_id < bottleneck
        ):
            worst = contribution
            bottleneck = requirement.node_id

    if denominator <= 0.0:  # pragma: no cover - weights are positive
        return DocumentReadiness(0.0, bottleneck, len(requirements), gaps)

    return DocumentReadiness(
        readiness=numerator / denominator,
        bottleneck_node_id=bottleneck,
        concept_count=len(requirements),
        gap_count=gaps,
    )


def expected_document_gain(
    requirements: tuple[Requirement, ...],
    effective_mastery: dict[str, float],
    node_id: str,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """How much this document's readiness would rise if `node_id` reached its tau_doc.

    Document readiness rather than role readiness, deliberately. The two disagree often: a
    concept can be a minor contributor to your AI Research track and the single thing standing
    between you and this paper. When the user asked "what do I need for *this*", ranking by
    anything else answers a question they did not ask.
    """
    target: float | None = None
    for requirement in requirements:
        if requirement.node_id == node_id:
            if sufficiency(requirement, effective_mastery.get(node_id, 0.0)) >= 1.0:
                return 0.0
            target = requirement.target
            break
    if target is None:
        return 0.0

    before = document_readiness(requirements, effective_mastery, config).readiness
    simulated = dict(effective_mastery)
    simulated[node_id] = target
    after = document_readiness(requirements, simulated, config).readiness
    return max(after - before, 0.0)


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One concept to study, with everything needed to justify its position."""

    node_id: str
    requirement: Requirement
    effective_mastery: float
    sufficiency: float
    expected_gain: float
    learning_cost: float
    priority: float
    #: prerequisites of this concept that are also unmet and therefore come first
    blocked_by: tuple[str, ...]


def document_plan(
    curriculum: CurriculumGraph,
    requirements: tuple[Requirement, ...],
    *,
    effective_mastery: dict[str, float],
    difficulty: dict[str, float] | None = None,
    leverage: dict[str, float] | None = None,
    current_importance: dict[str, float] | None = None,
    limit: int | None = None,
    config: EngineConfig = DEFAULT_CONFIG,
) -> tuple[PlanStep, ...]:
    """The ordered study plan: rank by gain-per-effort, then respect prerequisites.

    Two passes, because ranking and ordering answer different questions. `score_candidates`
    (§12) decides *what is worth studying* — the same expected-gain-per-cost ranking the rest
    of the system uses, so a document plan and a recommendation never disagree about value.
    Then a priority-respecting topological pass decides *what is studiable now*: a concept
    whose own prerequisites are still unmet cannot be studied first no matter how valuable it
    is, and putting it at the top would send the user into a session they are not ready for.

    Only unmet concepts appear. Something already sufficient for this document is not a step.
    """
    difficulties = difficulty or {}
    leverages = leverage or {}
    importances = current_importance or {}

    unmet = tuple(
        r for r in requirements if sufficiency(r, effective_mastery.get(r.node_id, 0.0)) < 1.0
    )
    if not unmet:
        return ()

    by_id = {r.node_id: r for r in unmet}

    def depth_of(node_id: str) -> Depth:
        return curriculum.node(node_id).max_required_depth or Depth.WORKING

    candidates = tuple(
        Candidate(
            node_id=r.node_id,
            expected_readiness_gain=expected_document_gain(
                requirements, effective_mastery, r.node_id, config
            ),
            learning_cost=learning_cost(
                effective_mastery.get(r.node_id, 0.0),
                target=r.target,
                difficulty=difficulties.get(
                    r.node_id, config.difficulty_for(depth_of(r.node_id))
                ),
                depth=depth_of(r.node_id),
                config=config,
            ),
            leverage=leverages.get(r.node_id, 0.0),
            current_importance=importances.get(r.node_id, r.weight),
        )
        for r in sorted(unmet, key=lambda r: r.node_id)
    )
    ranked = score_candidates(candidates, config)

    # Unmet prerequisites *within this document's set* — the only ones that gate an ordering
    # decision here. A prerequisite outside the document is not the user's problem right now.
    blockers = {
        node_id: tuple(sorted(curriculum.ancestors(node_id) & by_id.keys())) for node_id in by_id
    }

    ordered: list[Candidate] = []
    emitted: set[str] = set()
    remaining = list(ranked)
    while remaining:
        for index, candidate in enumerate(remaining):
            if all(blocker in emitted for blocker in blockers[candidate.node_id]):
                ordered.append(remaining.pop(index))
                emitted.add(candidate.node_id)
                break
        else:  # pragma: no cover - the curriculum is a validated DAG, so this cannot cycle
            ordered.append(remaining.pop(0))
            emitted.add(ordered[-1].node_id)

    steps = tuple(
        PlanStep(
            node_id=c.node_id,
            requirement=by_id[c.node_id],
            effective_mastery=effective_mastery.get(c.node_id, 0.0),
            sufficiency=sufficiency(by_id[c.node_id], effective_mastery.get(c.node_id, 0.0)),
            expected_gain=c.expected_readiness_gain,
            learning_cost=c.learning_cost,
            priority=c.priority,
            blocked_by=blockers[c.node_id],
        )
        for c in ordered
    )
    cap = config.document_plan_limit if limit is None else limit
    return steps[:cap]


def total_effort(steps: tuple[PlanStep, ...]) -> float:
    """Estimated hours to close every gap in the plan."""
    return sum(step.learning_cost for step in steps)


__all__ = [
    "DocumentReadiness",
    "PlanStep",
    "Requirement",
    "StatedConcept",
    "document_plan",
    "document_readiness",
    "expected_document_gain",
    "requirement_closure",
    "sufficiency",
    "total_effort",
]
