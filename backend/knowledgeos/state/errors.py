"""Layer 2 errors."""

from __future__ import annotations

from uuid import UUID


class StateError(Exception):
    """Base class for every Layer 2 failure."""


class UnknownNodeError(StateError):
    """State was written for a node that is not in the curriculum.

    Layer 2 overlays Layer 1; a state record with no node to attach to is orphaned data, and
    accepting it would let the overlay silently drift from the curriculum it describes.
    """

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__(f"node {node_id!r} is not in the curriculum")


class DuplicateSessionError(StateError):
    """History is append-only: a session_id may be written once."""

    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"session {session_id} already recorded; history is append-only")


class SessionNotFoundError(StateError):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"no such session: {session_id}")


class DocumentNotFoundError(StateError):
    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"no such document: {document_id}")

