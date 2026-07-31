"""Determinism and monotonicity property tests (CALC_ENGINE_SPEC.md §17, BUILD_SPEC.md G.4).

Purity is the engine's central guarantee, so it is tested rather than assumed. Randomised
inputs use a fixed seed — the *inputs* vary to cover the space, but the test itself is
reproducible, which matters when a failure needs diagnosing.
"""

from __future__ import annotations

import random

import pytest

from knowledgeos.curriculum import Depth, fixture_repository
from knowledgeos.engine import (
    DEFAULT_CONFIG,
    Observation,
    PrerequisiteInput,
    apply_session,
    effective_mastery,
    prerequisite_confidence,
    propagate,
    recompute,
    session_ability,
    update_intrinsic_mastery,
)
from knowledgeos.state import KnowledgeState

SEED = 20260801


@pytest.fixture(scope="module")
def curriculum():
    return fixture_repository().get()


def random_observations(count: int) -> list[Observation]:
    rng = random.Random(SEED)
    return [
        Observation(
            recall=rng.random(),
            depth=rng.random(),
            transfer=rng.random(),
            response_time_rating=rng.random(),
            llm_confidence=rng.random(),
        )
        for _ in range(count)
    ]


class TestDeterminism:
    """Same inputs ⇒ identical outputs. Always."""

    @pytest.mark.parametrize("observation", random_observations(25))
    @pytest.mark.parametrize("depth", list(Depth))
    def test_session_ability_is_deterministic(self, observation, depth):
        assert session_ability(observation, depth) == session_ability(observation, depth)

    @pytest.mark.parametrize("observation", random_observations(15))
    def test_apply_session_is_deterministic(self, observation):
        state = KnowledgeState.cold("prob-bayes").replace(
            intrinsic_mastery=0.4, session_count=2, stability=3.0, difficulty=0.5
        )
        first = apply_session(state=state, observation=observation, required_depth=Depth.DEEP)
        second = apply_session(state=state, observation=observation, required_depth=Depth.DEEP)
        assert first.intrinsic_mastery == second.intrinsic_mastery
        assert first.stability == second.stability
        assert first.variance == second.variance
        assert first.engine_confidence == second.engine_confidence

    def test_propagation_is_deterministic(self, curriculum):
        rng = random.Random(SEED)
        intrinsic = {n.node_id: rng.random() for n in curriculum}
        retentions = {n.node_id: rng.random() for n in curriculum}
        first = propagate(curriculum, intrinsic, retentions)
        second = propagate(curriculum, intrinsic, retentions)
        assert first == second

    def test_full_recompute_is_deterministic(self, curriculum):
        rng = random.Random(SEED)
        states = {
            n.node_id: KnowledgeState.cold(n.node_id).replace(
                intrinsic_mastery=rng.random(),
                session_count=rng.randint(0, 5),
                stability=rng.uniform(1.0, 40.0),
            )
            for n in curriculum
        }
        elapsed = {n.node_id: rng.uniform(0, 120) for n in curriculum}
        a = recompute(curriculum, states, days_elapsed=elapsed)
        b = recompute(curriculum, states, days_elapsed=elapsed)
        assert a.effective_mastery == b.effective_mastery
        assert a.prerequisite_confidence == b.prerequisite_confidence
        assert a.status == b.status
        assert a.health == b.health
        assert {k: v.readiness for k, v in a.readiness.items()} == {
            k: v.readiness for k, v in b.readiness.items()
        }

    def test_dict_ordering_does_not_affect_results(self, curriculum):
        """Insertion order must not leak into any score."""
        rng = random.Random(SEED)
        ids = [n.node_id for n in curriculum]
        intrinsic = {nid: rng.random() for nid in ids}
        retentions = {nid: rng.random() for nid in ids}

        shuffled = ids[:]
        random.Random(99).shuffle(shuffled)
        intrinsic_shuffled = {nid: intrinsic[nid] for nid in shuffled}
        retentions_shuffled = {nid: retentions[nid] for nid in shuffled}

        assert propagate(curriculum, intrinsic, retentions) == propagate(
            curriculum, intrinsic_shuffled, retentions_shuffled
        )


