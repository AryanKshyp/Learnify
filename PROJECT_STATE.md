# PROJECT_STATE.md

**Where the project stands right now.** This is the one file expected to change often — update it at
the end of any session that changes status, makes a decision, or finds an issue. Durable principles
belong in [CLAUDE.md](CLAUDE.md); system design belongs in [ARCHITECTURE.md](ARCHITECTURE.md).

**Last updated:** 2026-09-16

---

## Current position

**ALL NINE STAGES COMPLETE (0–8).** The build plan in `BUILD_SPEC.md` Part H is finished.
**755 tests green** (29 Postgres tests skip when Docker is down), ruff and layer contracts clean, frontend verified in a real browser with
0 console errors, and the README's steps reproduce a running system.

**The assessment engine is now prompt-driven and complete.** The application generates the
prompts; an LLM in any chat window executes them. No API key, no per-token cost — and the
boundary stays honest, because the app owns what to teach, how deep, what to observe and how to
score it. See "Assessment prompts" below.

| Layer | Status |
|---|---|
| L1 Curriculum content | **Complete** — 566 nodes deepened across all 16 sections, validated |
| L1 Curriculum loader | **Complete** — models, loader, validators, queries; 93 tests |
| L2 Knowledge State | **Complete** — in-memory *and* Postgres repositories, Alembic-migrated |
| L3 Decision Engine | **Complete** — 14 stages, §15 golden case passing, purity machine-enforced |
| L4 Assessment boundary | **Complete** — Schema A/B, strict validation, ingestion pipeline |
| API (Stage 5) | **Complete** — 17 endpoints, one error contract, OpenAPI, injected clock |
| Curriculum seeding (Stage 6) | **Complete** — the app defaults to the real graph; content shape verified |
| Frontend (Stage 7) | **Complete** — Cytoscape focus view, 3 tabs, session loop; screenshot-verified |
| Integration (Stage 8) | **Complete** — end-to-end test, `seed.py`, root README verified |
| External assessment engine | **Complete** — 3 app-owned prompts (study / assess / wrap-up), copy-paste |
| Document prep (post-Stage-8) | **Complete** — Schema C/D boundary, `knowledgeos.documents`, Prep tab |

Verified at each stage close, not assumed:

- `pytest` → **755 passed**. `ruff check .` → clean. `lint-imports` → 3 contracts kept.
- The purity contract is **proven to bite**: injecting `sqlalchemy`/`datetime`/`random` imports
  into `knowledgeos/engine` fails all three with line numbers, exit 1.
- `python build_graph.py` → `ERRORS: 0, WARNINGS: 0`; `python make_fixture.py` → `ERRORS: 0`.
- `CALC_ENGINE_SPEC.md` §15 golden case reproduces the spec's exact numbers.
- `docker compose up -d` + `alembic upgrade head` → Core User Flow verified against real Postgres.
- The frontend renders in a real browser (headless Chrome, `frontend/drive.mjs`) across all
  four views with **0 console errors**.
- The README's own steps were followed end to end: `alembic upgrade head` → `seed.py --demo` →
  `uvicorn` → `/overview` and `/recommendations` return the seeded state.

---

## `/health` now reports which store is really behind it — 2026-09-15

**The trap, found the hard way.** A backend started by hand or by a smoke check uses in-memory
storage. `run.ps1` leaves an already-running backend alone (correctly — it is idempotent), and
then reported `storage postgres` because *it* had brought Postgres up. Both statements were
true and the conclusion was false: the live backend was reading memory while Postgres sat there
healthy and unread. The app looked fine and showed no data, which reads as **"my assessments
are gone"** rather than "you are talking to the wrong store". Nothing was ever lost.

Three changes, so the invisible becomes visible:

1. **`GET /health` returns `storage` and `persistent`**, derived from the repository the app was
   actually handed — not from a flag set at startup. A caller that *intended* Postgres and fell
   back to memory would otherwise report the intention, which is the exact failure being
   exposed. An in-memory instance is indistinguishable from a persistent one until you restart
   it and the evidence is gone.
2. **`run.ps1` reads storage from `/health`** rather than inferring it, and when it leaves a
   running backend alone it warns loudly if that backend is in-memory while Postgres is up.
3. **`frontend/drive-prep.mjs` refuses to run against a persistent store** and deletes the
   document it creates. It ingests a document by design, so it cannot be read-only — which
   makes cleanup and a guard mandatory rather than polite. Fake assessment evidence left behind
   is worse than a stray test document: mastery is supposed to *be* evidence, and evidence
   nobody earned corrupts every number downstream.

