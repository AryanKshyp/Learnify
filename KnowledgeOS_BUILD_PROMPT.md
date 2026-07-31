# KnowledgeOS — Master Build Specification & Staged Prompt

> **What this document is.** This is the single source of truth for building KnowledgeOS. It is written to be handed to a coding agent (Claude Code) that knows **nothing** about this project. It contains the product constitution, the architecture, the exact data and schema contracts, the calculation-engine interface, the engineering rules, and a strict bottom-up build plan with per-stage success criteria.
>
> **How to use it.**
> 1. Put this file at the repo root as `BUILD_SPEC.md`.
> 2. Also provide `CALC_ENGINE_SPEC.md` — the deterministic calculation-engine specification. That document is the **authoritative source for every formula and default parameter**. This file defines *interfaces and behavior*; that file defines *the math*. Where they overlap, the math in `CALC_ENGINE_SPEC.md` wins.
> 3. Also provide `CURRICULUM_SPEC.md` — the seeded 6-role knowledge-graph content (from deep research). Used in Stage 6.
> 4. Work **one stage at a time, in order**. Do not begin a stage until the previous stage's success criteria pass. Use plan mode before each stage.
>
> **Golden rule for the agent:** Given identical inputs, this system must always produce identical outputs. No LLM ever computes mastery, retention, readiness, priority, or recommendations. The application owns all persistent truth.

---

## PART A — PRODUCT CONSTITUTION

### A.1 What KnowledgeOS is
A personal interview-preparation operating system that maintains a **persistent, evidence-based model of the user's knowledge**, detects gaps and prerequisite weaknesses, estimates retention over time, and continuously recommends what to study next to maximize interview readiness. It is a single-user tool intended for 6–12 months of sustained preparation.

### A.2 The problem it solves
The user repeatedly failed interview questions on topics they had "already studied." The real failures were: not knowing *what* knowledge was missing; undetected *prerequisite* gaps; no *objective* measure of what they actually knew; *forgetting* over time; not knowing what to study *next*; and preparation spread across *multiple overlapping roles*. No existing tool maintains a continuously updated model of interview readiness. KnowledgeOS does exactly that and nothing else.

### A.3 Supported roles (v1)
AI Research · AI Engineer · Data Science · Software Engineering · Product Management · Finance / Quantitative. Architecture must allow adding roles later without redesign.

### A.4 Non-objectives (explicitly out of scope)
KnowledgeOS is **not** an AI tutor, notes app, flashcard system, task manager, calendar, habit tracker, productivity app, or interview simulator. It may interoperate with such tools but never becomes one. Do not build any of these features, even if convenient.

### A.5 Product principles (non-negotiable)
1. **Single source of truth.** The application owns every piece of persistent information. Nothing important exists only inside an LLM.
2. **External assessment.** Teaching, questioning, and evaluation are external. The application only maintains knowledge state and makes decisions.
3. **Deterministic backend.** Every in-app calculation is deterministic and reproducible. The LLM never calculates mastery, retention, readiness, recommendations, or priorities — it only returns structured observations.
4. **Shared knowledge.** Each concept exists exactly once. Multiple roles reference the same concept and may assign it different importance and required depth. Never duplicate a concept.
5. **Knowledge requires evidence.** Reading, watching, or "feeling ready" never changes mastery. Only an assessment session provides evidence that knowledge changed.
6. **Explainability.** Every recommendation answers "why was this recommended?"; every readiness and mastery score answers "how was this calculated?" and is reproducible from stored evidence.

---

## PART B — ARCHITECTURE

Four independent layers. Each has a hard boundary.

### Layer 1 — Curriculum (static)
Defines *what should be known*, independent of the user. Roles, competencies, sub-competencies, concepts, assessable nodes, prerequisite edges, per-role importance, per-role required depth. This is a **Directed Acyclic Graph (DAG)**, not a tree: a node may have multiple parents; roles reference shared nodes. Never changes as a side effect of user activity.

### Layer 2 — Knowledge State (dynamic)
Represents the user's *current* knowledge. It **overlays** the curriculum graph — one state record per node — and never mutates the curriculum. Evolves **only** through assessment evidence.

### Layer 3 — Decision (deterministic)
Owns mastery calculation, retention/decay updates, prerequisite propagation, readiness calculation, priority calculation, and recommendation generation. Pure and reproducible. This is the heart of the system and is implemented strictly per `CALC_ENGINE_SPEC.md`.

