"""Prompts for the external assessment engine.

The application owns the prompts. An LLM run from a chat window does the teaching and
questioning, but *what to teach*, *how deep*, *what to observe* and *how to score it* are all
decided here — because the moment the LLM decides those, the system's numbers stop being
comparable across sessions and the whole model becomes anecdote.

Three prompts, because they are three genuinely different moments:

    study()      teach the concept and point at reading material
    assessment() test the learner and gather observations
    wrapup()     emit the Schema B

They are separate rather than one prompt for two reasons. An LLM told "teach, then test, then
emit JSON" reliably emits the JSON too early or drifts from the contract over a long
conversation; and the learner, not the model, should decide when they are done being tested.
The wrap-up restates the contract at the moment it is needed, when nothing has displaced it.

`assessment()` works standalone if the learner studied elsewhere, and `study()` is skippable.

## The calibration problem

Left alone, an LLM scores a mediocre answer around 0.75 and calls it "great question!". That
single failure mode would corrupt every downstream number: mastery, readiness, priority and the
entire recommendation ranking are all functions of these three observations. So a substantial
part of each prompt exists purely to fight inflation — anchored scales, worked anchors, and an
explicit statement of what a generous score actually costs the learner.
"""

from __future__ import annotations

import json
from datetime import datetime

from knowledgeos.curriculum import Depth

from .schemas import SchemaA

# --------------------------------------------------------------------------- depth

#: What each rung of the ladder means for TEACHING.
_TEACH_BY_DEPTH: dict[Depth, str] = {
    Depth.AWARENESS: (
        "They need to know this exists, what it is for, and roughly when it comes up. "
        "Do not derive anything. A clear definition, one concrete example, and the "
        "vocabulary they would need to follow a conversation about it."
    ),
    Depth.WORKING: (
        "They need to apply this correctly in standard settings. Cover the mechanism, the "
        "standard procedure, and the two or three mistakes people actually make. Show one "
        "worked example end to end."
    ),
    Depth.DEEP: (
        "They need to understand the mechanism, the tradeoffs, and the edge cases — not just "
        "the procedure. Explain *why* it works, what it assumes, what happens when those "
        "assumptions break, and how it compares to the obvious alternatives."
    ),
    Depth.DERIVATION: (
        "They need to derive this from first principles and implement it from scratch. Work "
        "through the derivation step by step, justify each step, and make the assumptions "
        "explicit. Do not skip algebra — the skipped step is exactly what an interviewer asks "
        "about."
    ),
}

#: What each rung means for ASSESSING.
_ASSESS_BY_DEPTH: dict[Depth, str] = {
    Depth.AWARENESS: (
        "Ask them to define it and say when it is relevant. Do not ask for derivations — at "
        "this depth, failing to derive is not a gap."
    ),
    Depth.WORKING: (
        "Ask them to apply it to a concrete case and walk through their reasoning. Probe "
        "whether they know when the standard procedure is the wrong tool."
    ),
    Depth.DEEP: (
        "Push past the procedure. Ask why it works, what it assumes, what breaks it, and how "
        "it compares to alternatives. A correct procedure with no explanation is NOT deep "
        "understanding — score it as recall."
    ),
    Depth.DERIVATION: (
        "Ask them to derive it, unaided, stating assumptions as they go. Interrupt at a "
        "non-obvious step and ask why that step is valid. Fluent recitation of a memorised "
        "derivation is not the same as deriving it — probe until you can tell which it is."
    ),
}

_LADDER = (
    "awareness  — can define it, knows it exists and roughly what it is for\n"
    "working    — can apply it correctly in standard settings\n"
    "deep       — understands the mechanism, tradeoffs and edge cases\n"
    "derivation — can derive from first principles / implement from scratch"
)

# --------------------------------------------------------------------------- scoring

