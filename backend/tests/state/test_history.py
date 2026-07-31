"""Append-only session history and replay ordering (BUILD_SPEC.md C.6, Stage 2).

Stage 2 success criterion: append several history records and reconstruct state ordering.
Replay is what makes every score reproducible from stored evidence (A.5.6), so ordering has
to be stable even when timestamps collide.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import uuid4

import pytest

from knowledgeos.state import (
    DuplicateSessionError,
    InMemorySessionHistoryRepository,
    SessionNotFoundError,
    SessionRecord,
)

T0 = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def record(node_id="prob-bayes", *, minutes=0, before=0.0, after=0.0, session_id=None):
    return SessionRecord(
        session_id=session_id or uuid4(),
        node_id=node_id,
        role_context="ai-research",
        created_at=T0 + timedelta(minutes=minutes),
        completed_at=T0 + timedelta(minutes=minutes + 30),
        schema_b={"observations": {"recall": after}},
        mastery_before=before,
        mastery_after=after,
    )


@pytest.fixture
def history():
    return InMemorySessionHistoryRepository()


class TestAppendOnly:
    def test_append_and_read_back(self, history):
        r = record()
        history.append(r)
        assert history.get(r.session_id) == r
        assert len(history) == 1

    def test_duplicate_session_id_is_refused(self, history):
        sid = uuid4()
        history.append(record(session_id=sid))
        with pytest.raises(DuplicateSessionError, match=str(sid)):
            history.append(record(session_id=sid, after=0.9))

    def test_a_refused_duplicate_does_not_corrupt_history(self, history):
        sid = uuid4()
        history.append(record(session_id=sid, after=0.3))
        with pytest.raises(DuplicateSessionError):
            history.append(record(session_id=sid, after=0.9))
        assert len(history) == 1
        assert history.get(sid).mastery_after == 0.3, "the original must survive"

    def test_there_is_no_update_or_delete(self, history):
        """Append-only is enforced by the interface having no way to do anything else."""
        for forbidden in ("update", "delete", "remove", "replace", "clear"):
            assert not hasattr(history, forbidden)

    def test_missing_session_returns_none(self, history):
        assert history.get(uuid4()) is None

    def test_require_raises_for_a_missing_session(self, history):
        with pytest.raises(SessionNotFoundError):
            history.require(uuid4())


class TestOrdering:
    def test_records_come_back_oldest_first(self, history):
        rs = [record(minutes=m) for m in (0, 10, 20)]
        for r in rs:
            history.append(r)
        assert [r.session_id for r in history.all()] == [r.session_id for r in rs]

    def test_identical_timestamps_keep_arrival_order(self, history):
        """created_at can tie; replay still needs one deterministic order."""
        a, b, c = (record(minutes=0, after=x) for x in (0.1, 0.2, 0.3))
        for r in (a, b, c):
            history.append(r)
        assert [r.mastery_after for r in history.all()] == [0.1, 0.2, 0.3]

    def test_ordering_is_stable_across_reads(self, history):
        for m in range(5):
            history.append(record(minutes=m))
        assert history.all() == history.all()

    def test_for_node_filters_and_preserves_order(self, history):
        history.append(record("prob-bayes", minutes=0, after=0.3))
        history.append(record("dl-attention", minutes=5, after=0.4))
        history.append(record("prob-bayes", minutes=10, after=0.6))
        bayes = history.for_node("prob-bayes")
        assert len(bayes) == 2
        assert [r.mastery_after for r in bayes] == [0.3, 0.6]

    def test_for_node_with_no_sessions_is_empty(self, history):
        assert history.for_node("prob-axioms") == ()

    def test_construction_from_existing_records_preserves_order(self):
        rs = [record(minutes=m) for m in (0, 5, 10)]
        assert InMemorySessionHistoryRepository(rs).all() == tuple(rs)


class TestReplay:
    """Reconstructing the evidence trail — the basis of A.5.6 explainability."""

    def test_mastery_progression_is_recoverable_from_history(self, history):
        for i, value in enumerate([0.30, 0.55, 0.72]):
            previous = 0.0 if i == 0 else [0.30, 0.55, 0.72][i - 1]
            history.append(record(minutes=i * 60, before=previous, after=value))

        trail = history.for_node("prob-bayes")
        assert [r.mastery_after for r in trail] == [0.30, 0.55, 0.72]

        # each record's "before" must equal the previous record's "after"
        for earlier, later in pairwise(trail):
            assert later.mastery_before == earlier.mastery_after

    def test_session_count_is_recoverable_by_replay(self, history):
        for m in range(4):
            history.append(record(minutes=m * 10))
        history.append(record("dl-attention", minutes=99))
        assert len(history.for_node("prob-bayes")) == 4

    def test_replaying_a_subset_by_node_covers_the_whole_history(self, history):
        for node in ("prob-bayes", "dl-attention", "prob-axioms"):
            history.append(record(node))
        nodes = ("prob-bayes", "dl-attention", "prob-axioms")
        by_node = sum(len(history.for_node(n)) for n in nodes)
        assert by_node == len(history.all())
