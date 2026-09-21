"""Schema C and Schema D — the only interface to the external document-extraction engine.

The same shape of contract as Schema A/B, for the same reason: KnowledgeOS must not care *how*
a document was read, only what came back. Strict validation, `extra="forbid"`, versioned.

    Schema C (out)   the concept catalogue plus the extraction prompt
    Schema D (in)    which curriculum concepts this document requires, and how deep

## What the extraction is allowed to decide

Only three things per concept: *is it here*, *how deep does the document go*, and *how central
is it*. Everything else — what the user is missing, what they must learn first, in what order,
and how long it will take — is computed from the graph and their mastery, neither of which the
model can see. A model that ranked study order would be guessing at the two inputs that
actually determine the answer.

## What Schema D deliberately does NOT contain

No `document_id` and no timestamps. A session's Schema B needs an id because the observation
must attach to the exact node and role context that generated it; getting that wrong corrupts
two nodes at once. A document extraction has no such prior state to pin — so the application
assigns the id and reads the clock itself, and two more fields a model could hallucinate
simply do not exist.

No prerequisites, either. The extraction reports what the document *engages with*; the
prerequisite closure is computed in Layer 3 from the DAG. If the model also walked the
prerequisite tree, the same concept would arrive twice with two different weights and the
document's centre of gravity would shift toward whatever foundations it happened to name.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from knowledgeos.curriculum import Depth

Score = Annotated[float, Field(ge=0.0, le=1.0)]

SCHEMA_C_NAME = "knowledgeos.document.catalogue"
SCHEMA_D_NAME = "knowledgeos.document.extraction"
SCHEMA_VERSION = 1

_STRICT = ConfigDict(frozen=True, extra="forbid")

#: What kind of thing was read. Affects nothing in the mathematics — it is display and recall,
#: so the user can tell "the Llama 3 paper" from "the Jane Street JD" in a list.
DocumentKind = Literal[
    "paper", "report", "job-description", "course", "book", "slides", "notes", "other"
]


# --------------------------------------------------------------------------- D


class DocumentMeta(BaseModel):
    """What was read."""

    model_config = _STRICT

    title: str = Field(min_length=1, max_length=300)
    kind: DocumentKind = "other"
    #: arXiv id, URL, company name — whatever identifies it. Optional and never parsed.
    source: str | None = Field(default=None, max_length=300)


class ExtractedConcept(BaseModel):
    """One curriculum concept the document requires."""

    model_config = _STRICT

    #: Must exist in the curriculum. Validated against the live graph on ingestion, not just
    #: against the catalogue that was handed out — a catalogue can be stale.
    node_id: str = Field(min_length=1)

    #: How deeply the *document* engages with it. Not how deeply the user's role needs it —
    #: those are different questions and a paper that merely name-drops a concept should not
    #: inherit the derivation target some role happens to demand of it.
    required_depth: Depth

    #: How central this concept is to this document, 0-1. Becomes the readiness weight, so an
    #: inflated value here makes an incidental mention look like a blocker.
    document_weight: Score

    #: Where in the document this came from. Required, because "why is this on my list?" must
    #: be answerable months later, and because a model that has to cite tends to invent less.
    evidence: str = Field(min_length=1, max_length=600)


class OutOfCurriculumConcept(BaseModel):
    """Something the document needs that has no node in the curriculum.

    Kept as free text and never matched to a node. This is the honest answer to a gap in the
    graph — and it is useful signal in its own right: a concept that keeps appearing here is a
    concept the curriculum should probably contain.
    """

    model_config = _STRICT

    label: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=1, max_length=600)


class SchemaD(BaseModel):
    """What the external extraction returns. Validated strictly; unknown fields are rejected."""

    model_config = _STRICT

    schema_name: Literal["knowledgeos.document.extraction"] = Field(
        default=SCHEMA_D_NAME, alias="schema"
    )
    schema_version: Literal[1] = SCHEMA_VERSION

    document: DocumentMeta
    #: One or two sentences on what the document is. Display only.
    summary: str = Field(default="", max_length=1000)

    concepts: tuple[ExtractedConcept, ...] = ()
    out_of_curriculum: tuple[OutOfCurriculumConcept, ...] = ()

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(c.node_id for c in self.concepts)


# --------------------------------------------------------------------------- C


class SchemaC(BaseModel):
    """What the application hands out: the catalogue the extraction must map into, and the
    prompt that tells it how.

    Symmetric with Schema A. It is a model rather than a bare string so the catalogue can be
    served with the facts a client needs to present it — how many concepts it covers, whether
    it is small enough to paste inline, and what to call the file if it is not.
    """

    model_config = _STRICT

    schema_name: Literal["knowledgeos.document.catalogue"] = Field(
        default=SCHEMA_C_NAME, alias="schema"
    )
    schema_version: Literal[1] = SCHEMA_VERSION

    prompt: str
    catalogue: str
    catalogue_filename: str
    concept_count: int
    sections: tuple[str, ...]
    role_id: str | None = None
    #: True when the catalogue is small enough to live inside the prompt rather than be
    #: attached as a file.
    fits_inline: bool = False


__all__ = [
    "SCHEMA_C_NAME",
    "SCHEMA_D_NAME",
    "SCHEMA_VERSION",
    "DocumentKind",
    "DocumentMeta",
    "ExtractedConcept",
    "OutOfCurriculumConcept",
    "SchemaC",
    "SchemaD",
]