**Known, pre-existing, not addressed here:** `session_history` is empty while three nodes carry
`session_count = 1`. State and history disagree, which breaks the C.6 promise that replaying
history reproduces current state. Unrelated to document prep — worth a look before relying on
replay.

---

## Document prep — added 2026-09-15

**"Upload a paper, find out what to study for it."** A fifth tab (**Prep**) and a new layer,
`knowledgeos.documents`. Built after the nine staged gates closed, following the same rules.

The document is **never uploaded to KnowledgeOS** and never parsed here. The user pastes it into
a chat window with an app-generated prompt; only the JSON comes back. No PDF library, no file
storage, no metered API call — and the boundary stays honest for the same reason the assessment
boundary does.

**The division of labour is the whole design:**

| The LLM decides | The app decides |
|---|---|
| which catalogue concepts the document engages with | which prerequisites it silently assumes |
| how deep the document goes on each | what the user is missing, and by how much |
| how central each is to the document | what order to study in, and how long it will take |
| where in the document each came from | the document's readiness, and its bottleneck |

The right column needs the prerequisite DAG and the user's mastery. The model can see neither,
so anything it said about them would be invention — which is why the prompt explicitly forbids
ranking, ordering, estimating, and listing prerequisites.

**The catalogue answers "does the user need to upload a concept list too?" — yes, and the app
generates it.** 566 concepts render to ~27 KB / ~7.6k tokens as `node_id | name`, grouped by
section. Too big to paste into a message, trivial as an attached `.txt`. `GET
/documents/catalogue` serves it scoped by role and/or section; under 8,000 characters it is
embedded in the prompt instead and nothing needs attaching. The scope choice is surfaced in the
UI with its trade-off stated, because a concept outside the scope comes back as
`out_of_curriculum` and looks like a curriculum gap when it is really a scoping mistake.

**Why a catalogue at all:** without it the model returns topic names in its own words and
something must guess which node each meant. A wrong guess attaches a document's requirements to
a concept it never mentioned, and nothing downstream can detect it. An unknown `node_id` is a
hard 422 that names every offending id — never a fuzzy match.

**Layer 3 additions** (`knowledgeos/engine/document.py`, pure, no new mastery mathematics):

- `requirement_closure()` — one backward pass in reverse topological order.
  `target[p] ← max(target[p], φ·w·target[n]/τ_max)`, `weight[p] ← max(weight[p], weight[n]·w·decay)`.
  Reuses φ (the frontier's "prerequisites are satisfied" threshold) rather than inventing a
  second notion of sufficiency. Chains terminate on `document_weight_floor`, not a hop limit.
- `document_readiness()` — §11's weighted harmonic mean over *sufficiency* = `min(EM/τ_doc, 1)`.
  Saturating is deliberate: knowing something far past what the document needs must not paper
  over a real gap elsewhere.
- `document_plan()` — `score_candidates` (§12) for value, then a priority-respecting
  topological pass for order. Ranked on **document** readiness gain, not role readiness: a
  concept can be minor for a role and the one thing blocking this paper.

Three new `[TUNABLE]`s in `engine/config.py`: `document_prerequisite_decay` (0.6),
`document_weight_floor` (0.05), `document_plan_limit` (25).

**Plans are recomputed on every read, never stored.** Only the Schema D is persisted
(`document_plans` table, migration `b7f2c419ad30`). Verified live against the real graph: on
*Attention Is All You Need* (5 stated concepts → 19 required, 14 implied), assessing three
linear-algebra prerequisites moved readiness 5.0% → 5.8% and effort 73.6h → 71.4h with no
re-extraction. A stored plan would have been a souvenir of the day it was pasted.

**Verified:** **728 passed** (704 + the 23 Postgres tests when a database is up) — 60 new
tests: 24 engine, 20 boundary, 16 API. `ruff check .`
clean, `lint-imports` 3 contracts kept with `knowledgeos.documents` now in the layer order, and
the Prep tab driven in headless Chrome (`frontend/drive-prep.mjs`) with **0 console errors**.

---

## Assessment prompts — added 2026-08-07

The external assessment engine is a set of **prompts the application generates**, not an API
integration. An LLM in any chat window executes them; nothing is metered.

`knowledgeos/assessment/prompts.py`, served at
`GET /sessions/open/{id}/prompt?phase=study|assess|wrapup|full`.

**Three prompts, not one.** An LLM told up front to "teach, then test, then emit JSON"
reliably emits the JSON early or drifts from the contract across a long conversation — and the
learner, not the model, should decide when they are done being tested. `assess` also works
standalone for someone who studied elsewhere.

| Phase | Does |
|---|---|
| `study` | Teaches to the target depth, then gives reading + practice + interview framing |
| `assess` | Tests. Does not teach, hint freely, or reveal scores — each would corrupt the measurement |
| `wrapup` | Emits the Schema B |
| `full` | study + assess in one paste, with the phase boundary still enforced |

**The app owns the scoring rubric, not the model.** The moment an LLM decides what `depth`
means, two sessions stop being comparable and the mastery number stops being evidence. So the
prompts carry anchored 0.00/0.25/0.50/0.75/1.00 scales for recall, depth and transfer, and
adapt teaching *and* questioning to the node's required depth (at `awareness` a missing
derivation is not a gap; at `derivation` fluent recitation is not the same as deriving).

