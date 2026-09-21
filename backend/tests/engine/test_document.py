"""Layer 3 document prep — closure, readiness, and plan ordering.

The properties asserted here are the ones the feature would be worthless without: that the
closure finds concepts the document never mentioned, that readiness is gated by the worst gap
rather than averaged over it, and that a plan never tells you to study something before its
prerequisites. Everything else is presentation.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import Depth, fixture_repository
from knowledgeos.curriculum.errors import NodeNotFoundError
from knowledgeos.engine import DEFAULT_CONFIG
from knowledgeos.engine.document import (
    Requirement,
    StatedConcept,
    document_plan,
    document_readiness,
    expected_document_gain,
    requirement_closure,
    sufficiency,
    total_effort,
)


@pytest.fixture
def curriculum():
    return fixture_repository().get()


def _stated(curriculum, depth=Depth.DEEP, weight=1.0):
    """A leaf-ish node with real prerequisites, so the closure has something to find."""
    candidates = [n for n in curriculum if curriculum.ancestors(n.node_id)]
    assert candidates, "fixture must contain at least one node with prerequisites"
    deepest = max(candidates, key=lambda n: len(curriculum.ancestors(n.node_id)))
    return StatedConcept(deepest.node_id, depth, weight)


# --------------------------------------------------------------------- closure


def test_closure_pulls_in_concepts_the_document_never_named(curriculum):
    """The headline value: prerequisites the extraction could not have known to list."""
    stated = _stated(curriculum)
    requirements = requirement_closure(curriculum, (stated,))

    ids = {r.node_id for r in requirements}
    assert stated.node_id in ids
    implied = {r.node_id for r in requirements if not r.stated}
    assert implied, "a node with prerequisites must produce implied requirements"
    assert implied <= curriculum.ancestors(stated.node_id)


def test_every_implied_concept_names_the_stated_one_that_needs_it(curriculum):
    """Explainability: "why is this on my list?" must always have an answer."""
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    for requirement in requirements:
        if requirement.stated:
            assert requirement.required_for is None
            assert requirement.distance == 0
        else:
            assert requirement.required_for is not None
            assert requirement.distance >= 1


def test_closure_attenuates_with_distance(curriculum):
    """Weight must decay along the chain, or one concept drags in the whole graph at full
    strength and the plan stops distinguishing the core from the foundations."""
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    by_distance: dict[int, list[float]] = {}
    for requirement in requirements:
        by_distance.setdefault(requirement.distance, []).append(requirement.weight)
    for distance, weights in by_distance.items():
        if distance + 1 in by_distance:
            assert max(by_distance[distance + 1]) <= max(weights) + 1e-9


def test_a_shallow_document_asks_less_of_its_prerequisites(curriculum):
    """A paper that name-drops a concept should not demand mastery of its foundations."""
    node_id = _stated(curriculum).node_id
    shallow = requirement_closure(
        curriculum, (StatedConcept(node_id, Depth.AWARENESS, 1.0),)
    )
    deep = requirement_closure(
        curriculum, (StatedConcept(node_id, Depth.DERIVATION, 1.0),)
    )
    shallow_targets = {r.node_id: r.target for r in shallow if not r.stated}
    deep_targets = {r.node_id: r.target for r in deep if not r.stated}
    assert shallow_targets, "expected implied requirements in both cases"
    for node, target in shallow_targets.items():
        assert target <= deep_targets[node] + 1e-9


def test_the_same_concept_stated_twice_takes_the_stricter_reading(curriculum):
    node_id = _stated(curriculum).node_id
    requirements = requirement_closure(
        curriculum,
        (
            StatedConcept(node_id, Depth.AWARENESS, 0.2),
            StatedConcept(node_id, Depth.DERIVATION, 0.9),
        ),
    )
    target = next(r for r in requirements if r.node_id == node_id)
    assert target.target == DEFAULT_CONFIG.target_for(Depth.DERIVATION)
    assert target.weight == 0.9


def test_closure_refuses_an_unknown_concept(curriculum):
    with pytest.raises(NodeNotFoundError):
        requirement_closure(curriculum, (StatedConcept("not-a-node", Depth.DEEP, 1.0),))


def test_closure_is_deterministic(curriculum):
    """Layer 3's standing contract: identical inputs, identical outputs."""
    stated = (_stated(curriculum),)
    assert requirement_closure(curriculum, stated) == requirement_closure(curriculum, stated)


# ------------------------------------------------------------------- readiness


def _requirements() -> tuple[Requirement, ...]:
    return (
        Requirement("a", target=0.8, weight=1.0, stated=True),
        Requirement("b", target=0.8, weight=1.0, stated=True),
        Requirement("c", target=0.8, weight=1.0, stated=True),
    )


def test_readiness_collapses_toward_the_worst_gap_not_the_average():
    """The whole reason this is harmonic. Two 1.0s and a 0.0 is not "mostly ready"."""
    requirements = _requirements()
    strong = document_readiness(requirements, {"a": 0.8, "b": 0.8, "c": 0.0})
    assert strong.readiness < 0.5, "an arithmetic mean would report ~0.67 here"
    assert strong.bottleneck_node_id == "c"


