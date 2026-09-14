# KnowledgeOS — backend

Python 3.12 · FastAPI · Pydantic v2 · PostgreSQL · networkx · pytest

Layer responsibilities and boundaries are documented in [../ARCHITECTURE.md](../ARCHITECTURE.md).
Current build stage and known issues are in [../PROJECT_STATE.md](../PROJECT_STATE.md).

## Setup

Requires Python 3.12 (the repo pins `requires-python = ">=3.12"`).

```bash
cd backend
py -3.12 -m venv .venv            # or: <path-to-python3.12> -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
cp .env.example .env
```

## Commands

```bash
pytest                 # test suite (Postgres tests use the separate knowledgeos_test
                       # database, created on first run - never your real data)
pytest -k <pattern>    # a single test / subset
ruff check .           # lint
ruff format .          # format
lint-imports           # ENFORCE LAYER BOUNDARIES - see below
```

Run all four before considering a stage done.

## Layer boundaries are enforced, not just documented

`lint-imports` checks the contracts declared in `pyproject.toml` against the real import graph:

1. **Layers are strictly ordered** — `api → assessment → engine → state → curriculum`. A lower
   layer importing a higher one fails the build.
2. **The engine is pure** — `knowledgeos.engine` may not import storage, transport, filesystem,
   `random`, `time`, or `datetime`. Determinism is the engine's central guarantee, and the
   easiest way to lose it is a `datetime.now()` buried inside a formula. **Time enters the
   engine as an explicit parameter** (e.g. `days_elapsed: float`), never by reading a clock.
3. **Curriculum depends on nothing internal** — Layer 1 is standalone.

These have been verified to actually fail on violation, not merely to pass on an empty tree.

## Database

Postgres rather than SQLite because the deployment target is Supabase, which *is* Postgres —
making that migration a deployment change rather than a port. See `ARCHITECTURE.md` §10.

```bash
docker compose up -d      # from the repo ROOT; starts postgres:16 on :5432
cd backend && alembic upgrade head
```

`alembic check` reports whether the models and the live schema have drifted. The database URL
comes from `knowledgeos.config.settings` (and therefore `.env`), **not** from `alembic.ini`, so
migrations can never run against a different database than the app.

Most of the suite does not need any of this. Layer 3 is pure and Layers 1–2 are exercised
through in-memory repositories, so the engine — the hardest part to get right — is tested with
zero infrastructure. `tests/state/test_postgres.py` is the part that needs a live database and
it **skips** rather than fails when one is not reachable.

Both repository implementations satisfy the same protocol, and a parity test asserts they
return identical results for identical operations. That is what makes testing everything above
Layer 2 against the fast in-memory implementation trustworthy.

## Layout

```
knowledgeos/
├── curriculum/   L1  static DAG            (Stage 1)
├── state/        L2  user overlay          (Stage 2)
├── engine/       L3  deterministic, pure   (Stage 3)
│   └── config.py     every [TUNABLE] parameter, in one place
├── assessment/   L4  Schema A/B boundary   (Stage 4)
├── api/              FastAPI routers       (Stage 5)
└── config.py         infrastructure settings only
tests/
└── conftest.py       shared fixtures
```

`config.py` at package root holds infrastructure settings; `engine/config.py` holds engine
tuning parameters. They are deliberately separate so Layer 3 never depends on app wiring.
