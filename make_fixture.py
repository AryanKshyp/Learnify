#!/usr/bin/env python3
"""
Derives curriculum_fixture.json — the small connected test slice used by Stages 1-3 —
from the full curriculum_graph.json.

The fixture must be an EXACT SUBSET of the real graph: identical node objects, identical
edge objects, edge-closed (every edge references a node inside the slice). That property is
what lets tests written against the fixture stay valid when the full graph is loaded at
Stage 6. Hand-maintaining the fixture breaks that property silently, so it is generated.

Selection = a set of seed nodes plus the transitive closure of their prerequisites. Seeds are
chosen so the slice exercises everything the Stage 1 loader must handle:
  - cross-section prerequisite edges
  - a node with MULTIPLE parents (proves the loader treats the graph as a DAG, not a tree)
  - a multi-hop chain (for ancestors / descendants queries)
  - nodes tagged for different role subsets, at all four required_depth levels
  - the CALC_ENGINE_SPEC.md SS15 golden chain: prob-conditional -> prob-bayes -> ml-naive-bayes

Run:  python make_fixture.py
"""

import json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = os.path.join(HERE, "curriculum_graph.json")
FIXTURE = os.path.join(HERE, "curriculum_fixture.json")

# Seeds. Their prerequisite ancestors are pulled in automatically.
SEEDS = [
    "ml-naive-bayes",          # SS15 golden chain leaf; also pulls prob-bayes -> prob-conditional
    "ml-logistic-regression",  # multi-parent node: 3 prerequisites across 2 sections
    "dl-attention",            # cross-section: deep-learning -> linear-algebra
]


def main():
    if not os.path.exists(GRAPH):
        sys.exit(f"ERROR: {GRAPH} not found - run build_graph.py first")

    with open(GRAPH, encoding="utf-8") as f:
        g = json.load(f)

    nodes_by_id = {n["node_id"]: n for n in g["nodes"]}
    prereqs = {}
    for e in g["edges"]:
        if e["type"] == "prerequisite":
            prereqs.setdefault(e["from_node_id"], []).append(e["to_node_id"])

    missing = [s for s in SEEDS if s not in nodes_by_id]
    if missing:
        sys.exit(f"ERROR: seed node(s) not in graph: {missing}")

    # transitive prerequisite closure over the seeds
    selected, queue = set(SEEDS), deque(SEEDS)
    while queue:
        cur = queue.popleft()
        for p in prereqs.get(cur, []):
            if p not in selected:
                selected.add(p)
                queue.append(p)

    # emit in the graph's own order so the fixture stays diff-stable
    out_nodes = [n for n in g["nodes"] if n["node_id"] in selected]
    out_edges = [
        e for e in g["edges"]
        if e["from_node_id"] in selected and e["to_node_id"] in selected
    ]
    fixture = {"roles": g["roles"], "nodes": out_nodes, "edges": out_edges}

    # ---- verify the invariants this file exists to guarantee ----
    errors = []

    # 1. exact subset: every node/edge object is byte-identical to the graph's
    for n in out_nodes:
        if n != nodes_by_id[n["node_id"]]:
            errors.append(f"node {n['node_id']} differs from curriculum_graph.json")
    graph_edges = {json.dumps(e, sort_keys=True) for e in g["edges"]}
    for e in out_edges:
        if json.dumps(e, sort_keys=True) not in graph_edges:
            errors.append(f"edge {e['from_node_id']}->{e['to_node_id']} not in curriculum_graph.json")

    # 2. edge-closed
    for e in out_edges:
        if e["from_node_id"] not in selected:
            errors.append(f"dangling edge from {e['from_node_id']}")
        if e["to_node_id"] not in selected:
            errors.append(f"dangling edge to {e['to_node_id']}")

    # 3. prerequisite-complete: no selected node may have a prerequisite outside the slice
    for nid in selected:
        for p in prereqs.get(nid, []):
            if p not in selected:
                errors.append(f"{nid} has prerequisite {p} outside the fixture")

    # 4. the SS15 golden chain must be present and correctly wired
    chain = [("prob-bayes", "prob-conditional"), ("ml-naive-bayes", "prob-bayes")]
    for dependent, prereq in chain:
        if dependent not in selected or prereq not in selected:
            errors.append(f"SS15 golden chain incomplete: {prereq} -> {dependent}")
        elif prereq not in prereqs.get(dependent, []):
            errors.append(f"SS15 golden chain edge missing: {dependent} requires {prereq}")

    # 5. the loader-exercising properties
    multi_parent = [nid for nid in selected if len(prereqs.get(nid, [])) >= 2]
    if not multi_parent:
        errors.append("no multi-parent node - fixture would not prove DAG (vs tree) handling")
    sections = {nodes_by_id[nid]["section"] for nid in selected}
    if len(sections) < 3:
        errors.append(f"only {len(sections)} sections - too few for cross-section prerequisite tests")
    cross = [
        e for e in out_edges
        if nodes_by_id[e["from_node_id"]]["section"] != nodes_by_id[e["to_node_id"]]["section"]
    ]
    if not cross:
        errors.append("no cross-section prerequisite edges")
    depths = {r["required_depth"] for nid in selected for r in nodes_by_id[nid]["roles"]}

    if errors:
        print(f"ERRORS: {len(errors)}")
        for x in errors:
            print("  x", x)
        sys.exit(1)

    with open(FIXTURE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(fixture, f, indent=2)
        f.write("\n")

    print(f"NODES: {len(out_nodes)}   EDGES: {len(out_edges)}")
    print(f"\nSections spanned ({len(sections)}): {', '.join(sorted(sections))}")
    print(f"Cross-section prerequisite edges: {len(cross)}")
    print(f"Multi-parent nodes: {', '.join(sorted(multi_parent))}")
    print(f"required_depth levels present: {', '.join(sorted(depths))}")
    print("SS15 golden chain: prob-conditional -> prob-bayes -> ml-naive-bayes  OK")
    print("\nERRORS: 0")
    print(f"wrote {FIXTURE}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - Python < 3.7
        pass
    main()