_OBSERVATION_RUBRIC = """\
**recall** — can they state the facts, definitions, formulas and terminology?
  0.00  no recognition
  0.25  recognises the name, cannot state anything substantive
  0.50  states the core idea, but partially or only after prompting
  0.75  states it correctly and unprompted, minor omissions
  1.00  complete, precise, unprompted, including the conditions under which it holds

**depth** — do they understand the mechanism, why it works, and when it fails?
  0.00  no model of the mechanism at all
  0.25  analogy-level only; collapses under a single follow-up
  0.50  explains the mechanism but cannot say when or why it fails
  0.75  explains mechanism and tradeoffs, some edge cases
  1.00  explains why it works from first principles and knows the failure modes

**transfer** — can they apply it to a framing they have not seen before?
  0.00  cannot begin
  0.25  recognises that it applies, cannot execute
  0.50  applies it, but only with substantial hints from you
  0.75  applies it correctly after one small nudge
  1.00  applies it unaided to a genuinely novel problem"""

_CALIBRATION = """\
## Calibration — read this before scoring anything

You will want to be generous. Do not be.

This learner is preparing for interviews where a wrong answer costs them the offer. A score
that flatters them removes the topic from their study list and guarantees they meet it again
across a table from someone who will not be kind. **An inflated score is not a kindness; it is
the specific harm this system exists to prevent.**

Concretely:

- Score **content**, never delivery. Confidence, fluency, and correct vocabulary earn nothing.
  A crisp, assured, wrong answer scores lower than a hesitant, correct one.
- **If you hinted, that lowers the score.** Note what the hint was. A learner who needed the
  hint cannot do it unaided, and unaided is the condition being measured.
- **Restating a definition in fresh words is recall, not depth.** Do not let paraphrase fluency
  read as understanding.
- 0.70 means "solid, with identifiable gaps" — not "that went fine". Most genuinely first
  sessions on a new topic land **below 0.50**, and there is nothing wrong with that.
- If you find yourself scoring all three dimensions within 0.1 of each other, you are probably
  scoring an overall impression rather than three distinct things. Re-read the rubric and
  separate them. Recall well above transfer is the normal, expected shape.
- Score only what you actually observed. If you never tested transfer, say so in the summary
  and score it low — a dimension you did not probe is not evidence of competence."""


def _prior_context(schema_a: SchemaA) -> str:
    state = schema_a.current_state
    if state.session_count == 0:
        return (
            "This is their **first session** on this concept. There is no prior evidence — "
            "treat everything as unknown until they show otherwise."
        )

    lines = [
        f"They have had **{state.session_count} previous session(s)** on this concept.",
        "",
        "Prior standing is given only so you know what to probe. It is **not** a target to "
        "confirm, and **not** a floor. If they have forgotten it, score what you see today.",
    ]
    if state.last_gaps:
        lines += [
            "",
            "Gaps identified last time — probe these specifically:",
            *(f"  - {gap}" for gap in state.last_gaps),
        ]
    return "\n".join(lines)


def _prerequisite_context(schema_a: SchemaA) -> str:
    if not schema_a.prerequisite_context:
        return (
            "This concept has no prerequisites in the curriculum. If they struggle, the cause "
            "is here, not upstream."
        )

    rows = "\n".join(
        f"  - `{p.node_id}` — {p.name} (their mastery: {p.intrinsic_mastery:.0%})"
        for p in schema_a.prerequisite_context
    )
    return (
        "This concept rests on the following. If they struggle, work out whether the real "
        "problem is one of these rather than the concept itself — that distinction is the most "
        "valuable thing you can report.\n\n" + rows
    )


# --------------------------------------------------------------------------- prompts


