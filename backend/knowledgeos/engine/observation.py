"""Pipeline stages 1-3 — observation, engine confidence, intrinsic mastery.

CALC_ENGINE_SPEC.md §3, §4, §5.

The framing that makes the rest coherent: **mastery is latent, and a Schema B is one noisy
observation of it**. Nothing here treats the LLM's numbers as truth. The engine computes its
own confidence from evidence (count, consistency, recency) and lets `llm_confidence`
contribute at most 20% of an update's weight, because LLM self-report is miscalibrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from knowledgeos.curriculum import Depth

from .config import DEFAULT_CONFIG, EngineConfig


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalized_variance(variance_raw: float, config: EngineConfig = DEFAULT_CONFIG) -> float:
    """σ² on 0..1, for the thresholds and for display.

    The *raw* value is the EWMA state and the thing worth persisting; this is a lens on it.
    Deriving it on demand rather than storing it is what keeps the round trip lossless: raw
    variance above `variance_normalizer` saturates here, so a stored normalised value could
    never be turned back into the number the EWMA needs on the next session.
    """
    return clamp(variance_raw / config.variance_normalizer)


@dataclass(frozen=True, slots=True)
class Observation:
    """The raw observations a Schema B carries (BUILD_SPEC.md C.8)."""

    recall: float
    depth: float
    transfer: float
    response_time_rating: float = 1.0
    llm_confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class SessionAbility:
    """§3 output — what this one session observed."""

    raw: float  # O_raw, before the fluency modifier
    value: float  # O

    @property
    def quality(self) -> float:
        """Q, used by the stability update (§6). The spec sets Q = O."""
        return self.value


def session_ability(
    observation: Observation,
    required_depth: Depth,
    config: EngineConfig = DEFAULT_CONFIG,
) -> SessionAbility:
    """§3 — combine recall/depth/transfer, then apply the response-time modifier.

    The weights shift toward depth and transfer as the required depth rises: at `derivation`,
    recalling the statement is worth 0.15 while applying it to an unseen framing is worth 0.40.

    The fluency modifier is deliberately capped small (λ=0.10). Slow, effortful recall signals
    less consolidated knowledge than fluent recall, but it is a nudge, never a verdict.
    """
    weights = config.weights_for(required_depth)
    raw = (
        weights.recall * observation.recall
        + weights.depth * observation.depth
        + weights.transfer * observation.transfer
    )
    modifier = 1.0 - config.lambda_time * (1.0 - observation.response_time_rating)
    return SessionAbility(raw=clamp(raw), value=clamp(raw * modifier))


@dataclass(frozen=True, slots=True)
class EvidenceQuality:
    """§4 output — the engine's own view of how much this evidence is worth."""

    running_mean: float  # μ
    variance_raw: float  # σ²_raw, un-normalised
    variance: float  # σ², normalised to 0..1
    confidence: float  # C
    evidence_weight: float  # ew, how far this session may move M


def evidence_quality(
    ability: SessionAbility,
    *,
    previous_mean: float,
    previous_variance_raw: float,
    session_count: int,
    days_since_last_session: float,
    llm_confidence: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> EvidenceQuality:
    """§4 — running variance, engine confidence, and this session's evidence weight.

    `session_count` is the count BEFORE this session.

    Note on ordering: the spec updates μ first, then computes σ²_raw from the deviation
    `(O − μ)`. That is read literally here — the deviation uses the freshly-updated mean. The
    alternative (deviating from the prior mean) is defensible too, but the spec's written order
    is what the golden values were produced against, and determinism matters more than taste.

    **First-session initialisation.** On session one there is no prior mean, and running the
    EWMA against the μ = 0 placeholder manufactures variance out of nothing: the deviation
    `(O − 0.5·O)` is large purely because μ was never initialised, which reports a perfectly
    ordinary first session as wildly inconsistent — enough to trip the σ² > 0.5 clause and
    label it `learning` regardless of how well it went. Worse, a genuinely contradictory second
    session then *lowers* variance, inverting the signal.

    A single observation cannot disagree with itself, so μ seeds to O and σ² starts at 0.
    Variance then measures what it is supposed to: disagreement BETWEEN sessions. The spec does
    not state this, but every alternative reading makes σ² mean something other than
    consistency.
    """
    kappa = config.kappa

    if session_count == 0:
        mean = ability.value
        variance_raw = 0.0
    else:
        mean = previous_mean + kappa * (ability.value - previous_mean)
        deviation = ability.value - mean
        variance_raw = (1.0 - kappa) * (previous_variance_raw + kappa * deviation**2)
    variance = normalized_variance(variance_raw, config)

    saturation = 1.0 - exp(-session_count / config.evidence_half_count)
    saturation_next = 1.0 - exp(-(session_count + 1) / config.evidence_half_count)
    recency = exp(-days_since_last_session / config.confidence_recency_days)

    confidence = clamp(saturation * (1.0 - config.c_var * variance) * recency)
    weight = clamp(
        config.g_var * (1.0 - variance)
        + config.g_n * saturation_next
        + config.g_llm * llm_confidence
    )
    return EvidenceQuality(
        running_mean=mean,
        variance_raw=variance_raw,
        variance=variance,
        confidence=confidence,
        evidence_weight=weight,
    )


def update_intrinsic_mastery(
    current: float,
    ability: SessionAbility,
    evidence_weight: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """§5 — a confidence-weighted step toward what this session observed.

    This is the ONLY function in the engine that changes intrinsic mastery, and it moves it
    solely toward observed evidence. Prerequisites, decay, and elapsed time never appear here;
    they act on effective mastery instead. That separation is the system's governing principle
    and the reason a decayed prerequisite never destroys what the user demonstrably knew.
    """
    alpha = config.alpha_base * evidence_weight
    return clamp(current + alpha * (ability.value - current))
