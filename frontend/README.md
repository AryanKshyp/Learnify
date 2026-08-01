# KnowledgeOS — frontend

React + Vite + TypeScript · Cytoscape.js for the graph

## Run

The backend must be running first:

```bash
cd backend && uvicorn knowledgeos.api.main:app --reload   # :8000
cd frontend && npm install && npm run dev                  # :5173
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend, so the frontend never learns
the backend's address and no CORS configuration exists purely for development.

```bash
npm run typecheck    # tsc --noEmit
npm run build        # production bundle
node drive.mjs       # headless smoke check -> shot-*.png (needs the dev server up)
```

## Why the graph is focused rather than complete

566 nodes and 847 edges in one layout is unreadable, and a force layout that size is slow to
settle. Instead the view centres on **one node and its neighbourhood**, with a focus-depth
control (Immediate → Nearby → Extended → Full chain) to widen or narrow it. That mirrors how the
engine reasons: prerequisites upstream, dependents downstream.

Layout is `dagre`, left-to-right, so an arrow always means *must be understood before* —
direction carries the meaning. With no node focused the view shows the **learning frontier**
(concepts whose prerequisites are already met); since those have no edges between them, that
case uses a grid, because dagre would stack them in one useless column.

## What the UI deliberately does not do

- **No dashboard on landing.** The graph is home; readiness and health live behind a tab.
- **Only Mastery and Importance on a node by default.** Retention, stability, intrinsic vs
  effective, variance, next review and the trace are all behind *Advanced*. Eleven numbers on
  first sight teaches nothing.
- **No manual number entry, anywhere.** State changes by one paste of a Schema B. Typing a
  mastery score would make it an opinion rather than evidence.

The domain groupings and section codes are shared with `viz_template.html` so the standalone
curriculum explorer and this app describe the graph the same way.
