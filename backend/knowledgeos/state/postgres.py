"""Postgres-backed implementations of the Layer 2 repository protocols.

Drop-in replacements for the in-memory repositories: the overlay, the engine, and the
assessment service are all written against the protocols and cannot tell which one they have.

Append-only is enforced here rather than merely intended. `append()` refuses to overwrite an
existing session, and there is deliberately no update or delete method — recalculation is meant
to be reproducible by replaying history, which is only true if history cannot be rewritten.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .errors import DocumentNotFoundError, DuplicateSessionError, UnknownNodeError
from .models import DocumentRecord, KnowledgeState, SessionRecord
from .tables import document_plans, knowledge_state, session_history


class PostgresKnowledgeStateRepository:
    """C.5 storage. Upsert-on-save, because state is a value keyed by node."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, node_id: str) -> KnowledgeState | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(knowledge_state).where(knowledge_state.c.node_id == node_id)
            ).mappings().first()
        return _to_state(row) if row else None

    def require(self, node_id: str) -> KnowledgeState:
        state = self.get(node_id)
        if state is None:
            raise UnknownNodeError(node_id)
        return state

    def save(self, state: KnowledgeState) -> None:
        self.save_many((state,))

    def save_many(self, states: Iterable[KnowledgeState]) -> None:
        rows = [_to_row(state) for state in states]
        if not rows:
            return
        statement = pg_insert(knowledge_state).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[knowledge_state.c.node_id],
            set_={
                column.name: statement.excluded[column.name]
                for column in knowledge_state.columns
                if column.name != "node_id"
            },
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def all(self) -> tuple[KnowledgeState, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(knowledge_state).order_by(knowledge_state.c.node_id)
            ).mappings().all()
        return tuple(_to_state(row) for row in rows)

    def clear(self) -> None:
        """Test-support only. Not part of the protocol."""
        with self._engine.begin() as connection:
            connection.execute(delete(session_history))
            connection.execute(delete(knowledge_state))


class PostgresSessionHistoryRepository:
    """C.6 storage. Append-only, enforced.

    Ordering is by `created_at` then `session_id`, so replay is deterministic even when two
    sessions share a timestamp — without the tiebreak, Postgres could return them in either
    order and a replay would not be reproducible.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(self, record: SessionRecord) -> None:
        if self.get(record.session_id) is not None:
            raise DuplicateSessionError(record.session_id)
        with self._engine.begin() as connection:
            connection.execute(insert(session_history).values(_record_to_row(record)))

    def get(self, session_id: UUID) -> SessionRecord | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(session_history).where(session_history.c.session_id == session_id)
            ).mappings().first()
        return _to_record(row) if row else None

    def for_node(self, node_id: str) -> tuple[SessionRecord, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(session_history)
                .where(session_history.c.node_id == node_id)
                .order_by(session_history.c.created_at, session_history.c.session_id)
            ).mappings().all()
        return tuple(_to_record(row) for row in rows)

    def all(self) -> tuple[SessionRecord, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(session_history).order_by(
                    session_history.c.created_at, session_history.c.session_id
                )
            ).mappings().all()
        return tuple(_to_record(row) for row in rows)

    def __len__(self) -> int:
        with self._engine.connect() as connection:
            return connection.execute(
                select(session_history.c.session_id)
            ).rowcount or len(self.all())


class PostgresDocumentRepository:
    """Saved document prep records. Upsert-on-save, keyed by document_id."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, record: DocumentRecord) -> None:
        row = _document_to_row(record)
        statement = pg_insert(document_plans).values(row)
        statement = statement.on_conflict_do_update(
            index_elements=[document_plans.c.document_id],
            set_={k: statement.excluded[k] for k in row if k != "document_id"},
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def get(self, document_id: UUID) -> DocumentRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(document_plans).where(document_plans.c.document_id == document_id)
                )
                .mappings()
                .first()
            )
        return _to_document(row) if row else None

    def all(self) -> tuple[DocumentRecord, ...]:
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    select(document_plans).order_by(
                        document_plans.c.created_at.desc(),
                        document_plans.c.document_id.desc(),
                    )
                )
                .mappings()
                .all()
            )
        return tuple(_to_document(row) for row in rows)

    def delete(self, document_id: UUID) -> None:
        with self._engine.begin() as connection:
            result = connection.execute(
                delete(document_plans).where(document_plans.c.document_id == document_id)
            )
        if result.rowcount == 0:
            raise DocumentNotFoundError(document_id)

    def clear(self) -> None:
        with self._engine.begin() as connection:
            connection.execute(delete(document_plans))

    def __len__(self) -> int:
        return len(self.all())


# ------------------------------------------------------------------ mapping


def _to_row(state: KnowledgeState) -> dict:
    data = state.model_dump()
    data["last_gaps"] = list(state.last_gaps)
    return data


def _to_state(row) -> KnowledgeState:
    data = dict(row)
    data["last_gaps"] = tuple(data.get("last_gaps") or ())
    return KnowledgeState.model_validate(data)


def _record_to_row(record: SessionRecord) -> dict:
    return record.model_dump(mode="json") | {
        "session_id": record.session_id,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
    }


def _to_record(row) -> SessionRecord:
    return SessionRecord.model_validate(dict(row))


def _document_to_row(record: DocumentRecord) -> dict:
    return record.model_dump(mode="json") | {
        "document_id": record.document_id,
        "created_at": record.created_at,
    }


def _to_document(row) -> DocumentRecord:
    return DocumentRecord.model_validate(dict(row))

