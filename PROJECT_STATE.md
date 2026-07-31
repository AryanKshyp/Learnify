# PROJECT_STATE.md

**Where the project stands right now.** This is the one file expected to change often — update it at
the end of any session that changes status, makes a decision, or finds an issue. Durable principles
belong in [CLAUDE.md](CLAUDE.md); system design belongs in [ARCHITECTURE.md](ARCHITECTURE.md).

**Last updated:** 2026-07-31

---

## Current position

**Stage 0 — in progress.** Design phase complete; repo promoted to root; docs restructured. The
scaffold itself (folder skeleton, dependency setup, empty test harness) is **not yet created**.

| Layer | Status |
|---|---|
| L1 Curriculum content | **Complete** — 566 nodes deepened across all 16 sections, validated |
| L1 Curriculum loader | Not started (Stage 1) |
| L2 Knowledge State | Not started (Stage 2) |
| L3 Decision Engine | Not started (Stage 3) |
| L4 Assessment boundary | Not started (Stage 4) |
| API / Frontend | Not started (Stages 5, 7) |
| External assessment engine | Not designed — separate, non-blocking artifact |

**No application code exists yet.**

---

## Curriculum graph — Layer 1 content COMPLETE

`python build_graph.py` prints **`ERRORS: 0, WARNINGS: 0`** and regenerates `curriculum_graph.json`.

**566 nodes · 847 edges · 6 roles · 16 sections.** Every section deepened to target depth on
2026-07-31 (was 245 nodes / 333 edges).

| Section | Nodes | | Section | Nodes |
|---|--:|---|---|--:|
| post-training-llms | 47 | | classical-ml | 36 |
| dsa | 46 | | cs-fundamentals | 35 |
| deep-learning | 45 | | data-science-analytics | 34 |
| nlp-llms | 43 | | product-management | 32 |
| finance-quant | 40 | | ml-systems-mlops | 31 |
| system-design | 38 | | probability / statistics | 30 / 30 |
| | | | calculus-optimization | 27 |
| | | | linear-algebra / behavioral | 26 / 26 |

Role tag counts: ai-engineer 391 · ai-research 338 · data-science 210 · finance-quant 205 ·
software-engineering 144 · product-management 111.

Built by 16 parallel `section-author` subagents run in four dependency-ordered waves
(foundations → mid-layer → ML depth → specialist), per `DEEPEN_GRAPH.md`. Each wave was committed
separately, so any wave is independently revertible.

`curriculum_fixture.json` is a 12-node connected slice (Probability → Linear Algebra → Optimization →
Classical ML → Self-Attention) used by Stages 1–3 before the full graph is loaded at Stage 6. **It
was not regenerated during the deepening** — it is still a valid subset of the graph, but no longer
representative of its density.

