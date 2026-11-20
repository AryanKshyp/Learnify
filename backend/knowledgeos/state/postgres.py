"""Postgres-backed implementations of the Layer 2 repository protocols.

Drop-in replacements for the in-memory repositories: the overlay, the engine, and the
assessment service are all written against the protocols and cannot tell which one they have.

Append-only is enforced here rather than merely intended. `append()` refuses to overwrite an
existing session, and there is deliberately no update or delete method — recalculation is meant
to be reproducible by replaying history, which is only true if history cannot be rewritten.

Every repository is bound to ONE user at construction and filters every statement by that
user. The contracts carry no `user_id`, so nothing above this layer can name another user's rows
even by mistake: a hosted deployment builds one repository per authenticated request, and
unauthenticated use is simply the user `LOCAL_USER`.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .errors import DocumentNotFoundError, DuplicateSessionError, UnknownNodeError
from .models import DocumentRecord, KnowledgeState, SessionRecord
from .tables import LOCAL_USER, document_plans, knowledge_state, session_history


class PostgresKnowledgeStateRepository:
    """C.5 storage. Upsert-on-save, because state is a value keyed by node."""

    def __init__(self, engine: Engine, user_id: str = LOCAL_USER) -> None:
        self._engine = engine
        self._user = user_id

    def get(self, node_id: str) -> KnowledgeState | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(knowledge_state).where(
                    knowledge_state.c.user_id == self._user,
                    knowledge_state.c.node_id == node_id,
                )
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
        rows = [_to_row(state) | {"user_id": self._user} for state in states]
        if not rows:
            return
        statement = pg_insert(knowledge_state).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[knowledge_state.c.user_id, knowledge_state.c.node_id],
            set_={
                column.name: statement.excluded[column.name]
                for column in knowledge_state.columns
                if column.name not in ("user_id", "node_id")
            },
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def all(self) -> tuple[KnowledgeState, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(knowledge_state)
                .where(knowledge_state.c.user_id == self._user)
                .order_by(knowledge_state.c.node_id)
            ).mappings().all()
        return tuple(_to_state(row) for row in rows)

    def clear(self) -> None:
        """Wipe THIS user's state and history. Test support and the account-reset endpoint."""
        with self._engine.begin() as connection:
            connection.execute(
                delete(session_history).where(session_history.c.user_id == self._user)
            )
            connection.execute(
                delete(knowledge_state).where(knowledge_state.c.user_id == self._user)
            )


class PostgresSessionHistoryRepository:
    """C.6 storage. Append-only, enforced.

    Ordering is by `created_at` then `session_id`, so replay is deterministic even when two
    sessions share a timestamp — without the tiebreak, Postgres could return them in either
    order and a replay would not be reproducible.
    """

    def __init__(self, engine: Engine, user_id: str = LOCAL_USER) -> None:
        self._engine = engine
        self._user = user_id

    def append(self, record: SessionRecord) -> None:
        # Existence is checked across ALL users: session ids are globally unique primary keys,
        # so another user's id must be reported as a duplicate rather than a database error.
        with self._engine.connect() as connection:
            taken = connection.execute(
                select(session_history.c.session_id).where(
                    session_history.c.session_id == record.session_id
                )
            ).first()
        if taken is not None:
            raise DuplicateSessionError(record.session_id)
        with self._engine.begin() as connection:
            connection.execute(
                insert(session_history).values(_record_to_row(record) | {"user_id": self._user})
            )

    def get(self, session_id: UUID) -> SessionRecord | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(session_history).where(
                    session_history.c.user_id == self._user,
                    session_history.c.session_id == session_id,
                )
            ).mappings().first()
        return _to_record(row) if row else None

    def for_node(self, node_id: str) -> tuple[SessionRecord, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(session_history)
                .where(
                    session_history.c.user_id == self._user,
                    session_history.c.node_id == node_id,
                )
                .order_by(session_history.c.created_at, session_history.c.session_id)
            ).mappings().all()
        return tuple(_to_record(row) for row in rows)

    def all(self) -> tuple[SessionRecord, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(session_history)
                .where(session_history.c.user_id == self._user)
                .order_by(session_history.c.created_at, session_history.c.session_id)
            ).mappings().all()
        return tuple(_to_record(row) for row in rows)

    def __len__(self) -> int:
        with self._engine.connect() as connection:
            return len(
                connection.execute(
                    select(session_history.c.session_id).where(
                        session_history.c.user_id == self._user
                    )
                ).all()
            )


class PostgresDocumentRepository:
    """Saved document prep records. Upsert-on-save, keyed by document_id."""

    def __init__(self, engine: Engine, user_id: str = LOCAL_USER) -> None:
        self._engine = engine
        self._user = user_id

    def save(self, record: DocumentRecord) -> None:
        row = _document_to_row(record) | {"user_id": self._user}
        statement = pg_insert(document_plans).values(row)
        # The update is guarded by the owner: an id that already belongs to someone else is not
        # overwritten, it simply matches no row.
        statement = statement.on_conflict_do_update(
            index_elements=[document_plans.c.document_id],
            set_={k: statement.excluded[k] for k in row if k not in ("document_id", "user_id")},
            where=document_plans.c.user_id == self._user,
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def get(self, document_id: UUID) -> DocumentRecord | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(document_plans).where(
                        document_plans.c.user_id == self._user,
                        document_plans.c.document_id == document_id,
                    )
                )
                .mappings()
                .first()
            )
        return _to_document(row) if row else None

    def all(self) -> tuple[DocumentRecord, ...]:
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    select(document_plans)
                    .where(document_plans.c.user_id == self._user)
                    .order_by(
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
                delete(document_plans).where(
                    document_plans.c.user_id == self._user,
                    document_plans.c.document_id == document_id,
                )
            )
        if result.rowcount == 0:
            raise DocumentNotFoundError(document_id)

    def clear(self) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                delete(document_plans).where(document_plans.c.user_id == self._user)
            )

    def __len__(self) -> int:
        return len(self.all())


# ------------------------------------------------------------------ mapping


def _to_row(state: KnowledgeState) -> dict:
    data = state.model_dump()
    data["last_gaps"] = list(state.last_gaps)
    return data


def _to_state(row) -> KnowledgeState:
    data = dict(row)
    data.pop("user_id", None)
    data["last_gaps"] = tuple(data.get("last_gaps") or ())
    return KnowledgeState.model_validate(data)


def _record_to_row(record: SessionRecord) -> dict:
    return record.model_dump(mode="json") | {
        "session_id": record.session_id,
        "created_at": record.created_at,
        "completed_at": record.completed_at,
    }


def _to_record(row) -> SessionRecord:
    data = dict(row)
    data.pop("user_id", None)
    return SessionRecord.model_validate(data)


def _document_to_row(record: DocumentRecord) -> dict:
    return record.model_dump(mode="json") | {
        "document_id": record.document_id,
        "created_at": record.created_at,
    }


def _to_document(row) -> DocumentRecord:
    data = dict(row)
    data.pop("user_id", None)
    return DocumentRecord.model_validate(data)

