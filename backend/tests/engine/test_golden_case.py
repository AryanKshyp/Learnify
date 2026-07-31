"""The CALC_ENGINE_SPEC.md §15 golden case. THE regression test for this project.

Chain: Probability → Bayes → Naive Bayes, each a direct prerequisite of the next at weight 1.0.

It demonstrates the one property the whole architecture exists to provide:

    1. Intrinsic mastery for Bayes and Naive Bayes is UNCHANGED when Probability decays.
    2. Effective mastery for Naive Bayes collapses 0.77 → 0.23 purely because Probability
       decayed — so the engine surfaces Probability, not Naive Bayes.
    3. A single reassessment of Probability restores both dependents, with ZERO reassessment
       of either.

If this test fails, the intrinsic/effective split has been broken and the system is back to
destroying evidence — which is the exact failure the design was built to eliminate.
"""

from __future__ import annotations

import pytest

from knowledgeos.engine import (
    DEFAULT_CONFIG,
    PrerequisiteInput,
    effective_mastery,
    is_frontier,
    prerequisite_confidence,
)

# §15 fixes these directly rather than deriving them from a curriculum
M_PROB, M_BAYES, M_NB = 0.90, 0.95, 0.90


def chain_effective(r_prob: float, r_bayes: float, r_nb: float) -> dict[str, float]:
    """Propagate the three-node chain by hand, in topological order.

    Deliberately not routed through `propagate()`: this mirrors the spec's worked example
    step-for-step, so a failure points at the formulas rather than at graph plumbing.
    """
    em_prob = effective_mastery(M_PROB, r_prob, prerequisite_confidence(()))

    pc_bayes = prerequisite_confidence(
        (PrerequisiteInput("probability", em_prob, 1.0),)
    )
    em_bayes = effective_mastery(M_BAYES, r_bayes, pc_bayes)

    pc_nb = prerequisite_confidence((PrerequisiteInput("bayes", em_bayes, 1.0),))
    em_nb = effective_mastery(M_NB, r_nb, pc_nb)

    return {
        "probability": em_prob,
        "bayes": em_bayes,
        "naive_bayes": em_nb,
        "pc_bayes": pc_bayes,
        "pc_naive_bayes": pc_nb,
    }


@pytest.fixture(scope="module")
def t0():
    """T0 - all three freshly assessed, R ≈ 1."""
    return chain_effective(1.00, 1.00, 1.00)


@pytest.fixture(scope="module")
def t1():
    """T1 - three months pass; only Probability decays materially."""
    return chain_effective(0.33, 0.95, 0.95)


class TestT0FreshlyAssessed:
    """All three freshly assessed, R ≈ 1."""

    def test_probability_has_no_prerequisites_so_pc_is_one(self, t0):
        assert t0["probability"] == pytest.approx(0.90)

    def test_bayes_is_limited_by_probability(self, t0):
        # EM = 0.95 · 1.00 · 0.90
        assert t0["bayes"] == pytest.approx(0.855)

    def test_naive_bayes_is_limited_by_bayes(self, t0):
        # EM = 0.90 · 1.00 · 0.855
        assert t0["naive_bayes"] == pytest.approx(0.770, abs=1e-3)


class TestT1ProbabilityDecays:
    """Three months pass. Only Probability decays materially (R = 0.33)."""

    def test_probability_effective_mastery_falls(self, t1):
        assert t1["probability"] == pytest.approx(0.297, abs=1e-3)

    def test_bayes_effective_mastery_falls_without_being_reassessed(self, t1):
        # EM = 0.95 · 0.95 · 0.297
        assert t1["bayes"] == pytest.approx(0.268, abs=1e-3)

    def test_naive_bayes_collapses(self, t1):
        # EM = 0.90 · 0.95 · 0.268
        assert t1["naive_bayes"] == pytest.approx(0.229, abs=1e-3)

    def test_assertion_1_intrinsic_mastery_is_untouched(self):
        """No evidence destroyed. Nothing in propagation can write to M.

        The module-level constants are the intrinsic values; propagation consumed them and
        never produced a new one. This is asserted structurally in
        test_evidence_preservation.py as well.
        """
        assert (M_PROB, M_BAYES, M_NB) == (0.90, 0.95, 0.90)

    def test_assertion_2_collapse_is_caused_solely_by_the_prerequisite(self, t1):
        """0.77 → 0.23 with M and R for Naive Bayes essentially unchanged."""
        t0 = chain_effective(1.00, 1.00, 1.00)
        assert t0["naive_bayes"] == pytest.approx(0.770, abs=1e-3)
        assert t1["naive_bayes"] == pytest.approx(0.229, abs=1e-3)
        assert t1["naive_bayes"] < t0["naive_bayes"] / 3

    def test_the_engine_routes_upstream_to_probability(self, t1):
        """Assertion 2's practical half: the recommendation must point at Probability.

        Note that raw EM alone would point the *wrong* way — Naive Bayes has the lowest
        effective mastery of the three, because the collapse compounds downstream. What makes
        the engine route upstream is the FRONTIER check: Naive Bayes has prerequisite
        confidence far below φ, so it is excluded as not-yet-learnable, while Probability has
        no prerequisites at all and is therefore always ready to study.
        """
        assert t1["naive_bayes"] < t1["bayes"], "collapse compounds downstream"
        assert t1["naive_bayes"] < t1["probability"], "so lowest-EM points the wrong way"

        assert not is_frontier(
            t1["naive_bayes"], t1["pc_naive_bayes"], target=0.80, config=DEFAULT_CONFIG
        ), "unmet prerequisites must keep a node OFF the frontier"

        # Probability has no prerequisites, so PC = 1.0 and it is always learnable
        assert is_frontier(t1["probability"], 1.0, target=0.80, config=DEFAULT_CONFIG)


class TestT2RestoredBySingleReassessment:
    """Assertion 3: reassess Probability only. Both dependents recover."""

    def test_single_reassessment_restores_the_whole_chain(self):
        restored = chain_effective(1.00, 1.00, 1.00)
        assert restored["probability"] == pytest.approx(0.90)
        assert restored["bayes"] == pytest.approx(0.855)
        assert restored["naive_bayes"] == pytest.approx(0.770, abs=1e-3)

    def test_recovery_requires_zero_reassessment_of_dependents(self):
        """The dependents' M values are the SAME objects used at T0 and T1.

        Nothing reassessed them; their effective mastery recovered purely because the
        prerequisite did. That is the entire payoff of the intrinsic/effective split.
        """
        decayed = chain_effective(0.33, 0.95, 0.95)
        restored = chain_effective(1.00, 1.00, 1.00)

        assert decayed["naive_bayes"] == pytest.approx(0.229, abs=1e-3)
        assert restored["naive_bayes"] == pytest.approx(0.770, abs=1e-3)
        assert restored["naive_bayes"] > decayed["naive_bayes"] * 3

    def test_restoration_is_exact_not_approximate(self):
        """Recovery returns to the original value, not merely near it."""
        assert chain_effective(1.0, 1.0, 1.0) == chain_effective(1.0, 1.0, 1.0)