### Verified after deepening
- 0 duplicate `node_id`s, 0 exact name collisions, 0 nodes without role tags.
- Prerequisite subgraph acyclic (Kahn's algorithm, in-validator).
- `CALC_ENGINE_SPEC.md` §15 golden chain intact: `prob-conditional → prob-bayes → ml-naive-bayes`.
- Cross-section near-duplicate scan (fuzzy name match, ratio ≥ 0.8) surfaced 11 candidates; all
  reviewed and confirmed to be genuinely distinct concepts that merely share vocabulary — e.g. three
  "variance reduction" nodes covering Monte Carlo estimators (`prob-`), SVRG/SAGA gradient variance
  (`opt-`), and CUPED for experiments (`ds-`). No merges needed.
- 3 orphan nodes with no edges at all: `cs-compilation-interpretation`, `beh-strengths-weaknesses`,
  `beh-offer-negotiation`. Not an error — standalone behavioral topics legitimately have no
  prerequisites — but `cs-compilation-interpretation` could reasonably gain one.

---

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-31 | **`d:\Learnify` is the project root and git repo.** Kit contents promoted up one level; `knowledgeos-kit/` dissolved. | Single clone holds specs + code; no drift between duplicate `CLAUDE.md` copies. Git history preserved (`git fsck` clean, all 10 tracked files unmodified). |
| 2026-07-31 | **Stack confirmed** — Python 3.12, FastAPI, Pydantic v2, networkx, pytest; React + Vite + TS + React Flow. | Stage 0 gate. Rationale in `ARCHITECTURE.md` §10. |
| 2026-07-31 | **PostgreSQL instead of SQLite — confirmed.** | The stated end state is multi-user on **Supabase**, which *is* Postgres. Developing on Postgres now makes that a deployment change rather than a port; SQLite first would mean rewriting migrations and reworking `uuid`/`jsonb`/`timestamptz`/array/constraint usage. Consequences in `ARCHITECTURE.md` §10. |
| 2026-07-31 | **Layer 1 curriculum deepened 245 → 566 nodes** via 16 parallel subagents in 4 waves. | Sections were unevenly built (6-9 nodes in several) which would have skewed readiness and recommendations toward whichever sections happened to be dense. |
| 2026-07-31 | **Docs split three ways** — constitution / state / architecture. | `CLAUDE.md` was mixing durable principles with volatile status, so it needed editing after every change. |

---

## Known issues

### 1. `build_graph.py` crashed when it found errors — **fixed 2026-07-31**
The script printed `✗`/`!` and interpolated node names into error strings, which Windows' cp1252
console cannot encode — so it raised `UnicodeEncodeError` **precisely when validation failed**, the
one moment its output matters. Fixed by reconfiguring stdout to UTF-8 in `__main__`. Verified by
injecting a duplicate id plus a non-ASCII node name: both errors now print, exit code 1, JSON not
written.

### 2. Spec inconsistencies surviving the mid-design critique — **fixed 2026-07-31**
All resolved. `KnowledgeOS_BUILD_PROMPT.md` was renamed to **`BUILD_SPEC.md`** (via `git mv`), which
is the name its own header instructs and the name all 16 existing cross-references in
`CALC_ENGINE_SPEC.md` and `CURRICULUM_BUILD_KIT.md` already used.

| Where | Was | Now |
|---|---|---|
| `BUILD_SPEC.md` C.7 (×3) | Schema A used `raw_mastery` | `intrinsic_mastery` (per `CALC_ENGINE_SPEC.md` §16) |
| `BUILD_SPEC.md` Stage 2 | cold node ⇒ `raw_mastery 0.0` | `intrinsic_mastery 0.0` |
| `BUILD_SPEC.md` C.1 example | `required_depth: "implementation"` | `deep` — `implementation` is not on the C.4 ladder |
| Filename | `KnowledgeOS_BUILD_PROMPT.md` | `BUILD_SPEC.md` |
| `BUILD_SPEC.md` intro + Stage 6 | Referenced non-existent `CURRICULUM_SPEC.md` | `curriculum_graph.json` + `CURRICULUM_BUILD_KIT.md` |

### 3. Contract fields absent from generated data — **open, Stage 1**
`build_graph.py` emits neither `schema_version` (C.1/C.2) nor `edge_id` (C.2); confirmed absent from
both `curriculum_graph.json` and `curriculum_fixture.json`. The Stage 1 loader must either synthesize
them or the generator must emit them. Decide at Stage 1 — don't bend the contract silently.

### 4. Golden-test chain is not in the fixture — **open, Stage 3**
`CALC_ENGINE_SPEC.md` §15 uses Probability → Bayes → Naive Bayes. `curriculum_fixture.json` has
`prob-conditional → prob-bayes` but **no Naive Bayes node**; `ml-naive-bayes` exists only in the full
graph. The §15 example specifies all its own `M`/`R`/`PC`/`D` values, so the clean fix is a dedicated
3-node test fixture rather than enlarging `curriculum_fixture.json`.

### 5. `core.autocrlf=true`, no `.gitattributes` — **cosmetic only**
The repo has `core.autocrlf=true`, so a fresh clone checks `curriculum_graph.json` out with CRLF
while `build_graph.py` now writes LF. Git normalizes both to LF when comparing, so **`git status`
stays clean and no spurious diff appears** — but an on-disk byte/hash comparison after a fresh clone
will differ until the file is regenerated once. Add `*.json text eol=lf` in a `.gitattributes` if
that verification path ever matters.

### 6. `knowledgeos-kit.zip` — resolved, no action
Deleted from `D:\Learnify` at 19:08 on 2026-07-31 (GUI deletion; recoverable from the Recycle Bin).
Fully redundant — it was a snapshot of the kit whose contents are now all at root and tracked in git.

---

## Next actions

1. **Finish Stage 0** — scaffold `backend/knowledgeos/{curriculum,state,engine,assessment,api}/`,
   `pyproject.toml`, dependencies, and a runnable empty pytest harness. Decide Postgres connection +
   Alembic. *Success: repo runs, `pytest` executes with 0 tests, stack installed.*
   Note: local Python is **3.11.9**, not the 3.12 named in the stack — either install 3.12 or amend
   the decision before pinning `requires-python`.
2. **Stage 1** — curriculum loader against `curriculum_fixture.json`: Pydantic models (C.1–C.3),
   networkx DAG build, validators (referential integrity + cycle rejection naming the path), query
   functions (by role / section / ancestors / descendants / prerequisites-of / dependents-of).
   Resolve known issue #3 here. *Do not load the full 566-node graph until fixture tests pass.*
4. **Stage 2** — knowledge-state overlay + append-only session history. Storage and retrieval only.
5. **Stage 3 — the heart.** The deterministic engine, exactly per `CALC_ENGINE_SPEC.md` §1 pipeline.
   Build the §15 golden test first (known issue #4). Simple stability model, not FSRS. Harmonic-mean
   readiness, not average.
6. **Stages 4–8** — Schema A/B boundary → API → seed the real 566-node graph → frontend → end-to-end.

**Parallel, non-blocking:** design the external assessment engine (the prompt/skill that runs a
session and emits valid Schema B) — still the largest unbuilt piece outside the app itself.

**Optional curriculum follow-ups** (Layer 1 content is complete; these are polish, not blockers):
regenerate `curriculum_fixture.json` from the deepened graph; give `cs-compilation-interpretation` a
prerequisite; spot-check importance/depth calls by eye — the validator guarantees structure, not
that the content judgments match yours.
