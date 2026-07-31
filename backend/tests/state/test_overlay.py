"""Overlay behaviour (BUILD_SPEC.md Stage 2).

Covers the success criteria: attach/read state for any node, cold defaults, and — the one
worth guarding hardest — that state never mutates the curriculum.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import fixture_repository
from knowledgeos.state import (
    InMemoryKnowledgeStateRepository,
    KnowledgeState,
    StateOverlay,
    Status,
    UnknownNodeError,
)


@pytest.fixture
def curriculum():
    return fixture_repository().get()


@pytest.fixture
def overlay(curriculum):
    return StateOverlay(curriculum, InMemoryKnowledgeStateRepository())


class TestAttachAndRead:
    def test_every_curriculum_node_has_a_state(self, overlay, curriculum):
        assert len(overlay.all()) == len(curriculum)

    def test_unassessed_node_reads_back_cold(self, overlay):
        assert overlay.state_for("prob-bayes") == KnowledgeState.cold("prob-bayes")

    def test_cold_default_is_applied_on_read_not_stored(self, overlay):
        """No rows are pre-seeded, so adding curriculum nodes needs no state migration."""
        overlay.state_for("prob-bayes")
        assert overlay._repository.all() == ()

    def test_saved_state_reads_back(self, overlay):
        saved = KnowledgeState.cold("prob-bayes").replace(
            intrinsic_mastery=0.8, session_count=2, status=Status.PRACTICED
        )
        overlay.save(saved)
        assert overlay.state_for("prob-bayes") == saved

    def test_get_pairs_node_with_state(self, overlay):
        pair = overlay.get("prob-bayes")
        assert pair.node.name == "Bayes' Theorem"
        assert pair.state.node_id == "prob-bayes"
        assert pair.node_id == "prob-bayes"

    def test_importance_comes_from_the_curriculum(self, overlay):
        pair = overlay.get("prob-bayes")
        assert pair.importance_for("ai-research") == 0.92
        assert pair.importance_for("astronaut") == 0.0


class TestCurriculumIsNeverMutated:
    """Stage 2 success criterion, and a Layer 1/2 boundary rule."""

    def test_saving_state_does_not_change_the_curriculum(self, curriculum):
        overlay = StateOverlay(curriculum, InMemoryKnowledgeStateRepository())
        before = {n.node_id: n.model_dump() for n in curriculum}

        for node in curriculum:
            overlay.save(
                KnowledgeState.cold(node.node_id).replace(
                    intrinsic_mastery=0.9, session_count=3, status=Status.MASTERED
                )
            )

        after = {n.node_id: n.model_dump() for n in curriculum}
        assert before == after

    def test_curriculum_graph_topology_is_unchanged_by_state(self, curriculum, overlay):
        edges_before = curriculum.edges
        order_before = curriculum.topological_order()
        overlay.save(KnowledgeState.cold("prob-bayes").replace(intrinsic_mastery=1.0))
        assert curriculum.edges == edges_before
        assert curriculum.topological_order() == order_before

    def test_state_for_an_unknown_node_is_refused(self, overlay):
        with pytest.raises(UnknownNodeError, match="not-a-node"):
            overlay.state_for("not-a-node")

    def test_saving_state_for_an_unknown_node_is_refused(self, overlay):
        with pytest.raises(UnknownNodeError, match="ghost"):
            overlay.save(KnowledgeState.cold("ghost"))

    def test_save_many_validates_every_node_before_writing_any(self, overlay):
        good = KnowledgeState.cold("prob-bayes").replace(intrinsic_mastery=0.5)
        bad = KnowledgeState.cold("ghost")
        with pytest.raises(UnknownNodeError):
            overlay.save_many((good, bad))
        assert overlay.state_for("prob-bayes").intrinsic_mastery == 0.0, (
            "a rejected batch must not partially apply"
        )


class TestLenses:
    def test_for_role_returns_only_nodes_serving_it(self, overlay):
        for item in overlay.for_role("finance-quant"):
            assert item.node.serves_role("finance-quant")

    def test_for_section(self, overlay):
        items = overlay.for_section("probability")
        assert len(items) == 9
        assert all(i.node.section == "probability" for i in items)

    def test_everything_is_unassessed_initially(self, overlay, curriculum):
        assert len(overlay.unassessed()) == len(curriculum)
        assert overlay.assessed() == ()

    def test_assessed_and_unassessed_partition_the_graph(self, overlay, curriculum):
        overlay.save(KnowledgeState.cold("prob-bayes").replace(session_count=1))
        assert len(overlay.assessed()) == 1
        assert len(overlay.unassessed()) == len(curriculum) - 1

    def test_cold_start_queue_never_includes_assessed_nodes(self, overlay):
        """CALC_ENGINE_SPEC.md §12 keeps unexplored nodes separate from assessed-but-weak ones."""
        overlay.save(
            KnowledgeState.cold("prob-bayes").replace(
                session_count=1, intrinsic_mastery=0.05, status=Status.LEARNING
            )
        )
        unassessed_ids = {i.node_id for i in overlay.unassessed()}
        assert "prob-bayes" not in unassessed_ids, (
            "a weak assessed node is not the same as an unexplored one"
        )

    def test_with_status(self, overlay):
        overlay.save(
            KnowledgeState.cold("prob-bayes").replace(
                session_count=2, status=Status.RETAINED
            )
        )
        retained = overlay.with_status(Status.RETAINED)
        assert [i.node_id for i in retained] == ["prob-bayes"]

    def test_iteration_matches_all(self, overlay):
        assert tuple(overlay) == overlay.all()
