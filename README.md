# KnowledgeOS

A personal interview-preparation operating system. It maintains an evidence-based model of what
you know across six role tracks, detects prerequisite gaps, models forgetting, and recommends
what to study next to maximise **expected readiness gain per unit of effort** — not to close the
biggest gap.

It is not a tutor, a notes app, or a flashcard system. Teaching and questioning happen
elsewhere; this owns the model of your knowledge and the decisions that follow from it.

---

## The idea it is built around

Two mastery numbers, and the distinction between them is the whole design:

- **`intrinsic_mastery`** — what you actually demonstrated. Evidence. It is *never* modified by
  prerequisites, decay, or the passage of time.
- **`effective_mastery`** = `intrinsic × retention × prerequisite_confidence` — what the system
  can currently *trust*. This is what recommendations act on.

So when Probability decays, Naive Bayes becomes less trustworthy without you having forgotten
it — and restudying Probability restores every dependent automatically, **with zero
reassessment**. Nothing is ever destroyed; it just stops being relied upon.

Three other choices follow from taking interviews seriously:

| Concern | Naive | Here |
|---|---|---|
| Readiness | average across topics | **weighted harmonic mean** — 100/100/15 fails an interview but averages 72 |
| Ranking | biggest gap first | **expected readiness gain ÷ learning cost** — effort is the scarce resource |
| Forgetting | full FSRS | **simple exponential stability** — these are discussions, not flashcard flips |

Every score is deterministic and carries a `computation_trace`. The LLM never computes mastery,
retention, readiness, or priority — it returns structured observations, and its self-reported
confidence is capped at 20% of any update's weight.

---

## Run it

Requires **Python 3.12**, **Node 20+**, and **Docker** (for Postgres).

```bash
# 1. database
docker compose up -d

# 2. backend
cd backend
py -3.12 -m venv .venv && .venv\Scripts\activate     # Windows
# python3.12 -m venv .venv && source .venv/bin/activate   # macOS / Linux
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python seed.py --demo          # optional: sample assessments so the UI has data
uvicorn knowledgeos.api.main:app --reload            # :8000

# 3. frontend, in a second terminal
cd frontend
npm install
npm run dev                                          # :5173
```

Open <http://localhost:5173>. API docs are at <http://localhost:8000/docs>.

Postgres is optional for a quick look — the API falls back to in-memory storage and says so
loudly, but assessments will not survive a restart.

## The loop

```
browse the graph → pick a concept → copy Schema A → assess externally → paste Schema B
      ↑                                                                        │
      └──────────────── everything recomputes ←────────────────────────────────┘
```

Knowledge state changes **only** through a validated Schema B. Reading, watching, or feeling
ready never move a number, and nothing in the UI accepts a typed score — that would make it an
opinion rather than evidence.

The assessment engine is **an LLM in any chat window** — no API key, nothing metered. The
application generates the prompts, in three steps:

1. **Study** — teaches the concept to the depth your target role needs, then gives reading and
   practice.
2. **Assess** — tests you. It will not teach, hint freely, or tell you how you are doing; each
   of those would corrupt the measurement.
3. **Wrap up** — the LLM replies with one JSON object. Paste it back.

The app owns the prompts deliberately. The moment the LLM decides what "depth" means, two
sessions stop being comparable and the mastery number stops being evidence of anything — so
the scoring rubric, the depth targets and the anti-inflation calibration all live in the
application. Identifiers and timestamps are pre-filled so the model cannot mismatch them, and
anything malformed is rejected with every problem listed at once.

## Commands

```bash
# curriculum (repo root)
python build_graph.py      # regenerate + validate curriculum_graph.json — must print ERRORS: 0
python make_fixture.py     # regenerate the test fixture as an exact subset of the graph
python build_viz.py        # render the standalone curriculum explorer

# backend
pytest                     # 601 tests
ruff check .
lint-imports               # enforce layer boundaries — see below
alembic upgrade head
python seed.py --reset --demo

# frontend
npm run typecheck
npm run build
node drive.mjs             # headless smoke check → shot-*.png (dev server must be running)
```

## Layout

```
CLAUDE.md              the constitution — principles that do not change
ARCHITECTURE.md        system design, layer boundaries, confirmed stack
PROJECT_STATE.md       current stage, decisions, known issues   ← read this first
BUILD_SPEC.md          data contracts (Schema A/B) + the 9-stage build plan
CALC_ENGINE_SPEC.md    every formula and tunable parameter

build_graph.py         the curriculum itself, as data + validator
curriculum_graph.json  566 nodes · 847 edges · 6 roles · 16 sections
curriculum_graph.html  standalone explorer — open it directly, no server

backend/knowledgeos/
  curriculum/          L1  the static prerequisite DAG
  state/               L2  per-node user overlay + append-only history
  engine/              L3  deterministic calculation — pure, no I/O
  assessment/          L4  the Schema A/B boundary
  api/                     FastAPI over L1–L4
frontend/              React + Vite + Cytoscape.js
```

## Layer boundaries are enforced, not documented

`lint-imports` checks three contracts against the real import graph:

1. Layers are strictly ordered — `api → assessment → engine → state → curriculum`.
2. **The engine is pure.** It may not import storage, transport, filesystem, `random`, `time`,
   or `datetime`. Time enters as a parameter (`days_elapsed: float`), never by reading a clock —
   which is what makes every score reproducible from stored evidence.
3. Curriculum depends on nothing internal.

These were verified to *fail on violation*, not merely to pass on an empty tree.

---

Design decisions and the reasoning behind them are in `PROJECT_STATE.md`; the known issues
section documents the places where the spec was ambiguous, what was chosen, and what was
deliberately left as specified rather than quietly "fixed".
