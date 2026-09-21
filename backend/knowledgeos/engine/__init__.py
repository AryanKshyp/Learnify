"""Layer 3 - Decision Engine (deterministic). The heart of the system.

Pure functions: state + inputs in, new values out, no I/O. Identical inputs must always
produce identical outputs. Implemented strictly per CALC_ENGINE_SPEC.md, whose §1 pipeline
fixes the ordering (never compute EM before PC, nor readiness before EM).

    from knowledgeos.engine import Observation, apply_session, recompute, recommend

    update   = apply_session(state=..., observation=Observation(0.7, 0.5, 0.3), ...)
    snapshot = recompute(curriculum, states)
    picks    = recommend(curriculum, snapshot, limit=5)

Time enters as `days_elapsed`/`days_since_last_session` and review scheduling comes back as a
number of days — the engine reads no clock, which is what makes every score reproducible.

## What this exports, and what it does not

Everything below is what a caller outside Layer 3 needs: the entry points, the config, and the
result types those entry points hand back. Individual stage functions — `session_ability`,
`propagate`, `derive_status`, `knowledge_health`, `score_candidates` and the rest — are NOT
re-exported. They have exactly one caller each, `pipeline.recompute`, and promoting them here
made the package interface wider than the thing it was meant to summarise.

They remain importable from their own modules, which is how the engine's own tests reach them:

    from knowledgeos.engine.propagation import propagate       # internal seam, for tests
    from knowledgeos.engine import recompute                   # external seam, for callers

That distinction is the point. The stage functions are an internal seam private to the
implementation; `recompute` is the interface, and it is the surface a change to the engine
should be verified through.
"""

from .config import DEFAULT_CONFIG, EngineConfig, ObservationWeights
from .document import (
    DocumentReadiness,
    PlanStep,
    Requirement,
    StatedConcept,
    document_plan,
    document_readiness,
    requirement_closure,
    total_effort,
)
from .observation import Observation
from .pipeline import (
    EngineSnapshot,
    KnowledgeHealth,
    SessionUpdate,
    apply_session,
    recommend,
    recompute,
    target_for_node,
    unexplored,
)
from .readiness import RoleReadiness
from .recommend import Candidate
from .retention import retention

__all__ = [
    "Candidate",
    "DEFAULT_CONFIG",
    "DocumentReadiness",
    "EngineConfig",
    "EngineSnapshot",
    "KnowledgeHealth",
    "Observation",
    "ObservationWeights",
    "PlanStep",
    "Requirement",
    "RoleReadiness",
    "SessionUpdate",
    "StatedConcept",
    "apply_session",
    "document_plan",
    "document_readiness",
    "recommend",
    "recompute",
    "requirement_closure",
    "retention",
    "target_for_node",
    "total_effort",
    "unexplored",
]
