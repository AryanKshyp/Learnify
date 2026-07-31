"""Every [TUNABLE] parameter of the deterministic engine (Layer 3), in one place.

`CALC_ENGINE_SPEC.md` requires "config, not constants": no numeric literal may appear inline in
engine logic. Every value below is traceable to a section of that spec, and changing behaviour
means changing this file — not hunting through formulas.

Nothing here imports I/O, a clock, or a random source (enforced by the import-linter contract
in pyproject.toml). Time enters the engine as an explicit parameter, never by reading a clock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from knowledgeos.curriculum import Depth


def _frozen(mapping: Mapping[Depth, float]) -> Mapping[Depth, float]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True, slots=True)
class ObservationWeights:
    """§3 — how recall/depth/transfer combine into one session ability.

    Deeper requirements weight understanding and transfer over recall: reciting a definition
    is weak evidence that you could derive the thing.
    """

    recall: float
    depth: float
    transfer: float

    def __post_init__(self) -> None:
        total = self.recall + self.depth + self.transfer
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"observation weights must sum to 1, got {total}")


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Defaults are exactly the spec's [TUNABLE] values."""

    # -- §3 observation model -------------------------------------------------
    observation_weights: Mapping[Depth, ObservationWeights] = field(
        default_factory=lambda: MappingProxyType(
            {
                Depth.AWARENESS: ObservationWeights(0.60, 0.30, 0.10),
                Depth.WORKING: ObservationWeights(0.40, 0.40, 0.20),
                Depth.DEEP: ObservationWeights(0.25, 0.45, 0.30),
                Depth.DERIVATION: ObservationWeights(0.15, 0.45, 0.40),
            }
        )
    )
    #: response-time influence. Deliberately small - a modifier, never a dominator.
    lambda_time: float = 0.10

    # -- §4 engine confidence & variance --------------------------------------
    kappa: float = 0.5  # EWMA rate for running mean / variance
    variance_normalizer: float = 0.10  # σ²_max
    evidence_half_count: float = 3.0  # n0
    confidence_recency_days: float = 30.0  # h_conf
    c_var: float = 0.6  # variance penalty on confidence

    #: evidence-weight mix. g_llm caps LLM self-report at 20% - it is miscalibrated and must
    #: never dominate a mastery update (§4).
    g_var: float = 0.45
    g_n: float = 0.35
    g_llm: float = 0.20

    # -- §5 intrinsic mastery -------------------------------------------------
    alpha_base: float = 0.5
    mastery_target: Mapping[Depth, float] = field(
        default_factory=lambda: _frozen(
            {
                Depth.AWARENESS: 0.50,
                Depth.WORKING: 0.65,
                Depth.DEEP: 0.80,
                Depth.DERIVATION: 0.90,
            }
        )
    )

    # -- §6 stability & retention ---------------------------------------------
    initial_stability_days: float = 1.0  # S_0
    beta: float = 1.2  # stability growth
    target_retention: float = 0.85  # θ, drives next review
    default_difficulty: Mapping[Depth, float] = field(
        default_factory=lambda: _frozen(
            {
                Depth.AWARENESS: 0.2,
                Depth.WORKING: 0.4,
                Depth.DEEP: 0.6,
                Depth.DERIVATION: 0.8,
            }
        )
    )
    #: per-session cap on upward difficulty drift (§6)
    difficulty_step: float = 0.05
    difficulty_variance_trigger: float = 0.5

    # -- §7 prerequisite confidence -------------------------------------------
    #: bottleneck lean. 0.6 weights the single weakest prerequisite over the average, because
    #: one missing prerequisite blocks understanding regardless of how solid the others are.
    gamma: float = 0.6

    # -- §9 frontier & critical path ------------------------------------------
    frontier_prerequisite_threshold: float = 0.70  # φ
    critical_path_discount: float = 0.6  # ζ per hop

    # -- §10 leverage & current importance ------------------------------------
    leverage_immediate: float = 0.30  # a
    leverage_indirect: float = 0.20  # b
    leverage_role_overlap: float = 0.25  # c
    leverage_critical_path: float = 0.25  # d
    leverage_importance_boost: float = 0.3  # η
    bottleneck_boost: float = 0.5  # ρ

    # -- §11 readiness ---------------------------------------------------------
    #: floor under EM in the harmonic mean. Without it a single zero makes readiness zero and
    #: the score stops discriminating between "one gap" and "nothing known".
    readiness_epsilon: float = 0.05

    # -- §12 cost, ERG, priority ----------------------------------------------
    base_cost_hours: Mapping[Depth, float] = field(
        default_factory=lambda: _frozen(
            {
                Depth.AWARENESS: 1.0,
                Depth.WORKING: 2.0,
                Depth.DEEP: 4.0,
                Depth.DERIVATION: 8.0,
            }
        )
    )
    #: MMR trade-off: 0.7 favours priority but still breaks up five near-identical picks.
    mmr_lambda: float = 0.7
    #: a node counts as "high CPV" (and joins the candidate set) at or above this
    high_cpv_threshold: float = 0.7

    # -- §14 knowledge health --------------------------------------------------
    health_coverage: float = 0.20  # h1
    health_mean_em: float = 0.35  # h2
    health_mean_retention: float = 0.20  # h3
    health_gap: float = 0.25  # h4
    #: "critical" = intrinsic importance at or above this for the active role
    critical_importance_threshold: float = 0.7

    # -- §13 status thresholds -------------------------------------------------
    status_learning_em: float = 0.40
    status_learning_variance: float = 0.5
    status_practiced_em: float = 0.70
    status_retained_retention: float = 0.80
    status_mastered_em: float = 0.85
    status_mastered_retention: float = 0.90
    status_mastered_variance: float = 0.25
    status_min_sessions: int = 2

    def target_for(self, depth: Depth) -> float:
        """τ — the mastery level at which a node counts as sufficient for `depth`."""
        return self.mastery_target[depth]

    def difficulty_for(self, depth: Depth) -> float:
        return self.default_difficulty[depth]

    def base_cost_for(self, depth: Depth) -> float:
        return self.base_cost_hours[depth]

    def weights_for(self, depth: Depth) -> ObservationWeights:
        return self.observation_weights[depth]


#: The default configuration. Pass an explicit EngineConfig to override.
DEFAULT_CONFIG = EngineConfig()
