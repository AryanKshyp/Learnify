# PROJECT_STATE.md

**Where the project stands right now.** This is the one file expected to change often — update it at
the end of any session that changes status, makes a decision, or finds an issue. Durable principles
belong in [CLAUDE.md](CLAUDE.md); system design belongs in [ARCHITECTURE.md](ARCHITECTURE.md).

**Last updated:** 2026-08-01

---

## Current position

**Stages 0–4 COMPLETE, and now genuinely persisted.** The Core User Flow runs end to end and
survives a restart: Postgres is live, migrated by Alembic, and the whole loop was verified
against the real database. **540 tests green.** Stage 5 (API) is unblocked with no caveats.

| Layer | Status |
|---|---|
| L1 Curriculum content | **Complete** — 566 nodes deepened across all 16 sections, validated |
| L1 Curriculum loader | **Complete** — models, loader, validators, queries; 93 tests |
| L2 Knowledge State | **Complete** — in-memory *and* Postgres repositories, Alembic-migrated |
| L3 Decision Engine | **Complete** — 14 stages, §15 golden case passing, purity machine-enforced |
| L4 Assessment boundary | **Complete** — Schema A/B, strict validation, ingestion pipeline |
| API / Frontend | Not started — API is **next** (Stage 5) |
| External assessment engine | Not designed — separate, non-blocking artifact |

All four backend layers are implemented and tested. Verified at each stage close, not assumed:

- `pytest` → **540 passed**. `ruff check .` → clean. `lint-imports` → 3 contracts kept.
- The purity contract is **proven to bite**: injecting `sqlalchemy`/`datetime`/`random` imports
  into `knowledgeos/engine` fails all three with line numbers, exit 1.
- `python build_graph.py` → `ERRORS: 0, WARNINGS: 0`; `python make_fixture.py` → `ERRORS: 0`.
- `CALC_ENGINE_SPEC.md` §15 golden case reproduces the spec's exact numbers.
- `docker compose up -d` + `alembic upgrade head` → Core User Flow verified against real Postgres.