### Layer 4 — Assessment (external, replaceable)
Teaches, questions, evaluates. Communicates with the application **only** through two structured schemas (Schema A out, Schema B in). KnowledgeOS knows nothing about how it works and must function against any engine that honors the schemas.

```
Curriculum (L1, static DAG)
        │  overlaid by
Knowledge State (L2, per-node)
        │  consumed by
Decision Engine (L3, deterministic) ──► recommendations, readiness, priorities
        ▲
        │  Schema A (out) ─────────►  Assessment Engine (L4, external)
        │  Schema B (in)  ◄─────────
```

---

## PART C — DATA CONTRACTS

> These are **interface contracts**. Field names, types, and semantics are fixed here. Storage representation (tables/columns) is an implementation detail chosen in Stage 1–2, but must round-trip these contracts losslessly. All scores are floats in `[0.0, 1.0]` unless noted. All timestamps are ISO-8601 UTC. All IDs are stable strings (slugs), never array indices.

### C.1 Curriculum graph — node
```jsonc
{
  "node_id": "attention-self",          // stable slug, unique across entire graph
  "type": "concept" | "assessable",     // assessable = a node that can be assessed directly
  "name": "Self-Attention",
  "section": "deep-learning",           // top-level grouping (a.k.a. competency area)
  "competency": "transformers",         // sub-grouping within section
  "description": "…",                   // short, human-readable
  "roles": [                            // per-role metadata; a node may serve many roles
    {
      "role_id": "ai-research",
      "importance": 0.95,               // 0..1, how much this node matters FOR THIS ROLE
      "required_depth": "derivation"    // see C.4 depth ladder
    },
    {
      "role_id": "ai-engineer",
      "importance": 0.80,
      "required_depth": "implementation"
    }
  ],
  "tags": ["math-heavy"],               // optional, freeform, for filtering only
  "schema_version": 1
}
```

### C.2 Curriculum graph — edge
```jsonc
{
  "edge_id": "attention-self__requires__linear-algebra-matmul",
  "type": "prerequisite" | "part_of",   // prerequisite = must-know-before; part_of = hierarchy
  "from_node_id": "attention-self",     // dependent
  "to_node_id": "linear-algebra-matmul",// prerequisite / parent
  "weight": 0.7,                        // 0..1, strength of dependency (used in propagation)
  "schema_version": 1
}
```
**Invariant:** the `prerequisite` subgraph must be acyclic. Loading must reject any curriculum whose prerequisite edges form a cycle, with a clear error naming the cycle.

### C.3 Role
```jsonc
{
  "role_id": "ai-research",
  "name": "AI Research",
  "priority_rank": 1,                   // 1 = highest priority for THIS user
  "schema_version": 1
}
```
User's fixed priority order (v1): `ai-research(1) > ai-engineer(2) > data-science(3) > software-engineering(4) > product(5) > finance(6)`.

### C.4 Depth ladder (ordered, low → high)
`awareness` < `working` < `deep` < `derivation`. Higher required depth ⇒ a higher mastery threshold is needed before the node counts as "sufficient" for that role. Exact thresholds per depth come from `CALC_ENGINE_SPEC.md`.

### C.5 Knowledge state (per node, per user)
```jsonc
{
  "node_id": "attention-self",
  "intrinsic_mastery": 0.0,             // M: latent estimate of what the user ACTUALLY knows; evidence, never
                                        //    modified by prerequisites/decay/time. 0.0 = never assessed (cold)
  "effective_mastery": 0.0,             // EM = M · R · PC. The only score reflecting time + prerequisites
  "retention": 0.0,                     // R: recall probability now, given decay since last review
  "stability": null,                    // S: forgetting time-constant (days); null until first session
  "difficulty": null,                   // D: node difficulty 0..1; defaults by depth tier, adjusts slowly
  "assessment_variance": 0.0,           // σ²: normalized variance of observations (high ⇒ needs more evidence)
  "engine_confidence": 0.0,             // C: engine-owned confidence in M (NOT the LLM's self-report)
  "session_count": 0,
  "last_assessed_at": null,             // ISO-8601 or null
  "next_review_at": null,               // scheduler output; null until first session
  "is_frontier": false,                 // DERIVED: EM < τ AND prerequisites sufficiently ready
  "critical_path_value": 0.0,           // CPV: gateway value toward high-importance downstream nodes
  "leverage": 0.0,                      // Lev: breadth of impact of improving this node
  "current_importance": 0.0,            // CurImp: dynamic importance (role/date/bottleneck/leverage-adjusted)
  "learning_cost": 0.0,                 // Cost: estimated effort to reach the depth target τ
  "status": "unassessed",               // DERIVED, never user-set: unassessed|learning|practiced|retained|mastered
  "last_gaps": [],                      // sub-gap strings from most recent Schema B
  "schema_version": 1
}
```
**Rules:** `status`, `is_frontier`, and every derived score above are *always* computed by the engine (per `CALC_ENGINE_SPEC.md`); there is no manual override anywhere. Cold ground truth is `intrinsic_mastery = 0.0`, `status = "unassessed"`. **`intrinsic_mastery` is never modified by prerequisites, decay, or time — only `effective_mastery` reflects those.** All derived-value definitions and formulas live in `CALC_ENGINE_SPEC.md`; this schema only fixes the storage contract.

