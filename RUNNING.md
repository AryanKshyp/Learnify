# Running Learnify locally

Three processes: **Postgres** (Docker), the **backend** (FastAPI, port 8000), and the
**frontend** (Vite, port 5173). The frontend talks to the backend through a proxy, so you only
ever open one address.

> Every command and every symptom below was run on this machine, not recalled from memory.
> Timings are what it actually took.

## One command

```powershell
.\run.cmd
```

Starts Docker Desktop if it isn't running, brings up Postgres, applies migrations, launches
both servers, waits until each actually answers, and opens the app. Safe to re-run — anything
already running is left alone.

| | |
|---|---|
| `.\run.cmd` | start everything |
| `.\run.cmd -Fresh` | start, wiping state and loading sample data |
| `.\run.cmd -Demo` | start and add sample data |
| `.\run.cmd -Stop` | stop everything (Postgres data kept) |
| `.\run.cmd -Dev` | backend with auto-reload, for editing code |
| `.\run.cmd -NoDocker` | run in memory, no database |

First run also creates the virtualenv and installs dependencies (~3 min). Use `run.ps1` directly
if you prefer; `run.cmd` only exists so PowerShell's execution policy can't block it.

The rest of this page is what those steps do by hand, and what to check when one of them fails.

---

## What you need

| | Version here | Check |
|---|---|---|
| Python | 3.12.10 | `python --version` |
| Node | 22.13.0 | `node --version` |
| Docker Desktop | 29.6.2 | `docker --version` |

Python **3.12 or newer** is required — `pyproject.toml` pins `requires-python = ">=3.12"` and
the code uses 3.12 syntax. A 3.11 install will fail at `pip install`.

