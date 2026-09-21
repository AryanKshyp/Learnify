"""ASGI entrypoint.

    uvicorn knowledgeos.api.main:app --reload

Wires Postgres when DATABASE_URL points at a reachable database, and falls back to in-memory
storage otherwise so the API can be demonstrated without infrastructure. The fallback is loud —
silently losing every assessment on restart would be far worse than refusing to start.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa

from knowledgeos.assessment import PostgresPendingSessionStore
from knowledgeos.config import settings
from knowledgeos.state import (
    PostgresDocumentRepository,
    PostgresKnowledgeStateRepository,
    PostgresSessionHistoryRepository,
)

from .app import create_app

logger = logging.getLogger(__name__)


#: The fallback below is only useful if it is quick. Without an explicit timeout the probe
#: waits on the OS default — minutes, with nothing in the log — so a machine with Docker
#: stopped looks like a hung startup rather than the documented fallback.
STARTUP_PROBE_TIMEOUT_SECONDS = 3


def _build():
    try:
        engine = sa.create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": STARTUP_PROBE_TIMEOUT_SECONDS},
        )
        with engine.connect() as connection:
            connection.execute(sa.text("select 1"))
    except Exception as exc:
        logger.warning(
            "Postgres unreachable (%s: %s) - falling back to IN-MEMORY storage. "
            "Assessments will NOT survive a restart. Run `docker compose up -d` and "
            "`alembic upgrade head` to persist.",
            type(exc).__name__,
            exc,
        )
        return create_app()

    logger.info("using Postgres at %s", engine.url.render_as_string(hide_password=True))
    return create_app(
        states=PostgresKnowledgeStateRepository(engine),
        history=PostgresSessionHistoryRepository(engine),
        pending=PostgresPendingSessionStore(engine),
        documents_repo=PostgresDocumentRepository(engine),
    )


app = _build()
