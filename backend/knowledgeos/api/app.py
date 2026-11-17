"""FastAPI application factory.

Built as a factory rather than a module-level `app` so tests can construct an instance with an
in-memory stack and a frozen clock, and production can wire Postgres — without either knowing
about the other.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, FastAPI

from knowledgeos.assessment import AssessmentService, PendingSessionStore
from knowledgeos.config import settings
from knowledgeos.curriculum import (
    DEFAULT_CURRICULUM_PATH,
    CurriculumGraph,
    JsonCurriculumRepository,
)
from knowledgeos.documents import DocumentService
from knowledgeos.state import (
    DocumentRepository,
    InMemoryDocumentRepository,
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    KnowledgeStateRepository,
    SessionHistoryRepository,
    StateOverlay,
)
from knowledgeos.state.tables import LOCAL_USER

from .auth import Authenticator, get_user_id
from .errors import register_error_handlers
from .frontend import mount_frontend
from .llm_settings import LlmSettingsStore
from .routers import documents, graph, llm, recommendations, sessions
from .stacks import Stack, StackProvider


def _storage_label(repository: object) -> str:
    """Which store this instance is actually using, for `/health`.

    Derived from the repository it was handed rather than from a flag set at startup. The
    distinction matters: a caller that *intended* Postgres and silently fell back to memory
    would otherwise report the intention, which is exactly the failure this is here to expose.
    An in-memory instance is indistinguishable from a persistent one until you restart it and
    your evidence is gone, so it has to be visible before then.
    """
    name = type(repository).__name__
    if name.startswith("Postgres"):
        return "postgres"
    if name.startswith("InMemory"):
        return "memory"
    return name


DESCRIPTION = """
An evidence-based model of what you know, across six interview tracks.

**The loop.** Browse the graph → pick a concept → `POST /sessions` for a Schema A → run the
assessment externally → `POST /sessions/ingest` with the Schema B. That is the only way
knowledge state changes: reading, watching, or feeling ready never move a score.

**Prep for a document.** `GET /documents/catalogue` for a prompt and the concept list, run
the extraction in any chat window, `POST /documents/ingest` with the JSON. The document itself
is never uploaded here: the app stores what it *requires*, not what it says. The extraction
reports which concepts appear and how deep; the prerequisite closure, the gaps, the order and
the effort are all computed from the graph and your mastery.

**Two mastery numbers, deliberately.** `intrinsic_mastery` is evidence and is never altered by
prerequisites, decay, or time. `effective_mastery` is what the system can currently *trust*,
and is what recommendations act on. When a prerequisite decays, dependents lose trust without
losing evidence — and restudying the prerequisite restores them with no reassessment.

