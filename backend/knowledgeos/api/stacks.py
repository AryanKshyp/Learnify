"""One service stack per user.

The assessment and document services are bound to repositories, and repositories are bound to a
single user (see `state/postgres.py`). A hosted deployment therefore builds a stack per
authenticated request - cheap, because the curriculum is shared and everything else is a thin
wrapper - rather than holding one global stack that every user would share.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from knowledgeos.assessment import AssessmentService
from knowledgeos.documents import DocumentService


@dataclass(frozen=True, slots=True)
class Stack:
    service: AssessmentService
    documents: DocumentService
    #: "postgres" | "memory" - what is really behind this stack, reported by `/health`.
    storage: str = "memory"


class StackProvider:
    """Resolves the stack for a user id.

    `shared` is the single-user mode: one stack for everybody (local use and the test suite).
    `factory` is the hosted mode: build a stack scoped to the given user.
    """

    def __init__(
        self,
        *,
        shared: Stack | None = None,
        factory: Callable[[str], Stack] | None = None,
    ) -> None:
        if (shared is None) == (factory is None):
            raise ValueError("pass exactly one of `shared` or `factory`")
        self._shared = shared
        self._factory = factory

    @property
    def per_user(self) -> bool:
        return self._factory is not None

    def for_user(self, user_id: str) -> Stack:
        if self._shared is not None:
            return self._shared
        assert self._factory is not None
        return self._factory(user_id)