**A large part of each prompt exists purely to fight score inflation**, which is the single
failure mode that would corrupt everything downstream — mastery, readiness, priority and the
whole ranking are functions of these three numbers. Left alone an LLM scores a mediocre answer
at ~0.75. The prompts state that most genuine first sessions land below 0.50, that needing a
hint lowers the score, that paraphrase fluency is recall rather than depth, and that an
inflated score is the specific harm the system exists to prevent.

**Failure modes designed out rather than instructed against:**
- `session_id`, `node_id` and `completed_at` are **pre-filled** — a mismatched id or a
  hallucinated date is a hard rejection, and neither needs to be asked for.
- `prerequisite_flags` lists the **exact valid node_ids**; an unknown id is rejected.
- `recommended_next_concepts` is pre-filled `[]` — the app ranks by leverage, cost and
  readiness, which the model cannot see.
- Prior mastery is included for targeting but explicitly marked "not a target, not a floor",
  because telling a model the previous score invites it to confirm that score.
- The prompt states that `llm_confidence` is capped at 20% of update weight, removing any
  incentive to overstate it.
- The UI strips a markdown fence before parsing: models add one despite instructions, and the
  contract that matters is the object's shape, not its packaging.

A test asserts that a **filled-in wrap-up template is actually accepted by the ingestion
pipeline**. If the template and validator ever drift, every session would fail at the last
step — after the learner has done all the work.

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

### Shareable graph visualization — added 2026-08-01
`python build_viz.py` renders `curriculum_graph.json` into **`curriculum_graph.html`**, a
self-contained 427 KB page (no server, no network) for external review of Layer 1 content. Five
views: **Start here** (see below), **Map** (16 section plates in six domain bands, shaded by depth /
role importance / downstream leverage), **Chains** (a concept's prerequisite cone and dependents, n
hops each way), **Nodes** (sortable, filterable, CSV export), **Audit** (10 structural checks,
coverage and depth distributions, cross-section dependency matrix, longest chain, highest-leverage
concepts).

**Start here** is the default view and the one to send to someone who has never seen the project.
It applies overview-first / detail-on-demand rather than showing 566 nodes at once:

- **Level 1** — the 16 sections as bubbles in six left-to-right domain columns, sized by concept
  count. Only the 23 topic links carrying ≥3 edges are drawn by default (stated in the legend, not
  hidden); clicking a topic reveals all of its links and colours what it needs orange and what
  builds on it green.
- **Level 2** — one topic opened, its concepts laid out as labelled chips in numbered learning
  steps (intra-section longest-path layers, 5 per row). Clicking a concept lights its direct
  prerequisites and dependents; a prerequisite in another topic navigates there rather than
  leaving a dead selection.
- A **"Preparing for"** role filter restyles both levels — off-role topics shrink and go dashed —
  and stays in sync with the expert `Role` select on the other tabs.

Colour is load-bearing and was validated with the dataviz skill's checker rather than eyeballed:
16- and 6-way categorical palettes both FAIL the all-pairs colourblind gate (worst normal-vision
ΔE 12.9 against a floor of 15), so section identity is carried by **position**, magnitude by a
single-hue blue ramp, and selection state by the blue/orange/aqua trio that does pass all-pairs in
both light and dark.

