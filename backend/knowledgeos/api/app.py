"""FastAPI application factory.

Built as a factory rather than a module-level `app` so tests can construct an instance with an
in-memory stack and a frozen clock, and production can wire Postgres — without either knowing
about the other.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from knowledgeos.assessment import AssessmentService
from knowledgeos.curriculum import (
    DEFAULT_CURRICULUM_PATH,
    CurriculumGraph,
    JsonCurriculumRepository,
)
from knowledgeos.state import (
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    KnowledgeStateRepository,
    SessionHistoryRepository,
    StateOverlay,
)

from .errors import register_error_handlers
from .routers import graph, recommendations, sessions

DESCRIPTION = """
An evidence-based model of what you know, across six interview tracks.

**The loop.** Browse the graph → pick a concept → `POST /sessions` for a Schema A → run the
assessment externally → `POST /sessions/ingest` with the Schema B. That is the only way
knowledge state changes: reading, watching, or feeling ready never move a score.

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
) -> FastAPI:
    """Build the application.

    Defaults to the real curriculum with in-memory storage. Pass repositories to persist —
    they are protocols, so the Postgres implementations drop straight in.
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
        ],
    )

    resolved = curriculum or JsonCurriculumRepository(curriculum_path).get()
    overlay = StateOverlay(resolved, states or InMemoryKnowledgeStateRepository())
    service = AssessmentService(
        resolved, overlay, history or InMemorySessionHistoryRepository()
    )

    app.state.curriculum = resolved
    app.state.service = service

    register_error_handlers(app)
    app.include_router(graph.router)
    app.include_router(recommendations.router)
    app.include_router(sessions.router)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, object]:
        """Liveness, plus enough to confirm the right curriculum is loaded."""
        return {
            "status": "ok",
            "curriculum_nodes": len(resolved),
            "curriculum_edges": len(resolved.edges),
            "roles": len(resolved.roles),
        }

    return app
