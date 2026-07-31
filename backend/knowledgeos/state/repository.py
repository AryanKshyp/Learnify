"""Storage interfaces for Layer 2, and an in-memory implementation.

Two separate protocols, because the two stores have genuinely different rules:

* `KnowledgeStateRepository` is **mutable** — one current record per node, overwritten as
  evidence arrives.
* `SessionHistoryRepository` is **append-only** — records are never updated or deleted, which
  is what makes state reconstructible by replay (C.6).

Splitting them means the append-only guarantee is expressed in the type rather than in a
comment somebody has to remember. A Postgres-backed implementation satisfies the same
protocols without any caller changing.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable
from uuid import UUID

from .errors import DuplicateSessionError, SessionNotFoundError
from .models import KnowledgeState, SessionRecord


@runtime_checkable
class KnowledgeStateRepository(Protocol):
    """Current knowledge state, one record per node."""

    def get(self, node_id: str) -> KnowledgeState | None:
        """Stored state for `node_id`, or None if it has never been written.

        Returns None rather than a cold default so callers can distinguish "no record" from
        "record showing no evidence". `StateOverlay` is what applies the cold default.
        """
        ...

    def save(self, state: KnowledgeState) -> None: ...

    def save_many(self, states: Iterable[KnowledgeState]) -> None: ...

    def all(self) -> tuple[KnowledgeState, ...]: ...


@runtime_checkable
class SessionHistoryRepository(Protocol):
    """Append-only assessment history."""

    def append(self, record: SessionRecord) -> None:
        """Record a session. Raises DuplicateSessionError if the id was already used."""
        ...

    def get(self, session_id: UUID) -> SessionRecord | None: ...

    def for_node(self, node_id: str) -> tuple[SessionRecord, ...]:
        """Every session for a node, oldest first."""
        ...

    def all(self) -> tuple[SessionRecord, ...]:
        """Every session, oldest first."""
        ...


class InMemoryKnowledgeStateRepository:
    """Dict-backed state store.

    Complete and correct for single-process use — the engine and its tests need nothing more.
    """

    def __init__(self, states: Iterable[KnowledgeState] = ()) -> None:
        self._states: dict[str, KnowledgeState] = {s.node_id: s for s in states}

    def get(self, node_id: str) -> KnowledgeState | None:
        return self._states.get(node_id)

    def save(self, state: KnowledgeState) -> None:
        self._states[state.node_id] = state

    def save_many(self, states: Iterable[KnowledgeState]) -> None:
        for state in states:
            self.save(state)

    def all(self) -> tuple[KnowledgeState, ...]:
        return tuple(self._states[key] for key in sorted(self._states))

    def clear(self) -> None:
        self._states.clear()


class InMemorySessionHistoryRepository:
    """List-backed append-only history.

    Insertion order is preserved and treated as authoritative: `created_at` can tie (two
    sessions generated in the same clock tick), so ordering by timestamp alone would be
    non-deterministic. Replay depends on a stable order, so arrival order breaks the tie.
    """

    def __init__(self, records: Iterable[SessionRecord] = ()) -> None:
        self._records: list[SessionRecord] = []
        self._by_id: dict[UUID, int] = {}
        for record in records:
            self.append(record)

    def append(self, record: SessionRecord) -> None:
        if record.session_id in self._by_id:
            raise DuplicateSessionError(record.session_id)
        self._by_id[record.session_id] = len(self._records)
        self._records.append(record)

    def get(self, session_id: UUID) -> SessionRecord | None:
        index = self._by_id.get(session_id)
        return None if index is None else self._records[index]

    def require(self, session_id: UUID) -> SessionRecord:
        record = self.get(session_id)
        if record is None:
            raise SessionNotFoundError(session_id)
        return record

    def for_node(self, node_id: str) -> tuple[SessionRecord, ...]:
        return tuple(r for r in self._records if r.node_id == node_id)

    def all(self) -> tuple[SessionRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)