The graph JSON is embedded verbatim and every figure is recomputed in the browser from it, so a
reviewer's numbers are derived from the committed bytes rather than from a snapshot taken at build
time. Spot-checked against Python: max depth 19, longest chain 20, 24 roots, 286 leaves, 1399 role
assignments, top-leverage 218/205/198/190 — all agree. The Audit tab's one non-PASS is the
documented 3 isolated nodes, reported as REVIEW rather than FAIL.

`build_viz.py` reads `viz_template.html`; `build/viz_body.html` is a body-only fragment for hosting
and is gitignored.

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
| 2026-09-14 | **Session role is chosen by the learner; the default is the node's most *important* role, not its highest-*ranked* one.** | Rank alone meant every node tagged for AI Research (rank 1) was assessed at the AI Research depth however marginal it was to that role — `dsa-big-o` was taught to `working` (importance 0.60) instead of `derivation` (importance 0.95 for Software Engineering). The learner targets six overlapping roles and only they know which one a session serves, so `POST /sessions` now takes an optional `role_id`; the importance-ranked default only fires when none is given. Rule written up as `BUILD_SPEC.md` C.7.1. |
| 2026-09-16 | **`StateOverlay` narrowed from twelve methods to three.** | `get`, `for_role`, `for_section`, `assessed`, `unassessed`, `with_status`, `__iter__`, `curriculum` and `NodeState.importance_for` had no production caller — each was a one-line filter over `all()` that made the interface wider than the two rules the class exists to enforce (validate writes against the curriculum, apply cold defaults on read). Slicing belongs to `CurriculumGraph` and ranking to the engine. `save_many` went with them: its only caller was `_apply_derived`, deleted the same day. `unassessed` was also a rival definition of the set `engine.unexplored` derives, so the predicate now has one home — `KnowledgeState.is_assessed`. A test pins the three-method surface so the lenses cannot creep back. |
| 2026-09-16 | **The assessment protocol moved into `lib/session-protocol.ts`.** | Twelve `useState` calls in `SessionFlow` modelled a five-state protocol, and one illegal combination was reachable: `loading` started `true` and was only cleared by the prompt effect, which returned early without a session id — so a failed open rendered the error beside a permanently disabled "Loading…" button with no way out but closing the panel. `loading` is now derived from the stage rather than stored. The union also captures the distinction the flags could not: failing to *open* is terminal and offers a retry, while a rejected *paste* leaves the session open to fix and resubmit. `parseSchemaB` — the fence-stripper, the most failure-prone line in the frontend — is now a pure exported function instead of three lines inside an event handler, and `Phase` is declared once instead of four times. |
| 2026-09-16 | **One module owns reading server state in the frontend (`src/api/server-state.tsx`).** | Invalidation is global by nature — propagation means one ingestion moves almost every number on screen — but it was expressed as a `refreshKey` integer prop threaded into four components, each re-implementing the same fetch-and-cancel effect. The convention was invisible: a new view that forgot the prop, the dependency entry or the cancellation guard showed stale numbers rather than failing. Three of the four had no rejection handler at all, so a failed request left a permanent spinner (Overview), a blank panel (NodeInspector) or a heading over nothing (Recommendations), with the reason only in the console; `App` caught its two but flattened them with `String(e)`, discarding the multi-problem envelope the backend exists to produce. `useServerState` owns fetching, cancellation, error unwrapping and re-reading; `useInvalidate` replaces the prop. A caller can no longer opt out of handling a failure, because there is no `.catch` to leave off. |
| 2026-09-16 | **The role/section lens moved into `recommend()`, and `Candidate` now carries its own explanation factors.** | The routers used to ask for `limit * 4` (role) or `limit * 8` (section) unfiltered picks and filter them down. That ranks and MMR-diversifies a set it is about to discard — so the diversity guarantee landed on the wrong list and the survivors could all be near-duplicates — and the multipliers were guesses: a lens whose eligible nodes all ranked below the window returned fewer than `limit`, or nothing, with no signal. `recommend()` now takes `role_id` / `section` and intersects the candidate set before scoring. Separately, `_explain` recomputed the per-role bottlenecks and the descendant count in the API layer, both of which the engine had already computed and discarded; `Candidate` carries them as factors (`blocking_roles`, `unlocks`, `is_frontier`) and the router only formats the sentence. |
| 2026-09-16 | **The engine's single-caller stage modules were dissolved into `pipeline.py`, and the package interface narrowed from 55 exported names to 23 (47 before document prep added its eight).** | `status.py`, `health.py` and `position.py` each held stages with exactly one caller — `pipeline.recompute` — behind an interface as wide as its implementation, so reading the small module instead of the pipeline was never an option and one number's derivation spanned four files. They are now sections of `pipeline.py`. `observation`, `retention`, `propagation`, `readiness` and `recommend` stay separate because they have callers besides the pipeline; folding `position`/`readiness` in would have produced an import cycle with `recommend`. The package now exports only the entry points, the config and the result types; stage functions remain importable from their own modules, which is how the engine's own tests reach them — an internal seam, distinct from the interface. |
| 2026-08-01 | **Purity contract relaxed to `allow_indirect_imports`.** | The engine legitimately imports the Layer 2 `Status` type, whose module references `datetime`/`uuid` as *field types*. That transitive edge is not a clock read. Direct imports of `datetime`/`random`/`os` in engine code are still rejected — re-verified by injection after the change. |

