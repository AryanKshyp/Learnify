"""Overlay behaviour (BUILD_SPEC.md Stage 2).

Covers the success criteria: attach/read state for any node, cold defaults, and — the one
worth guarding hardest — that state never mutates the curriculum.

The overlay deliberately has no lenses (`for_role`, `for_section`, `assessed`, `unassessed`,
`get`, `with_status`). They were one-line filters over `all()` with no caller but these tests,
and their removal is why this file no longer has a `TestLenses`. Slicing is the curriculum's
job and ranking is the engine's; what is tested here is the join and the two rules guarding it.
"""

from __future__ import annotations

import pytest

from knowledgeos.curriculum import fixture_repository
from knowledgeos.state import (
    InMemoryKnowledgeStateRepository,
    KnowledgeState,
    StateOverlay,
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
            intrinsic_mastery=0.8, session_count=2
        )
        overlay.save(saved)
        assert overlay.state_for("prob-bayes") == saved

    def test_all_pairs_each_node_with_its_state(self, overlay):
        pair = next(i for i in overlay.all() if i.node_id == "prob-bayes")
        assert pair.node.name == "Bayes' Theorem"
        assert pair.state.node_id == "prob-bayes"
        assert not pair.is_assessed

    def test_the_interface_is_three_methods(self, overlay):
        """The lenses were wider than the rules they sat on. Pinned so they do not creep back."""
        public = {name for name in dir(overlay) if not name.startswith("_")}
        assert public == {"state_for", "all", "save"}


class TestCurriculumIsNeverMutated:
    """Stage 2 success criterion, and a Layer 1/2 boundary rule."""

    def test_saving_state_does_not_change_the_curriculum(self, curriculum):
        overlay = StateOverlay(curriculum, InMemoryKnowledgeStateRepository())
        before = {n.node_id: n.model_dump() for n in curriculum}

        for node in curriculum:
            overlay.save(
                KnowledgeState.cold(node.node_id).replace(
                    intrinsic_mastery=0.9, session_count=3
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
