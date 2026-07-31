# CALC_ENGINE_SPEC.md — Deterministic Decision Engine (Layer 3)

> **Status & provenance.** This is the authoritative specification for the deterministic calculation engine of KnowledgeOS (Layer 3 in `BUILD_SPEC.md`). It was written to be consistent with the architecture review that identified the following governing principle:
>
> > **Separate what the user actually knows (intrinsic) from what the system can currently trust (effective).** Never destroy evidence; let prerequisites, decay, and time influence *effective* standing and recommendations without overwriting intrinsic mastery.
>
> All formulas are deterministic: identical inputs always produce identical outputs. No LLM computes any quantity here. Every default parameter is marked `[TUNABLE]`; reconcile against your own numbers if you have preferred values.
>
> **Consistency note:** several definitions here supersede the interface sketch in `BUILD_SPEC.md` Part F and require field additions in Part C.5/C.8. The deltas are listed in §16. Update `BUILD_SPEC.md` to match before implementation so there is a single source of truth.

---

## 0. Two-graph separation (foundational)

There are two graphs, never merged (roads vs. traffic):

- **Static Knowledge Graph** — nodes and edges (`BUILD_SPEC.md` C.1–C.2). Never changes as a side effect of user activity.
- **Dynamic Knowledge State** — per-node user values, overlaying the graph (`BUILD_SPEC.md` C.5). Changes only via assessment evidence.

The engine reads both and writes only Knowledge State. It never mutates the Knowledge Graph.

---

## 1. The pipeline (canonical ordering)

Every recompute runs in this exact order. Each stage is a pure function of the previous.

```
Assessment (Schema B)
   → 1. Observation model            → session ability O
   → 2. Engine confidence & variance → C, σ²   (engine-owned, not the LLM's)
   → 3. Intrinsic mastery update     → M        (latent estimate; evidence, never destroyed)
   → 4. Stability & retention        → S, R(t)  (simple forgetting, NOT full FSRS)
   → 5. Prerequisite confidence      → PC       (parent → child, over the DAG)
   → 6. Effective mastery            → EM = M·R·PC   (M never overwritten)
   → 7. Frontier & critical path     → is_frontier, CPV
   → 8. Leverage & current importance→ Lev, CurImp
   → 9. Readiness (bottleneck)       → Readiness_r per role
   → 10. Learning cost               → Cost
   → 11. Expected readiness gain     → ERG
   → 12. Priority & recommendations  → Priority, top-N (diversified)
   → 13. Status derivation           → status
   → 14. Knowledge health            → Health
```

Stages 1–4 run for the assessed node only. Stages 5–14 run for the assessed node plus every node whose value could change (its dependents for PC/EM; affected roles for readiness). Stages 5–12 are also the read path used to answer "what should I study next?" without any new assessment.

---

## 2. Notation

| Symbol | Meaning | Range |
|---|---|---|
| `M` | intrinsic mastery — latent estimate of what the user actually knows | 0..1 |
| `R(t)` | retention — probability of recall now, given time since last review | 0..1 |
| `S` | stability — time constant of forgetting (days) | >0 |
| `D` | node difficulty (intrinsic property) | 0..1 |
| `PC` | prerequisite confidence — how trustworthy this node is given upstream health | 0..1 |
| `EM` | effective mastery = `M · R · PC` | 0..1 |
| `C` | engine confidence in `M` (evidence-based) | 0..1 |
| `σ²` | assessment variance for the node | 0..1 (normalized) |
| `Lev` | leverage — breadth of impact of improving this node | 0..1 |
| `CPV` | critical-path value | 0..1 |
| `CurImp` | current (dynamic) importance | 0..1 |
| `τ` | mastery target implied by required depth (§5 table) | 0..1 |
| `π_r` | role-priority weight for role r | 0..1 |

Observations from Schema B: `recall`, `depth`, `transfer`, `response_time_rating`, `llm_confidence` — all 0..1.

---

## 3. Stage 1 — Observation model

Mastery is **latent**. A Schema B is **one observation** of it. (Future observation sources — real coding interviews, paper discussions — plug in here as additional observation types without changing the model.)

**Session ability:**
```
O_raw = w_recall·recall + w_depth·depth + w_transfer·transfer
```
Weights depend on the node's required depth for the session's role — deeper roles weight understanding/transfer over recall:

| required_depth | w_recall | w_depth | w_transfer |
|---|---|---|---|
| awareness    | 0.60 | 0.30 | 0.10 |
| working      | 0.40 | 0.40 | 0.20 |
| deep         | 0.25 | 0.45 | 0.30 |
| derivation   | 0.15 | 0.45 | 0.40 |
`[TUNABLE]` weights sum to 1 per row.

**Response-time modifier** (retrieval fluency / automaticity: fluent recall signals more consolidated knowledge than slow, effortful recall):
```
O = O_raw · (1 − λ_time·(1 − response_time_rating))
λ_time = 0.10   [TUNABLE]   # deliberately small — a modifier, never a dominator
```
`O` is the session's observed ability, in 0..1.

**Session quality** `Q = O` (used by stability, §4).

---

## 4. Stage 2 — Engine confidence & variance (engine-owned)

LLM self-reported confidence is **miscalibrated** and must not dominate. The engine computes its own confidence from evidence, using `llm_confidence` only as a minor input.

**Running assessment variance** (EWMA of squared deviation of `O` from running mean `μ`):
```
μ      ← μ + κ·(O − μ)                     # κ = 0.5 [TUNABLE]
σ²_raw ← (1−κ)·(σ²_raw + κ·(O − μ)²)
σ²     = clamp(σ²_raw / σ²_max, 0, 1)      # σ²_max = 0.10 [TUNABLE] normalizer
```
High `σ²` ⇒ inconsistent evidence ⇒ "needs more evidence."

**Engine confidence:**
```
evidence_saturation = 1 − exp(−n / n0)      # n = session_count, n0 = 3 [TUNABLE]
recency             = exp(−Δt_last / h_conf) # Δt_last = days since last session, h_conf = 30 [TUNABLE]
C = clamp( evidence_saturation · (1 − c_var·σ²) · recency, 0, 1 )
c_var = 0.6  [TUNABLE]
```

**Evidence weight** — how much this session moves `M` (engine-dominated; `llm_confidence` is a small term):
```
ew = clamp( g_var·(1 − σ²) + g_n·evidence_saturation_next + g_llm·llm_confidence, 0, 1 )
g_var = 0.45,  g_n = 0.35,  g_llm = 0.20   [TUNABLE]   # LLM ≤ 20% of the weight
```

---

## 5. Stage 3 — Intrinsic mastery update

Confidence-weighted move toward the observation (recency-weighted; older sessions naturally discounted):
```
α = α_base · ew                # α_base = 0.5 [TUNABLE]
M ← M + α·(O − M)
```
- Cold start: `M = 0`, `session_count = 0` (see `BUILD_SPEC.md` C.5).
- `M` is **evidence**. It is *never* modified by prerequisites, decay, or time. Only `EM` reflects those.

**Required-depth target** `τ` (mastery level at which a node "counts" for that depth):

| required_depth | τ |
|---|---|
| awareness  | 0.50 |
| working    | 0.65 |
| deep       | 0.80 |
| derivation | 0.90 |
`[TUNABLE]`. For a node serving multiple roles, use the max `τ` over roles when judging absolute sufficiency, but per-role `τ` when computing that role's readiness.

---

## 6. Stage 4 — Stability & retention (simple, not full FSRS)

We steal **stability / retention / forgetting** but not Anki's full FSRS machinery — sessions here are discussions/derivations/applications, not flashcard flips, so a debuggable model is preferred.

**Retention (exponential forgetting):**
```
R(t) = exp(−Δt / S)            # Δt = days since last_assessed_at
```
`Δt = 0` at assessment ⇒ `R = 1`. `R` decays toward 0 as time passes without review.

**Stability update after a session** (well-understood, easy material consolidates faster):
```
S_new = S_old · (1 + β · Q · M · (1 − D))
S_0   = 1.0 day                 # on first session [TUNABLE]
β     = 1.2                     # [TUNABLE]
```
`Q` = session quality (§3), `M` = post-update intrinsic mastery, `D` = difficulty.

**Difficulty** `D`: default by depth tier — awareness 0.2, working 0.4, deep 0.6, derivation 0.8 `[TUNABLE]`. Adjust slowly and bounded from observed struggle: if `σ²` high or many sessions needed to reach `τ`, nudge `D` up by ≤0.05 per session, clamp 0..1.

