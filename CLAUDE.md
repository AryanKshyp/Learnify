# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **This file is the constitution: principles, boundaries, and rules that do not change as work
> progresses.** It should almost never need editing. Volatile facts — what stage we're on, node
> counts, known issues, what to do next — live in [PROJECT_STATE.md](PROJECT_STATE.md). System design
> lives in [ARCHITECTURE.md](ARCHITECTURE.md). If something here contradicts what you're about to do,
> stop and flag it rather than silently proceeding.

**Read at session start:** this file → [PROJECT_STATE.md](PROJECT_STATE.md) (where things stand).
Then, as the task requires: [ARCHITECTURE.md](ARCHITECTURE.md) for system design,
[BUILD_SPEC.md](BUILD_SPEC.md) for contracts and the staged plan,
[CALC_ENGINE_SPEC.md](CALC_ENGINE_SPEC.md) in full before touching the engine.

---

## 1. What this project is

**KnowledgeOS** is a personal interview-preparation operating system. It maintains a persistent,
evidence-based model of the user's knowledge across six target roles, detects gaps and prerequisite
weaknesses, models forgetting over time, and recommends what to study next to maximize interview
readiness — optimizing **expected readiness gain per unit learning effort**, not just "close the
biggest gap."

**Origin:** the user was rejected from 15+ internship interviews despite having "studied everything."
The real failure was never knowing *what* was missing, never detecting prerequisite gaps, having no
objective measure of actual knowledge, forgetting over time, and not knowing what to study next —
across six overlapping role tracks. KnowledgeOS solves exactly that, and nothing else.

**Supported roles (v1), in priority order:** AI Research (1) · AI Engineer (2) · Data Science (3) ·
Software Engineering (4) · Product Management (5) · Finance / Quantitative (6).

**Explicitly NOT this project — do not build these even if convenient:** an AI tutor, notes app,
flashcard system, task manager, calendar, habit tracker, general productivity app, or interview
simulator.

---

## 2. The governing principle (read this twice)

> **Separate what the user actually knows (intrinsic) from what the system can currently trust
> (effective).** Intrinsic mastery is evidence — it is never modified by prerequisites, decay, or
> time. Only *effective* mastery reflects those. Nothing important exists only inside an LLM; the
> application owns all persistent truth. The LLM (external assessment engine) only returns
> structured observations — it never computes mastery, retention, readiness, priority, or
> recommendations. Every score the engine produces must be deterministic and reproducible: identical
> inputs always produce identical outputs.

This single distinction is why the calculation engine looks the way it does. Do not "simplify" it
away — a full architecture critique already stress-tested this design and this was the conclusion.

---

## 3. Product principles (non-negotiable)

1. **Single source of truth.** The application owns every piece of persistent information.
2. **External assessment.** Teaching, questioning, and evaluation happen outside the app.
3. **Deterministic backend.** The LLM never calculates mastery, retention, readiness,
   recommendations, or priorities.
4. **Shared knowledge.** Each concept exists exactly once, with per-role importance and depth.
   Never duplicate a concept.
5. **Knowledge requires evidence.** Reading, watching, or "feeling ready" never changes mastery.
   Only a validated assessment session does.
6. **Explainability.** Every recommendation answers "why was this recommended?"; every score answers
   "how was this calculated?" and is reproducible from stored evidence.

---

## 4. Architecture in one screen

```
Layer 1 — Curriculum (static)         What SHOULD be known. A DAG. Independent of the user.
Layer 2 — Knowledge State (dynamic)   What the user knows. Overlays L1, never mutates it.
                                       Changes ONLY via validated assessment evidence.
Layer 3 — Decision Engine             Mastery, retention, propagation, readiness, priority.
          (deterministic)              Pure functions. No LLM. No I/O.
Layer 4 — Assessment (external)       Teaches/questions/evaluates. Talks to the app ONLY
                                       through Schema A (out) and Schema B (in).
```

Layer 3 is the heart and the hardest part to get right. Build it with extreme care and test it
against the `CALC_ENGINE_SPEC.md` §15 golden example before trusting it.

Full detail — layer import rules, contract map, pipeline ordering, stack: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## 5. Document map and authority order

