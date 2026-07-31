"""Status derivation (§13) and the forgetting model (§6).

The status tests matter more than they look: the spec's stated evaluation order is wrong, and
`status.py` deliberately deviates from it. These pin the corrected behaviour so nobody
"restores" the literal reading later.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import Depth
from knowledgeos.engine import (
    DEFAULT_CONFIG,
    days_until_review,
    derive_status,
    initial_difficulty,
    is_due,
    retention,
    role_priority_weights,
    update_stability,
)
from knowledgeos.state import Status


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
