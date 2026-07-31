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
| L1 Curriculum content | Built and validated — not yet loaded by any code |
| L1 Curriculum loader | Not started (Stage 1) |
| L2 Knowledge State | Not started (Stage 2) |
| L3 Decision Engine | Not started (Stage 3) |
| L4 Assessment boundary | Not started (Stage 4) |
| API / Frontend | Not started (Stages 5, 7) |
| External assessment engine | Not designed — separate, non-blocking artifact |

**No application code exists yet.**

---

## Curriculum graph

`python build_graph.py` prints **`ERRORS: 0, WARNINGS: 0`** and regenerates `curriculum_graph.json`
byte-identically.

**245 nodes · 333 edges · 6 roles · 16 sections.**

Deliberately deepened first, matching role priority: `dsa` 32 · `deep-learning` 31 ·
`post-training-llms` 30 · `nlp-llms` 29.

Structurally sound but thinner — core sub-topics covered, not exhaustive: `cs-fundamentals` 8 ·
`ml-systems-mlops` 7 · `behavioral` 6 · `linear-algebra` 9 · `calculus-optimization` 9 ·
`system-design` 9 · `data-science-analytics` 9 · `product-management` 9.

Role tag counts: ai-research 176 · ai-engineer 178 · data-science 96 · finance-quant 96 ·
software-engineering 58 · product-management 39.

`curriculum_fixture.json` is a 12-node connected slice (Probability → Linear Algebra → Optimization →
Classical ML → Self-Attention) used by Stages 1–3 before the full graph is loaded at Stage 6.

---

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-31 | **`d:\Learnify` is the project root and git repo.** Kit contents promoted up one level; `knowledgeos-kit/` dissolved. | Single clone holds specs + code; no drift between duplicate `CLAUDE.md` copies. Git history preserved (`git fsck` clean, all 10 tracked files unmodified). |
| 2026-07-31 | **Stack confirmed** — Python 3.12, FastAPI, Pydantic v2, networkx, pytest; React + Vite + TS + React Flow. | Stage 0 gate. Rationale in `ARCHITECTURE.md` §10. |
| 2026-07-31 | **PostgreSQL instead of SQLite.** | Deliberate deviation from `BUILD_SPEC.md` Stage 0, to keep hosted/multi-user deployment open. Consequences (migrations, test DB isolation) in `ARCHITECTURE.md` §10. |
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
   `pyproject.toml`, dependencies, and a runnable empty pytest harness. Get Postgres connection +
   Alembic decided. *Success: repo runs, `pytest` executes with 0 tests, stack installed.*
2. **Fix known issue #2** (spec inconsistencies) — cheap, and each one silently misleads whichever
   stage consumes it.
3. **Stage 1** — curriculum loader against `curriculum_fixture.json`: Pydantic models (C.1–C.3),
   networkx DAG build, validators (referential integrity + cycle rejection naming the path), query
   functions (by role / section / ancestors / descendants / prerequisites-of / dependents-of).
   Resolve known issue #3 here. *Do not load the full 245-node graph until fixture tests pass.*
4. **Stage 2** — knowledge-state overlay + append-only session history. Storage and retrieval only.
5. **Stage 3 — the heart.** The deterministic engine, exactly per `CALC_ENGINE_SPEC.md` §1 pipeline.
   Build the §15 golden test first (known issue #4). Simple stability model, not FSRS. Harmonic-mean
   readiness, not average.
6. **Stages 4–8** — Schema A/B boundary → API → seed the real graph → frontend → end-to-end.

**Parallel, non-blocking:** design the external assessment engine (the prompt/skill that runs a
session and emits valid Schema B). Optional: use `DEEPEN_GRAPH.md` to deepen thin sections before
Stage 6.
