"""Postgres-backed implementation of `PendingSessionStore`.

The other half of the seam whose in-memory implementation lives in `service.py`. Both halves
are needed for the seam to be real: the fast one for tests, the durable one for anything that
can be restarted.

Durability is not a nicety here. The two halves of a session are separated by a copy-paste into
another tool, so an open session routinely outlives a deploy — and a Schema A that vanishes
takes the assessment with it, leaving no history record that it ever happened. Every other
durable fact in the system is in Postgres; this one belongs there too.

It lives in Layer 4 rather than alongside the Layer 2 repositories because it stores a
`SchemaA`, which is an assessment contract. Layer 2 may not import it.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Engine, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from knowledgeos.state.tables import pending_sessions

from .schemas import SchemaA


class PostgresPendingSessionStore:
    """Open Schema A payloads, keyed by session id.

    Upsert-on-open rather than insert, so regenerating a Schema A for a session id that is
    already open replaces it instead of failing. Re-opening is a legitimate thing to do — the
    learner lost the paste and asked for it again — and the payload is rebuilt from the same
    state, so the two are equivalent anyway.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def open(self, schema_a: SchemaA) -> None:
        row = {
            "session_id": schema_a.session_id,
            "node_id": schema_a.target.node_id,
            "created_at": schema_a.generated_at,
            "schema_a": schema_a.to_payload(),
            "schema_version": schema_a.schema_version,
        }
        statement = pg_insert(pending_sessions).values(row)
        statement = statement.on_conflict_do_update(
            index_elements=[pending_sessions.c.session_id],
            set_={k: statement.excluded[k] for k in row if k != "session_id"},
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def take(self, session_id: UUID) -> SchemaA | None:
        """Retrieve and remove in one statement.

        `DELETE ... RETURNING` rather than a read followed by a delete: a session is ingested
        exactly once, and two concurrent ingests of the same paste must not both see the row
        and both apply the evidence.
        """
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    delete(pending_sessions)
                    .where(pending_sessions.c.session_id == session_id)
                    .returning(pending_sessions.c.schema_a)
                )
                .mappings()
                .first()
            )
        return _to_schema_a(row) if row else None

    def peek(self, session_id: UUID) -> SchemaA | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(pending_sessions.c.schema_a).where(
                        pending_sessions.c.session_id == session_id
                    )
                )
                .mappings()
                .first()
            )
        return _to_schema_a(row) if row else None

    def all(self) -> tuple[SchemaA, ...]:
        """Every open session, ordered by session id.

        By id rather than by `created_at` to match the in-memory store exactly — the parity
        test is only worth anything if the two agree on order as well as on content.
        """
        with self._engine.connect() as connection:
            rows = (
                connection.execute(
                    select(pending_sessions.c.schema_a).order_by(
                        pending_sessions.c.session_id
                    )
                )
                .mappings()
                .all()
            )
        return tuple(_to_schema_a(row) for row in rows)

    def clear(self) -> None:
        """Test-support only. Not part of the protocol."""
        with self._engine.begin() as connection:
            connection.execute(delete(pending_sessions))

    def __len__(self) -> int:
        return len(self.all())


def _to_schema_a(row) -> SchemaA:
    """Rebuild from the stored payload.

    Validated on the way out rather than trusted: the payload is the wire contract, and a
    Schema A that no longer parses is a schema-version problem worth failing loudly on, not
    something to hand to the external engine and hope.
    """
    return SchemaA.model_validate(row["schema_a"])