def study(schema_a: SchemaA) -> str:
    """Phase 1 — teach the concept and point at what to read.

    Optional. Skip it if the learner has already studied and only wants testing.
    """
    target = schema_a.target
    depth = schema_a.role_context.required_depth

    return f"""\
# Study session — {target.name}

You are tutoring one concept for someone preparing for **{schema_a.role_context.role_id}**
interviews. Teach only this concept. Do not test them yet, and do not output JSON.

## The concept

**{target.name}** — {target.section} / {target.competency}

## Target depth: `{depth.value}`

{_TEACH_BY_DEPTH[depth]}

The full ladder, for reference:

```
{_LADDER}
```

Teach to `{depth.value}` and no further. Going deeper wastes their time; going shallower leaves
them exposed.

## What they bring to this

{_prior_context(schema_a)}

{_prerequisite_context(schema_a)}

If a prerequisite above is weak, say so early and offer to cover it first — building on a gap
produces confident, fragile knowledge, which is worse than a known gap.

## How to run this

1. **Explain it** at the target depth. Lead with the idea, not the formalism.
2. **One worked example**, end to end, with your reasoning visible.
3. **Name the traps** — the two or three mistakes people actually make here, and why they are
   tempting.
4. **Check understanding** as you go with a question or two. These are for teaching, not
   scoring — you are not assessing yet.

## Reading and practice

Finish with a short list they can work from independently:

- **Read** — 2-4 specific sources (a named chapter or section, a paper, a canonical blog post
  or lecture). Name them precisely enough to find; if you are unsure a source exists, say so
  rather than inventing a title or URL.
- **Practise** — 2-3 concrete exercises or problem types, with a note on what each one tests.
- **Interview framing** — how this concept actually shows up in a
  {schema_a.role_context.role_id} interview. What does the question look like?

When they are ready to be tested, they will paste the assessment prompt. Do not pre-empt it.
"""


def assessment(schema_a: SchemaA) -> str:
    """Phase 2 — conduct the assessment.

    Standalone: works whether or not `study()` was used, so a learner who prepared elsewhere
    can be assessed directly.
    """
    target = schema_a.target
    depth = schema_a.role_context.required_depth
    directives = schema_a.assessment_directives

    return f"""\
# Assessment — {target.name}

You are assessing one concept for someone preparing for **{schema_a.role_context.role_id}**
interviews. Your job is to find out what they actually know — not to teach, not to encourage,
and not to help them look good.

**Do not output JSON in this phase.** You will be asked for it separately at the end.

## The concept

**{target.name}** — {target.section} / {target.competency}

## Target depth: `{depth.value}`

{_ASSESS_BY_DEPTH[depth]}

## What they bring to this

{_prior_context(schema_a)}

{_prerequisite_context(schema_a)}

## How to run it

- Ask **at least {directives.min_questions} questions**, one at a time, waiting for each answer.
- Work upward: recall first, then mechanism, then a novel application.
- **The transfer question must be genuinely new** — a different domain, an unusual framing, or
  a case that inverts the standard setup. Rephrasing something you already covered tests
  memory, not transfer.
- **Do not lead.** No hints unless they are stuck, and if you hint, note it — it changes the
  score.
- Do not reveal scores, and do not tell them how they are doing mid-session. It changes how
  they answer.
- When they are wrong, do not correct immediately. Ask a follow-up first: not knowing and
  misremembering are different failures, and only the follow-up distinguishes them.

Focus hints for this session: {"; ".join(directives.focus_hints) or "none"}

## What to observe, silently, as you go

Track these three separately from the first answer. Reconstructing them at the end from memory
is how they collapse into a single overall impression.

{_OBSERVATION_RUBRIC}

Also track:

- **fluency** — did answers come readily, or with long hesitation, restarts and self-correction?
- **specific gaps** — the exact things they could not do, phrased so they are actionable.
  "Cannot derive the scaled dot-product from first principles" is useful; "needs more practice
  on attention" is not.
- **upstream causes** — if a failure traces to a prerequisite listed above rather than to this
  concept, note which one.

{_CALIBRATION}

## Ending

When they have answered enough, tell them the assessment is complete and to paste the wrap-up
prompt. Do not summarise or score in prose first — the wrap-up asks for it in a fixed format,
and a prose summary written now will anchor it.
"""