---

## Known issues

### 23. The wire contract had drifted, and the status map defeated the compiler — **fixed 2026-09-16**
`api/types.ts` is hand-maintained alongside `api/schemas.py` with no single owner, and it had
drifted in four concrete places:

* `ApiErrorBody` was missing `session_id`, `node_id`, `role_id` and `valid_roles`, all of which
  `api/errors.py` attaches. An unknown-session or wrong-role rejection degraded to the bare
  message and dropped the detail that said which session, or which roles were actually valid.
  `ApiError.problems` now surfaces them.
* The `/sessions/open/{id}/prompt` response was declared inline in `client.ts` with three of the
  six keys the endpoint returns.
* `POST /sessions` sent an untyped object literal; `SessionRequest` had no TS counterpart.
* Schema A crossed as `Record<string, unknown>` and was cast blind at three call sites.

Four client members — `health`, `readiness`, `unexplored`, `sessions` — had no caller anywhere
in `src/`. Removed.

Separately, `STATUS_COLOR` and `STATUS_LABEL` were typed `Record<string, string>`, which threw
away the `Status` union declared right next to them: adding a status to the backend enum would
compile clean and render a colourless node. Both are now `Record<Status, string>`, so it is a
compile error until the ramp is extended.

**Not done, and a real decision rather than an oversight:** generating `types.ts` from the
OpenAPI the backend already serves. That is the actual fix for drift — it makes divergence a
build failure instead of a runtime blank — but it adds a codegen dependency and a build step,
which is a workflow change rather than a refactor. The drift above is repaired by hand; the
generator is still worth doing.

### 22. `KnowledgeState.replace()` bypassed validation entirely — **fixed 2026-09-16**
Found while updating tests after issue #17: `replace` was `model_copy(update=changes)`, which
writes straight into the instance without validating. Unknown field names became phantom
attributes (`replace(status=...)` silently attached a field the model no longer has, and
`hasattr` then returned True for it) and range constraints were skipped entirely —
`replace(intrinsic_mastery=99.0)` produced a `Score` of 99.0.

This matters more than it looks, because `replace` is the **only** way state is ever written:
`AssessmentService.ingest` builds every post-session record with it. So every engine-produced
value reached storage without passing the model's own validation, and the sole remaining check
was the Postgres `CheckConstraint` — which the in-memory repository does not have, meaning the
fast test path could not see a bad value at all. It also quietly undercut the `extra="forbid"`
guarantee that issue #17's test relies on.