### C.6 Session history record (append-only, per assessment)
```jsonc
{
  "session_id": "uuid",
  "node_id": "attention-self",
  "role_context": "ai-research",        // role used to parameterize this session (see C.8)
  "created_at": "…",                    // when Schema A was generated
  "completed_at": "…",                  // when Schema B was ingested
  "schema_a": { /* full Schema A, C.7 */ },
  "schema_b": { /* full Schema B, C.8 */ },
  "mastery_before": 0.0,                // snapshot for auditability
  "mastery_after": 0.0,
  "computation_trace": { /* explainability blob from engine, see F.4 */ },
  "schema_version": 1
}
```
History is **append-only**. Recalculation of state must be reproducible by replaying history through the deterministic engine.

### C.7 Schema A — Assessment INPUT (application → assessment engine)
Generated on command by the application from curriculum + current state. Tells the external engine what to assess and at what depth.
```jsonc
{
  "schema": "knowledgeos.assessment.input",
  "schema_version": 1,
  "session_id": "uuid",                 // app-generated; engine must echo it in Schema B
  "generated_at": "…",
  "target": {
    "node_id": "attention-self",
    "name": "Self-Attention",
    "section": "deep-learning",
    "competency": "transformers"
  },
  "role_context": {
    "role_id": "ai-research",           // highest-priority role tagging this node (see C.8 selection rule)
    "importance": 0.95,
    "required_depth": "derivation"      // engine should probe to at least this depth
  },
  "current_state": {
    "raw_mastery": 0.42,
    "retention": 0.31,
    "session_count": 2,
    "last_gaps": ["softmax scaling", "why divide by sqrt(d_k)"]
  },
  "prerequisite_context": [             // lets the engine probe whether failures trace upstream
    { "node_id": "linear-algebra-matmul", "name": "Matrix Multiplication", "raw_mastery": 0.88 },
    { "node_id": "prob-softmax",          "name": "Softmax / Normalization", "raw_mastery": 0.35 }
  ],
  "assessment_directives": {           // advisory only; engine may adapt
    "min_questions": 5,
    "must_probe_depth": "derivation",
    "focus_hints": ["target previous gaps", "test transfer to unseen framing"]
  }
}
```

### C.8 Schema B — Assessment OUTPUT (assessment engine → application)
The **only** way knowledge state changes. The application validates it strictly, then feeds the scores into the deterministic engine. The engine — not the LLM — computes mastery from these observations.
```jsonc
{
  "schema": "knowledgeos.assessment.output",
  "schema_version": 1,
  "session_id": "uuid",                 // MUST equal the Schema A session_id
  "node_id": "attention-self",          // MUST equal the Schema A target node_id
  "completed_at": "…",
  "observations": {
    "recall":   0.70,                   // remembered the facts/definitions
    "depth":    0.45,                   // understood mechanism, not just surface
    "transfer": 0.30                    // applied to a novel framing / unseen problem
  },
  "response_time_rating": 0.6,          // 0..1 normalized; 1 = fast & fluent, 0 = very slow/halting
  "llm_confidence": 0.85,               // the assessment engine's self-reported certainty. ACCEPTED but CAPPED:
                                        //   contributes ≤20% of update weight. The KnowledgeOS engine computes
                                        //   its OWN confidence + variance from evidence (see CALC_ENGINE_SPEC §4).
                                        //   LLM self-report never dominates a mastery update.
  "gaps_identified": [                  // specific, actionable sub-gaps
    "cannot derive scaled dot-product from first principles",
    "confuses attention weights with attention scores"
  ],
  "prerequisite_flags": [               // prereq node_ids the engine suspects are the real cause
    "prob-softmax"
  ],
  "recommended_next_concepts": [        // advisory only; engine's opinion, app decides
    "multi-head-attention"
  ],
  "evidence_summary": "…"               // 1–3 sentences, stored for audit/explainability
}
```
**Validation (hard-fail on any violation):** `session_id` and `node_id` must match the open session; all of `recall`, `depth`, `transfer`, `response_time_rating`, `llm_confidence` present and in `[0,1]`; `gaps_identified` is a list (possibly empty); every id in `prerequisite_flags` / `recommended_next_concepts` must exist in the curriculum. Reject with a precise error; never silently coerce.

