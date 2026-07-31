# ARCHITECTURE.md — KnowledgeOS

System design, layer boundaries, and the decisions locked at Stage 0.

This document describes **how the system is built**. It is stable: it changes only when the
architecture itself changes, not when work progresses. For *what should be known* read
[BUILD_SPEC.md](BUILD_SPEC.md) and [CALC_ENGINE_SPEC.md](CALC_ENGINE_SPEC.md); for
*where the project currently stands* read [PROJECT_STATE.md](PROJECT_STATE.md).

---

## 1. Repository layout

`d:\Learnify` is the project root and the git repository. Design documents, the curriculum
generator, and application code all live here.

```
d:\Learnify\
├── CLAUDE.md                     # durable constitution — read first
├── ARCHITECTURE.md               # this file
├── PROJECT_STATE.md              # volatile: current stage, decisions, known issues
│
├── BUILD_SPEC.md                 # master spec: data contracts + 9-stage build plan
├── CALC_ENGINE_SPEC.md           # authoritative for every Layer 3 formula
├── CURRICULUM_BUILD_KIT.md       # curriculum authoring contract
├── DEEPEN_GRAPH.md               # optional: graph-expansion orchestration
├── knowledgeos-research.md       # supporting bibliography (reference only)
│
├── build_graph.py                # curriculum generator + validator
├── curriculum_graph.json         # generated seed curriculum (Stage 6)
├── curriculum_fixture.json       # small connected slice (Stages 1–3)
│
└── .claude/agents/               # section-author, graph-integrator subagents
```

**Planned scaffold** (Stage 0, not yet created) — folder names mirror the four layers so a boundary
violation is visible as a bad import:

```
backend/
├── knowledgeos/
│   ├── curriculum/   # L1 — static DAG: models, loader, validators, queries
│   ├── state/        # L2 — knowledge-state overlay + append-only session history
│   ├── engine/       # L3 — pure deterministic calculation; NO I/O
│   │   └── config.py #      every [TUNABLE] parameter, in one place
│   ├── assessment/   # L4 boundary — Schema A generation, Schema B validation/ingest
│   └── api/          # FastAPI routers over L1–L4
├── tests/
└── pyproject.toml

frontend/             # Stage 7 — React + Vite + TypeScript
```

---

## 2. The two-graph separation (foundational)

Two graphs that are **never merged** — roads versus traffic:

| | Static Knowledge Graph | Dynamic Knowledge State |
|---|---|---|
| Holds | nodes, edges, per-role importance/depth | per-node user values |
| Changes | only when curriculum is authored | only via validated assessment evidence |
| Owner | Layer 1 | Layer 2 |

The engine **reads both and writes only Knowledge State**. It never mutates the Knowledge Graph.
User activity has no side effect on the curriculum, ever.

---

## 3. The four layers

```
Layer 1 — Curriculum (static)          What SHOULD be known. A DAG. User-independent.
        │  overlaid by
Layer 2 — Knowledge State (dynamic)    What the user currently knows. Never mutates L1.
        │  consumed by
Layer 3 — Decision Engine              Pure deterministic functions. No LLM. No I/O.
        │                              → recommendations, readiness, priorities
        ▲
        │  Schema A (out) ────────►    Layer 4 — Assessment (external, replaceable)
        │  Schema B (in)  ◄────────    Teaches / questions / evaluates.
```

### Layer 1 — Curriculum (static)
A **DAG, not a tree**: a node may have multiple parents, and roles reference shared nodes. Defines
roles, sections, competencies, assessable nodes, prerequisite edges, per-role importance and
required depth.

*Hard invariant:* the `prerequisite` subgraph is acyclic. Loading must **reject** a curriculum whose
prerequisite edges form a cycle, naming the cycle path.

*Hard invariant:* each concept exists **exactly once**. A concept serving several roles is one node
with multiple entries in `roles[]` — never `prob-bayes-for-ai` plus `prob-bayes-for-finance`.

### Layer 2 — Knowledge State (dynamic)
One state record per node, overlaying the curriculum. Evolves **only** through validated assessment
evidence — reading, watching, or feeling ready never changes mastery. Session history is
**append-only**, and replaying it through the engine must reproduce current state exactly.

### Layer 3 — Decision Engine (deterministic) — the heart
Owns mastery, retention/decay, prerequisite propagation, readiness, priority, recommendations.
Implemented strictly per `CALC_ENGINE_SPEC.md`. Pure: state in, values out, no I/O.