def test_readiness_is_one_when_every_concept_meets_its_target():
    requirements = _requirements()
    result = document_readiness(requirements, {"a": 0.8, "b": 0.8, "c": 0.8})
    assert result.readiness == pytest.approx(1.0)
    assert result.gap_count == 0


def test_knowing_one_concept_far_beyond_the_target_does_not_hide_a_gap():
    """Sufficiency saturates, so incidental depth cannot paper over a real blocker."""
    requirements = _requirements()
    balanced = document_readiness(requirements, {"a": 0.8, "b": 0.8, "c": 0.4})
    lopsided = document_readiness(requirements, {"a": 1.0, "b": 1.0, "c": 0.4})
    assert lopsided.readiness == pytest.approx(balanced.readiness)


def test_the_bottleneck_accounts_for_centrality_not_just_the_lowest_score():
    """A slightly weaker grasp of the central concept outranks a bad grasp of a footnote."""
    requirements = (
        Requirement("core", target=0.8, weight=1.0, stated=True),
        Requirement("aside", target=0.8, weight=0.06, stated=False, required_for="core"),
    )
    result = document_readiness(requirements, {"core": 0.2, "aside": 0.0})
    assert result.bottleneck_node_id == "core"


def test_readiness_of_an_empty_requirement_set_is_zero():
    result = document_readiness((), {})
    assert result.readiness == 0.0
    assert result.bottleneck_node_id is None
    assert not result.is_explainable


def test_sufficiency_saturates_at_one():
    requirement = Requirement("a", target=0.5, weight=1.0, stated=True)
    assert sufficiency(requirement, 0.25) == pytest.approx(0.5)
    assert sufficiency(requirement, 0.5) == pytest.approx(1.0)
    assert sufficiency(requirement, 0.9) == pytest.approx(1.0)


def test_a_zero_target_is_already_satisfied():
    assert sufficiency(Requirement("a", target=0.0, weight=1.0, stated=True), 0.0) == 1.0


# ------------------------------------------------------------------------ gain


def test_closing_a_gap_raises_document_readiness():
    requirements = _requirements()
    mastery = {"a": 0.8, "b": 0.8, "c": 0.0}
    assert expected_document_gain(requirements, mastery, "c") > 0.0


def test_a_concept_already_at_target_has_nothing_to_gain():
    requirements = _requirements()
    mastery = {"a": 0.8, "b": 0.8, "c": 0.0}
    assert expected_document_gain(requirements, mastery, "a") == 0.0


def test_a_concept_the_document_does_not_need_has_nothing_to_gain():
    assert expected_document_gain(_requirements(), {}, "unrelated") == 0.0


# ------------------------------------------------------------------------ plan


def test_a_plan_never_puts_a_concept_before_its_prerequisites(curriculum):
    """The ordering contract. Studying a dependent first wastes the session."""
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    steps = document_plan(curriculum, requirements, effective_mastery={})

    seen: set[str] = set()
    for step in steps:
        unmet = curriculum.ancestors(step.node_id) & {s.node_id for s in steps}
        assert unmet <= seen, f"{step.node_id} was scheduled before {unmet - seen}"
        seen.add(step.node_id)


def test_a_plan_lists_only_unmet_concepts(curriculum):
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    mastery = {r.node_id: 1.0 for r in requirements}
    assert document_plan(curriculum, requirements, effective_mastery=mastery) == ()


def test_a_plan_respects_its_limit(curriculum):
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    steps = document_plan(curriculum, requirements, effective_mastery={}, limit=2)
    assert len(steps) <= 2


def test_plan_steps_report_what_blocks_them(curriculum):
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    steps = document_plan(curriculum, requirements, effective_mastery={})
    ids = {s.node_id for s in steps}
    for step in steps:
        assert set(step.blocked_by) == curriculum.ancestors(step.node_id) & ids


def test_total_effort_is_the_sum_of_step_costs(curriculum):
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    steps = document_plan(curriculum, requirements, effective_mastery={})
    assert total_effort(steps) == pytest.approx(sum(s.learning_cost for s in steps))


def test_effort_falls_as_the_user_learns(curriculum):
    """Partial knowledge must cost less to finish than no knowledge at all."""
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    cold = document_plan(curriculum, requirements, effective_mastery={})
    partial = document_plan(
        curriculum,
        requirements,
        effective_mastery={r.node_id: r.target * 0.5 for r in requirements},
    )
    assert total_effort(partial) < total_effort(cold)


def test_plan_is_deterministic(curriculum):
    requirements = requirement_closure(curriculum, (_stated(curriculum),))
    first = document_plan(curriculum, requirements, effective_mastery={})
    second = document_plan(curriculum, requirements, effective_mastery={})
    assert [s.node_id for s in first] == [s.node_id for s in second]
