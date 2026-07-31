"""Layer 2 - Knowledge State (dynamic).

Per-node overlay of what the user currently knows, plus append-only session history. Overlays
the curriculum; never mutates it. Changes ONLY via validated assessment evidence.

    from knowledgeos.curriculum import fixture_repository
    from knowledgeos.state import InMemoryKnowledgeStateRepository, StateOverlay

    overlay = StateOverlay(fixture_repository().get(), InMemoryKnowledgeStateRepository())
    overlay.state_for("prob-bayes")   # cold until assessed
    overlay.unassessed()              # the cold-start backlog

This layer stores and retrieves. It computes nothing: every derived field holds its cold
default until the Stage 3 engine produces a value for it.
"""

from .errors import (
    DuplicateSessionError,
    SessionNotFoundError,
    StateError,
    UnknownNodeError,
)
from .models import KnowledgeState, SessionRecord, Status
from .overlay import NodeState, StateOverlay
from .repository import (
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    KnowledgeStateRepository,
    SessionHistoryRepository,
)

__all__ = [
    "DuplicateSessionError",
    "InMemoryKnowledgeStateRepository",
    "InMemorySessionHistoryRepository",
    "KnowledgeState",
    "KnowledgeStateRepository",
    "NodeState",
    "SessionHistoryRepository",
    "SessionNotFoundError",
    "SessionRecord",
    "StateError",
    "StateOverlay",
    "Status",
    "UnknownNodeError",
]
