"""The pipeline end to end, on the real fixture curriculum.

The golden case proves the formulas; this proves they are wired together in the right order
and behave sensibly on a real graph with real prerequisite structure.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import Depth, fixture_repository
from knowledgeos.engine import (
    DEFAULT_CONFIG,
    Observation,
    apply_session,
    recommend,
    recompute,
    unexplored,
)
from knowledgeos.state import KnowledgeState, Status


@pytest.fixture(scope="module")
def curriculum():
    return fixture_repository().get()


@pytest.fixture
def cold_states(curriculum):
    return {n.node_id: KnowledgeState.cold(n.node_id) for n in curriculum}


class TestColdStart:
    def test_everything_starts_unassessed(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        assert all(s is Status.UNASSESSED for s in snapshot.status.values())

    def test_cold_graph_has_zero_effective_mastery(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        assert all(em == 0.0 for em in snapshot.effective_mastery.values())

    def test_root_nodes_are_trusted_even_when_unknown(self, curriculum, cold_states):
        """PC is about prerequisites, not about the node itself."""
        snapshot = recompute(curriculum, cold_states)
        assert snapshot.prerequisite_confidence["prob-axioms"] == 1.0

    def test_only_roots_are_on_the_frontier_when_nothing_is_known(self, curriculum, cold_states):
        """Nothing downstream is learnable yet, which is the whole point of the frontier."""
        snapshot = recompute(curriculum, cold_states)
        for node_id in snapshot.frontier_ids:
            assert not curriculum.prerequisites_of(node_id), (
                f"{node_id} is on the frontier but its prerequisites are unmet"
            )

    def test_unexplored_queue_covers_every_node(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        assert len(unexplored(curriculum, cold_states, snapshot)) == len(curriculum)

    def test_readiness_is_low_but_not_zero(self, curriculum, cold_states):
        """ε keeps readiness meaningful rather than collapsing every role to 0."""
        snapshot = recompute(curriculum, cold_states)
        for readiness in snapshot.readiness.values():
            assert 0.0 < readiness.readiness < 0.1

    def test_health_is_near_zero_but_reports_components(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        assert snapshot.health.coverage == 0.0
        assert snapshot.health.critical_node_count > 0
        assert snapshot.health.critical_gap_ratio == 1.0


class TestSessionUpdatesState:
    def test_a_strong_session_raises_intrinsic_mastery(self):
        state = KnowledgeState.cold("prob-axioms")
        update = apply_session(
            state=state,
            observation=Observation(0.9, 0.85, 0.8, response_time_rating=0.9),
            required_depth=Depth.DEEP,
        )
        assert update.intrinsic_mastery > 0.0
        assert update.session_count == 1
        assert update.stability > 0.0
        assert update.days_until_review > 0.0

    def test_retention_is_one_at_the_moment_of_assessment(self):
        update = apply_session(
            state=KnowledgeState.cold("prob-axioms"),
            observation=Observation(0.8, 0.8, 0.8),
            required_depth=Depth.WORKING,
        )
        assert update.retention == 1.0

    def test_repeated_strong_sessions_converge_upward(self):
        state = KnowledgeState.cold("prob-axioms")
        mean = 0.0
        values = []
        for _ in range(6):
            update = apply_session(
                state=state,
                observation=Observation(0.95, 0.95, 0.95),
                required_depth=Depth.WORKING,
                previous_running_mean=mean,
            )
            values.append(update.intrinsic_mastery)
            mean = update.running_mean
            state = state.replace(
                intrinsic_mastery=update.intrinsic_mastery,
                session_count=update.session_count,
                stability=update.stability,
                difficulty=update.difficulty,
                assessment_variance_raw=update.variance_raw,
            )
        assert values == sorted(values), "consistent strong evidence must not oscillate"
        assert values[-1] > 0.8

    def test_llm_confidence_cannot_dominate_an_update(self):
        """§4 caps llm_confidence at 20% of evidence weight."""
        state = KnowledgeState.cold("prob-axioms")
        weak_observation = Observation(0.1, 0.1, 0.1, llm_confidence=0.0)
        same_but_llm_certain = Observation(0.1, 0.1, 0.1, llm_confidence=1.0)

        a = apply_session(state=state, observation=weak_observation, required_depth=Depth.DEEP)
        b = apply_session(
            state=state, observation=same_but_llm_certain, required_depth=Depth.DEEP
        )
        assert b.intrinsic_mastery - a.intrinsic_mastery < 0.05, (
            "a confident LLM must not turn weak evidence into high mastery"
        )

    def test_stability_grows_with_mastery(self):
        weak = apply_session(
            state=KnowledgeState.cold("x"),
            observation=Observation(0.2, 0.2, 0.2),
            required_depth=Depth.WORKING,
        )
        strong = apply_session(
            state=KnowledgeState.cold("x"),
            observation=Observation(0.95, 0.95, 0.95),
            required_depth=Depth.WORKING,
        )
        assert strong.stability > weak.stability


class TestPropagationOnRealGraph:
    def test_improving_a_root_lifts_its_descendants(self, curriculum, cold_states):
        """The payoff of propagation, on a real multi-hop chain."""
        before = recompute(curriculum, cold_states)

        states = dict(cold_states)
        for node_id in ("prob-axioms", "prob-conditional", "prob-counting"):
            states[node_id] = KnowledgeState.cold(node_id).replace(
                intrinsic_mastery=0.95, session_count=3, stability=30.0
            )
        after = recompute(curriculum, states)

        assert after.effective_mastery["prob-bayes"] >= before.effective_mastery["prob-bayes"]
        assert (
            after.prerequisite_confidence["prob-bayes"]
            > before.prerequisite_confidence["prob-bayes"]
        )

    def test_decay_lowers_effective_but_never_intrinsic(self, curriculum):
        """The governing invariant, on the real graph rather than the 3-node chain."""
        states = {
            n.node_id: KnowledgeState.cold(n.node_id).replace(
                intrinsic_mastery=0.9, session_count=3, stability=10.0
            )
            for n in curriculum
        }
        fresh = recompute(curriculum, states, days_elapsed=dict.fromkeys(states, 0.0))
        stale = recompute(curriculum, states, days_elapsed=dict.fromkeys(states, 120.0))

        for node_id in states:
            assert stale.effective_mastery[node_id] < fresh.effective_mastery[node_id]
            assert states[node_id].intrinsic_mastery == 0.9, "M must be untouched"

    def test_readiness_reports_a_bottleneck(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        for readiness in snapshot.readiness.values():
            if readiness.node_count:
                assert readiness.is_explainable, "every readiness value must name its blocker"
                assert readiness.bottleneck_node_id in curriculum


class TestRecommendations:
    def test_recommends_only_learnable_nodes(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        picks = recommend(curriculum, snapshot, limit=5)
        for pick in picks:
            confidence = snapshot.prerequisite_confidence[pick.node_id]
            assert confidence >= 0.7 or snapshot.critical_path_value[pick.node_id] >= 0.7

    def test_respects_the_limit(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        assert len(recommend(curriculum, snapshot, limit=3)) <= 3

    def test_is_deterministic(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        first = [c.node_id for c in recommend(curriculum, snapshot, limit=5)]
        second = [c.node_id for c in recommend(curriculum, snapshot, limit=5)]
        assert first == second

    def test_never_recommends_an_already_sufficient_node(self, curriculum):
        states = {
            n.node_id: KnowledgeState.cold(n.node_id).replace(
                intrinsic_mastery=1.0, session_count=5, stability=1000.0
            )
            for n in curriculum
        }
        snapshot = recompute(curriculum, states)
        assert recommend(curriculum, snapshot, limit=5) == (), (
            "a fully-mastered graph has nothing worth recommending"
        )

    def test_mmr_diversifies_away_from_one_competency(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        picks = recommend(curriculum, snapshot, limit=5)
        # previously guarded by `if len(picks) >= 3`, which passed silently whenever the
        # fixture produced fewer — i.e. exactly when the guarantee was worth checking
        assert len(picks) >= 3, "the fixture must yield enough candidates to diversify"
        competencies = {
            (curriculum.node(p.node_id).section, curriculum.node(p.node_id).competency)
            for p in picks
        }
        assert len(competencies) > 1, "MMR must not return five clones"


class TestRecommendationLens:
    """Role and section lenses, applied before scoring rather than after.

    The router used to over-fetch `limit * 4` unfiltered picks and filter them down. That ranks
    and MMR-diversifies a set it is about to discard, so the diversity guarantee landed on the
    wrong list and the endpoint could silently return fewer than `limit` — or nothing — when a
    lens's eligible nodes all ranked below the over-fetch window.
    """

    def eligible(self, curriculum, snapshot, node_ids):
        """The candidate set — frontier ∪ high-CPV — restricted to `node_ids`."""
        candidates = {n for n, on in snapshot.frontier.items() if on}
        candidates |= {
            n
            for n, cpv in snapshot.critical_path_value.items()
            if cpv >= DEFAULT_CONFIG.high_cpv_threshold
            and snapshot.effective_mastery[n] < snapshot.targets[n]
        }
        return candidates & set(node_ids)

    def test_role_lens_returns_only_that_role_s_nodes(self, curriculum, cold_states):
        for role in curriculum.roles:
            snapshot = recompute(curriculum, cold_states, active_role_id=role.role_id)
            picks = recommend(curriculum, snapshot, limit=5, role_id=role.role_id)
            allowed = {n.node_id for n in curriculum.nodes_by_role(role.role_id)}
            assert {p.node_id for p in picks} <= allowed

    def test_section_lens_returns_only_that_section_s_nodes(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        for section in {n.section for n in curriculum}:
            picks = recommend(curriculum, snapshot, limit=5, section=section)
            assert all(curriculum.node(p.node_id).section == section for p in picks)

    def test_a_lens_never_silently_under_returns(self, curriculum, cold_states):
        """Exactly min(limit, eligible) — the guarantee post-filtering could not make."""
        snapshot = recompute(curriculum, cold_states)
        for section in {n.section for n in curriculum}:
            in_section = [n.node_id for n in curriculum.nodes_by_section(section)]
            expected = min(3, len(self.eligible(curriculum, snapshot, in_section)))
            picks = recommend(curriculum, snapshot, limit=3, section=section)
            assert len(picks) == expected, section

    def test_lenses_intersect(self, curriculum, cold_states):
        role = curriculum.roles[0].role_id
        snapshot = recompute(curriculum, cold_states, active_role_id=role)
        sections = {n.section for n in curriculum.nodes_by_role(role)}
        for section in sections:
            picks = recommend(
                curriculum, snapshot, limit=5, role_id=role, section=section
            )
            for pick in picks:
                node = curriculum.node(pick.node_id)
                assert node.section == section
                assert node.requirement_for(role) is not None

    def test_an_empty_lens_returns_nothing_rather_than_falling_back(
        self, curriculum, cold_states
    ):
        snapshot = recompute(curriculum, cold_states)
        assert recommend(curriculum, snapshot, limit=5, section="no-such-section") == ()

    def test_diversification_runs_on_the_filtered_set(self, curriculum, cold_states):
        """MMR must see only eligible candidates, or it diversifies against the wrong list."""
        snapshot = recompute(curriculum, cold_states)
        for role in curriculum.roles:
            picks = recommend(curriculum, snapshot, limit=5, role_id=role.role_id)
            if len(picks) >= 3:
                competencies = {
                    (curriculum.node(p.node_id).section, curriculum.node(p.node_id).competency)
                    for p in picks
                }
                assert len(competencies) > 1, role.role_id

    def test_lensed_results_are_deterministic(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        role = curriculum.roles[0].role_id
        first = [c.node_id for c in recommend(curriculum, snapshot, limit=5, role_id=role)]
        second = [c.node_id for c in recommend(curriculum, snapshot, limit=5, role_id=role)]
        assert first == second


class TestRecommendationReasons:
    """Explanation factors come off the engine, not from re-deriving in the API layer."""

    def test_every_pick_carries_its_reason_factors(self, curriculum, cold_states):
        snapshot = recompute(curriculum, cold_states)
        picks = recommend(curriculum, snapshot, limit=5)
        assert picks
        for pick in picks:
            assert pick.unlocks == len(curriculum.descendants(pick.node_id))
            assert pick.is_frontier == snapshot.frontier[pick.node_id]
            assert pick.blocking_roles == tuple(
                sorted(
                    role_id
                    for role_id, readiness in snapshot.readiness.items()
                    if readiness.bottleneck_node_id == pick.node_id
                )
            )

    def test_blocking_roles_are_populated_when_a_pick_is_a_bottleneck(
        self, curriculum, cold_states
    ):
        snapshot = recompute(curriculum, cold_states)
        bottlenecks = {
            r.bottleneck_node_id for r in snapshot.readiness.values() if r.bottleneck_node_id
        }
        picks = recommend(curriculum, snapshot, limit=len(curriculum))
        flagged = {p.node_id for p in picks if p.blocking_roles}
        assert flagged == {p.node_id for p in picks} & bottlenecks

    def test_reason_factors_survive_a_lens(self, curriculum, cold_states):
        role = curriculum.roles[0].role_id
        snapshot = recompute(curriculum, cold_states, active_role_id=role)
        for pick in recommend(curriculum, snapshot, limit=5, role_id=role):
            assert pick.unlocks == len(curriculum.descendants(pick.node_id))
