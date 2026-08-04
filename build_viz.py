#!/usr/bin/env python3
"""Render curriculum_graph.json into a shareable, self-contained HTML explorer.

Two outputs, from one template:

  curriculum_graph.html   a complete document — open it by double-clicking, mail it,
                          drop it in a shared folder. No server, no network.
  build/viz_body.html     the same page as a body fragment, for publishing as a
                          hosted artifact (which supplies its own <html>/<head>).

The graph JSON is embedded verbatim. Every number the page shows — depth, closure
sizes, the cross-section matrix, the integrity checks — is recomputed in the browser
from that embedded copy, so what a reviewer reads is derived from the same bytes that
are committed to the repo, not from a snapshot taken here.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = ROOT / "curriculum_graph.json"
TEMPLATE = ROOT / "viz_template.html"
STANDALONE = ROOT / "curriculum_graph.html"
FRAGMENT = ROOT / "build" / "viz_body.html"

DOC_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="KnowledgeOS Layer 1 curriculum graph: {nodes} assessable concepts, {edges} prerequisite edges, 6 target roles.">
<style>*{{margin:0}}html{{background:#f9f9f7}}@media(prefers-color-scheme:dark){{html{{background:#0d0d0d}}}}</style>
</head>
<body>
"""
DOC_TAIL = "</body>\n</html>\n"


def main() -> int:
    if not GRAPH.exists():
        print(f"ERROR: {GRAPH.name} not found. Run `python build_graph.py` first.")
        return 1
    if not TEMPLATE.exists():
        print(f"ERROR: {TEMPLATE.name} not found.")
        return 1

    raw = GRAPH.read_bytes()
    graph = json.loads(raw)

    n_nodes, n_edges = len(graph["nodes"]), len(graph["edges"])
    ids = {n["node_id"] for n in graph["nodes"]}
    problems = []
    if len(ids) != n_nodes:
        problems.append(f"{n_nodes - len(ids)} duplicate node_id(s)")
    dangling = [
        e for e in graph["edges"]
        if e["from_node_id"] not in ids or e["to_node_id"] not in ids
    ]
    if dangling:
        problems.append(f"{len(dangling)} edge(s) referencing a missing node")
    for p in problems:
        print(f"WARNING: {p} — the page will surface this in its Audit tab")

    # Compact, and neutralise "</" so the JSON can never terminate the <script> element.
    payload = json.dumps(graph, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    built = datetime.now(timezone.utc).strftime("Built %Y-%m-%d %H:%M UTC")

    body = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("/*__GRAPH_JSON__*/ null", payload)
        .replace("/*__BUILT__*/", built)
        .replace("/*__SRC_BYTES__*/ 0", str(len(raw)))
    )

    for token in ("__GRAPH_JSON__", "__BUILT__", "__SRC_BYTES__"):
        if token in body:
            print(f"ERROR: placeholder {token} was not substituted.")
            return 1

    STANDALONE.write_text(
        DOC_HEAD.format(nodes=n_nodes, edges=n_edges) + body + DOC_TAIL,
        encoding="utf-8",
        newline="\n",
    )
    FRAGMENT.parent.mkdir(exist_ok=True)
    FRAGMENT.write_text(body, encoding="utf-8", newline="\n")

    kb = STANDALONE.stat().st_size / 1024
    print(f"{n_nodes} nodes, {n_edges} edges, {len({n['section'] for n in graph['nodes']})} sections")
    print(f"wrote {STANDALONE.relative_to(ROOT)}  ({kb:.0f} KB, self-contained)")
    print(f"wrote {FRAGMENT.relative_to(ROOT).as_posix()}  (body fragment)")
    print(f"ERRORS: {len(problems)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