class TestMonotonicity:
    """Sanity properties the spec calls out explicitly (§17)."""

    @pytest.mark.parametrize("depth", list(Depth))
    def test_higher_observations_never_lower_session_ability(self, depth):
        weak = Observation(0.2, 0.2, 0.2, 1.0, 0.5)
        strong = Observation(0.9, 0.9, 0.9, 1.0, 0.5)
        assert session_ability(strong, depth).value >= session_ability(weak, depth).value

    @pytest.mark.parametrize("observation", random_observations(15))
    def test_higher_observation_moves_mastery_toward_it(self, observation):
        """M steps toward O, so the update never overshoots away from the evidence."""
        current = 0.5
        ability = session_ability(observation, Depth.DEEP)
        updated = update_intrinsic_mastery(current, ability, evidence_weight=0.8)
        if ability.value > current:
            assert current <= updated <= ability.value
        else:
            assert ability.value <= updated <= current

    def test_a_decayed_prerequisite_never_raises_a_dependent(self):
        """The core propagation property, stated as an inequality."""
        healthy = prerequisite_confidence((PrerequisiteInput("p", 0.9, 1.0),))
        decayed = prerequisite_confidence((PrerequisiteInput("p", 0.3, 1.0),))
        assert decayed <= healthy
        assert effective_mastery(0.8, 1.0, decayed) <= effective_mastery(0.8, 1.0, healthy)

    def test_more_prerequisites_met_never_lowers_confidence(self):
        one_weak = prerequisite_confidence(
            (PrerequisiteInput("a", 0.9, 1.0), PrerequisiteInput("b", 0.2, 1.0))
        )
        both_strong = prerequisite_confidence(
            (PrerequisiteInput("a", 0.9, 1.0), PrerequisiteInput("b", 0.9, 1.0))
        )
        assert both_strong >= one_weak

    def test_effective_mastery_never_exceeds_intrinsic(self):
        """EM = M·R·PC with R,PC ≤ 1, so trust can never exceed evidence."""
        rng = random.Random(SEED)
        for _ in range(200):
            m, r, pc = rng.random(), rng.random(), rng.random()
            assert effective_mastery(m, r, pc) <= m + 1e-12

    def test_bottleneck_dominates_the_blend(self):
        """γ=0.6 leans on the minimum: one weak prerequisite must drag PC down hard."""
        many_strong_one_weak = prerequisite_confidence(
            (
                PrerequisiteInput("a", 1.0, 1.0),
                PrerequisiteInput("b", 1.0, 1.0),
                PrerequisiteInput("c", 1.0, 1.0),
                PrerequisiteInput("weak", 0.0, 1.0),
            )
        )
        assert many_strong_one_weak < 0.35, (
            "averaging would give 0.75 here; the bottleneck lean must prevent that"
        )


class TestBoundedness:
    @pytest.mark.parametrize("observation", random_observations(30))
    @pytest.mark.parametrize("depth", list(Depth))
    def test_scores_stay_in_range(self, observation, depth):
        ability = session_ability(observation, depth)
        assert 0.0 <= ability.value <= 1.0
        state = KnowledgeState.cold("x").replace(session_count=1, stability=2.0, difficulty=0.4)
        update = apply_session(state=state, observation=observation, required_depth=depth)
        assert 0.0 <= update.intrinsic_mastery <= 1.0
        assert 0.0 <= update.variance <= 1.0
        assert 0.0 <= update.engine_confidence <= 1.0
        assert update.stability > 0.0

    def test_all_snapshot_scores_are_bounded(self, curriculum):
        rng = random.Random(SEED)
        states = {
            n.node_id: KnowledgeState.cold(n.node_id).replace(
                intrinsic_mastery=rng.random(),
                session_count=rng.randint(0, 4),
                stability=rng.uniform(0.5, 30.0),
            )
            for n in curriculum
        }
        snapshot = recompute(curriculum, states)
        for node_id in snapshot.effective_mastery:
            assert 0.0 <= snapshot.effective_mastery[node_id] <= 1.0
            assert 0.0 <= snapshot.prerequisite_confidence[node_id] <= 1.0
            assert 0.0 <= snapshot.critical_path_value[node_id] <= 1.0
            assert 0.0 <= snapshot.leverage[node_id] <= 1.0
            assert snapshot.learning_cost[node_id] >= 0.0
        for readiness in snapshot.readiness.values():
            assert 0.0 <= readiness.readiness <= 1.0
        assert 0.0 <= snapshot.health.score <= 100.0


class TestConfigNotConstants:
    def test_changing_a_tunable_changes_behaviour(self):
        """Proves the parameters are actually wired, not shadowed by inline literals."""
        from dataclasses import replace

        strict = replace(DEFAULT_CONFIG, gamma=1.0)  # pure bottleneck
        lenient = replace(DEFAULT_CONFIG, gamma=0.0)  # pure weighted average
        prereqs = (PrerequisiteInput("a", 1.0, 1.0), PrerequisiteInput("b", 0.0, 1.0))
        assert prerequisite_confidence(prereqs, strict) == pytest.approx(0.0)
        assert prerequisite_confidence(prereqs, lenient) == pytest.approx(0.5)
