"""Document prep — "what do I need to know to read this?"

The loop mirrors the assessment loop exactly: `GET /documents/catalogue` for the prompt and the
concept list, run the extraction in any chat window, `POST /documents/ingest` with the JSON that
comes back. The document is never uploaded here — KnowledgeOS stores what it *requires*, not
what it says.

Plans are recomputed on every read rather than stored. Assessing one prerequisite lifts the
readiness of every document that needed it, with no re-extraction, which is only true if
nothing about the plan was frozen at ingestion time.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Query, Response, status

from knowledgeos.api.dependencies import Context, Documents
from knowledgeos.api.schemas import (
    CatalogueOut,
    DocumentPlanOut,
    DocumentSummary,
    OutOfCurriculumOut,
    PlanStepOut,
    RequirementOut,
)
from knowledgeos.documents import DocumentPlan, SchemaD

router = APIRouter(tags=["documents"])


def _reason(step, curriculum, requirement) -> str:
    """Why this step is where it is, in one sentence.

    Assembled from the factors that actually produced the ranking rather than written to sound
    convincing — `BUILD_SPEC.md` A.5.6 requires every recommendation to be explainable, and an
    explanation that is not derived from the computation is decoration.
    """
    if requirement.stated:
        head = "The document works with this directly"
    else:
        via = curriculum.node(requirement.required_for).name
        hops = "a prerequisite" if requirement.distance == 1 else "an upstream prerequisite"
        head = f"Not mentioned in the document — {hops} of {via}"

    if step.sufficiency <= 0.0:
        gap = "you have no evidence here yet"
    else:
        gap = f"you are at {step.sufficiency:.0%} of what it needs"

    if step.blocked_by:
        tail = f"; {len(step.blocked_by)} other concept(s) on this list come first"
    else:
        tail = "; nothing else on this list blocks it"
    return f"{head}, and {gap}{tail}."


def _plan_out(plan: DocumentPlan, context: Context) -> DocumentPlanOut:
    curriculum = context.curriculum
    snapshot = context.snapshot()
    by_id = {r.node_id: r for r in plan.requirements}

    def name_of(node_id: str | None) -> str | None:
        return curriculum.node(node_id).name if node_id else None

    extraction = SchemaD.model_validate(plan.record.extraction)

    return DocumentPlanOut(
        document_id=plan.record.document_id,
        title=plan.record.title,
        kind=plan.record.kind,
        source=plan.record.source,
        summary=plan.record.summary,
        created_at=plan.record.created_at,
        readiness=plan.readiness.readiness,
        bottleneck_node_id=plan.readiness.bottleneck_node_id,
        bottleneck_name=name_of(plan.readiness.bottleneck_node_id),
        concept_count=plan.readiness.concept_count,
        gap_count=plan.readiness.gap_count,
        total_hours=plan.total_hours,
        requirements=tuple(
            RequirementOut(
                node_id=r.node_id,
                name=curriculum.node(r.node_id).name,
                section=curriculum.node(r.node_id).section,
                competency=curriculum.node(r.node_id).competency,
                target=r.target,
                weight=r.weight,
                stated=r.stated,
                required_for=r.required_for,
                required_for_name=name_of(r.required_for),
                distance=r.distance,
                mastery=snapshot.effective_mastery[r.node_id],
                sufficiency=min(snapshot.effective_mastery[r.node_id] / r.target, 1.0)
                if r.target > 0
                else 1.0,
                status=snapshot.status[r.node_id],
            )
            for r in plan.requirements
        ),
        steps=tuple(
            PlanStepOut(
                node_id=step.node_id,
                name=curriculum.node(step.node_id).name,
                section=curriculum.node(step.node_id).section,
                target=step.requirement.target,
                mastery=step.effective_mastery,
                sufficiency=step.sufficiency,
                weight=step.requirement.weight,
                stated=step.requirement.stated,
                required_for_name=name_of(step.requirement.required_for),
                expected_gain=step.expected_gain,
                learning_cost_hours=step.learning_cost,
                priority=step.priority,
                blocked_by=step.blocked_by,
                reason=_reason(step, curriculum, by_id[step.node_id]),
            )
            for step in plan.steps
        ),
        out_of_curriculum=tuple(
            OutOfCurriculumOut(label=item.label, evidence=item.evidence)
            for item in extraction.out_of_curriculum
        ),
    )


def _summary(plan: DocumentPlan, context: Context) -> DocumentSummary:
    curriculum = context.curriculum
    bottleneck = plan.readiness.bottleneck_node_id
    return DocumentSummary(
        document_id=plan.record.document_id,
        title=plan.record.title,
        kind=plan.record.kind,
        source=plan.record.source,
        summary=plan.record.summary,
        created_at=plan.record.created_at,
        readiness=plan.readiness.readiness,
        bottleneck_node_id=bottleneck,
        bottleneck_name=curriculum.node(bottleneck).name if bottleneck else None,
        concept_count=plan.readiness.concept_count,
        gap_count=plan.readiness.gap_count,
        stated_count=len(plan.stated),
        implied_count=len(plan.implied),
        total_hours=plan.total_hours,
    )


@router.get("/documents/catalogue", response_model=CatalogueOut)
def get_catalogue(
    documents: Documents,
    role: str | None = Query(None, description="narrow the catalogue to one role's concepts"),
    section: list[str] | None = Query(None, description="narrow to these sections; repeatable"),
    inline: bool | None = Query(
        None,
        description="embed the catalogue in the prompt instead of referring to an attached "
        "file. Defaults to whether it is small enough to be worth it.",
    ),
):
    """The extraction prompt, and the concept catalogue it tells the model to map into.

    Scoping is a real trade-off, so it is the caller's to make: a scoped catalogue fits inside
    the prompt and needs no attachment, but a concept outside the scope cannot be reported at
    all — it comes back as `out_of_curriculum` and looks like a gap in the curriculum when it
    is really a gap in the scope.
    """
    schema_c = documents.schema_c(
        role_id=role, sections=tuple(section or ()), inline=inline
    )
    return CatalogueOut(
        prompt=schema_c.prompt,
        catalogue=schema_c.catalogue,
        catalogue_filename=schema_c.catalogue_filename,
        concept_count=schema_c.concept_count,
        sections=schema_c.sections,
        role_id=schema_c.role_id,
        fits_inline=schema_c.fits_inline,
        approx_tokens=int(len(schema_c.catalogue) / 3.6),
    )


@router.post(
    "/documents/ingest", response_model=DocumentPlanOut, status_code=status.HTTP_201_CREATED
)
def ingest_document(context: Context, documents: Documents, payload: dict[str, Any] = Body(...)):
    """Accept a Schema D extraction and return the plan it implies.

    Rejected whole or accepted whole. An extraction naming one unknown concept is never stored
    with a hole in it, because a document whose readiness silently ignores part of what it
    requires is worse than no document at all.
    """
    plan = documents.ingest(payload, now=context.now)
    return _plan_out(plan, context)


@router.get("/documents", response_model=tuple[DocumentSummary, ...])
def list_documents(context: Context, documents: Documents):
    """Every saved document, newest first, each with readiness recomputed right now."""
    difficulty = {
        node_id: state.difficulty
        for node_id, state in context.states().items()
        if state.difficulty is not None
    }
    return tuple(
        _summary(plan, context)
        for plan in documents.all_plans(snapshot=context.snapshot(), difficulty=difficulty)
    )


@router.get("/documents/{document_id}", response_model=DocumentPlanOut)
def get_document(document_id: UUID, context: Context, documents: Documents):
    """One document in full: every concept it needs, and the ordered plan to close the gaps."""
    difficulty = {
        node_id: state.difficulty
        for node_id, state in context.states().items()
        if state.difficulty is not None
    }
    plan = documents.plan(document_id, snapshot=context.snapshot(), difficulty=difficulty)
    return _plan_out(plan, context)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, documents: Documents) -> Response:
    """Forget a document.

    Deletable, unlike session history. A document is a goal, not evidence — removing one
    changes nothing about what the user knows, so the append-only discipline that protects
    assessments would only be clutter here.
    """
    documents.delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
