"""Layer 2 model contracts (BUILD_SPEC.md C.5, C.6)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from knowledgeos.state import KnowledgeState, SessionRecord, Status


class TestColdDefaults:
    """Stage 2 success criterion: cold defaults are correct."""

    def test_cold_node_has_no_evidence(self):
        state = KnowledgeState.cold("prob-bayes")
        assert state.node_id == "prob-bayes"
        assert state.intrinsic_mastery == 0.0
        assert state.status is Status.UNASSESSED
        assert state.session_count == 0
        assert not state.is_assessed

    def test_cold_node_has_no_forgetting_curve_yet(self):
        state = KnowledgeState.cold("prob-bayes")
        assert state.stability is None, "stability is undefined before the first session"
        assert state.difficulty is None, "difficulty is assigned by depth tier at Stage 3"
        assert state.last_assessed_at is None
        assert state.next_review_at is None

    def test_cold_node_has_no_derived_position(self):
        state = KnowledgeState.cold("prob-bayes")
        assert state.effective_mastery == 0.0
        assert state.retention == 0.0
        assert state.engine_confidence == 0.0
        assert state.assessment_variance == 0.0
        assert state.is_frontier is False
        assert state.critical_path_value == 0.0
        assert state.leverage == 0.0
        assert state.current_importance == 0.0
        assert state.learning_cost == 0.0
        assert state.last_gaps == ()

    def test_bare_construction_matches_cold(self):
        assert KnowledgeState(node_id="x") == KnowledgeState.cold("x")


class TestStateIsImmutable:
    """State changes by producing a new value, never by mutating one in place."""

    def test_cannot_assign(self):
        state = KnowledgeState.cold("x")
        with pytest.raises(ValidationError):
            state.intrinsic_mastery = 0.9

    def test_replace_returns_a_new_value_and_leaves_the_original_alone(self):
        original = KnowledgeState.cold("x")
        updated = original.replace(intrinsic_mastery=0.7, session_count=1)
        assert updated.intrinsic_mastery == 0.7
        assert updated.session_count == 1
        assert original.intrinsic_mastery == 0.0, "the original must be untouched"
        assert updated is not original

    def test_unknown_field_is_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeState(node_id="x", mastery=0.5)  # not a real field


class TestStateFieldRanges:
    @pytest.mark.parametrize(
        "field",
        [
            "intrinsic_mastery",
            "effective_mastery",
            "retention",
            "assessment_variance",
            "engine_confidence",
        ],
    )
    @pytest.mark.parametrize("bad", [-0.01, 1.01])
    def test_scores_are_bounded(self, field, bad):
        with pytest.raises(ValidationError):
            KnowledgeState(node_id="x", **{field: bad})

    def test_session_count_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            KnowledgeState(node_id="x", session_count=-1)

    def test_stability_must_be_positive_when_set(self):
        with pytest.raises(ValidationError):
            KnowledgeState(node_id="x", stability=0.0)
        assert KnowledgeState(node_id="x", stability=1.0).stability == 1.0

    def test_current_importance_may_exceed_one(self):
        """CALC_ENGINE_SPEC.md §10 multiplies importance by date and bottleneck factors."""
        assert KnowledgeState(node_id="x", current_importance=1.8).current_importance == 1.8

    def test_learning_cost_is_hours_not_a_score(self):
        assert KnowledgeState(node_id="x", learning_cost=8.0).learning_cost == 8.0

    def test_status_must_be_on_the_ladder(self):
        with pytest.raises(ValidationError):
            KnowledgeState(node_id="x", status="pretty-good")


class TestSessionRecord:
    def _record(self, **overrides):
        base = {
            "session_id": uuid4(),
            "node_id": "prob-bayes",
            "role_context": "ai-research",
            "created_at": datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        }
        return SessionRecord(**{**base, **overrides})

    def test_open_session_is_not_complete(self):
        record = self._record()
        assert not record.is_complete
        assert record.schema_b is None
        assert record.completed_at is None

    def test_session_is_complete_once_schema_b_is_ingested(self):
        record = self._record(
            schema_b={"observations": {"recall": 0.7}},
            completed_at=datetime(2026, 8, 1, 12, 45, tzinfo=UTC),
        )
        assert record.is_complete

    def test_schema_b_without_completion_time_is_not_complete(self):
        assert not self._record(schema_b={"x": 1}).is_complete

    def test_payloads_are_stored_verbatim(self):
        """Layer 2 keeps the evidence whole; Stage 4 owns validating its shape."""
        payload = {"observations": {"recall": 0.7, "depth": 0.45}, "gaps_identified": ["x"]}
        assert self._record(schema_b=payload).schema_b == payload

    def test_records_are_immutable(self):
        record = self._record()
        with pytest.raises(ValidationError):
            record.node_id = "something-else"

    def test_mastery_snapshots_bound_the_update(self):
        record = self._record(mastery_before=0.2, mastery_after=0.55)
        assert record.mastery_before == 0.2
        assert record.mastery_after == 0.55
