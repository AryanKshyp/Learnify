"""Layer 4 boundary - Assessment interface.

Generates Schema A (out) and strictly validates Schema B (in). The assessment engine itself is
external and replaceable; KnowledgeOS knows nothing about how it works. Schema B is the ONLY
way knowledge state changes.

    service = AssessmentService(curriculum, overlay, history)
    schema_a = service.generate("prob-bayes", now=now)   # copy this out
    result   = service.ingest(pasted_payload, now=now)   # paste the answer back

This layer owns the clock: it converts real timestamps into the `days_elapsed` floats the
engine consumes, so the engine itself stays reproducible.
"""

from .errors import (
    AssessmentError,
    SchemaValidationError,
    SessionMismatchError,
    UnknownNodeReferenceError,
    UnknownSessionError,
)
from .schemas import (
    SCHEMA_A_NAME,
    SCHEMA_B_NAME,
    SCHEMA_VERSION,
    AssessmentDirectives,
    CurrentState,
    Observations,
    PrerequisiteContext,
    RoleContext,
    SchemaA,
    SchemaB,
    TargetNode,
)
from .service import (
    AssessmentService,
    IngestResult,
    InMemoryPendingSessionStore,
    PendingSessionStore,
    days_between,
)

__all__ = [
    "SCHEMA_A_NAME",
    "SCHEMA_B_NAME",
    "SCHEMA_VERSION",
    "AssessmentDirectives",
    "AssessmentError",
    "AssessmentService",
    "CurrentState",
    "InMemoryPendingSessionStore",
    "IngestResult",
    "Observations",
    "PendingSessionStore",
    "PrerequisiteContext",
    "RoleContext",
    "SchemaA",
    "SchemaB",
    "SchemaValidationError",
    "SessionMismatchError",
    "TargetNode",
    "UnknownNodeReferenceError",
    "UnknownSessionError",
    "days_between",
]