### Layer 4 — Assessment (external, replaceable)
Teaches, questions, evaluates. Communicates **only** through two schemas. KnowledgeOS knows nothing
about how it works and must function against any engine honoring the contracts. It returns
*structured observations* — it never computes mastery, retention, readiness, priority, or
recommendations.

---

## 4. Layer boundaries as import rules

The boundary is enforceable in code review as a dependency rule:

| Module | May import | May **not** import |
|---|---|---|
| `curriculum/` | — | anything internal |
| `state/` | `curriculum` (types) | `engine`, `api` |
| `engine/` | `curriculum` + `state` **types only** | any storage, DB, HTTP, clock, or filesystem |
| `assessment/` | `curriculum`, `state`, `engine` | `api` |
| `api/` | all of the above | — |

The critical rule: **`engine/` imports no I/O of any kind.** Time is an *input parameter*, never
`datetime.now()` read inside a formula — otherwise determinism dies silently.

---

## 5. Data contracts — where each one is authoritative

All contracts live in `BUILD_SPEC.md` Part C. Storage representation is an implementation choice,
but must round-trip these losslessly. All scores are floats in `[0,1]` unless noted; timestamps are
ISO-8601 UTC; IDs are stable slugs, never array indices.

| Contract | Section | Notes |
|---|---|---|
| Curriculum node | C.1 | `node_id` prefixed with section abbreviation |
| Curriculum edge | C.2 | `prerequisite` \| `part_of`; prerequisite subgraph acyclic |
| Role | C.3 | fixed 6-role registry with `priority_rank` |
| Depth ladder | C.4 | `awareness` < `working` < `deep` < `derivation` |
| Knowledge state | C.5 | per node; every derived field engine-computed |
| Session history | C.6 | append-only; replayable |
| **Schema A** (out) | C.7 | app → assessment engine |
| **Schema B** (in) | C.8 | assessment engine → app; the *only* way state changes |

Schema B validation is **strict and hard-fails**: matching `session_id`/`node_id`, all observation
values present and in `[0,1]`, referenced node ids must exist. Never silently coerce or drop fields.

---

## 6. The engine pipeline (canonical ordering)

Every recompute runs in this exact order; each stage is a pure function of the previous. Never
compute `EM` before `PC`, nor readiness before `EM`.

```
Schema B
  1. Observation model             → O        session ability
  2. Engine confidence & variance  → C, σ²    engine-owned, NOT the LLM's
  3. Intrinsic mastery update      → M        evidence; never destroyed
  4. Stability & retention         → S, R(t)  simple forgetting, NOT full FSRS
  5. Prerequisite confidence       → PC       topological order over the DAG
  6. Effective mastery             → EM = M · R · PC
  7. Frontier & critical path      → is_frontier, CPV
  8. Leverage & current importance  → Lev, CurImp
  9. Readiness (bottleneck)        → Readiness_r   weighted harmonic mean
 10. Learning cost                 → Cost
 11. Expected readiness gain       → ERG
 12. Priority & recommendations    → Priority, MMR-diversified top-N
 13. Status derivation             → status
 14. Knowledge health              → Health
```

Stages 1–4 run for the assessed node only. Stages 5–14 run for that node plus every node whose value
could change. Stages 5–12 are also the **read path** answering "what should I study next?" with no
new assessment.

### The three method choices that were deliberately settled
A mid-design architecture critique changed these. The newer choice is correct; older language
implying the earlier design is a bug to fix, not a question to ask.

| Concern | Rejected | **Chosen** | Why |
|---|---|---|---|
| Forgetting | full FSRS | simple exponential stability | sessions are discussions, not flashcard flips; debuggable |
| Readiness | average | **weighted harmonic mean** | interviews punish bottlenecks — 100/100/15 fails but averages 72 |
| Ranking | biggest gap | **expected readiness gain per unit cost** | effort is the scarce resource |
| Mastery | one score | **intrinsic vs. effective split** | never destroy evidence |

---

## 7. The governing invariant

> **Intrinsic mastery (`M`) is evidence. It is never modified by prerequisites, decay, or time.
> Only effective mastery (`EM = M · R · PC`) reflects those.**

This is why the engine looks the way it does. Do not "simplify" it away.

