"""Document prep — "what do I need to know to read this?"

A boundary to an external LLM, exactly like Layer 4's assessment boundary and for the same
reason: the reading happens outside, the deciding happens here.

    from knowledgeos.documents import DocumentService

    service  = DocumentService(curriculum, InMemoryDocumentRepository())
    schema_c = service.schema_c(role_id="ai-research")   # catalogue + prompt, to paste
    plan     = service.ingest(pasted_json, now=now)      # -> readiness, gaps, study order

The document itself is never uploaded here and never parsed here. KnowledgeOS stores what a
document *requires*, not what it says — which is why this needs no PDF library, no file
storage, and no metered API call.

The division of labour is the whole design:

    the LLM decides   which catalogue concepts appear, how deep, how central, and why
    the app decides   what the reader is missing, what the document silently assumes,
                      what order to study in, and how long it will take

The second list needs the prerequisite DAG and the user's mastery. The model can see neither,
so anything it said about them would be invention.
"""

from .catalogue import CATALOGUE_FILENAME, Catalogue
from .errors import (
    DocumentError,
    DuplicateConceptError,
    EmptyExtractionError,
    ExtractionValidationError,
    UnknownConceptError,
)
from .prompts import extraction
from .schemas import (
    SCHEMA_C_NAME,
    SCHEMA_D_NAME,
    SCHEMA_VERSION,
    DocumentKind,
    DocumentMeta,
    ExtractedConcept,
    OutOfCurriculumConcept,
    SchemaC,
    SchemaD,
)
from .service import DocumentPlan, DocumentService

__all__ = [
    "CATALOGUE_FILENAME",
    "SCHEMA_C_NAME",
    "SCHEMA_D_NAME",
    "SCHEMA_VERSION",
    "Catalogue",
    "DocumentError",
    "DocumentKind",
    "DocumentMeta",
    "DocumentPlan",
    "DocumentService",
    "DuplicateConceptError",
    "EmptyExtractionError",
    "ExtractedConcept",
    "ExtractionValidationError",
    "OutOfCurriculumConcept",
    "SchemaC",
    "SchemaD",
    "UnknownConceptError",
    "extraction",
]