Every score is deterministic and carries a `computation_trace`.
"""


def create_app(
    *,
    curriculum: CurriculumGraph | None = None,
    curriculum_path: Path | str = DEFAULT_CURRICULUM_PATH,
    states: KnowledgeStateRepository | None = None,
    history: SessionHistoryRepository | None = None,
    pending: PendingSessionStore | None = None,
    documents_repo: DocumentRepository | None = None,
    stack_factory: Callable[[str], Stack] | None = None,
    authenticator: Authenticator | None = None,
    llm_settings: LlmSettingsStore | None = None,
    frontend_dist: Path | str | None = None,
) -> FastAPI:
    """Build the application.

    Defaults to the real curriculum with in-memory storage. Pass repositories to persist —
    they are protocols, so the Postgres implementations drop straight in.

    Hosted use passes `stack_factory` (one service stack per user, built from user-scoped
    repositories) and an `authenticator`; the single `states`/`history`/... arguments are the
    single-user mode and are ignored when a factory is given.
    """
    app = FastAPI(
        title="KnowledgeOS",
        description=DESCRIPTION,
        version="0.1.0",
        openapi_tags=[
            {"name": "graph", "description": "Browse the curriculum. Role, competency and "
             "concept are lenses over one graph, never separate datasets."},
            {"name": "recommendations", "description": "What to study next, and why. Ranked by "
             "expected readiness gain per unit of effort - not by biggest gap."},
            {"name": "sessions", "description": "The assessment loop. Schema A out, Schema B in."},
            {"name": "documents", "description": "Prep for a paper, report or job description. "
             "Schema C out, Schema D in. The document is never uploaded here - the app stores "
             "what it REQUIRES, not what it says."},
        ],
    )

    # `is None` rather than `or` throughout: every in-memory repository defines __len__, so an
    # empty one is falsy — and empty is precisely how an injected store arrives. With `or`, a
    # caller passing a real repository silently got a fresh in-memory one instead.
    resolved = curriculum if curriculum is not None else JsonCurriculumRepository(
        curriculum_path
    ).get()
    if stack_factory is not None:
        stacks = StackProvider(factory=stack_factory)
        # Only used to report which store is behind the factory; holds no user data.
        probe = stacks.for_user(LOCAL_USER)
    else:
        state_repository = (
            InMemoryKnowledgeStateRepository() if states is None else states
        )
        overlay = StateOverlay(resolved, state_repository)
        service = AssessmentService(
            resolved,
            overlay,
            InMemorySessionHistoryRepository() if history is None else history,
            pending=pending,
        )
        probe = Stack(
            storage=_storage_label(state_repository),
            service=service,
            documents=DocumentService(
                resolved,
                InMemoryDocumentRepository() if documents_repo is None else documents_repo,
            ),
        )
        stacks = StackProvider(shared=probe)
        # Single-user mode only: with per-user stacks there is no one global service, and
        # exposing the probe's would invite code that quietly serves everyone as `local`.
        app.state.service = probe.service
        app.state.documents = probe.documents
    service = probe.service

    app.state.curriculum = resolved
    app.state.stacks = stacks
    app.state.authenticator = authenticator
    app.state.llm_settings = (
        llm_settings if llm_settings is not None else LlmSettingsStore.in_memory()
    )

    register_error_handlers(app)
    # Every router requires a signed-in caller, including the ones that only read the shared
    # curriculum: with accounts on there is no reason for any route but `/health` (which the
    # host probes) to answer an anonymous request.
    for module in (graph, recommendations, sessions, documents, llm):
        app.include_router(module.router, dependencies=[Depends(get_user_id)])

    storage = probe.storage
    pending_storage = _storage_label(service.pending)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, object]:
        """Liveness, the curriculum loaded, and **which store is really behind it**.

        `storage` and `persistent` are reported because an in-memory instance looks identical
        to a persistent one from the outside — until it is restarted and every assessment is
        gone. Anything that decides whether to leave a running backend alone needs to be able
        to ask, rather than assume from whether a database happens to be up.

        `pending_storage` is reported separately because it can differ: open Schema A payloads
        are a distinct store, and one held in memory behind persistent knowledge state loses
        any session that is still waiting for its Schema B. `persistent` means both.
        """
        return {
            "status": "ok",
            "curriculum_nodes": len(resolved),
            "curriculum_edges": len(resolved.edges),
            "roles": len(resolved.roles),
            "storage": storage,
            "pending_storage": pending_storage,
            "persistent": storage != "memory" and pending_storage != "memory",
            "auth": "required" if authenticator is not None else "none",
        }

    @app.get("/config", tags=["ops"])
    def public_config() -> dict[str, object]:
        """What the browser needs before anyone is signed in.

        Public on purpose: the sign-in screen cannot authenticate to learn how to authenticate.
        Contains only values that are public by design (the project URL and anon key).
        """
        if authenticator is None:
            return {"auth": False}
        return {
            "auth": True,
            "supabase_url": settings.supabase_url,
            "supabase_anon_key": settings.supabase_anon_key,
        }

    if frontend_dist is not None:
        mount_frontend(app, Path(frontend_dist))

    return app
