"""Layer 2 - Knowledge State (dynamic).

Per-node overlay of what the user currently knows, plus append-only session history. Overlays
the curriculum; never mutates it. Changes ONLY via validated assessment evidence.

    from knowledgeos.curriculum import fixture_repository
    from knowledgeos.state import InMemoryKnowledgeStateRepository, StateOverlay

    overlay = StateOverlay(fixture_repository().get(), InMemoryKnowledgeStateRepository())
    overlay.state_for("prob-bayes")   # cold until assessed
    overlay.all()                     # every node joined to its state

This layer stores and retrieves. It computes nothing: every derived field holds its cold
default until the Stage 3 engine produces a value for it.
"""

from .errors import (
    DocumentNotFoundError,
    DuplicateSessionError,
    SessionNotFoundError,
    StateError,
    UnknownNodeError,
)
from .models import DocumentRecord, KnowledgeState, SessionRecord, Status
from .overlay import NodeState, StateOverlay
from .postgres import (
    PostgresDocumentRepository,
    PostgresKnowledgeStateRepository,
    PostgresSessionHistoryRepository,
)
from .repository import (
    DocumentRepository,
    InMemoryDocumentRepository,
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    KnowledgeStateRepository,
    SessionHistoryRepository,
)

__all__ = [
    "DocumentNotFoundError",
    "DocumentRecord",
    "DocumentRepository",
    "DuplicateSessionError",
    "InMemoryDocumentRepository",
    "InMemoryKnowledgeStateRepository",
    "InMemorySessionHistoryRepository",
    "KnowledgeState",
    "KnowledgeStateRepository",
    "NodeState",
    "PostgresDocumentRepository",
    "PostgresKnowledgeStateRepository",
    "PostgresSessionHistoryRepository",
    "SessionHistoryRepository",
    "SessionNotFoundError",
    "SessionRecord",
    "StateError",
    "StateOverlay",
    "Status",
    "UnknownNodeError",
]
