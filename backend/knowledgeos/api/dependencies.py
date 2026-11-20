"""Dependency wiring.

Everything the routers need comes from here, so a test can swap the whole stack — including the
clock — through `app.dependency_overrides` without touching a single endpoint.

`now` is a dependency rather than a call to `datetime.now()` inside handlers. The engine is
already clock-free; making the API's clock injectable too means an integration test can advance
time by a year and assert on decay, which is otherwise untestable.

The engine snapshot is computed **once per request** and reused. Several endpoints need it, and
at 566 nodes a recompute is ~60ms — cheap enough to do per request, wasteful to do three times
within one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from knowledgeos.assessment import AssessmentService
from knowledgeos.curriculum import CurriculumGraph
from knowledgeos.documents import DocumentService
from knowledgeos.engine import EngineSnapshot

from .auth import UserId
from .stacks import Stack


def get_now() -> datetime:
    """The current time, injectable. Overridden in tests to make decay assertable."""
    return datetime.now(UTC)


def get_curriculum(request: Request) -> CurriculumGraph:
    return request.app.state.curriculum


def get_stack(request: Request, user_id: UserId) -> Stack:
    """The services for the authenticated caller - never another user's."""
    return request.app.state.stacks.for_user(user_id)


def get_service(stack: Annotated[Stack, Depends(get_stack)]) -> AssessmentService:
    return stack.service


def get_documents(stack: Annotated[Stack, Depends(get_stack)]) -> DocumentService:
    return stack.documents


@dataclass(slots=True)
class RequestContext:
    """Curriculum, service, clock, and the per-request caches."""

    curriculum: CurriculumGraph
    service: AssessmentService
    now: datetime
    _snapshot: EngineSnapshot | None = None
    _active_role_id: str | None = None
    _states: dict | None = None

    def snapshot(self, active_role_id: str | None = None) -> EngineSnapshot:
        """The engine snapshot, computed at most once per (request, role lens).

        The role lens changes `current_importance`, so a different lens genuinely needs a
        different snapshot rather than a cached one.
        """
        if self._snapshot is None or active_role_id != self._active_role_id:
            self._snapshot = self.service.recompute(
                now=self.now, active_role_id=active_role_id
            )
            self._active_role_id = active_role_id
        return self._snapshot

    def states(self) -> dict:
        """Knowledge state keyed by node_id, read once per request.

        Several endpoints need both the snapshot and the raw state; without this the same
        query runs two or three times to answer one request.
        """
        if self._states is None:
            self._states = {item.node_id: item.state for item in self.service.overlay.all()}
        return self._states


def get_context(
    curriculum: Annotated[CurriculumGraph, Depends(get_curriculum)],
    service: Annotated[AssessmentService, Depends(get_service)],
    now: Annotated[datetime, Depends(get_now)],
) -> RequestContext:
    return RequestContext(curriculum=curriculum, service=service, now=now)


Context = Annotated[RequestContext, Depends(get_context)]
Curriculum = Annotated[CurriculumGraph, Depends(get_curriculum)]
Service = Annotated[AssessmentService, Depends(get_service)]
Documents = Annotated[DocumentService, Depends(get_documents)]
Now = Annotated[datetime, Depends(get_now)]