**Review trigger / scheduling:** review when `R(t)` would fall below target retention `θ`:
```
θ = 0.85                        # [TUNABLE]
next_review_at = last_assessed_at + (−S · ln θ) days   # since R=θ ⇒ Δt = −S·ln θ
```
With `θ=0.85`, `Δt* ≈ 0.163·S`. Flag a node **due** when `now ≥ next_review_at` (equivalently `R(now) ≤ θ`).

---

## 7. Stage 5 — Prerequisite confidence (parent → child, non-destructive)

Prerequisite decay flows **downstream**: if `Probability` decays, `Naive Bayes` becomes **less trustworthy** without altering its own intrinsic mastery. Computed in **topological order** over the prerequisite DAG (prerequisites resolved first).

For node `X` with prerequisites `p_i` and edge weights `w_i` (`BUILD_SPEC.md` C.2):
```
if X has no prerequisites:  PC(X) = 1
else:
  wavg = Σ_i w_i·EM(p_i) / Σ_i w_i           # weighted average (breadth)
  wmin = min_i EM(p_i)                        # bottleneck (a single weak critical prereq)
  PC(X) = γ·wmin + (1−γ)·wavg                 # bottleneck-leaning blend
  γ = 0.6   [TUNABLE]
```
`EM(p_i)` is the prerequisite's own effective mastery (already computed, since we go in topological order). Termination is guaranteed — the prerequisite subgraph is acyclic.

---

## 8. Stage 6 — Effective mastery

```
EM(X) = M(X) · R_X(t) · PC(X)
```
This is the only score that reflects time and prerequisites. `M(X)` is untouched. **No data destroyed** — restudy of `Probability` restores `Naive Bayes`'s `EM` automatically, with zero reassessment of `Naive Bayes`.

---

## 9. Stage 7 — Frontier & critical path

