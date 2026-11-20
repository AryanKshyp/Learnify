"""ASGI entrypoint.

    uvicorn knowledgeos.api.main:app --reload

Wires Postgres when DATABASE_URL points at a reachable database, and falls back to in-memory
storage otherwise so the API can be demonstrated without infrastructure. The fallback is loud —
silently losing every assessment on restart would be far worse than refusing to start.

Hosted deployments set SUPABASE_URL (or SUPABASE_JWT_SECRET), which turns on accounts: every
request must carry a valid Supabase access token and each user gets repositories scoped to
their own id. In production (ENVIRONMENT=production) the server refuses to start unless
accounts, a reachable database and an encryption key are all configured - there is no way to
come up serving one shared account to the public.
"""

from __future__ import annotations

import logging
from pathlib import Path

import sqlalchemy as sa

from knowledgeos.assessment import AssessmentService, PostgresPendingSessionStore
from knowledgeos.config import settings
from knowledgeos.curriculum import DEFAULT_CURRICULUM_PATH, JsonCurriculumRepository
from knowledgeos.documents import DocumentService
from knowledgeos.llm import Vault
from knowledgeos.state import (
    PostgresDocumentRepository,
    PostgresKnowledgeStateRepository,
    PostgresSessionHistoryRepository,
    StateOverlay,
)

from .app import create_app
from .auth import Authenticator
from .llm_settings import LlmSettingsStore
from .stacks import Stack

logger = logging.getLogger(__name__)


#: The fallback below is only useful if it is quick. Without an explicit timeout the probe
#: waits on the OS default — minutes, with nothing in the log — so a machine with Docker
#: stopped looks like a hung startup rather than the documented fallback.
STARTUP_PROBE_TIMEOUT_SECONDS = 3


class ConfigurationError(RuntimeError):
    """The deployment is misconfigured in a way that must not be papered over."""


def _frontend_dist() -> Path | None:
    return Path(settings.frontend_dist) if settings.frontend_dist else None


def _build():
    authenticator = Authenticator(settings) if settings.auth_enabled else None
    if settings.is_production and authenticator is None:
        raise ConfigurationError(
            "ENVIRONMENT=production requires SUPABASE_URL (or SUPABASE_JWT_SECRET): without "
            "accounts every visitor would share one user's data."
        )

    try:
        engine = sa.create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": STARTUP_PROBE_TIMEOUT_SECONDS},
        )
        with engine.connect() as connection:
            connection.execute(sa.text("select 1"))
    except Exception as exc:
        if authenticator is not None or settings.is_production:
            # In-memory storage shared across authenticated users would be a data leak, and in
            # production it would silently discard everyone's evidence on restart.
            raise ConfigurationError(
                f"Accounts are enabled but Postgres is unreachable ({type(exc).__name__}: "
                f"{exc}). Refusing to start rather than fall back to shared in-memory storage."
            ) from exc
        logger.warning(
            "Postgres unreachable (%s: %s) - falling back to IN-MEMORY storage. "
            "Assessments will NOT survive a restart. Run `docker compose up -d` and "
            "`alembic upgrade head` to persist.",
            type(exc).__name__,
            exc,
        )
        return create_app(frontend_dist=_frontend_dist())

    logger.info("using Postgres at %s", engine.url.render_as_string(hide_password=True))

    if settings.secrets_encryption_key:
        vault = Vault(settings.secrets_encryption_key)
    elif authenticator is not None:
        raise ConfigurationError(
            "SECRETS_ENCRYPTION_KEY is required when accounts are enabled: it encrypts the API "
            "keys users save. See backend/.env.example for how to generate one."
        )
    else:
        # Single-user local use: keys saved this run are readable only until restart.
        vault = Vault.ephemeral()

    curriculum = JsonCurriculumRepository(DEFAULT_CURRICULUM_PATH).get()

    def build_stack(user_id: str) -> Stack:
        states = PostgresKnowledgeStateRepository(engine, user_id)
        return Stack(
            storage="postgres",
            service=AssessmentService(
                curriculum,
                StateOverlay(curriculum, states),
                PostgresSessionHistoryRepository(engine, user_id),
                pending=PostgresPendingSessionStore(engine, user_id),
            ),
            documents=DocumentService(curriculum, PostgresDocumentRepository(engine, user_id)),
        )

    return create_app(
        curriculum=curriculum,
        stack_factory=build_stack,
        authenticator=authenticator,
        llm_settings=LlmSettingsStore(vault, engine),
        frontend_dist=_frontend_dist(),
    )


app = _build()