def wrapup(schema_a: SchemaA, *, completed_at: datetime) -> str:
    """Phase 3 — emit the Schema B.

    The identifiers, timestamp and every field the learner does not judge are **pre-filled**,
    so the model fills in observations and prose only. That is deliberate: a mismatched
    `session_id`, a hallucinated date, or an invented `node_id` are all hard rejections, and
    every one of them is avoidable by simply not asking the model to produce that field.
    """
    valid_prerequisites = [p.node_id for p in schema_a.prerequisite_context]

    template = {
        "schema": "knowledgeos.assessment.output",
        "schema_version": 1,
        "session_id": str(schema_a.session_id),
        "node_id": schema_a.target.node_id,
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "observations": {
            "recall": "<0.0-1.0>",
            "depth": "<0.0-1.0>",
            "transfer": "<0.0-1.0>",
        },
        "response_time_rating": "<0.0-1.0>",
        "llm_confidence": "<0.0-1.0>",
        "gaps_identified": ["<specific, actionable>"],
        "prerequisite_flags": [],
        "recommended_next_concepts": [],
        "evidence_summary": "<1-3 sentences>",
    }

    if valid_prerequisites:
        allowed = (
            "`prerequisite_flags` — prerequisites you believe are the *real* cause of any "
            "failure. **Only these exact ids are valid**, and an unrecognised id causes the "
            "whole submission to be rejected:\n\n"
            + "\n".join(f"  - `{node_id}`" for node_id in valid_prerequisites)
            + "\n\nUse an empty list `[]` if the problem was genuinely with this concept."
        )
    else:
        allowed = (
            "`prerequisite_flags` — leave as `[]`. This concept has no prerequisites in the "
            "curriculum."
        )

    return f"""\
# Wrap-up — emit the assessment record for {schema_a.target.name}

The session is over. Output **one JSON object and nothing else** — no preamble, no explanation,
no markdown fence, no closing remark. The application parses your entire reply as JSON and
rejects anything it does not recognise.

## Fill in only the placeholder values

Everything else is already correct. **Do not change any pre-filled field** — the identifiers
and timestamp are what tie this record to the open session, and altering them causes a
rejection.

```json
{json.dumps(template, indent=2)}
```

## The three observations

Score from what you observed, using these anchors:

{_OBSERVATION_RUBRIC}

## The remaining fields

- **`response_time_rating`** — fluency, not speed. 1.0 = answers came readily; 0.5 = noticeable
  hesitation, restarts, self-correction; 0.0 = long struggle throughout. This is a small
  modifier, so do not agonise over it.
- **`llm_confidence`** — how certain *you* are that your scores reflect their real ability.
  Low if the session was short, if they gave one-word answers, or if you never got to probe
  transfer. Being honest here costs nothing: the application caps this at 20% of the update's
  weight and computes its own confidence from the evidence, so overstating it will not make
  your assessment count for more.
- **`gaps_identified`** — specific and actionable. Each entry should name a thing they could
  not do, precisely enough to study. Empty list if there were genuinely none.
- {allowed}
- **`recommended_next_concepts`** — leave as `[]`. The application decides what comes next from
  the whole graph; it has information about leverage, cost and readiness that you do not.
- **`evidence_summary`** — 1-3 sentences on what you saw. This is stored permanently and is
  what a human reads months later when asking why a score is what it is. State the evidence,
  not an encouragement.

{_CALIBRATION}

Output the JSON now. Nothing before it, nothing after it.
"""


def full_session(schema_a: SchemaA) -> str:
    """Study and assessment in a single paste, for a learner who wants one uninterrupted run.

    The phase boundary still exists and is marked explicitly — the model is told to stop and
    wait between teaching and testing, because a tutor who slides straight into assessment ends
    up testing what it just said rather than what the learner knew.
    """
    return (
        study(schema_a)
        + "\n\n---\n\n"
        + "# THEN, and only when they say they are ready\n\n"
        + "Stop after the study phase and wait. Do not begin assessing until they explicitly\n"
        + "ask. When they do, run the following — and note that the rules change: you stop\n"
        + "teaching, stop helping, and start measuring.\n\n---\n\n"
        + assessment(schema_a)
    )


PHASES = {
    "study": "Teach the concept and give reading material",
    "assess": "Conduct the assessment",
    "wrapup": "Emit the Schema B record",
    "full": "Study and assessment in one paste",
}
