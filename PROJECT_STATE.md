# PROJECT_STATE.md

**Where the project stands right now.** This is the one file expected to change often — update it at
the end of any session that changes status, makes a decision, or finds an issue. Durable principles
belong in [CLAUDE.md](CLAUDE.md); system design belongs in [ARCHITECTURE.md](ARCHITECTURE.md).

**Last updated:** 2026-07-31

---

## Current position

**Stage 0 — COMPLETE.** Design phase done, repo promoted to root, docs restructured, Layer 1
curriculum content complete, backend scaffolded on Python 3.12 with a runnable test harness and
machine-enforced layer boundaries. **Stage 1 is unblocked.**

| Layer | Status |
|---|---|
| L1 Curriculum content | **Complete** — 566 nodes deepened across all 16 sections, validated |
| L1 Curriculum loader | Not started — **next** (Stage 1) |
| L2 Knowledge State | Not started (Stage 2) |
| L3 Decision Engine | Not started (Stage 3) |
| L4 Assessment boundary | Not started (Stage 4) |
| API / Frontend | Not started (Stages 5, 7) |
| External assessment engine | Not designed — separate, non-blocking artifact |

**Scaffold only — no feature code.** Every layer package exists with a docstring stating its
boundary and which stage populates it. Stage 0 forbids calculation, endpoint, schema-generation
and UI code, and none was written.

Verified at Stage 0 close:
- `pytest` → 0 tests, exit 0 (an empty suite is deliberately treated as success; see
  `backend/tests/conftest.py`, which stops mattering once Stage 1 adds real tests).
- `ruff check .` → all checks passed.
- `lint-imports` → 3 contracts kept. **Proven to bite**: injecting `sqlalchemy`, `datetime` and
  `random` imports into `knowledgeos/engine` made all three fail with line numbers, exit 1.
- `python build_graph.py` → `ERRORS: 0, WARNINGS: 0`; `python make_fixture.py` → `ERRORS: 0`.

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
| 2026-07-31 | **Python 3.12.10 installed**; project pins `requires-python = ">=3.12"`. | Stack decision named 3.12; the machine had only a 3.11.9 Store build. Installed via winget alongside it — 3.11 left untouched. venv at `backend/.venv`. |
| 2026-07-31 | **Layer boundaries enforced via import-linter**, not left to review. | `ARCHITECTURE.md` §4 declared rules nothing checked. Layer 3 purity is the system's central guarantee and the cheapest way to lose it is one `datetime.now()` inside a formula. |
| 2026-07-31 | **`curriculum_fixture.json` is generated, not hand-maintained** (`make_fixture.py`). | The fixture must be an exact, edge-closed subset of the real graph or Stage 1–3 tests silently diverge from Stage 6 behaviour. Hand-editing cannot guarantee that; derivation can. |

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

### 4. Golden-test chain missing from the fixture — **fixed 2026-07-31**
`curriculum_fixture.json` is now generated by `make_fixture.py` and seeded so the
`CALC_ENGINE_SPEC.md` §15 chain `prob-conditional → prob-bayes → ml-naive-bayes` is present and
correctly wired — the generator asserts it and exits non-zero if it ever breaks.

The fixture grew 12 → **26 nodes / 35 edges** across 6 sections. Larger than the "~8 nodes"
`BUILD_SPEC.md` Stage 1 suggests, because prerequisite-closure is mandatory: a fixture node whose
prerequisites sit outside the slice would make the loader's prereq/ancestor queries return
answers that are wrong-by-construction. The generator verifies closure, exact-subset fidelity,
≥3 sections, cross-section edges, a multi-parent node (proving DAG-not-tree handling), and all
four `required_depth` levels.

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

1. **Stage 1** — curriculum loader against `curriculum_fixture.json`: Pydantic models (C.1–C.3),
   networkx DAG build, validators (referential integrity + cycle rejection naming the path), query
   functions (by role / section / ancestors / descendants / prerequisites-of / dependents-of).
   Resolve known issue #3 (`schema_version` / `edge_id`) here. *Do not load the full 566-node graph
   until the fixture tests pass.*
2. **Stage 2** — knowledge-state overlay + append-only session history. Storage and retrieval only,
   no calculation. First stage that needs Postgres running (`docker compose up -d`) and Alembic.
3. **Stage 3 — the heart.** The deterministic engine, exactly per `CALC_ENGINE_SPEC.md` §1 pipeline.
   Build the §15 golden test first — the fixture now contains its chain. Simple stability model, not
   FSRS. Harmonic-mean readiness, not average. Keep `lint-imports` green: it is what stops a clock
   read or a storage call from silently entering a formula.
4. **Stages 4–8** — Schema A/B boundary → API → seed the real 566-node graph → frontend → end-to-end.

**Parallel, non-blocking:** design the external assessment engine (the prompt/skill that runs a
session and emits valid Schema B) — still the largest unbuilt piece outside the app itself.

**Optional curriculum polish** (Layer 1 content is complete; none of these block anything): give
`cs-compilation-interpretation` a prerequisite so it is not an orphan; spot-check importance/depth
calls by eye — the validator guarantees structure, not that the content judgments match yours.
