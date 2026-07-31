# CLAUDE.md — KnowledgeOS Project Context

> Read this file at the start of every session. It is the persistent memory for this project — the
> constitution, the architecture, the map of every artifact in this repo, and where the project
> currently stands. If anything you're about to do contradicts this file, stop and flag it rather
> than silently proceeding.

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
across six overlapping role tracks. KnowledgeOS is the tool that solves exactly that, and nothing else.

**Supported roles (v1), in the user's priority order:**
1. AI Research
2. AI Engineer
3. Data Science
4. Software Engineering
5. Product Management
6. Finance / Quantitative

**Explicitly NOT this project (do not build these features even if convenient):** an AI tutor, a notes
app, a flashcard system, a task manager, a calendar, a habit tracker, a general productivity app, or an
interview simulator.

---

## 2. The governing principle (read this twice)

> **Separate what the user actually knows (intrinsic) from what the system can currently trust
> (effective).** Intrinsic mastery is evidence — it is never modified by prerequisites, decay, or
> time. Only *effective* mastery reflects those. Nothing important exists only inside an LLM; the
> application owns all persistent truth. The LLM (external assessment engine) only returns
> structured observations — it never computes mastery, retention, readiness, priority, or
> recommendations. Every score the engine produces must be deterministic and reproducible: identical
> inputs always produce identical outputs.

This single distinction (intrinsic vs. effective) is why the calculation engine looks the way it does.
Do not "simplify" it away — a full architecture critique already stress-tested this design (see
`CALC_ENGINE_SPEC.md` header) and this was the conclusion.

---

## 3. Four-layer architecture

```
Layer 1 — Curriculum (static)         What SHOULD be known. A DAG. Independent of the user.
Layer 2 — Knowledge State (dynamic)   What the user currently knows. Overlays Layer 1, never
                                       mutates it. Changes ONLY via validated assessment evidence.
Layer 3 — Decision Engine (deterministic)  Mastery, retention, propagation, readiness, priority,
                                       recommendations. Pure functions. No LLM involved. No I/O.
Layer 4 — Assessment (external, replaceable)  Teaches/questions/evaluates. Talks to the app ONLY
                                       through two schemas (Schema A out, Schema B in).
```

Layer 3 (the engine) is the heart of the system and the hardest part to get right. Build it with
extreme care and test it against the golden example in `CALC_ENGINE_SPEC.md` §15 before trusting it.

---

## 4. Every artifact in this repo, and what it's for

Read these in this order the first time you touch the project.