Now `model_validate({**self.model_dump(), **changes})`. Six parametrised cases pin it. Directly
a CLAUDE.md §7 rule ("validation is strict and fails loudly; never silently coerce or drop
unknown fields") that nothing was enforcing.

### 21. Two "fast fallback" paths were not fast — **fixed 2026-09-16**
Both had the same shape: documented graceful degradation with no connect timeout, so the
graceful path took minutes and read as a hang.

* `tests/state/test_postgres.py` promises in its docstring that it skips when Postgres is
  unreachable. With Docker stopped a full `pytest` took over two minutes on OS-level connect
  timeouts before deciding to skip. Now 3s, and the suite runs in ~17s either way.
* `api/main.py` probes Postgres at startup and falls back to in-memory "loudly". With Docker
  stopped, uvicorn produced no output at all for minutes before the warning appeared. Now the
  probe times out in 3s and the fallback is immediate.

Found by hitting both while verifying earlier work, not by reading.

### 20. Engine orchestration was untested; six stage functions had no tests at all — **fixed 2026-09-16**
The formulas were well covered and the sequencing was not. `test_golden_case.py` deliberately
propagates its three-node chain by hand so a failure points at a formula rather than at graph
plumbing — defensible, but it means the project's central regression test never touches
`propagate()` or `recompute()`. The 130 lines whose docstring says "ordering is not negotiable"
had nothing asserting the ordering, and `knowledge_health` — the number on the home screen, 8
parameters, four tunables — had zero direct tests; the API only asserted that its keys exist.

`tests/engine/test_orchestration.py` adds 37 tests through `recompute`'s own interface: EM ≤ M,
frontier implies ready prerequisites *and* a real gap, raising any node never lowers a
descendant (randomised), every stage covers every node, and — the one ordering dependency not
visible in the data flow — readiness must run before `current_importance` or bottlenecks lose
their boost. Plus direct values for `knowledge_health`, `critical_path_values`,
`leverage_values`, `intrinsic_importance`, `is_frontier`, `target_for_node`, `min_max_normalize`,
`score_candidates`, `similarity`, `diversify` and `cold_start_queue`.

Also removed a guard that made an existing assertion vacuous: the MMR diversity check in
`test_pipeline.py` was wrapped in `if len(picks) >= 3`, so it passed silently in exactly the
case where the guarantee was worth checking.

### 18. σ² was persisted normalised, coupling storage to a tunable — **fixed 2026-09-16**
`assessment_variance` was stored as `variance_raw / variance_normalizer`, clamped to 0..1, and
multiplied back up on the next session (`state.assessment_variance * config.variance_normalizer`
in `apply_session`). Two things were wrong with that, and one thing was not.

Wrong: the engine had to know the storage format in order to reconstruct its own EWMA state, and
`variance_normalizer` — a `[TUNABLE]` — became retroactive, silently reinterpreting every row
already written the moment it was retuned. Storage also bounded the engine's arithmetic, since
the field was typed `Score`.

**Not wrong, and worth recording because the original report claimed otherwise:** the clamp never
actually fired. With κ = 0.5 the EWMA ceiling is ≈0.0625 — measured, not reasoned — against a
normalizer of 0.10, so no stored value was ever truncated and no learner's variance was ever
lost. This was a latent trap, not a live defect. A test now pins that the clamp stays
unreachable, so a future change to κ or the normalizer has to notice.

The column is now `assessment_variance_raw`, unbounded and non-negative, holding the engine's own
value. `engine.observation.normalized_variance` derives the 0..1 form and `EngineSnapshot.variance`
carries it for the §13 status gates and for the node-detail display — so the wire contract is
unchanged. Migration `e7412ab9cc05` renames and rescales by the 0.10 in force at write time;
verified forward and back on a scratch database, including the data rescale (0.625 → 0.0625 → 0.625).

**Spec change, flagged:** C.5 named the field and called it normalised. `BUILD_SPEC.md` C.5 is
updated to match.

### 19. Frontend server state had no owner — **fixed 2026-09-16**
Five components fetched independently, and cache invalidation after an ingest was a `refreshKey`
integer prop drilled into four of them, each re-implementing `let cancelled = false` around its
own effect. Three had no `.catch` whatsoever: a failed `/overview` spun forever, a failed
`/nodes/{id}` rendered blank, and failed recommendations rendered a heading over nothing — all
three silent, with the reason only in the console.

`src/api/server-state.tsx` now owns it. `useServerState(load, deps)` does the fetching,
cancellation, error unwrapping into `problems[]`, and re-reads on invalidation;
`useInvalidate()` replaces the prop and is called after every write, including document
save/delete in Prep. `problemsOf` replaced three hand-rolled `instanceof ApiError` ladders.
Error handling is now structural: there is no `.catch` for a call site to omit.

Verified in a real browser against an isolated migrated database: all five tabs render with no
console errors, and after driving a full assessment through the UI the views re-read
(`/roles`, `/sections`, `/graph`) and the inspector moved 0% → 29%.

### 17. Knowledge state cached eight derived values that nothing read — **fixed 2026-09-16**
Every ingest ran `_apply_derived`, a full-graph upsert writing `effective_mastery`, `retention`,
`is_frontier`, `critical_path_value`, `leverage`, `current_importance`, `learning_cost` and
`status` onto all 566 knowledge-state rows. Its docstring called it "a cache so the API can serve
a node without re-running the pipeline". Nothing served from it: every handler read
`snapshot.*`, and a grep for production reads of `state.effective_mastery` and its six siblings
returned zero hits. Only `status` had a reader — the ingest response's `status_before`.

Worse than useless, because all eight are functions of the clock. Retention decays by the hour
and effective mastery, cost and status move with it, so the row was wrong the hour after it was
written and there was nothing to indicate it. A second source of truth that disagrees with the
first by design.

Deleted: the seven unread fields and `status` are gone from `KnowledgeState`, from
`knowledge_state`, and from C.5 (migration `d5b90c4a1e73`, verified forward and back on a
scratch database). `EngineSnapshot` is now the only place derived values exist. What remains in
storage is exactly the evidence the engine needs to reproduce them.

`status_before` / `status_after` on the ingest response now come from snapshots taken either
side of the write, inside `AssessmentService.ingest`. That costs one extra pass over the graph
per ingest — roughly what the removed 566-row upsert cost — and it is *more* correct than the
column was: the cached value ignored any decay since the previous ingest.

Consequences: `StateOverlay.with_status()` went with the field it filtered on (it had no
production callers). `extra="forbid"` on the model means writing any of the eight is now a loud
validation failure rather than a field nobody notices is wrong, which a test pins.

**Spec change, flagged:** C.5 listed all eight as stored fields, so this edits a contract rather
than an implementation detail. `BUILD_SPEC.md` C.5 is updated to match, with the reasoning
inline; per CLAUDE.md §5 the spec is authoritative, so leaving code and spec disagreeing was not
an option.

### 16. An open session did not survive a restart — **fixed 2026-09-16**
Schema A payloads lived in `InMemoryPendingSessionStore`, a process dict, while every other
durable fact was in Postgres. `create_app` had no `pending=` parameter, so `main.py` wired
Postgres for state, history and documents and left this one in memory with nothing to swap in.

The two halves of a session are separated by a copy-paste into another tool, so an open session
routinely outlives a deploy. A restart in that window made `POST /sessions/ingest` return 404
`UnknownSessionError` permanently — the assessment was unrecoverable, and because nothing is
appended to `session_history` until ingestion succeeds, there was no record it had happened.

`PendingSessionStore` had been a protocol with one implementation since Stage 4: a hypothetical
seam. It now has two. `PostgresPendingSessionStore` (`assessment/postgres.py`) stores the Schema A
verbatim in a new `pending_sessions` table; `take()` is a single `DELETE ... RETURNING` so two
concurrent ingests of the same paste cannot both apply the evidence. The table deliberately has
**no** foreign key to `knowledge_state`, unlike `session_history` — a node has no state row until
its first Schema B lands, and an FK would refuse exactly the first session on every concept.

Found while fixing it: `self._pending = pending or InMemoryPendingSessionStore()`. The Postgres
store defines `__len__`, so an **empty** store is falsy and the injected one was silently thrown
away. The same `or` idiom was used for every repository in `create_app`, and
`InMemorySessionHistoryRepository` and `InMemoryDocumentRepository` both define `__len__` too —
so passing an empty one of those has been silently replaced by a fresh instance all along. All
five sites now test `is None`.

`/health` reports `pending_storage` separately and `persistent` now means both stores, because
knowledge state in Postgres with pending sessions in memory still loses open sessions.

Verified: a session opened through one `AssessmentService`, then ingested through a completely
fresh stack rebuilt over the same database, lands (`test_a_session_survives_a_restart`); plus a
parity test against the in-memory store, mirroring the ones for state and history.

### 15. The Postgres tests deleted the development database — **fixed 2026-09-14**
`tests/state/test_postgres.py`'s `engine` fixture connected to `settings.database_url` — the same
database the running app uses — and the `states` fixture called `repo.clear()` (`DELETE FROM
session_history; DELETE FROM knowledge_state`) before **and** after each of its 23 tests. There
was no separate test database. Every full `pytest` run therefore wiped all real assessment
history, silently, and had done so since the Postgres tests landed: the container log carries the
same constraint-violation signature on 08-01, 08-04, 08-07, 08-13, 09-05, 09-06, 09-09, 09-10,
09-11, 09-12 and 09-14. Two real sessions (`dsa-big-o`, `dsa-arrays-strings`) were destroyed on
2026-09-14; they are not recoverable — there are no backups, WAL archiving is not configured, and
no endpoint exposes the stored `schema_b` needed to replay them.

Fixed with `settings.test_database_url` (default `…/knowledgeos_test`), which the fixture creates
via the `postgres` maintenance database if absent, plus two refusals **before any connection is
opened**: the database name must end in `_test`, and it must differ from `database_url`. The guard
is the durable half — a separate URL alone would be one mis-set env var away from the same loss.

Verified: a sentinel row written to the dev database survives a full `pytest` run (664 passed);
pointing `TEST_DATABASE_URL` at `knowledgeos` fails every test at setup with
`refusing to run: … does not end in '_test'` and deletes nothing.

**Unrelated finding, still open.** The backend serving port 8000 on 2026-09-12–14 was started by
hand under system Python (not `backend/.venv`) and was running code old enough that only `states`
was wired to Postgres — `session_history` was in-memory, so `/sessions` reported two records that
no longer existed in the database. Worth knowing when a symptom looks impossible: check the
process was started from `run.cmd` and is running current code before trusting what it reports.

### 14. Every prompt was framed for AI Research — **fixed 2026-09-14**
`select_role_context` picked the role with the lowest `priority_rank`, and AI Research is rank 1.
Importance and required depth were never consulted, so any node AI Research touched was taught
and tested through that lens at that depth. Studying Big-O as a Software Engineering candidate
produced an AI-Research-framed prompt targeting `working` when the role needs `derivation` —
under-preparing the learner on their most important algorithms topic, which is the exact failure
this system exists to prevent.

Fixed in three parts:

- `POST /sessions` accepts an optional `role_id`; `AssessmentService.generate` and
  `select_role_context` thread it through. A role the node is not tagged for is a 422
  (`RoleNotApplicableError`) naming the roles that do apply; an unknown role is the existing 404.
- The default became "most important role", ties on `priority_rank` then `role_id` — still fully
  deterministic. `dsa-big-o` now defaults to software-engineering / `derivation`.
- `SessionFlow` shows an **Assessing for** selector listing the node's roles with their depths,
  defaulted from the global role filter when the node serves it. That filter existed already but
  was never passed to the session — the one place it mattered most.

Verified: 664 tests green; `dsa-big-o` over HTTP returns software-engineering/`derivation` by
default, ai-research/`working` when asked for; driven in headless Chrome (`frontend/drive-role.mjs`)
switching the role and re-reading the generated prompt's depth, 0 console errors.

**Consequence to be aware of:** nodes are now assessed by default at the depth of whichever role
needs them most, which can be a role low on the priority list — `prob-axioms` defaults to
finance-quant / `derivation` rather than ai-research / `deep`. That errs toward over-depth, which
costs time; the previous behaviour erred toward under-depth, which costs the offer. Selecting a
role in the dropdown removes the ambiguity entirely.

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

### 13. N+1 query in `StateOverlay` — **fixed 2026-08-01**
`all()`, `for_role()` and `for_section()` looped over `get()`, issuing one query per node — 566
round-trips to answer a single request. Completely invisible against the in-memory repository
(dict lookups) and only surfaced when the API was measured against Postgres with the real
curriculum. Fixed with a single bulk read joined in memory: **635ms → 8ms**.

End-to-end effect on the 566-node graph with Postgres:

| Endpoint | Before | After |
|---|--:|--:|
| `GET /overview` | 1401ms | **121ms** |
| `GET /recommendations` | 978ms | **228ms** |
| `GET /graph?role=…` | 2258ms | **67ms** |
| `POST /sessions/ingest` | 3435ms | **296ms** |

The lesson generalises: the in-memory repository makes the test suite fast, but it cannot
reveal a query-count problem. Any new bulk read must go through `StateOverlay._stored()`.

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

The staged build plan is done. What remains is one artifact and some judgement calls that need
real usage data rather than more code.

1. **Build the external assessment engine.** The prompt or Claude skill that conducts a session
   and emits a valid Schema B. Every contract it must honour is implemented and strictly
   validated, so it can be developed against a live, unforgiving API rather than a document.
   Until it exists, the loop works but needs a hand-written Schema B.
2. **Use it, then tune.** Known issues #10 (leverage terms combine unbounded counts with bounded
   scores before normalising) and #11 (ERG does not re-propagate into dependents) are both
   implemented exactly as specified and flagged rather than quietly "fixed". Both are better
   judged against real sessions than against intuition.
3. **Optional polish:** give `cs-compilation-interpretation` a prerequisite so it is not an
   orphan; spot-check importance/depth calls by eye — the validator guarantees structure, not
   that the content judgements match yours.

### If it is ever made multi-user (Supabase)
The contracts carry no `user_id`; scoping would be added at the storage layer only. The engine
is pure and the curriculum is shared and static, so neither would change.
