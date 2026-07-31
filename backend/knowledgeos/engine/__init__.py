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
"""

from .config import DEFAULT_CONFIG, EngineConfig, ObservationWeights
from .health import KnowledgeHealth, knowledge_health
from .observation import (
    EvidenceQuality,
    Observation,
    SessionAbility,
    clamp,
    evidence_quality,
    session_ability,
    update_intrinsic_mastery,
)
from .pipeline import (
    EngineSnapshot,
    SessionUpdate,
    apply_session,
    recommend,
    recompute,
    target_for_node,
    unexplored,
)
from .position import (
    critical_path_values,
    current_importance,
    intrinsic_importance,
    is_frontier,
    leverage_values,
    min_max_normalize,
)
from .propagation import (
    PrerequisiteInput,
    effective_mastery,
    prerequisite_confidence,
    propagate,
)
from .readiness import (
    RoleReadiness,
    all_role_readiness,
    role_priority_weights,
    role_readiness,
)
from .recommend import (
    Candidate,
    cold_start_queue,
    diversify,
    expected_readiness_gain,
    learning_cost,
    score_candidates,
    similarity,
)
from .retention import (
    adjust_difficulty,
    days_until_review,
    initial_difficulty,
    is_due,
    retention,
    update_stability,
)
from .status import derive_status

__all__ = [
    "DEFAULT_CONFIG",
    "Candidate",
    "EngineConfig",
    "EngineSnapshot",
    "EvidenceQuality",
    "KnowledgeHealth",
    "Observation",
    "ObservationWeights",
    "PrerequisiteInput",
    "RoleReadiness",
    "SessionAbility",
    "SessionUpdate",
    "adjust_difficulty",
    "all_role_readiness",
    "apply_session",
    "clamp",
    "cold_start_queue",
    "critical_path_values",
    "current_importance",
    "days_until_review",
    "derive_status",
    "diversify",
    "effective_mastery",
    "evidence_quality",
    "expected_readiness_gain",
    "initial_difficulty",
    "intrinsic_importance",
    "is_due",
    "is_frontier",
    "knowledge_health",
    "learning_cost",
    "leverage_values",
    "min_max_normalize",
    "prerequisite_confidence",
    "propagate",
    "recommend",
    "recompute",
    "retention",
    "role_priority_weights",
    "role_readiness",
    "score_candidates",
    "session_ability",
    "similarity",
    "target_for_node",
    "unexplored",
    "update_intrinsic_mastery",
    "update_stability",
]