**Frontier (learner's fringe)** — a first-class concept, not just a traversal detail. Recommendations search the frontier first (large speed + explainability win):
```
is_frontier(X) =  EM(X) < τ_X                         # not yet sufficient
              AND PC(X) ≥ φ                            # prerequisites sufficiently ready
φ = 0.70   [TUNABLE]
```
A node with unmet prerequisites is *not* on the frontier — the engine routes you to the prerequisite instead (this is the prerequisite-cause surfacing from `BUILD_SPEC.md` F.5).

**Critical-path value** — is `X` a gateway to many high-importance downstream targets:
```
CPV_raw(X) = Σ over descendants d of ( IntrinsicImp*(d) · ζ^(depth(X→d)) )
ζ = 0.6   [TUNABLE]   # per-hop discount
CPV(X)    = min-max normalize CPV_raw across all nodes → 0..1
```
`IntrinsicImp*(d)` = max intrinsic importance of `d` over its roles; `depth(X→d)` = shortest prerequisite-hops from `X` to `d`.

---

## 10. Stage 8 — Leverage & current importance

**Leverage** (expanded well beyond descendant count):
```
Lev_raw(X) = a·immediate_unlocks + b·indirect_unlocks + c·role_overlap + d·CPV(X)
immediate_unlocks = # nodes for which X is a DIRECT prerequisite
indirect_unlocks  = # transitive dependents of X
role_overlap      = # roles referencing X (importance-weighted sum)
a,b,c,d = 0.30, 0.20, 0.25, 0.25   [TUNABLE]
Lev(X) = min-max normalize Lev_raw across all nodes → 0..1
```

**Importance is not constant** — split intrinsic (static, per-role, from curriculum) from current (dynamic, runtime):
```
CurImp(X) = IntrinsicImp_{r*}(X) · date_factor · bottleneck_factor · (1 + η·Lev(X))
r*             = active role, or highest-priority role tagging X
date_factor    = interview-date proximity multiplier (1.0 if no date set; rises as date nears)
bottleneck_factor = 1 + ρ if X currently limits some Readiness_r, else 1   (ρ = 0.5 [TUNABLE])
η = 0.3   [TUNABLE]
```
Graph weights are never rewritten; `CurImp` is derived each recompute.

---

## 11. Stage 9 — Readiness (bottleneck, not average)

Interviews punish bottlenecks, so an average is wrong (a role that's 100/100/15 fails, but averages to 72). Use the **weighted harmonic mean** over the role's critical nodes — one near-zero `EM` tanks it:
```
Readiness_r = ( Σ_{n∈N_r} I_n ) / ( Σ_{n∈N_r} I_n / max(EM(n), ε) )
N_r = nodes tagged with role r     I_n = IntrinsicImp_r(n)     ε = 0.05  [TUNABLE]
```
Report, alongside the number, the **binding bottleneck**: `argmin_{n∈N_r} EM(n)` (weighted). Every readiness value is thus explainable as "held back by node X."
*(Alternative if you prefer: `weighted_average · lowest_critical_cluster`. The harmonic mean is recommended as the single cleaner formula.)*

---

## 12. Stage 10–12 — Learning cost, expected readiness gain, priority

The recommendation objective is **not** "close the biggest gap." It is **maximize expected readiness gain per unit learning effort**.

**Learning cost** (effort to move `X` from current `EM` to `τ_X`):
```
Cost(X) = base_cost(depth_X) · D_X · (τ_X − EM(X))_+ / τ_X
base_cost:  awareness 1, working 2, deep 4, derivation 8   (hours, [TUNABLE])
```
(Frontier restriction means prerequisites are already met, so no upstream cost penalty is added; `(·)_+` = positive part.)

**Expected readiness gain** — simulate raising `EM(X)` to `τ_X`, propagate the change to X's dependents' `PC`/`EM`, recompute readiness, aggregate across roles by priority:
```
ERG_r(X) = Readiness_r[ EM(X)→τ_X, propagated ] − Readiness_r[ now ]
ERG(X)   = Σ_r π_r · max(ERG_r(X), 0)
π_r ∝ 1/priority_rank(r), normalized so Σ π_r = 1   [TUNABLE weighting scheme]
```
Because readiness is bottleneck-based, improving a bottleneck yields large `ERG`; improving an already-strong node yields ≈0 — exactly the desired behavior.

**Priority** = benefit per unit cost, modulated by leverage and current importance:
```
Priority_raw(X) = ( ERG(X) / Cost(X) ) · (1 + Lev(X)) · CurImp(X)
```
**Candidate set:** `Frontier ∪ {high-CPV nodes}` only — never all nodes.
**Normalize:** min-max each factor across candidates before combining so no single term dominates.
**Diversify:** produce top-N via **MMR** (maximal marginal relevance) so a list isn't five near-duplicates from one competency:
```
MMR pick:  argmax_X [ δ·Priority(X) − (1−δ)·max_{Y∈selected} sim(X,Y) ]
sim(X,Y) = shared-competency / shared-prerequisite overlap
δ = 0.7   [TUNABLE]
```
Produce three lists: **Overall**, **per-Role**, **per-Competency** (`BUILD_SPEC.md` Part E).

**Cold-start track:** nodes with `session_count = 0` have no evidence and are kept in a **separate "unexplored" queue**, ranked by `CurImp · (1 + Lev)`. They never masquerade as assessed-but-weak nodes. (Frontier detection already surfaces the *ready-to-learn* unexplored nodes; the unexplored queue is the explicit backlog.)

---

## 13. Stage 13 — Status derivation (never user-set)

Derived from `EM`, `R`, evidence, and depth target `τ`:
```
unassessed : session_count == 0
learning   : EM < 0.40  OR  σ² high (σ² > 0.5)
practiced  : 0.40 ≤ EM < 0.70
retained   : EM ≥ 0.70  AND  R ≥ 0.80  AND  session_count ≥ 2
mastered   : EM ≥ max(0.85, τ)  AND  R ≥ 0.90  AND  σ² ≤ 0.25  AND  session_count ≥ 2
```
`[TUNABLE]`. Evaluate top-down; first match wins.

---

## 14. Stage 14 — Knowledge Health (single dashboard number)

```
Health = 100 · ( h1·coverage
               + h2·mean_EM_critical
               + h3·mean_R_critical
               + h4·(1 − critical_gap_ratio) )
coverage           = assessed_critical_nodes / total_critical_nodes
mean_EM_critical   = importance-weighted mean EM over critical nodes
mean_R_critical    = importance-weighted mean R over critical nodes
critical_gap_ratio = critical nodes with EM < τ / total_critical_nodes
h1,h2,h3,h4 = 0.20, 0.35, 0.20, 0.25   [TUNABLE]
```
Report the four components and `frontier_size` separately for the home view. "Critical" = nodes with `IntrinsicImp ≥ 0.7` for the active role `[TUNABLE]`.

---

## 15. Worked example (golden test)

Directly demonstrates the evidence-preserving fix. Chain: `Probability → Bayes → Naive Bayes` (each a direct prerequisite of the next, edge weight 1.0). Difficulty: Prob 0.4, Bayes 0.5, NB 0.5.

**T0 — all freshly assessed to high intrinsic mastery, R≈1:**
```
Probability : M=0.90  R=1.00  PC=1.00       EM=0.90
Bayes       : M=0.95  R=1.00  PC=EM(Prob)=0.90   EM=0.95·1.00·0.90 = 0.855
Naive Bayes : M=0.90  R=1.00  PC=EM(Bayes)=0.855 EM=0.90·1.00·0.855 = 0.770
```

**T1 — three months pass; only Probability decays (say S_prob makes R_prob=0.33); Bayes & NB not reviewed either but assume their own R still high for illustration (R=0.95):**
```
Probability : M=0.90 (UNCHANGED)  R=0.33  PC=1.00  EM=0.90·0.33 = 0.297
Bayes       : M=0.95 (UNCHANGED)  R=0.95  PC=EM(Prob)=0.297
              EM = 0.95·0.95·0.297 = 0.268
Naive Bayes : M=0.90 (UNCHANGED)  R=0.95  PC=EM(Bayes)=0.268
              EM = 0.90·0.95·0.268 = 0.229
```
**Assertions the engine must satisfy:**
1. Intrinsic `M` for Bayes and Naive Bayes is **unchanged** (0.95, 0.90) — no evidence destroyed.
2. Effective `EM` for Naive Bayes collapsed 0.77 → 0.23 **purely because Probability decayed** — the recommendation engine now surfaces `Probability` (the frontier/critical-path root), not Naive Bayes.
3. After a single reassessment restoring `Probability` (R→1, EM→0.90), recomputing propagation restores Bayes `EM≈0.855` and Naive Bayes `EM≈0.77` with **zero reassessment** of Bayes or Naive Bayes.

Encode all three as regression tests.

---

## 16. Consistency deltas for `BUILD_SPEC.md`

These changes are required so the two documents agree (honoring the single-source-of-truth principle):

**C.5 Knowledge State — add / rename fields:**
- rename `raw_mastery` → `intrinsic_mastery` (`M`); keep `effective_mastery` (`EM`).
- add: `retention` (`R`), `stability` (`S`), `difficulty` (`D`), `assessment_variance` (`σ²`), `engine_confidence` (`C`), `is_frontier` (bool), `critical_path_value` (`CPV`), `leverage` (`Lev`), `current_importance` (`CurImp`), `learning_cost` (`Cost`).

**C.8 Schema B — semantics change (no field removed):** `llm_confidence` remains an accepted input but is capped at ≤20% of update weight (§4). The engine, not the LLM, owns confidence and variance.

**Part F — replace method choices:**
- F.3 retention: **simple exponential stability model** (§6), *not* full FSRS.
- F.6 readiness: **weighted harmonic mean / bottleneck** (§11), *not* average.
- F.7 priority: **expected readiness gain per unit learning cost** (§12), *not* gap-ranking.
- Add first-class modules absent from the sketch: **frontier detection** (§9), **critical path** (§9), **learning cost** (§12), **assessment variance/reliability** (§4), **intrinsic-vs-current importance** (§10), **expanded leverage** (§10), **knowledge health** (§14).

**Part I Definition of Done — add:** intrinsic mastery is never modified by prerequisites/decay/time; the §15 worked example passes as a regression test.

---

## 17. Engine-wide guarantees

- **Purity:** every function takes state + inputs, returns new values, performs no I/O. Same inputs ⇒ identical outputs.
- **Ordering:** always run the §1 pipeline in order; never compute `EM` before `PC`, nor readiness before `EM`.
- **Explainability:** every produced value (`M`, `R`, `EM`, `Readiness_r`, `Priority`) returns a `computation_trace` — inputs, parameters, and intermediate terms — persisted in session history and surfaced in the Advanced view.
- **Config, not constants:** every `[TUNABLE]` parameter lives in one config module. No literal appears inline in logic.
- **Determinism tests:** unit + property tests (same input → same output; monotonicity: higher observations ⇒ not-lower `M`; a decayed prerequisite ⇒ not-higher dependent `EM`) plus the §15 golden case.