---

## PART D — CORE USER FLOW

```
Open app
  → Browse knowledge graph  (home)  OR  Browse recommendations (dedicated page)
  → Select a concept
  → App generates Schema A  (copy to clipboard)
  → [external] Assessment session produces Schema B
  → Paste Schema B into app
  → App validates → deterministic engine updates knowledge state
  → App recalculates retention, propagation, readiness, priorities, recommendations
  → Repeat
```
No other learning activity exists inside the app. There is no note-taking or flashcard surface.

---

## PART E — FRONTEND PRINCIPLES

- The **knowledge graph is the primary interface**, not a dashboard. Home renders the interactive graph, never analytics-first.
- Browse by **Role**, **Competency (section)**, or **Concept** — all views are lenses over the same single graph. Filtering by role re-weights importance through that role's lens.
- **Recommendations live on their own page**, grouped by **Overall**, **Role**, and **Competency**, so the user can follow interest while staying guided. (When bored of one section, they can pull the top items from another.)
- On any node, only **Mastery** and **Importance** are visible by default. All other metrics (retention, stability, effective vs raw mastery, next-review date, computation trace) live behind an **Advanced** view.
- The session flow is: node → **Generate & copy Schema A** → **Paste Schema B** → confirm → state updates. One paste, parsed automatically. No manual number entry.

---

## PART F — DECISION ENGINE (LAYER 3) INTERFACE

> Implement **exactly** per `CALC_ENGINE_SPEC.md`. That document is authoritative for all formulas, ordering, and default parameters; do not invent them. This section fixes the *interface and behavioral guarantees* the rest of the app depends on, using the same method choices the spec settled on.
>
> **Governing principle:** separate what the user *actually knows* (`intrinsic_mastery`, evidence) from what the system can *currently trust* (`effective_mastery`). Intrinsic mastery is never modified by prerequisites, decay, or time.
>
> **Canonical pipeline (run in this order — see `CALC_ENGINE_SPEC` §1):** `observation → engine confidence + variance → intrinsic mastery → stability + retention → prerequisite confidence → effective mastery → frontier + critical path → leverage + current importance → readiness → learning cost → expected readiness gain → priority → status → knowledge health`.

### F.1 Observation model → per-session ability
Combine `recall`, `depth`, `transfer` into one session ability, with weights that shift toward depth/transfer for higher required depths, then apply a small `response_time_rating` modifier (fluent recall signals more consolidated knowledge). This is an **observation** of latent mastery, not mastery itself. Scheme per spec §3.

### F.2 Engine confidence & assessment variance (engine-owned)
The engine computes its **own** confidence and variance from evidence (count, consistency, recency); `llm_confidence` is only a minor capped input (≤20% of update weight). Maintain a running `assessment_variance`; high variance ⇒ "needs more evidence" and a smaller trusted update. Per spec §4.

### F.3 Intrinsic mastery update (latent estimate)
Update `intrinsic_mastery` by a confidence-weighted move toward the session observation (recency-weighted; older evidence discounted). `intrinsic_mastery` is **evidence** — never altered by prerequisites, decay, or time. Updates `session_count`, `last_assessed_at`. Per spec §5.

### F.4 Stability & retention (simple forgetting model — NOT full FSRS)
Compute `retention = exp(−Δt / stability)` and update `stability` after each session as a function of mastery, difficulty, and session quality. Derive `next_review_at` from the target-retention trigger. This is a deliberately simple, debuggable model — sessions are discussions/derivations/applications, not flashcard flips. Per spec §6.