| File | What it is | Authoritative for |
|---|---|---|
| `CLAUDE.md` | This file. | Project context, orientation, current state. |
| `KnowledgeOS_BUILD_PROMPT.md` | The master build specification. | Product principles, architecture, **data contracts (Schema A, Schema B, node, session-history)**, frontend principles, engineering rules, and the **9-stage gated build plan**. This is the spec you implement against. |
| `CALC_ENGINE_SPEC.md` | The deterministic calculation-engine spec. | **Every formula and default parameter** for Layer 3 — intrinsic mastery, retention/decay, prerequisite propagation, frontier detection, leverage, readiness, priority. Where this and the build prompt disagree on a formula, **this file wins** (the build prompt's Part F and C.5/C.8 were already updated to match it, but if you find a residual conflict, trust this file and fix the build prompt). |
| `CURRICULUM_BUILD_KIT.md` | The curriculum authoring contract. | The 16-section taxonomy, section→role coverage matrix, node/edge schema, importance/depth/edge-weight rubrics, and the dedup rules that keep shared concepts (Probability, DSA, Behavioral, etc.) as single multi-role nodes instead of duplicates. |
| `build_graph.py` | The curriculum graph generator + validator. | **The actual current curriculum**, expressed as Python data (`n(...)` node calls, `e(...)` edge calls) plus a validator that checks: unique section-prefixed node_ids, referential integrity on every edge, **acyclicity of the prerequisite subgraph** (Kahn's algorithm), no duplicate concepts, and in-range rubric values. Run `python3 build_graph.py` any time you touch it — it must print `ERRORS: 0` before you trust the output. |
| `curriculum_graph.json` | The full validated seed curriculum. | Output of `build_graph.py`. This is what Stage 6 loads. **245 nodes, 333 edges, 6 roles, 16 sections**, zero validation errors as of last generation. |
| `curriculum_fixture.json` | A small ~12-node connected test slice. | What Stage 1 loads first, before the full 245-node graph — spans Probability → Linear Algebra → Optimization → ML → Self-Attention with real cross-section prerequisites. |
| `.claude/agents/section-author.md` | Subagent definition. | Deepens ONE curriculum section in `build_graph.py`, self-validates, reports back. Used for expanding graph content, not for app code. |
| `.claude/agents/graph-integrator.md` | Subagent definition. | Runs after a wave of `section-author` subagents to reconcile duplicate concepts / dangling edges / cycles they may have introduced in isolation, and drive the validator to zero errors. |
| `DEEPEN_GRAPH.md` | Orchestration plan. | How to run `section-author` + `graph-integrator` in dependency-ordered **waves** to safely expand the graph further, if desired. Not required for the app to function — the current graph is already buildable. |

**If you are Claude Code reading this for the first time:** read `KnowledgeOS_BUILD_PROMPT.md` in full
next, then `CALC_ENGINE_SPEC.md` in full. Skim `CURRICULUM_BUILD_KIT.md` and `build_graph.py` to
understand the curriculum shape. You do not need to read `DEEPEN_GRAPH.md` or the agent files unless
asked to expand the graph.

---

## 5. Current project state (as of last update)

- **Design phase: complete.** Product spec, architecture, both schemas, the full deterministic-engine
  math (including the post-critique redesign — intrinsic/effective split, bottleneck readiness,
  frontier detection, learning cost, expected readiness gain), and the curriculum taxonomy are all
  finalized and internally consistent.
- **Curriculum graph: built and validated, not yet exhaustive.** 245 nodes / 333 edges across all 16
  sections and 6 roles. `python3 build_graph.py` currently prints `ERRORS: 0, WARNINGS: 0`. The four
  sections aligned with the user's top priorities — `dsa` (32 nodes), `deep-learning` (31),
  `post-training-llms` (30), `nlp-llms` (29) — have been deliberately deepened first. Thinner sections
  (`cs-fundamentals` 8, `ml-systems-mlops` 7, `behavioral` 6, `linear-algebra`/`calculus-optimization` 9
  each) are structurally sound but lower-depth; they cover the core sub-topics but not exhaustively.
- **No application code exists yet.** Stage 0 (repo scaffold + stack confirmation) has not started.
- **The external assessment engine (Layer 4) has not been designed yet.** The schemas it must honor
  (Schema A / Schema B) are fully specified in `KnowledgeOS_BUILD_PROMPT.md` C.7–C.8, but the actual
  prompt/skill that conducts an assessment session and emits a valid Schema B does not exist yet. This
  is a separate, standalone artifact — build it whenever convenient; it is not blocking Stages 0–3.

---

## 6. Engineering rules (non-negotiable, apply to every task)

**Surgical changes.** Touch only what the current task requires. Don't "improve" adjacent code or
formatting. Don't refactor what isn't broken. Match existing style even if you'd do it differently. If
you spot unrelated dead code, mention it — don't delete it. Remove only the imports/variables/functions
*your* change orphaned. Every changed line should trace directly to the current task.

**Goal-driven execution.** For every task, state explicit, checkable success criteria first, then
implement, then verify against them and loop until they pass. Don't declare a task done without
demonstrating the passing result.

**Gated stages.** Follow the 9-stage build plan in `KnowledgeOS_BUILD_PROMPT.md` Part H **in order**.
Do not start a stage until the previous stage's success criteria are met and its tests are green. Use
plan mode before each stage and get confirmation before writing code.

**Purity of the engine.** Layer 3 functions take state + inputs and return new values with no I/O.
Same inputs must always produce identical outputs. This is tested, not assumed.

**Evidence preservation.** Intrinsic mastery is never modified by prerequisites, decay, or time. The
`CALC_ENGINE_SPEC.md` §15 worked example (Probability → Bayes → Naive Bayes) must pass as a regression
test before Stage 3 is considered done.

---

## 7. Recommended stack (confirm at Stage 0, don't assume)

Backend: Python 3.12, FastAPI, Pydantic v2 (strict Schema A/B validation), SQLite, `networkx` for DAG
traversal/propagation, `pytest`. Frontend: React + Vite + TypeScript, React Flow or Cytoscape.js for the
graph-native home view. Rationale is in `KnowledgeOS_BUILD_PROMPT.md` Stage 0. If this doesn't fit,
raise it before writing code — not after.

---

## 8. Next steps, in order

1. **Stage 0.** Scaffold the repo per `KnowledgeOS_BUILD_PROMPT.md` Stage 0. Confirm the stack. Write
   `ARCHITECTURE.md`. Set up the empty test harness. No feature code yet.
2. **Stage 1.** Build the curriculum graph loader (Layer 1) against `curriculum_fixture.json` first —
   models, storage, DAG validators, query functions (by role / competency / ancestors / descendants /
   prerequisites-of / dependents-of). Only load the full `curriculum_graph.json` once the fixture-based
   tests pass.
2. **Stage 2.** Knowledge state overlay + append-only session history (Layer 2). Storage and retrieval
   only — no calculation yet.
3. **Stage 3 — the heart.** The deterministic engine (Layer 3), implemented exactly per
   `CALC_ENGINE_SPEC.md`'s pipeline (§1): observation → engine confidence/variance → intrinsic mastery
   → stability/retention → prerequisite confidence → effective mastery → frontier/critical-path →
   leverage/current-importance → bottleneck readiness → learning cost → expected readiness gain →
   priority → status → knowledge health. The §15 golden test must pass. Do not implement full FSRS —
   use the simple stability model in §6. Do not average for readiness — use the weighted harmonic mean
   in §11.
4. **Stage 4.** Schema A generation + Schema B validation/ingestion — the Layer 4 boundary.
5. **Stage 5.** Backend API over Layers 1–4.
6. **Stage 6.** Load the real `curriculum_graph.json` (245 nodes) as the seed curriculum.
7. **Stage 7.** Frontend: graph-first home (no dashboards), recommendations page (Overall / Role /
   Competency), node detail (Mastery + Importance by default, Advanced view for the rest), the
   Schema-A-copy → Schema-B-paste session loop.
8. **Stage 8.** End-to-end integration test of the full Core User Flow, README, done.

**Parallel/optional track, whenever convenient, not blocking the above:** design and build the external
assessment engine (Layer 4) — the actual prompt or Claude skill that conducts a session and emits a
valid Schema B. Also optional: use `DEEPEN_GRAPH.md` + the two subagents to expand the remaining thin
curriculum sections before Stage 6, if more depth is wanted before seeding.

---

## 9. If something seems inconsistent

This project went through an explicit architecture critique mid-design (documented in
`CALC_ENGINE_SPEC.md`'s header) that changed several original decisions: FSRS → simple stability model,
average readiness → bottleneck (harmonic mean) readiness, gap-ranking → expected-readiness-gain-per-cost
ranking, and the intrinsic/effective mastery split. If you encounter older language anywhere implying
the pre-critique design (e.g. "raw_mastery" instead of "intrinsic_mastery", or readiness-as-average),
the newer design in `CALC_ENGINE_SPEC.md` is correct — fix the inconsistency and move on, don't ask
which one to use.