**Not yet built:** the HTTP API (Stage 5), the real-curriculum seed (Stage 6, only the 26-node
fixture is loaded), the frontend (Stage 7), and the external assessment engine.

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
| 2026-08-01 | **Curriculum served from JSON in memory behind `CurriculumRepository`**, not from Postgres. | Layer 1 is static and user-independent, so it may never need a database. Keeps Stages 1–3 — including the hard engine work — runnable with zero infrastructure. A DB-backed implementation can replace it without touching callers. |
| 2026-08-01 | **networkx DAG is built INVERTED relative to the JSON** (prerequisite → dependent). | Makes `nx.ancestors` return prerequisites, `nx.descendants` return dependents, and `topological_sort` yield prerequisites first — which is exactly what `CALC_ENGINE_SPEC.md` §7 propagation requires. Reversing it would produce a valid-looking DAG and silently backwards propagation, so it is asserted in tests. |
| 2026-08-01 | **State and history are separate protocols**; history has no update or delete method. | Append-only is what makes state reconstructible by replay (C.6). Expressing it in the interface beats a comment nobody has to obey — a test asserts the methods simply do not exist. |
| 2026-08-01 | **Cold defaults applied on READ, not pre-seeded as rows.** | Adding curriculum nodes then never requires a migration of user state: a new node is simply cold until assessed. `get()` returns `None` for "no record" so the overlay, not the store, owns the default. |
| 2026-08-01 | **Postgres persistence deferred until the daemon runs** (see known issue #8). | Writing storage code that cannot be executed would mean reporting Stage 2 as done on the strength of untested code. Stage 3 is pure and needs no DB, so the critical path is unaffected. |
| 2026-08-01 | **Engine takes `days_elapsed: float` and returns *days until review*, never a timestamp.** | The purity contract forbids `datetime` in `engine/`, which forced the cleaner design: time is an input, so every score is reproducible from stored evidence. The caller converts to a timestamp. |
| 2026-08-01 | **Purity contract relaxed to `allow_indirect_imports`.** | The engine legitimately imports the Layer 2 `Status` type, whose module references `datetime`/`uuid` as *field types*. That transitive edge is not a clock read. Direct imports of `datetime`/`random`/`os` in engine code are still rejected — re-verified by injection after the change. |

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

### 3. Contract fields absent from generated data — **resolved 2026-08-01**
`schema_version` and `edge_id` are supplied by the Pydantic models rather than stored in JSON:
`schema_version` defaults to 1, and `edge_id` is a `computed_field` derived from
`(from_node_id, type, to_node_id)` in the C.2 format (`x__requires__y`). Deriving it means the
id can never contradict the edge it names. The JSON files are unchanged.

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

### 7. `Depth` ordering was silently alphabetical — **fixed 2026-08-01**
`Depth` is a `StrEnum`, so it inherited `str`'s comparison operators, and `@total_ordering` was
a no-op (it only supplies operators a class is *missing*). `max()` therefore compared
alphabetically: `"working" > "derivation"` because `w > d`. Every mastery target τ derived from
a node's deepest role requirement would have been wrong, without any error. Caught by a unit
test written before the engine existed. Fixed by defining all four comparison operators over
ladder position, and raising `TypeError` on comparison with a bare string rather than silently
falling back to `str` ordering.

**Carry into Stage 3:** the same trap applies to any ordered enum added later.

### 12. Two contract gaps found while building Stage 4 — **fixed, documented**

**C.5 has no field for the running mean μ.** `CALC_ENGINE_SPEC.md` §4 maintains μ as EWMA
state alongside σ², but the §16 field-addition list names only `assessment_variance`. Without
persisting μ the variance calculation restarts every session, so σ² could never measure
disagreement *between* sessions. Added `observation_mean` to `KnowledgeState` as a documented
extension to C.5.

**σ² was manufactured on the first session.** With μ starting at 0.0, session one's deviation
`(O − 0.5·O)` is large purely because μ was never initialised — reporting an ordinary first
session as wildly inconsistent, enough to trip the `σ² > 0.5` clause and label it `learning`
regardless of how well it went. Worse, a genuinely contradictory *second* session then
**lowered** variance, inverting the signal entirely. Caught by a Stage 4 round-trip test.
Fixed by seeding μ = O and σ² = 0 on the first session: one observation cannot disagree with
itself. Verified: two consistent strong sessions → σ² = 0.000; a contradictory third → 0.400.

### 9. Spec ambiguities resolved while implementing the engine — **decided, documented**
Two places where `CALC_ENGINE_SPEC.md` could not be followed literally. Both resolutions are
pinned by tests so they cannot be silently reverted.

**§13 status ordering — the spec's stated order is unreachable.** It lists
`unassessed → learning → practiced → retained → mastered` and says "evaluate top-down; first
match wins". But `retained` requires EM ≥ 0.70 and `mastered` requires EM ≥ 0.85, so a
genuinely mastered node matches `retained` first and `mastered` can never be returned.
Resolved by evaluating **most demanding first**: `unassessed → learning → mastered → retained
→ practiced`. `learning` stays ahead of the strong tiers deliberately — its σ² clause means
"the observations disagree", and self-contradictory evidence should not read as `retained`.

**§4 EWMA ordering is ambiguous.** The spec updates μ, then computes σ²_raw from `(O − μ)`,
without saying whether that μ is pre- or post-update. Implemented literally in written order
(deviation from the *updated* mean). Either is defensible; determinism matters more than
taste, so the choice is documented at the call site.

### 10. §10 leverage terms are on mismatched scales — **implemented as specified, flagged**
`Lev_raw = a·immediate_unlocks + b·indirect_unlocks + c·role_overlap + d·CPV`, normalised
*after* combining. But `immediate_unlocks`/`indirect_unlocks` are unbounded counts while CPV
and role_overlap are ≤ ~1, so on the 566-node graph the count terms dominate and CPV
contributes almost nothing before normalisation. The spec is explicit that normalisation
happens after combining, so that is what is implemented — changing it would alter the spec's
math, not an implementation detail. Worth revisiting during tuning; normalising each term
first is the obvious alternative.

### 11. ERG does not re-propagate into dependents — **simplification, flagged**
`expected_readiness_gain` raises the candidate's own EM to τ and re-runs readiness, but does
not re-propagate the improvement into its dependents' PC. Full propagation costs a graph pass
per candidate; since readiness already counts every dependent node directly, the resulting
ranking is very close. First thing to revisit if recommendations look wrong on deep chains.

### 8. Postgres persistence — **resolved 2026-08-01**
WSL had no kernel installed, so Docker Desktop's WSL2 backend could not start. Resolved by
`wsl --update` (now 2.7.11.0, kernel 6.18.33.2-2). Docker Desktop 4.84.0 lives in a per-user
path (`%LOCALAPPDATA%\Programs\DockerDesktop`), not Program Files, which is why the standard
PATH lookups missed it.

Now working end to end and verified, not assumed:
- `docker compose up -d` → `postgres:16` healthy in ~5s. The compose file written blind at
  Stage 0 turned out to be correct.
- `alembic upgrade head` creates both tables; `downgrade base` → `upgrade head` round-trips
  cleanly; `alembic check` reports no drift between models and live schema.
- 23 Postgres tests pass against the real database, including full-field round-trips, NULL
  handling (`stability`/`difficulty` are NULL until first assessment, not 0.0), `jsonb` payload
  fidelity, timezone preservation, and DB-level CHECK constraints rejecting out-of-range scores
  written behind the models' back.
- A **parity test** asserts the Postgres and in-memory repositories return identical results
  for identical operations — which is what makes testing everything above Layer 2 against the
  fast in-memory implementation trustworthy.
- `tests/state/test_postgres.py` **skips** rather than fails when no database is reachable.

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

1. **Stage 5 — backend API.** FastAPI over Layers 1–4: browse graph (by role / competency /
   whole), node detail with state, recommendations (overall / per-role / per-competency),
   generate Schema A, submit Schema B. Typed request/response models, a consistent error
   contract, OpenAPI. `AssessmentService` already exposes exactly these operations, so this is
   mostly transport and error mapping.
2. **Stage 6** — seed the real 566-node graph (currently only the 26-node fixture is loaded).
3. **Stages 7–8** — frontend (graph-first home, Advanced panel, the copy/paste session loop) →
   end-to-end integration test → README.

**Parallel, non-blocking:** design the external assessment engine — the prompt/skill that
conducts a session and emits a valid Schema B. The single largest unbuilt piece. Every contract
it must honour is now implemented and strictly validated, so it can be developed against a
real, unforgiving target rather than against a document.

**Engine tuning, once there is real session data:** known issues #10 (leverage term scales) and
#11 (ERG propagation depth), both implemented as specified and flagged rather than quietly
"fixed".

**Optional curriculum polish:** give `cs-compilation-interpretation` a prerequisite; spot-check
importance/depth calls by eye.