### F.5 Prerequisite confidence → effective mastery (parent → child, non-destructive)
Compute `prerequisite_confidence` for each node from its prerequisites' effective mastery (bottleneck-leaning blend of weighted-min and weighted-average, using edge `weight`), in **topological order**. Then `effective_mastery = intrinsic_mastery · retention · prerequisite_confidence`. A decayed prerequisite lowers a dependent's **effective** mastery without touching its **intrinsic** mastery — and restudying the prerequisite restores dependents automatically, with zero reassessment. Per spec §7–§8.

### F.6 Frontier, critical path & prerequisite-cause detection
Mark `is_frontier` for nodes not yet sufficient (`EM < τ`) whose prerequisites are ready. A weak node with *unready* prerequisites is **not** on the frontier — the engine routes to the prerequisite instead (this is prerequisite-cause surfacing). Compute `critical_path_value` (gateway value toward high-importance downstream nodes). Recommendations search the frontier ∪ high-CPV nodes, never all nodes. Per spec §9.

### F.7 Leverage & current importance
Compute `leverage` from immediate + indirect unlocks + role overlap + critical-path value. Compute `current_importance` dynamically from intrinsic per-role importance, interview-date proximity, whether the node is a current bottleneck, and leverage — **without** rewriting static graph weights. Per spec §10.

### F.8 Readiness (bottleneck, not average)
Per role, readiness is a **weighted harmonic mean** of effective mastery over the role's nodes (weighted by per-role importance) — so one near-zero critical node tanks the score, matching interview reality. Report the binding bottleneck node alongside each readiness value. Per spec §11.

### F.9 Learning cost, expected readiness gain & priority
Estimate `learning_cost` per node (effort to reach `τ`). The recommendation objective is **maximize expected readiness gain per unit learning cost**, not close the biggest gap: `priority = (expected_readiness_gain / learning_cost) · leverage · current_importance`, over the frontier ∪ high-CPV candidate set, min-max normalized so no factor dominates, then **MMR**-diversified for top-N. Provide Overall, per-Role, per-Competency lists. Per spec §12.

### F.10 Cold start & knowledge health
Cold nodes (`session_count = 0`) live in a **separate "unexplored" queue** ranked by current importance and leverage — never mixed with assessed-but-weak nodes. Compute a single `Knowledge Health` score (coverage, mean effective mastery, mean retention, critical-gap ratio) plus its components and frontier size for the home view. Per spec §12–§14.

### F.11 Status derivation
Derive `status` (`unassessed | learning | practiced | retained | mastered`) from effective mastery, retention, variance, evidence count, and the depth target — never user-set. Per spec §13.

