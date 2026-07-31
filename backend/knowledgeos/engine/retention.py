"""Pipeline stage 4 — stability and retention. CALC_ENGINE_SPEC.md §6.

A deliberately simple exponential forgetting model, **not** full FSRS. Sessions here are
discussions, derivations and applications rather than flashcard flips, so a debuggable
two-parameter model is worth more than a finely-tuned scheduler whose behaviour nobody can
explain. The spec settled this explicitly.

No clock is read anywhere: elapsed time arrives as `days_elapsed`, and review scheduling is
returned as a number of days for the caller to turn into a timestamp. That keeps the whole
module a pure function of its arguments — the same inputs always produce the same retention.
"""

from __future__ import annotations

from math import exp, log

from knowledgeos.curriculum import Depth

from .config import DEFAULT_CONFIG, EngineConfig
from .observation import clamp


def retention(days_elapsed: float, stability: float | None) -> float:
    """R(t) = exp(−Δt / S) — probability of recall now.

    A node with no stability yet (never assessed) has no forgetting curve, so retention is 0:
    there is nothing to retain. At the moment of assessment Δt = 0 and R = 1.
    """
    if stability is None or stability <= 0.0:
        return 0.0
    if days_elapsed <= 0.0:
        return 1.0
    return clamp(exp(-days_elapsed / stability))


def update_stability(
    current: float | None,
    *,
    quality: float,
    mastery: float,
    difficulty: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """S_new = S_old · (1 + β·Q·M·(1−D)).

    Material that is well understood and easy consolidates fastest, so the interval grows
    multiplicatively. A poor session (Q≈0) or barely-held material (M≈0) leaves stability
    where it was rather than shrinking it — the model never punishes, it just fails to reward.

    `mastery` is the POST-update intrinsic mastery, per the spec's stage ordering.
    """
    base = config.initial_stability_days if current is None else current
    growth = 1.0 + config.beta * quality * mastery * (1.0 - difficulty)
    return base * growth


def days_until_review(stability: float, config: EngineConfig = DEFAULT_CONFIG) -> float:
    """How long until retention decays to the target θ.

    From R = exp(−Δt/S) = θ, so Δt = −S·ln θ. With θ = 0.85 that is ≈ 0.163·S.

    Returned in days rather than as a timestamp because the engine performs no I/O and reads no
    clock; Stage 4 adds this to `last_assessed_at`.
    """
    if stability <= 0.0:
        return 0.0
    return -stability * log(config.target_retention)


def is_due(
    days_elapsed: float,
    stability: float | None,
    config: EngineConfig = DEFAULT_CONFIG,
) -> bool:
    """True once retention has fallen to or below the target θ."""
    if stability is None:
        return False
    return retention(days_elapsed, stability) <= config.target_retention


def initial_difficulty(depth: Depth, config: EngineConfig = DEFAULT_CONFIG) -> float:
    """D — default by depth tier, before any observed struggle adjusts it."""
    return config.difficulty_for(depth)


def adjust_difficulty(
    current: float,
    *,
    variance: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> float:
    """Nudge difficulty up when evidence is inconsistent.

    Bounded to `difficulty_step` per session and clamped to 0..1 — the spec is explicit that
    this must move slowly. Difficulty only ever rises here: a node that turns out hard stays
    marked hard until re-authored, rather than oscillating with each session's noise.
    """
    if variance <= config.difficulty_variance_trigger:
        return clamp(current)
    return clamp(current + config.difficulty_step)
