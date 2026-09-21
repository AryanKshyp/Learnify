"""The wiring between the stages, and the stages nothing else tests.

The formulas are well covered — `test_golden_case.py` pins them against the spec's worked
example, `test_determinism.py` pins purity and monotonicity. But the golden case deliberately
propagates its three-node chain **by hand** so a failure points at a formula rather than at
graph plumbing, which means the project's central regression test never touches `propagate()`
or `recompute()` at all. The 130 lines of stage sequencing whose docstring says "ordering is
not negotiable" had nothing asserting the ordering.

This file tests `recompute` through its own interface: the invariants that only hold if the
stages run in the right order with the right inputs, plus direct values for the six stage
functions that had zero test references — `knowledge_health` most of all, since it is the
number on the home screen and the API only ever asserted that its keys exist.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from knowledgeos.curriculum import fixture_repository
from knowledgeos.curriculum.errors import RoleNotFoundError
from knowledgeos.engine import DEFAULT_CONFIG, recompute, target_for_node
from knowledgeos.engine.pipeline import (
    KnowledgeHealth,
    critical_path_values,
    current_importance,
    intrinsic_importance,
    is_frontier,
    knowledge_health,
    leverage_values,
)
from knowledgeos.engine.recommend import (
    Candidate,
    cold_start_queue,
    diversify,
    min_max_normalize,
    score_candidates,
    similarity,
)
from knowledgeos.state import KnowledgeState

SEED = 20260916


@pytest.fixture(scope="module")
def curriculum():
    return fixture_repository().get()


def states_from(curriculum, mastery: dict[str, float]) -> dict[str, KnowledgeState]:
    """Assessed state for every node, so nothing is filtered out for lack of evidence."""
    return {
        n.node_id: KnowledgeState.cold(n.node_id).replace(
            intrinsic_mastery=mastery.get(n.node_id, 0.0),
            session_count=2,
            stability=1000.0,  # effectively no decay, so propagation is what is under test
            difficulty=0.5,
        )
        for n in curriculum
    }


def random_mastery(curriculum, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    return {n.node_id: rng.random() for n in curriculum}


# --------------------------------------------------------------- stage ordering


class TestStageOrdering:
    """Invariants that only hold if the pipeline runs its stages in the stated order."""

    @pytest.mark.parametrize("seed", range(SEED, SEED + 5))
    def test_effective_mastery_never_exceeds_intrinsic(self, curriculum, seed):
        """EM = M · R · PC, so EM ≤ M for every node on every graph."""
        mastery = random_mastery(curriculum, seed)
        snapshot = recompute(curriculum, states_from(curriculum, mastery))
        for node_id, effective in snapshot.effective_mastery.items():
            assert effective <= mastery[node_id] + 1e-9, node_id

    @pytest.mark.parametrize("seed", range(SEED, SEED + 3))
    def test_frontier_implies_ready_prerequisites_and_a_real_gap(self, curriculum, seed):
        """Stage 7 consumes stage 5's PC and stage 6's EM. Wrong order, wrong frontier."""
        snapshot = recompute(curriculum, states_from(curriculum, random_mastery(curriculum, seed)))
        threshold = DEFAULT_CONFIG.frontier_prerequisite_threshold
        for node_id, on_frontier in snapshot.frontier.items():
            if on_frontier:
                assert snapshot.prerequisite_confidence[node_id] >= threshold, node_id
                assert snapshot.effective_mastery[node_id] < snapshot.targets[node_id], node_id

    @pytest.mark.parametrize("seed", range(SEED, SEED + 3))
    def test_raising_a_node_never_lowers_a_descendant(self, curriculum, seed):
        """Propagation runs in topological order, prerequisites first.

        If `propagate` visited nodes in an arbitrary order, a dependent could be computed from
        a stale prerequisite and improving the prerequisite would sometimes *lower* it.
        """
        mastery = random_mastery(curriculum, seed)
        before = recompute(curriculum, states_from(curriculum, mastery))

        rng = random.Random(seed)
        lifted = rng.choice([n.node_id for n in curriculum])
        mastery[lifted] = 1.0
        after = recompute(curriculum, states_from(curriculum, mastery))

        for descendant in curriculum.descendants(lifted):
            assert (
                after.prerequisite_confidence[descendant]
                >= before.prerequisite_confidence[descendant] - 1e-9
            ), f"{lifted} -> {descendant}"
            assert (
                after.effective_mastery[descendant]
                >= before.effective_mastery[descendant] - 1e-9
            ), f"{lifted} -> {descendant}"

    def test_readiness_runs_before_current_importance(self, curriculum):
        """The one ordering dependency that is not obvious from the data flow.

        Stage 9 produces the bottlenecks; stage 10's CurImp multiplies them by `bottleneck_boost`.
        Computed the other way round, every node would miss the boost and the recommendation
        ranking would stop preferring the thing actually holding a role back.
        """
        snapshot = recompute(curriculum, states_from(curriculum, random_mastery(curriculum, SEED)))
        bottlenecks = {
            r.bottleneck_node_id for r in snapshot.readiness.values() if r.bottleneck_node_id
        }
        assert bottlenecks, "the fixture must produce at least one bottleneck to test this"

        for node_id in bottlenecks:
            boosted = snapshot.current_importance[node_id]
            unboosted = current_importance(
                curriculum,
                node_id,
                leverage=snapshot.leverage[node_id],
                is_bottleneck=False,
            )
            assert boosted > unboosted, (
                f"{node_id} is a bottleneck but carries no boost — CurImp was computed "
                "before readiness"
            )

    def test_learning_cost_is_zero_exactly_where_the_target_is_met(self, curriculum):
        snapshot = recompute(curriculum, states_from(curriculum, random_mastery(curriculum, SEED)))
        for node_id, cost in snapshot.learning_cost.items():
            sufficient = snapshot.effective_mastery[node_id] >= snapshot.targets[node_id]
            if sufficient and snapshot.targets[node_id] > 0:
                assert cost == 0.0, node_id

    def test_every_stage_covers_every_node(self, curriculum):
        """A stage that silently skipped nodes would show up as a missing key, not a wrong one."""
        snapshot = recompute(curriculum, states_from(curriculum, random_mastery(curriculum, SEED)))
        ids = {n.node_id for n in curriculum}
        for name in (
            "prerequisite_confidence",
            "effective_mastery",
            "retention",
            "variance",
            "targets",
            "frontier",
            "critical_path_value",
            "leverage",
            "current_importance",
            "learning_cost",
            "status",
        ):
            assert set(getattr(snapshot, name)) == ids, name

    def test_a_missing_elapsed_entry_does_not_silently_mean_no_decay(self, curriculum):
        """`days_elapsed` is a parallel dict, so a caller can under-fill it.

        Documented behaviour is that an absent node means Δt = 0. Pinned because the
        alternative reading — treating it as an error — would be a behaviour change, and
        because a caller building it from a stale node set gets full retention for free.
        """
        states = states_from(curriculum, random_mastery(curriculum, SEED))
        full = recompute(curriculum, states, days_elapsed={n: 0.0 for n in states})
        empty = recompute(curriculum, states, days_elapsed={})
        assert full.retention == empty.retention


# ------------------------------------------------------------- knowledge health


class TestKnowledgeHealth:
    """Stage 14 — the number on the home screen, previously asserted only by key presence."""

    def test_health_is_the_weighted_sum_of_its_four_components(self, curriculum):
        role_id = curriculum.roles[0].role_id
        critical = [
            n
            for n in curriculum.nodes_by_role(role_id)
            if (r := n.requirement_for(role_id))
            and r.importance >= DEFAULT_CONFIG.critical_importance_threshold
        ]
        assert critical, "the fixture must have critical nodes for this role"
        ids = [n.node_id for n in critical]

        # every critical node assessed, fully mastered, perfectly retained, target met
        health = knowledge_health(
            curriculum,
            effective_mastery=dict.fromkeys(ids, 1.0),
            retention=dict.fromkeys(ids, 1.0),
            session_counts=dict.fromkeys(ids, 3),
            targets=dict.fromkeys(ids, 0.5),
            frontier_size=0,
            active_role_id=role_id,
        )
        assert health.coverage == 1.0
        assert health.mean_effective_mastery == pytest.approx(1.0)
        assert health.mean_retention == pytest.approx(1.0)
        assert health.critical_gap_ratio == 0.0
        assert health.score == pytest.approx(100.0), "all four components maxed"
        assert health.critical_node_count == len(critical)

    def test_a_cold_graph_scores_only_the_no_gaps_term_it_has_not_earned(self, curriculum):
        """Nothing assessed: coverage 0, means 0, and every critical node below target."""
        role_id = curriculum.roles[0].role_id
        ids = [n.node_id for n in curriculum.nodes_by_role(role_id)]
        health = knowledge_health(
            curriculum,
            effective_mastery=dict.fromkeys(ids, 0.0),
            retention=dict.fromkeys(ids, 0.0),
            session_counts=dict.fromkeys(ids, 0),
            targets=dict.fromkeys(ids, 0.8),
            frontier_size=3,
            active_role_id=role_id,
        )
        assert health.coverage == 0.0
        assert health.critical_gap_ratio == 1.0
        assert health.score == pytest.approx(0.0)
        assert health.frontier_size == 3

    def test_importance_weighting_means_a_weak_critical_node_hurts_more(self, curriculum):
        """The means are importance-weighted, so which node is weak has to matter."""
        role_id = curriculum.roles[0].role_id
        weighted = [
            (n.node_id, r.importance)
            for n in curriculum.nodes_by_role(role_id)
            if (r := n.requirement_for(role_id))
            and r.importance >= DEFAULT_CONFIG.critical_importance_threshold
        ]
        if len({importance for _, importance in weighted}) < 2:
            pytest.skip("this role's critical nodes all share one importance")

        most = max(weighted, key=lambda pair: pair[1])[0]
        least = min(weighted, key=lambda pair: pair[1])[0]
        ids = [node_id for node_id, _ in weighted]

        def score_with_weak(weak: str) -> float:
            mastery = dict.fromkeys(ids, 1.0)
            mastery[weak] = 0.0
            return knowledge_health(
                curriculum,
                effective_mastery=mastery,
                retention=dict.fromkeys(ids, 1.0),
                session_counts=dict.fromkeys(ids, 3),
                targets=dict.fromkeys(ids, 0.5),
                frontier_size=0,
                active_role_id=role_id,
            ).score

        assert score_with_weak(most) < score_with_weak(least)

    def test_no_critical_nodes_scores_zero_rather_than_dividing_by_zero(self, curriculum):
        """`total_importance` is a denominator, so the empty case has to be handled, not risked."""
        role_id = curriculum.roles[0].role_id
        impossible = replace(DEFAULT_CONFIG, critical_importance_threshold=1.01)
        health = knowledge_health(
            curriculum,
            effective_mastery={},
            retention={},
            session_counts={},
            targets={},
            frontier_size=0,
            active_role_id=role_id,
            config=impossible,
        )
        assert isinstance(health, KnowledgeHealth)
        assert health.score == 0.0
        assert health.critical_node_count == 0

    def test_an_unknown_role_is_refused_rather_than_scored_as_empty(self, curriculum):
        """A typo in the role lens must not read as "perfect health, nothing critical"."""
        with pytest.raises(RoleNotFoundError):
            knowledge_health(
                curriculum,
                effective_mastery={},
                retention={},
                session_counts={},
                targets={},
                frontier_size=0,
                active_role_id="astronaut",
            )


# ------------------------------------------------------------- graph position


class TestGraphPosition:
    def test_critical_path_value_is_normalised_and_favours_gateways(self, curriculum):
        values = critical_path_values(curriculum)
        assert set(values) == {n.node_id for n in curriculum}
        assert min(values.values()) == pytest.approx(0.0)
        assert max(values.values()) == pytest.approx(1.0)

        leaves = [n.node_id for n in curriculum if not curriculum.descendants(n.node_id)]
        assert leaves, "the fixture must have leaf nodes"
        assert all(values[leaf] == pytest.approx(0.0) for leaf in leaves), (
            "a node with nothing downstream is a gateway to nothing"
        )

    def test_leverage_rises_with_what_a_node_unlocks(self, curriculum):
        critical_path = critical_path_values(curriculum)
        leverage = leverage_values(curriculum, critical_path)
        ranked = sorted(curriculum, key=lambda n: len(curriculum.descendants(n.node_id)))
        fewest, most = ranked[0].node_id, ranked[-1].node_id
        assert leverage[most] > leverage[fewest]

    def test_intrinsic_importance_is_the_max_across_roles(self, curriculum):
        for node in curriculum:
            expected = max((r.importance for r in node.roles), default=0.0)
            assert intrinsic_importance(curriculum, node.node_id) == expected

    def test_is_frontier_needs_both_halves(self):
        target, ready = 0.8, DEFAULT_CONFIG.frontier_prerequisite_threshold
        assert is_frontier(0.2, ready, target)
        assert not is_frontier(0.9, ready, target), "already sufficient"
        assert not is_frontier(0.2, ready - 0.01, target), "prerequisites not ready"

    def test_target_is_the_max_over_the_roles_a_node_serves(self, curriculum):
        for node in curriculum:
            depth = node.max_required_depth
            expected = DEFAULT_CONFIG.target_for(depth) if depth else 0.0
            assert target_for_node(curriculum, node.node_id) == expected


# ------------------------------------------------------------ ranking internals


class TestRankingInternals:
    """`score_candidates`, `diversify`, `similarity`, `min_max_normalize`, `cold_start_queue`.

    All five were reachable only through `recommend`, and the one assertion that touched
    diversification was guarded by `if len(picks) >= 3` — so it passed silently whenever the
    fixture produced fewer.
    """

    def test_min_max_normalize_maps_to_the_unit_interval(self):
        assert min_max_normalize({}) == {}
        assert min_max_normalize({"a": 2.0, "b": 4.0, "c": 6.0}) == {
            "a": 0.0,
            "b": 0.5,
            "c": 1.0,
        }

    def test_a_flat_distribution_normalises_to_zero_not_one(self):
        """If nothing differentiates the nodes the factor must contribute nothing to ranking,
        rather than inflating every candidate to maximum."""
        assert min_max_normalize({"a": 3.0, "b": 3.0}) == {"a": 0.0, "b": 0.0}

    def candidates(self) -> tuple[Candidate, ...]:
        return (
            Candidate("cheap-big", expected_readiness_gain=0.4, learning_cost=1.0,
                      leverage=0.9, current_importance=0.9),
            Candidate("dear-small", expected_readiness_gain=0.1, learning_cost=8.0,
                      leverage=0.1, current_importance=0.2),
            Candidate("middling", expected_readiness_gain=0.2, learning_cost=2.0,
                      leverage=0.5, current_importance=0.5),
        )

    def test_scoring_prefers_gain_per_unit_cost_not_the_biggest_gain(self):
        scored = score_candidates(self.candidates())
        assert [c.node_id for c in scored][0] == "cheap-big"
        assert scored[0].priority >= scored[-1].priority
        assert [c.priority for c in scored] == sorted(
            (c.priority for c in scored), reverse=True
        )

    def test_a_zero_cost_candidate_scores_zero_rather_than_dividing_by_zero(self):
        free = Candidate("already-there", expected_readiness_gain=0.9, learning_cost=0.0,
                         leverage=1.0, current_importance=1.0)
        scored = score_candidates((free, *self.candidates()))
        assert next(c for c in scored if c.node_id == "already-there").priority == 0.0

    def test_scoring_nothing_returns_nothing(self):
        assert score_candidates(()) == ()

    def test_similarity_is_one_for_a_node_against_itself(self, curriculum):
        node_id = next(iter(curriculum)).node_id
        assert similarity(curriculum, node_id, node_id) == 1.0

    def test_nodes_in_one_competency_are_maximally_similar(self, curriculum):
        by_competency: dict[tuple[str, str], list[str]] = {}
        for node in curriculum:
            by_competency.setdefault((node.section, node.competency), []).append(node.node_id)
        pair = next((ids for ids in by_competency.values() if len(ids) >= 2), None)
        if pair is None:
            pytest.skip("the fixture has no competency with two nodes")
        assert similarity(curriculum, pair[0], pair[1]) == 1.0

    def test_diversify_keeps_the_top_candidate_and_respects_the_limit(self, curriculum):
        scored = score_candidates(
            tuple(
                Candidate(n.node_id, expected_readiness_gain=0.5, learning_cost=1.0,
                          leverage=0.5, current_importance=0.5)
                for n in curriculum
            )
        )
        picked = diversify(curriculum, scored, 4)
        assert len(picked) == 4
        assert picked[0].node_id == scored[0].node_id, "highest priority always leads"
        assert len({c.node_id for c in picked}) == 4

    def test_diversify_spreads_across_competencies(self, curriculum):
        """The guarantee MMR exists for, asserted unconditionally."""
        scored = score_candidates(
            tuple(
                Candidate(n.node_id, expected_readiness_gain=0.5, learning_cost=1.0,
                          leverage=0.5, current_importance=0.5)
                for n in curriculum
            )
        )
        picked = diversify(curriculum, scored, 5)
        competencies = {
            (curriculum.node(c.node_id).section, curriculum.node(c.node_id).competency)
            for c in picked
        }
        assert len(competencies) > 1, "MMR must not return five variations of one topic"

    def test_diversify_degenerate_inputs(self, curriculum):
        assert diversify(curriculum, (), 5) == ()
        scored = score_candidates(self.candidates()[:1])
        assert diversify(curriculum, scored, 0) == ()

    def test_cold_start_queue_ranks_by_importance_times_leverage(self):
        ranked = cold_start_queue(
            ("low", "high", "mid"),
            current_importance={"low": 0.1, "mid": 0.5, "high": 0.9},
            leverage={"low": 0.0, "mid": 0.5, "high": 1.0},
        )
        assert ranked == ("high", "mid", "low")

    def test_cold_start_queue_is_deterministic_under_ties(self):
        tied = {"a": 0.5, "b": 0.5, "c": 0.5}
        flat = dict.fromkeys(tied, 0.0)
        first = cold_start_queue(("c", "a", "b"), current_importance=tied, leverage=flat)
        second = cold_start_queue(("b", "c", "a"), current_importance=tied, leverage=flat)
        assert first == second