| File | Authoritative for |
|---|---|
| `CLAUDE.md` | This constitution: principles, rules, boundaries. |
| `PROJECT_STATE.md` | Current stage, decisions log, known issues, next actions. **Volatile.** |
| `ARCHITECTURE.md` | System design, layer boundaries, repo layout, confirmed stack. |
| `BUILD_SPEC.md` | The master build spec — data contracts (Schema A/B, node, state, history) and the 9-stage gated build plan. |
| `CALC_ENGINE_SPEC.md` | **Every formula and default parameter** for Layer 3. |
| `CURRICULUM_BUILD_KIT.md` | Curriculum authoring contract: taxonomy, rubrics, dedup rules. |
| `build_graph.py` | The actual curriculum content, as Python data + validator. |
| `DEEPEN_GRAPH.md` | Optional: orchestration for expanding the graph via subagents. |
| `knowledgeos-research.md` | Supporting bibliography. Reference only — not a spec. |

**When two documents disagree:**
`CALC_ENGINE_SPEC.md` (math) → `BUILD_SPEC.md` (contracts & behavior) →
`ARCHITECTURE.md` (structure) → everything else.

---

## 6. Commands

**Curriculum (repo root):**
```bash
python build_graph.py     # regenerate + validate curriculum_graph.json.
                          # Must print "ERRORS: 0" before you trust the output.
                          # Validates: unique section-prefixed node_ids, referential integrity,
                          # prerequisite-DAG acyclicity (Kahn), duplicate concepts, rubric ranges.
python make_fixture.py    # regenerate curriculum_fixture.json as an exact, edge-closed subset
                          # of curriculum_graph.json. Re-run after changing the graph.
```

**Backend (`cd backend`, venv activated — Python 3.12):**
```bash
pytest                    # test suite
pytest -k <pattern>       # a single test / subset
ruff check .              # lint
lint-imports              # enforce the ARCHITECTURE.md layer boundaries
```

Run all four before considering a stage done. `lint-imports` is the machine check on Layer 3's
purity — it fails the build if the engine imports storage, transport, a clock, or randomness.

Setup steps are in [backend/README.md](backend/README.md). Frontend does not exist until Stage 7.

---

## 7. Engineering rules (apply to every task)

**Surgical changes.** Touch only what the current task requires. Don't "improve" adjacent code or
formatting. Don't refactor what isn't broken. Match existing style even if you'd do it differently.
If you spot unrelated dead code, mention it — don't delete it. Remove only the
imports/variables/functions *your* change orphaned. Every changed line should trace directly to the
current task.

**Goal-driven execution.** State explicit, checkable success criteria first, then implement, then
verify against them and loop until they pass. Never declare a task done without showing the passing
result.

**Gated stages.** Follow the 9-stage plan in `BUILD_SPEC.md` Part H **in order**. Do
not start a stage until the previous stage's success criteria are met and its tests are green. Plan
before each stage and get confirmation before writing code.

**Purity of the engine.** Layer 3 functions take state + inputs and return new values with no I/O.
Time is an input parameter, never read from a clock inside a formula. Same inputs must always produce
identical outputs. This is tested, not assumed.

**Evidence preservation.** Intrinsic mastery is never modified by prerequisites, decay, or time. The
`CALC_ENGINE_SPEC.md` §15 worked example (Probability → Bayes → Naive Bayes) must pass as a
regression test before Stage 3 counts as done.

**Config, not constants.** Every `[TUNABLE]` parameter lives in one config module. No numeric literal
inline in engine logic.

**Schema discipline.** Every schema is versioned. Validation is strict and fails loudly with precise
messages. Never silently coerce or drop unknown fields on Schema B ingestion.

---

## 8. If something seems inconsistent

This project went through an explicit architecture critique mid-design that changed several original
decisions:

| Rejected | Correct |
|---|---|
| full FSRS | simple exponential stability model |
| readiness as average | bottleneck / weighted harmonic mean |
| rank by biggest gap | rank by expected readiness gain per unit cost |
| single `raw_mastery` | `intrinsic_mastery` vs. `effective_mastery` split |

If you encounter older language implying the pre-critique design, `CALC_ENGINE_SPEC.md` is correct —
**fix the inconsistency and move on; don't ask which one to use.** Note the fix in
`PROJECT_STATE.md` so the correction is visible.
