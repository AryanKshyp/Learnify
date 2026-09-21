"""The document boundary: hand out Schema C, validate and ingest Schema D, compute the plan.

This layer does the bookkeeping the engine must not: it reads the clock, assigns ids, talks to
storage, and converts the boundary's Pydantic shapes into the plain dataclasses Layer 3 takes.
`now` is always an argument rather than a call to `datetime.now()`, so ingesting the same
extraction with the same `now` produces a byte-identical record.

**Extractions are stored; plans are not.** A plan is a function of the extraction and current
mastery, and mastery moves every time the user assesses anything. Recomputing on every read is
what keeps a document's readiness number true a month later instead of frozen at whatever it
was the day it was pasted — and it means studying a prerequisite raises the readiness of every
document that needed it, without re-running a single extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from knowledgeos.curriculum import CurriculumGraph
from knowledgeos.engine import (
    DEFAULT_CONFIG,
    DocumentReadiness,
    EngineConfig,
    EngineSnapshot,
    PlanStep,
    Requirement,
    StatedConcept,
    document_plan,
    document_readiness,
    requirement_closure,
    total_effort,
)
from knowledgeos.state import DocumentNotFoundError, DocumentRecord, DocumentRepository

from . import catalogue as catalogue_module
from . import prompts
from .errors import (
    DuplicateConceptError,
    EmptyExtractionError,
    ExtractionValidationError,
    UnknownConceptError,
)
from .schemas import SchemaC, SchemaD


@dataclass(frozen=True, slots=True)
class DocumentPlan:
    """Everything the Prep view shows for one document, computed fresh."""

    record: DocumentRecord
    requirements: tuple[Requirement, ...]
    readiness: DocumentReadiness
    steps: tuple[PlanStep, ...]
    total_hours: float

    @property
    def stated(self) -> tuple[Requirement, ...]:
        """Concepts the document named itself."""
        return tuple(r for r in self.requirements if r.stated)

    @property
    def implied(self) -> tuple[Requirement, ...]:
        """Concepts the document assumes but never mentions — the closure's contribution."""
        return tuple(r for r in self.requirements if not r.stated)