The consequence that makes it worth the complexity: when `Probability` decays, `Naive Bayes` becomes
*less trustworthy* (`EM` collapses) without losing its own evidence — and restudying `Probability`
restores every dependent automatically, **with zero reassessment**. The `CALC_ENGINE_SPEC.md` §15
worked example (Probability → Bayes → Naive Bayes) encodes this as the golden regression test.

---

## 8. Cross-cutting guarantees

- **Purity.** Engine functions take state + inputs, return new values, perform no I/O. Same inputs ⇒
  identical outputs. Tested, not assumed.
- **Explainability.** Every produced value (`M`, `R`, `EM`, `Readiness_r`, `Priority`) returns a
  `computation_trace` — inputs, parameters, intermediate terms — persisted in session history (C.6)
  and surfaced in the Advanced view.
- **Config, not constants.** Every `[TUNABLE]` parameter lives in one config module. No numeric
  literal appears inline in engine logic.
- **Schema discipline.** Every schema carries `schema_version`. Validation fails loudly and precisely.
- **Replayability.** State is reconstructible by replaying append-only history through the engine.

---

## 9. Frontend principles (Stage 7)

- The **knowledge graph is the primary interface**, not a dashboard. Home renders the interactive
  graph; analytics is never the landing surface.
- Role / Competency / Concept are **lenses over one graph**, not separate data.
- **Recommendations live on their own page**, grouped Overall / Role / Competency.
- A node shows **Mastery + Importance only** by default; everything else (retention, stability,
  effective vs. intrinsic, next review, trace) sits behind an **Advanced** view.
- Session loop: node → *Generate & copy Schema A* → *Paste Schema B* → confirm → state updates.
  One paste, parsed automatically. **No manual number entry anywhere.**

---

## 10. Stack — confirmed at Stage 0

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| API | FastAPI |
| Validation | Pydantic v2 (strict Schema A/B) |
| Storage | **PostgreSQL** |
| Graph ops | `networkx` (in-memory DAG traversal/propagation) |
| Tests | `pytest` |
| Frontend | React + Vite + TypeScript, React Flow *(revisit at Stage 7)* |

**Rationale.** Pydantic v2 makes strict Schema A/B validation first-class, which is the sharpest
boundary in the system. `networkx` gives ancestors/descendants/topological-sort for free — exactly
the operations prerequisite propagation needs. FastAPI's typed models and generated OpenAPI keep the
API honest against the contracts.

### Deviation from spec: PostgreSQL instead of SQLite
`BUILD_SPEC.md` Stage 0 recommends SQLite on the grounds that this is a single-user local tool. The
stated end state is **multi-user on Supabase**, and Supabase *is* Postgres — so developing on
Postgres from the start makes that migration a deployment change rather than a port. Building on
SQLite first would mean rewriting migrations and reworking types that SQLite lacks natively (`uuid`,
`jsonb`, `timestamptz`, arrays, real constraints) — exactly the schema surface these contracts need.
The cost is paid now, once, instead of later under a working application.

Consequences to plan for:

- A running server and connection configuration become prerequisites for local development.
- Migrations need a real tool (Alembic) rather than ad-hoc schema creation.
- Tests need an isolated database — a per-test transaction rollback fixture, or a disposable test
  database. Engine tests are unaffected: **Layer 3 is pure and touches no database at all**, so the
  bulk of the hardest testing stays storage-free.
- The C.5/C.6 contracts carry no `user_id`. That is correct for v1; multi-user would add scoping at
  the storage layer without changing the contracts or the engine.

---

## 11. Non-objectives (architectural guardrails)

KnowledgeOS is **not** an AI tutor, notes app, flashcard system, task manager, calendar, habit
tracker, productivity app, or interview simulator. It may interoperate with such tools but never
becomes one. No note-taking or flashcard surface exists inside the app. Do not build these even when
convenient — the architecture has no place to put them.

---

## 12. Definition of done (global)

- Every layer boundary in §3–§4 respected; no LLM computes any protected quantity.
- Every concept exists once; shared nodes referenced by multiple roles.
- Knowledge state changes **only** via validated Schema B.
- Every mastery / retention / readiness / priority value is reproducible and carries a
  `computation_trace`.
- **`intrinsic_mastery` is never modified by prerequisites, decay, or time**; the §15 worked example
  passes as a regression test.
- Readiness is bottleneck-based; recommendations optimize expected readiness gain per unit cost.
- The engine is deterministic under property tests; golden cases pass.
- The Core User Flow works end-to-end from a clean clone per the README.
- None of the non-objectives (§11) were built.
