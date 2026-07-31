"""Pipeline stage 13 — status derivation. CALC_ENGINE_SPEC.md §13.

Status is always derived from evidence and never set by hand.

## A deliberate deviation from the spec's stated evaluation order

The spec lists the tiers as `unassessed → learning → practiced → retained → mastered` and says
"evaluate top-down; first match wins". Taken literally that is wrong: `retained` requires
EM ≥ 0.70 and `mastered` requires EM ≥ 0.85, so a genuinely mastered node matches `retained`
first and can never be reported as mastered.

Resolved by evaluating **most demanding first** — which is plainly the intent, since the tiers
are otherwise a ladder:

    unassessed  (no evidence at all, so nothing else can apply)
    learning    (evidence is weak OR too inconsistent to trust)
    mastered
    retained
    practiced

`learning` stays ahead of the strong tiers on purpose. Its σ² clause means "the observations
disagree with each other"; a node whose evidence is self-contradictory should not be reported
as retained regardless of how high the average looks. `mastered` already demands low variance,
so it is unaffected.
"""

from __future__ import annotations

from knowledgeos.state import Status

from .config import DEFAULT_CONFIG, EngineConfig


def derive_status(
    *,
    effective_mastery: float,
    retention: float,
    variance: float,
    session_count: int,
    target: float,
    config: EngineConfig = DEFAULT_CONFIG,
) -> Status:
    """The node's status given its current evidence."""
    if session_count == 0:
        return Status.UNASSESSED

    if (
        effective_mastery < config.status_learning_em
        or variance > config.status_learning_variance
    ):
        return Status.LEARNING

    enough_sessions = session_count >= config.status_min_sessions

    if (
        effective_mastery >= max(config.status_mastered_em, target)
        and retention >= config.status_mastered_retention
        and variance <= config.status_mastered_variance
        and enough_sessions
    ):
        return Status.MASTERED

    if (
        effective_mastery >= config.status_practiced_em
        and retention >= config.status_retained_retention
        and enough_sessions
    ):
        return Status.RETAINED

    return Status.PRACTICED