Docker is only for Postgres. You can run without it — see
[Running without Docker](#running-without-docker) — but nothing you do will survive a restart.

---

## First-time setup

Run once. Takes about three minutes, most of it `pip install`.

```powershell
# from the repo root
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

<details>
<summary>bash / macOS / Linux</summary>

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```
</details>

Then the frontend:

```powershell
cd ..\frontend
npm install
```

Then create the database schema (Docker must be running — see step 1 below):

```powershell
cd ..\backend
alembic upgrade head
```

**You do not need a `.env` file.** `knowledgeos/config.py` already defaults to the same
connection string `docker-compose.yml` creates. Copy `.env.example` to `.env` only if you want
to point at a different database.

### Optional: sample data

An empty install shows an empty graph, which makes it hard to tell working from broken.

```powershell
python seed.py --demo
```

```
curriculum: 566 nodes, 847 edges, 16 sections, 6 roles  [validated]
demo: 9 sessions recorded
stored: 566 state rows, 9 assessed, 9 sessions
health: 0.8/100, frontier 24 nodes
  AI Research     5.0%   held back by dl-attention
```

`python seed.py --reset --demo` wipes everything first. `--reset` alone clears it back to empty.

---

## Every time

Three terminals. Order matters: the backend needs the database, and the frontend proxies to the
backend.

### 1 · Database

```powershell
# repo root
docker compose up -d
```

Docker Desktop must be running first. If `docker ps` errors, start Docker Desktop and wait —
**it can take a minute or two**, and on this machine the first launch sometimes doesn't stick
and needs a second attempt. Postgres itself is healthy about 2 seconds after the container
starts.

```powershell
docker compose ps        # STATUS should read "Up (healthy)"
```

### 2 · Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn knowledgeos.api.main:app --reload
```

Runs on **http://localhost:8000**. Keep `--reload` — without it the server keeps serving the
code it started with, and a change you just made appears to do nothing.

### 3 · Frontend

```powershell
cd frontend
npm run dev
```

Runs on **http://localhost:5173**.

## Open it

### 👉 http://localhost:5173

The **first page load takes about 5 seconds** — Vite compiles on demand. It is instant after
that. A blank page for a few seconds is normal; a blank page for thirty is not.

Also available:
- **http://localhost:8000/docs** — interactive API reference
- **`curriculum_graph.html`** in the repo root — the standalone curriculum explorer.
  Double-click it. No server, no network, nothing to start.

---

## Check it actually works

```powershell
curl http://localhost:8000/health
# {"status":"ok","curriculum_nodes":566,"curriculum_edges":847,"roles":6}

curl http://localhost:5173/api/health
# same response — this proves the proxy is wired
```

If the first works and the second doesn't, the backend is fine and the problem is the frontend
proxy (`frontend/vite.config.ts`).

`curriculum_nodes: 566` confirms the real curriculum loaded. If you see **26**, something is
serving the small test fixture instead.

---

## Stopping

`Ctrl+C` in the frontend and backend terminals. Then:

```powershell
docker compose down       # stops Postgres, keeps your data
docker compose down -v    # stops it and DELETES the volume — all assessments gone
```

Data lives in a Docker volume, so `down` and `up -d` is safe. Only `-v` destroys it.

---

## Troubleshooting

### `docker` is not recognised

Docker Desktop installs per-user on some machines —
`%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin` — rather than under Program Files, and
that directory may not be on PATH. Either add it, or call it directly:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" ps
```

If you installed Docker Desktop while a terminal was open, that terminal has the old PATH.
Open a new one.

### "Docker Desktop is unable to start"

Usually WSL has no kernel installed. Check:

```powershell
wsl --version      # should print a Kernel version line
wsl --status
```

If the kernel line is missing, `wsl --update` (elevated) and restart Docker Desktop. Docker
provides its own `docker-desktop` distro, so "no installed distributions" on its own is fine.

### Checking whether Docker is ready

Use `docker ps`, not `docker info`. `docker info` can **exit 0 while printing an error**, so a
script that checks only the exit code will report a dead daemon as ready.

### The page won't load at 127.0.0.1

Use **`localhost`**, not `127.0.0.1`. Vite binds to `localhost` only, and the difference is not
cosmetic:

```
127.0.0.1:5173 -> connection failed
localhost:5173 -> 200
```

This bites `curl` and scripts more than browsers.

### Port already in use

Something from a previous run is still holding it.

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object -Expand OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

Swap `8000` for `5173` or `5432` as needed.

### A code change did nothing

The backend was started without `--reload`. New endpoints will 404 and edits will not appear.
Restart it with the flag.

### Assessments disappear when I restart

The backend could not reach Postgres and fell back to in-memory storage. It says so in its
startup log:

```
Postgres unreachable (...) - falling back to IN-MEMORY storage.
Assessments will NOT survive a restart.
```

Start Docker, run `alembic upgrade head`, and restart the backend.

### `seed.py` reports it cannot reach Postgres

Exactly what it says — the container isn't up. `docker compose up -d`, then
`alembic upgrade head`, then retry.

### `alembic` complains about the schema

```powershell
alembic upgrade head     # apply pending migrations
alembic check            # "No new upgrade operations detected." = models and schema agree
```

If `check` reports differences, the models moved without a migration.

### The graph is empty

Expected on a fresh install — nothing is assessed yet. `python seed.py --demo` gives it
something to show. The graph home deliberately opens on the **learning frontier** (concepts
whose prerequisites are already met), so an untouched install shows only root concepts.

### My assessments have disappeared

Check which store the running backend is actually using:

```powershell
curl http://localhost:8000/health
```

If it says `"storage": "memory"`, **nothing is lost** — the app is reading an in-memory instance
and your data is still in Postgres, unread. This happens when a backend was already listening on
:8000 before you ran `.
un.cmd`: it is idempotent and leaves a running backend alone, so a
throwaway one started by hand or by a smoke check stays in place.

```powershell
.
un.cmd -Stop
.
un.cmd
```

`run.cmd` now reads storage from `/health` rather than assuming, and warns when it leaves a
backend alone that turns out to be in-memory while Postgres is up. To confirm your data is
there before restarting:

```powershell
docker exec knowledgeos-postgres psql -U knowledgeos -d knowledgeos `
  -c "select node_id, intrinsic_mastery, session_count from knowledge_state where session_count > 0;"
```

---

## Running without Docker

The backend falls back to in-memory storage if Postgres is unreachable, so this works for a
quick look:

```powershell
cd backend
uvicorn knowledgeos.api.main:app --reload
```

The curriculum still loads (it comes from `curriculum_graph.json`, not the database), and the
full session loop works. **Everything you record is lost when the process stops.** The fallback
is deliberately loud in the log, and `/health` reports `"storage": "memory"`, so you can always
tell from outside the process which store you are talking to.

---

## What to do first

1. Click a concept in the graph. The panel on the right shows **Mastery** and **Importance**;
   everything else is under **Advanced**. To find a specific topic rather than pan for it, use
   the **Browse** tab — search all 566 concepts and filter by section, competency, status, or
   whether the prerequisites are already met.
2. Hit **Start assessment**. You get three prompts to copy into any LLM chat window — study,
   assess, then wrap up. No API key; nothing is metered.
3. Paste the JSON the LLM returns into the box. That is the only thing in the application that
   changes what it believes you know.

The full loop is in the [README](README.md#the-loop).

---

## Developing

```powershell
# backend (venv activated)
pytest                 # 655 tests
ruff check .
lint-imports           # enforces the layer boundaries

# frontend
npm run typecheck
npm run build
node drive.mjs         # headless browser smoke check; dev server must be running

# curriculum (repo root)
python build_graph.py  # regenerate + validate — must print ERRORS: 0
python make_fixture.py # regenerate the test fixture after changing the graph
python build_viz.py    # rebuild curriculum_graph.html
```

Run all four backend checks before considering a change done. `lint-imports` is the one that
catches architectural drift — it fails if the engine imports storage, transport, a clock, or
randomness.
