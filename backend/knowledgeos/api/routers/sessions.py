"""The assessment session loop — the only way knowledge state ever changes.

    POST /sessions            -> Schema A (copy this into the external engine)
    POST /sessions/ingest     -> paste the returned Schema B back

Schema B arrives as an arbitrary JSON body rather than a typed FastAPI model on purpose. If
FastAPI validated it, malformed input would produce FastAPI's own error shape and bypass the
Layer 4 validator that reports *every* violation at once. Routing the raw body through
`AssessmentService.parse` keeps one validator and one error contract — and this is a
copy-paste boundary, where getting all the problems in one response actually matters.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Query, status

from knowledgeos.api.dependencies import Context, Service
from knowledgeos.api.schemas import IngestResponse, SessionRecordOut, SessionRequest
from knowledgeos.assessment import SchemaA

router = APIRouter(tags=["sessions"])


def _record_out(record) -> SessionRecordOut:
    return SessionRecordOut(
        session_id=str(record.session_id),
        node_id=record.node_id,
        role_context=record.role_context,
        created_at=record.created_at,
        completed_at=record.completed_at,
        mastery_before=record.mastery_before,
        mastery_after=record.mastery_after,
    )


@router.post("/sessions", response_model=dict, status_code=status.HTTP_201_CREATED)
def open_session(request: SessionRequest, context: Context) -> dict[str, Any]:
    """Generate the Schema A for a node and open the session.

    Returned as the raw wire payload (with the `schema` key) so the client can hand it to the
    external engine verbatim — reserialising it would risk drifting from the contract the
    engine is written against.
    """
    schema_a = context.service.generate(
        request.node_id, now=context.now, min_questions=request.min_questions
    )
    return schema_a.to_payload()


@router.get("/sessions/open", response_model=tuple[dict, ...])
def list_open_sessions(service: Service) -> tuple[dict, ...]:
    """Sessions generated but not yet answered."""
    return tuple(schema_a.to_payload() for schema_a in service.pending.all())


@router.get("/sessions/open/{session_id}", response_model=dict)
def get_open_session(session_id: UUID, service: Service) -> dict[str, Any]:
    """Re-fetch a Schema A the user did not finish copying."""
    schema_a: SchemaA | None = service.pending.peek(session_id)
    if schema_a is None:
        from knowledgeos.assessment import UnknownSessionError

        raise UnknownSessionError(session_id)
    return schema_a.to_payload()


@router.post("/sessions/ingest", response_model=IngestResponse)
def ingest_session(context: Context, payload: dict[str, Any] = Body(...)) -> IngestResponse:
    """Validate a Schema B, run the engine, persist, and recompute.

    Nothing is written until validation fully passes, so a rejected paste leaves state
    untouched and the session still open to retry.
    """
    node_id = payload.get("node_id")
    status_before = (
        context.service.overlay.state_for(node_id).status
        if isinstance(node_id, str) and node_id in context.curriculum
        else None
    )

    result = context.service.ingest(payload, now=context.now)

    return IngestResponse(
        node_id=result.record.node_id,
        intrinsic_mastery_before=result.state_before.intrinsic_mastery,
        intrinsic_mastery_after=result.state_after.intrinsic_mastery,
        status_before=status_before or result.state_before.status,
        status_after=result.state_after.status,
        next_review_at=result.state_after.next_review_at,
        session=_record_out(result.record),
        computation_trace=result.record.computation_trace,
    )


@router.get("/sessions", response_model=tuple[SessionRecordOut, ...])
def list_sessions(
    service: Service, node_id: str | None = Query(None, description="filter to one node")
):
    """Completed session history, oldest first.

    Append-only: this is the evidence trail every mastery score is reproducible from.
    """
    records = service.history.for_node(node_id) if node_id else service.history.all()
    return tuple(_record_out(r) for r in records)
