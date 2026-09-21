"""Status derivation (§13) and the forgetting model (§6).

The status tests matter more than they look: the spec's stated evaluation order is wrong, and
`derive_status` deliberately deviates from it. These pin the corrected behaviour so nobody
"restores" the literal reading later.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from knowledgeos.curriculum import Depth, fixture_repository
from knowledgeos.engine import DEFAULT_CONFIG, Observation, apply_session, recompute, retention
from knowledgeos.engine.observation import normalized_variance
from knowledgeos.engine.pipeline import derive_status
from knowledgeos.engine.readiness import role_priority_weights
from knowledgeos.engine.retention import (
    days_until_review,
    initial_difficulty,
    is_due,
    update_stability,
)
from knowledgeos.state import (
    InMemoryKnowledgeStateRepository,
    KnowledgeState,
    StateOverlay,
    Status,
)


def status(em, *, r=1.0, var=0.0, n=3, target=0.8):
    return derive_status(
        effective_mastery=em,
        retention=r,
        variance=var,
        session_count=n,
        target=target,
    )


class TestStatusLadder:
    def test_no_evidence_is_unassessed(self):
        assert status(0.9, n=0) is Status.UNASSESSED

    def test_low_effective_mastery_is_learning(self):
        assert status(0.2) is Status.LEARNING

    def test_middling_is_practiced(self):
        assert status(0.55) is Status.PRACTICED

    def test_strong_and_fresh_is_retained(self):
        assert status(0.75, r=0.9, n=2) is Status.RETAINED

    def test_very_strong_is_mastered(self):
        assert status(0.95, r=0.95, var=0.1, n=3) is Status.MASTERED


class TestStatusOrderingDeviation:
    """The spec says "evaluate top-down"; taken literally, mastered is unreachable."""

    def test_a_mastered_node_is_not_reported_as_retained(self):
        """Literal top-down would match `retained` first and never reach `mastered`."""
        assert status(0.95, r=0.95, var=0.05, n=4) is Status.MASTERED

    def test_inconsistent_evidence_beats_a_high_average(self):
        """High variance means the observations disagree - that is not "retained"."""
        assert status(0.9, r=0.95, var=0.8, n=5) is Status.LEARNING

    def test_mastered_requires_low_variance(self):
        assert status(0.95, r=0.95, var=0.3, n=4) is Status.RETAINED

    def test_mastered_requires_high_retention(self):
        assert status(0.95, r=0.5, var=0.05, n=4) is Status.PRACTICED

    def test_mastered_respects_a_high_depth_target(self):
        """τ can exceed 0.85, and then 0.85 is not enough."""
        assert status(0.88, r=0.95, var=0.05, n=4, target=0.90) is Status.RETAINED
        assert status(0.92, r=0.95, var=0.05, n=4, target=0.90) is Status.MASTERED

    def test_one_session_can_never_be_retained_or_mastered(self):
        """Two consistent sessions minimum - a single data point is not a trend."""
        assert status(0.95, r=0.99, var=0.0, n=1) is Status.PRACTICED


class TestRetention:
    def test_no_stability_means_no_retention(self):
        assert retention(10.0, None) == 0.0

    def test_retention_is_one_at_assessment_time(self):
        assert retention(0.0, 5.0) == 1.0

    def test_retention_decays_monotonically(self):
        values = [retention(d, 10.0) for d in (0, 5, 10, 20, 40)]
        assert values == sorted(values, reverse=True)

    def test_higher_stability_retains_longer(self):
        assert retention(30.0, 60.0) > retention(30.0, 10.0)

    def test_one_time_constant_gives_the_expected_fraction(self):
        assert retention(10.0, 10.0) == pytest.approx(0.3679, abs=1e-3)


class TestStabilityGrowth:
    def test_first_session_starts_from_the_configured_base(self):
        s = update_stability(None, quality=0.0, mastery=0.0, difficulty=0.5)
        assert s == DEFAULT_CONFIG.initial_stability_days

    def test_a_good_session_on_easy_material_grows_fastest(self):
        easy = update_stability(10.0, quality=0.9, mastery=0.9, difficulty=0.1)
        hard = update_stability(10.0, quality=0.9, mastery=0.9, difficulty=0.9)
        assert easy > hard

    def test_stability_never_shrinks(self):
        """The model rewards; it does not punish."""
        assert update_stability(10.0, quality=0.0, mastery=0.0, difficulty=0.5) >= 10.0

    def test_difficulty_defaults_rise_with_depth(self):
        difficulties = [initial_difficulty(d) for d in Depth]
        assert difficulties == sorted(difficulties)


class TestReviewScheduling:
    def test_review_interval_scales_with_stability(self):
        assert days_until_review(20.0) == pytest.approx(2 * days_until_review(10.0))

    def test_interval_matches_the_target_retention(self):
        """At the scheduled moment, retention should equal θ."""
        stability = 30.0
        interval = days_until_review(stability)
        assert retention(interval, stability) == pytest.approx(
            DEFAULT_CONFIG.target_retention, abs=1e-9
        )

    def test_not_due_before_the_interval_and_due_after(self):
        stability = 30.0
        interval = days_until_review(stability)
        assert not is_due(interval * 0.5, stability)
        assert is_due(interval * 1.5, stability)

    def test_never_assessed_is_never_due(self):
        assert not is_due(1000.0, None)


class TestRolePriorityWeights:
    def test_weights_sum_to_one(self, ):
        from knowledgeos.curriculum import fixture_repository

        weights = role_priority_weights(fixture_repository().get())
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_top_priority_role_carries_the_most_weight(self):
        from knowledgeos.curriculum import fixture_repository

        curriculum = fixture_repository().get()
        weights = role_priority_weights(curriculum)
        ranked = sorted(curriculum.roles, key=lambda r: r.priority_rank)
        values = [weights[r.role_id] for r in ranked]
        assert values == sorted(values, reverse=True)


class TestVarianceRoundTrip:
    """σ² survives storage unchanged, whatever the tunables say. CALC_ENGINE_SPEC.md §4.

    Variance is EWMA state: each session's update needs the previous *raw* value back. It used
    to be persisted in the 0..1 form — divided by `variance_normalizer` and clamped on write,
    multiplied back on read — which coupled two things that should not be coupled. The engine
    had to know the storage format, and storage bounded the engine's arithmetic.

    Measured honestly: with κ = 0.5 the EWMA ceiling is ≈0.0625 raw, below the 0.10 normalizer,
    so the clamp never actually fired and no stored value was ever truncated. What the old
    scheme really cost was a latent trap — the tests below pin the two properties that make it
    unreachable rather than merely unlikely.
    """

    def a_state(self, **overrides):
        return KnowledgeState.cold("prob-axioms").replace(**overrides)

    def disagreeing_run(self, rounds=20, config=DEFAULT_CONFIG):
        """Alternate strong and weak sessions, threading state the way ingestion does."""
        state = self.a_state()
        mean = 0.0
        for index in range(rounds):
            observed = 1.0 if index % 2 == 0 else 0.0
            update = apply_session(
                state=state,
                observation=Observation(observed, observed, observed),
                required_depth=Depth.WORKING,
                previous_running_mean=mean,
                config=config,
            )
            mean = update.running_mean
            state = state.replace(
                intrinsic_mastery=update.intrinsic_mastery,
                session_count=update.session_count,
                stability=update.stability,
                difficulty=update.difficulty,
                observation_mean=update.running_mean,
                assessment_variance_raw=update.variance_raw,
            )
        return state

    def test_the_stored_value_does_not_depend_on_the_tunable(self):
        """The property worth having: `variance_normalizer` is a display choice, not a unit.

        Under the old scheme the persisted number was `raw / variance_normalizer`, so retuning
        that constant silently reinterpreted every row already in the database. Now it scales
        only the lens.
        """
        loose = replace(DEFAULT_CONFIG, variance_normalizer=0.10)
        tight = replace(DEFAULT_CONFIG, variance_normalizer=0.02)

        assert (
            self.disagreeing_run(config=loose).assessment_variance_raw
            == self.disagreeing_run(config=tight).assessment_variance_raw
        )

    def test_a_tighter_normalizer_would_have_truncated_the_stored_value(self):
        """The trap the old scheme was one config change away from.

        At the shipped 0.10 the EWMA never reaches the clamp. At 0.02 it does — and the old
        write-then-rescale round trip loses the real number, while the raw one does not.
        """
        config = replace(DEFAULT_CONFIG, variance_normalizer=0.02)
        produced = self.disagreeing_run(config=config).assessment_variance_raw

        assert normalized_variance(produced, config) == 1.0, "the lens saturates here"
        lossy = normalized_variance(produced, config) * config.variance_normalizer
        assert lossy < produced, "the old round trip would have truncated it"

    def test_at_the_shipped_tunables_the_clamp_never_fires(self):
        """Stated as a test so a future change to κ or the normalizer has to notice."""
        peak = self.disagreeing_run().assessment_variance_raw
        assert peak < DEFAULT_CONFIG.variance_normalizer, (
            f"raw variance reached {peak}, which the 0..1 lens would now saturate"
        )

    def test_raw_variance_survives_a_save_and_reload(self):
        overlay = StateOverlay(
            fixture_repository().get(), InMemoryKnowledgeStateRepository()
        )
        overlay.save(self.a_state(session_count=3, assessment_variance_raw=0.42))
        assert overlay.state_for("prob-axioms").assessment_variance_raw == 0.42

    def test_the_snapshot_carries_the_normalised_value_for_the_status_gates(self):
        """Derived, like every other computed value — it lives on the snapshot, not the row."""
        curriculum = fixture_repository().get()
        states = {
            n.node_id: KnowledgeState.cold(n.node_id).replace(assessment_variance_raw=0.18)
            for n in curriculum
        }
        snapshot = recompute(curriculum, states)
        assert all(v == 1.0 for v in snapshot.variance.values())