class DocumentService:
    """Generate Schema C, ingest Schema D, and recompute plans on demand."""

    def __init__(
        self,
        curriculum: CurriculumGraph,
        documents: DocumentRepository,
        config: EngineConfig = DEFAULT_CONFIG,
    ) -> None:
        self._curriculum = curriculum
        self._documents = documents
        self._config = config

    @property
    def curriculum(self) -> CurriculumGraph:
        return self._curriculum

    @property
    def documents(self) -> DocumentRepository:
        return self._documents

    # ----------------------------------------------------------------- out

    def schema_c(
        self,
        *,
        role_id: str | None = None,
        sections: tuple[str, ...] = (),
        inline: bool | None = None,
    ) -> SchemaC:
        """The catalogue and the prompt that goes with it.

        Both in one response, because they are one artefact: a prompt that says "use the
        attached catalogue" is wrong if the catalogue was scoped differently, and handing them
        out separately makes that mismatch possible.
        """
        if role_id is not None:
            self._curriculum.role(role_id)  # raises RoleNotFoundError -> 404
        built = catalogue_module.build(self._curriculum, role_id=role_id, sections=sections)
        embed = built.fits_inline if inline is None else inline
        return SchemaC(
            prompt=prompts.extraction(built, inline=embed),
            catalogue=built.text,
            catalogue_filename=built.filename,
            concept_count=built.concept_count,
            sections=built.sections,
            role_id=role_id,
            fits_inline=embed,
        )

    # ------------------------------------------------------------------ in

    def parse(self, payload: dict[str, Any] | SchemaD) -> SchemaD:
        """Validate the shape. Every problem at once, never just the first."""
        if isinstance(payload, SchemaD):
            return payload
        try:
            return SchemaD.model_validate(payload)
        except ValidationError as error:
            raise ExtractionValidationError(
                [
                    f"{'.'.join(str(p) for p in problem['loc']) or '<root>'}: {problem['msg']}"
                    for problem in error.errors()
                ]
            ) from error

    def ingest(
        self, payload: dict[str, Any] | SchemaD, *, now: datetime, document_id: UUID | None = None
    ) -> DocumentPlan:
        """Validate an extraction, store it, and return the plan it implies.

        Semantic validation happens after shape validation and before anything is written: an
        extraction naming one unknown concept is rejected whole rather than stored with a hole
        in it. Partial acceptance would leave a document whose readiness silently ignores part
        of what it requires.
        """
        schema_d = self.parse(payload)

        if not schema_d.concepts:
            raise EmptyExtractionError()

        seen: dict[str, int] = {}
        for node_id in schema_d.node_ids:
            seen[node_id] = seen.get(node_id, 0) + 1
        if duplicates := [n for n, count in seen.items() if count > 1]:
            raise DuplicateConceptError(duplicates)

        # Checked against the live curriculum, not the catalogue that was handed out — a
        # catalogue can be days old, and the graph is the only thing that decides what exists.
        if unknown := [n for n in schema_d.node_ids if n not in self._curriculum]:
            raise UnknownConceptError(unknown)

        record = DocumentRecord(
            document_id=document_id or uuid4(),
            title=schema_d.document.title,
            kind=schema_d.document.kind,
            source=schema_d.document.source,
            summary=schema_d.summary,
            created_at=now,
            extraction=schema_d.model_dump(mode="json", by_alias=True),
        )
        self._documents.save(record)
        return self.plan(record, snapshot=None)

    # --------------------------------------------------------------- plans

    def get(self, document_id: UUID) -> DocumentRecord:
        record = self._documents.get(document_id)
        if record is None:
            raise DocumentNotFoundError(document_id)
        return record

    def delete(self, document_id: UUID) -> None:
        self._documents.delete(document_id)

    def requirements(self, record: DocumentRecord) -> tuple[Requirement, ...]:
        """The document's full concept set, stated plus closure.

        Concepts that have since left the curriculum are dropped rather than raising. An
        extraction is a historical record and the graph is allowed to change under it; refusing
        to open a six-month-old document because one node was renamed would be the wrong
        trade. Ingestion is where unknown ids are rejected — that is the gate that matters.
        """
        schema_d = SchemaD.model_validate(record.extraction)
        stated = tuple(
            StatedConcept(
                node_id=concept.node_id,
                depth=concept.required_depth,
                weight=concept.document_weight,
            )
            for concept in schema_d.concepts
            if concept.node_id in self._curriculum
        )
        if not stated:
            return ()
        return requirement_closure(self._curriculum, stated, self._config)

    def plan(
        self,
        record: DocumentRecord | UUID,
        *,
        snapshot: EngineSnapshot | None,
        difficulty: dict[str, float] | None = None,
        limit: int | None = None,
    ) -> DocumentPlan:
        """Recompute this document's plan against current knowledge state.

        The snapshot is passed in rather than computed here: several endpoints need it, it
        costs a full graph pass, and the request context already caches exactly one.
        `difficulty` is per-node and lives in stored state rather than the snapshot; without it
        the cost model falls back to the depth default, which is right for an unassessed node
        and stale for an assessed one.
        """
        if isinstance(record, UUID):
            record = self.get(record)

        requirements = self.requirements(record)
        mastery = dict(snapshot.effective_mastery) if snapshot else {}

        readiness = document_readiness(requirements, mastery, self._config)
        steps = document_plan(
            self._curriculum,
            requirements,
            effective_mastery=mastery,
            difficulty=difficulty,
            leverage=dict(snapshot.leverage) if snapshot else None,
            current_importance=dict(snapshot.current_importance) if snapshot else None,
            limit=limit,
            config=self._config,
        )
        return DocumentPlan(
            record=record,
            requirements=requirements,
            readiness=readiness,
            steps=steps,
            total_hours=total_effort(steps),
        )

    def all_plans(
        self,
        *,
        snapshot: EngineSnapshot | None,
        difficulty: dict[str, float] | None = None,
    ) -> tuple[DocumentPlan, ...]:
        """Every saved document, newest first, each with live readiness."""
        return tuple(
            self.plan(record, snapshot=snapshot, difficulty=difficulty)
            for record in self._documents.all()
        )


__all__ = ["DocumentPlan", "DocumentService"]