### F.12 Hard guarantees
- **Purity:** engine functions take state + inputs and return new values with **no I/O**. Same inputs ⇒ identical outputs, always.
- **Ordering:** always run the F-pipeline in order; never compute effective mastery before prerequisite confidence, nor readiness before effective mastery.
- **Evidence preservation:** `intrinsic_mastery` is never modified by prerequisites, decay, or time. The `CALC_ENGINE_SPEC` §15 worked example (Probability → Bayes → Naive Bayes) must pass as a regression test.
- **Explainability:** every produced score returns a `computation_trace` — inputs, parameters, intermediate terms — persisted in session history (C.6) and surfaced in the Advanced view.
- **Config, not constants:** all parameters live in one config module (loaded from the spec's `[TUNABLE]` defaults), never hard-coded inline.

---

## PART G — ENGINEERING RULES (apply to every stage)

### G.1 Bottom-up, gated stages
Build in the order in Part H. **Do not** start a stage until the prior stage's success criteria pass and tests are green. Before each stage, produce a short plan and wait for confirmation.

### G.2 Surgical changes
Touch only what the current task requires; clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style even if you'd personally do it differently.
- If you spot unrelated dead code, **mention it — don't delete it**.
- Remove only the imports/variables/functions **your** change orphaned; leave pre-existing dead code unless asked.
- Test: every changed line traces directly to the current task.

### G.3 Goal-driven execution
For each task, first state explicit, checkable **success criteria**, then implement, then **verify against them and loop until they pass**. Don't declare done on a task whose criteria you haven't demonstrably met (show the passing test/output).

### G.4 Determinism & tests
The Layer-3 engine gets unit tests **and** property tests asserting determinism (same input → same output) and monotonic sanity (e.g., higher observations ⇒ not-lower mastery). Prefer golden-test cases drawn from `CALC_ENGINE_SPEC.md` worked examples.

### G.5 Schema discipline
Every schema is versioned (`schema_version`). Validation is strict and fails loudly with precise messages. Never silently coerce or drop unknown fields on Schema B ingestion.

---

## PART H — STAGED BUILD PLAN

> Each stage lists **Objective → Deliverables → Success criteria → Do NOT**. Complete and verify a stage before the next.

### Stage 0 — Foundation & design sign-off
**Objective:** Scaffold the repo and lock decisions. No feature logic.
**Deliverables:**
- Repo skeleton and folder structure separating the four layers (`curriculum/`, `state/`, `engine/`, `assessment/`, `api/`, plus `frontend/` later).
- `CLAUDE.md` at root encoding Part A.5 principles, Part G rules, and the recommended stack.
- `ARCHITECTURE.md` summarizing Part B and the data contracts' locations.
- Dependency setup + an empty, runnable test harness (0 tests).
- **Recommended stack (confirm or object before coding):** Backend — Python 3.12, FastAPI, Pydantic v2 (schema validation is central), SQLite for storage, `networkx` for in-memory DAG traversal/propagation, `pytest` for tests. Frontend — React + Vite + TypeScript, with a graph-native viz library (React Flow or Cytoscape.js). Rationale: Pydantic gives first-class strict Schema A/B validation; networkx gives DAG ancestor/descendant/topological operations for free; SQLite fits a single-user local tool; the split cleanly honors the deterministic-backend / external-assessment boundary. If you disagree with any choice, raise it now — not after code exists.
**Success:** repo runs, test harness executes, `CLAUDE.md` + `ARCHITECTURE.md` present, stack confirmed.
**Do NOT:** write any calculation, endpoint, schema-generation, or UI code.

### Stage 1 — Curriculum graph (Layer 1)
**Objective:** The static DAG: schema, models, storage, loader, validators.
**Deliverables:** Pydantic models for node (C.1), edge (C.2), role (C.3); persistence; a graph loader that builds a `networkx` DAG; validators enforcing referential integrity and **prerequisite-subgraph acyclicity** (reject cycles with a named path); query functions — by role, by competency/section, ancestors, descendants, prerequisites-of, dependents-of. Include a **tiny fixture curriculum** (~8 nodes, a few cross-section prerequisites) for testing only.
**Success:** load fixture; validation catches an injected cycle and a dangling edge; all query functions return correct sets; tests green.
**Do NOT:** add user state, any calculation, or seed the real curriculum yet.

### Stage 2 — Knowledge state (Layer 2)
**Objective:** Per-node user-state overlay + append-only session history.
**Deliverables:** models for knowledge state (C.5) and session history (C.6); storage; overlay/join logic ("give me each node with its state"); defaults (cold node ⇒ `raw_mastery 0.0`, `status "unassessed"`); read/write; history append + full-replay read.
**Success:** attach/read state for any node; cold defaults correct; append several history records and reconstruct state ordering; state never mutates curriculum; tests green.
**Do NOT:** compute mastery/retention/priority yet — storage and retrieval only.

### Stage 3 — Calculation engine (Layer 3) — the heart
**Objective:** Implement the deterministic engine per `CALC_ENGINE_SPEC.md` (its §1 pipeline / this doc's F.1–F.11), honoring F.12.
**Deliverables:** pure functions for the full pipeline — observation model, engine confidence + variance, intrinsic mastery update, simple stability/retention + `next_review_at`, prerequisite-confidence propagation (topological), effective mastery, frontier + critical-path detection, leverage + current importance, bottleneck readiness (weighted harmonic mean), learning cost, expected-readiness-gain priority + MMR diversification, cold-start queue, knowledge health, status derivation; a single `config` module holding all `[TUNABLE]` parameters; `computation_trace` output on every score; unit + property (determinism + monotonicity) tests; the **§15 worked example (Probability → Bayes → Naive Bayes) as a golden regression test**.
**Success:** the §15 golden case passes (intrinsic preserved, effective collapses on prerequisite decay, restores on single reassessment); determinism holds across randomized inputs; `status` and `is_frontier` derivations match thresholds; traces populated; tests green.
**Do NOT:** touch storage, API, or UI from inside engine functions — keep them pure (state in, values out). Do not implement full FSRS; use the simple stability model.

### Stage 4 — Assessment interface (Layer 4 boundary)
**Objective:** Generate Schema A; validate + ingest Schema B; drive the update pipeline.
**Deliverables:** Schema A generator (C.7) that selects `role_context` as the **highest-priority role tagging the node** and pulls prerequisite context from the graph; strict Schema B validator (C.8 rules); ingestion pipeline: validate → run engine (Stage 3) → persist new state → append history → recompute retention/propagation/readiness/priorities; schema versioning + clear rejection errors.
**Success:** any concept yields a valid Schema A; a valid Schema B updates state deterministically and appends history; malformed / mismatched-`session_id` / out-of-range Schema B is rejected with a precise message; a full round-trip (generate A → feed mock B → state changes) passes and is reproducible.
**Do NOT:** build the assessment engine, questioning, or teaching — that is a separate external project.

### Stage 5 — Backend API
**Objective:** HTTP layer over Layers 1–4.
**Deliverables:** FastAPI endpoints — browse graph (by role / competency / whole), node detail (with state), recommendations (overall / per-role / per-competency), generate Schema A for a node, submit Schema B; typed request/response models; consistent error contract; auto OpenAPI docs.
**Success:** endpoints return correct data against the fixture; submitting Schema B via the API updates state and changes subsequent recommendations; integration tests green; OpenAPI renders.
**Do NOT:** start the UI.

### Stage 6 — Curriculum seeding
**Objective:** Populate the **real** curriculum for all 6 roles from `CURRICULUM_SPEC.md`.
**Deliverables:** curriculum data files (roles, competencies, concepts, assessable nodes, prerequisite + part_of edges, per-role importance, per-role required depth) covering AI Research, AI Engineer, Data Science, SWE, Product, Finance/Quant; loaded and validated; shared **leverage nodes** (e.g., Probability, DSA, System Design, Statistics) present **exactly once** with multiple role references.
**Success:** full graph loads and passes DAG + referential validation; shared concepts are single nodes referenced by multiple roles; role/competency traversal works on real data; no duplication.
**Do NOT:** modify engine or schemas to accommodate content — content conforms to the existing contracts. Flag any content that can't be expressed and stop; don't bend the schema silently.

### Stage 7 — Frontend
**Objective:** The graph-first UI and the session loop, per Part E.
**Deliverables:** React + Vite + TS app; interactive graph **home** (browsable, filter by role / competency / concept; role filter re-weights importance lens); **recommendations page** grouped Overall / Role / Competency; **node detail** showing **Mastery + Importance** by default with an **Advanced** panel for the rest (retention, stability, effective vs raw, next-review, trace); **session flow**: node → Generate & copy Schema A → paste Schema B → confirm → state updates and views refresh.
**Success:** graph renders and is navigable; recommendations show grouped correctly; node detail defaults to the two metrics with Advanced revealing the rest; copying Schema A and pasting a Schema B completes the loop end-to-end and updates the graph.
**Do NOT:** make analytics the home page; do not add notes, flashcards, timers, or any Non-objective (A.4).

### Stage 8 — Integration & end-to-end
**Objective:** Prove the whole Core User Flow (Part D).
**Deliverables:** end-to-end test covering seed → browse → recommend → generate Schema A → ingest (mock) Schema B → recompute → re-recommend; a seed script; a `README` with exact run steps for backend + frontend.
**Success:** the full loop runs end-to-end and is deterministic (same mock Schema B ⇒ same resulting state and recommendations); README steps reproduce a running system from a clean clone.
**Do NOT:** add scope. Ship the loop working before anything else.

---

## PART I — GLOBAL DEFINITION OF DONE
- Every layer boundary in Part B is respected; no LLM computes any protected quantity (A.5.3).
- Every concept exists once; shared nodes referenced by multiple roles (A.5.4).
- Knowledge state changes **only** via validated Schema B (A.5.5).
- Every mastery / retention / readiness / priority value is reproducible and carries a `computation_trace` (A.5.6, F.12).
- **`intrinsic_mastery` is never modified by prerequisites, decay, or time** — only `effective_mastery` reflects those. The `CALC_ENGINE_SPEC` §15 worked example passes as a regression test.
- Readiness is bottleneck-based (not an average); recommendations optimize expected readiness gain per unit learning cost (not raw gap).
- The engine is deterministic under property tests; golden cases from `CALC_ENGINE_SPEC.md` pass.
- The Core User Flow (Part D) works end-to-end from a clean clone per the README.
- None of the Non-objectives (A.4) were built.
