/**
 * The graph home view — focused, not a hairball.
 *
 * 566 nodes in one force layout is unreadable and slow to settle, so instead of drawing
 * everything we draw a **neighbourhood around a focused node** and let you widen or narrow it.
 * That matches how the engine actually reasons: prerequisites upstream, dependents downstream,
 * and a frontier in between.
 *
 * The layout is `dagre`, left-to-right, so an arrow always means "must be understood before".
 * Reading direction carries the semantics, which is the same decision the standalone explorer
 * made by ordering rows by prerequisite depth.
 */

import { useEffect, useMemo, useRef } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import dagre from "cytoscape-dagre";

import type { Edge, NodeSummary } from "../api/types";
import { FOCUS_DEPTHS, STATUS_COLOR, sectionCode } from "../lib/domain";

cytoscape.use(dagre);

interface Props {
  nodes: NodeSummary[];
  edges: Edge[];
  focusId: string | null;
  depth: number;
  onFocus: (nodeId: string) => void;
  onDepthChange: (depth: number) => void;
}

/**
 * Collect the neighbourhood of `focusId` within `depth` hops, in both directions.
 *
 * Upstream and downstream are gathered separately rather than by treating the graph as
 * undirected: walking undirected from a node reaches its *siblings* (other dependents of a
 * shared prerequisite), which are not part of its story and swamp the view.
 */
function neighbourhood(
  focusId: string,
  edges: Edge[],
  depth: number,
): Set<string> {
  const prereqs = new Map<string, string[]>();
  const dependents = new Map<string, string[]>();
  const link = (map: Map<string, string[]>, key: string, value: string) => {
    const existing = map.get(key);
    if (existing) existing.push(value);
    else map.set(key, [value]);
  };
  for (const edge of edges) {
    link(prereqs, edge.from_node_id, edge.to_node_id);
    link(dependents, edge.to_node_id, edge.from_node_id);
  }

  const included = new Set<string>([focusId]);
  const walk = (adjacency: Map<string, string[]>) => {
    let frontier = [focusId];
    for (let hop = 0; hop < depth && frontier.length; hop += 1) {
      const next: string[] = [];
      for (const id of frontier) {
        for (const neighbour of adjacency.get(id) ?? []) {
          if (!included.has(neighbour)) {
            included.add(neighbour);
            next.push(neighbour);
          }
        }
      }
      frontier = next;
    }
  };
  walk(prereqs);
  walk(dependents);
  return included;
}

export function GraphView({ nodes, edges, focusId, depth, onFocus, onDepthChange }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);

  const visible = useMemo(() => {
    if (!focusId) {
      // No focus yet: show the frontier — the nodes actually available to learn next.
      const frontier = nodes.filter((n) => n.is_frontier).slice(0, 40);
      const ids = new Set(frontier.map((n) => n.node_id));
      return { ids, nodes: frontier };
    }
    const ids = neighbourhood(focusId, edges, depth);
    return { ids, nodes: nodes.filter((n) => ids.has(n.node_id)) };
  }, [nodes, edges, focusId, depth]);

  const elements = useMemo<ElementDefinition[]>(() => {
    const nodeEls: ElementDefinition[] = visible.nodes.map((n) => ({
      data: {
        id: n.node_id,
        label: n.name,
        code: sectionCode(n.section),
        mastery: n.mastery,
        color: STATUS_COLOR[n.status] ?? STATUS_COLOR.unassessed,
        focused: n.node_id === focusId ? 1 : 0,
        frontier: n.is_frontier ? 1 : 0,
      },
    }));
    const edgeEls: ElementDefinition[] = edges
      .filter((e) => visible.ids.has(e.from_node_id) && visible.ids.has(e.to_node_id))
      .map((e) => ({
        data: {
          id: e.edge_id,
          // drawn prerequisite -> dependent so arrows read "comes before"
          source: e.to_node_id,
          target: e.from_node_id,
          weight: e.weight,
        },
      }));
    return [...nodeEls, ...edgeEls];
  }, [visible, edges, focusId]);

  useEffect(() => {
    if (!container.current) return;
    const instance = cytoscape({
      container: container.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-wrap": "wrap",
            "text-max-width": "130px",
            "font-size": "11px",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "data(color)",
            "background-opacity": 0.16,
            "border-width": 1.5,
            "border-color": "data(color)",
            color: "#000",
            shape: "round-rectangle",
            width: "150px",
            height: "44px",
            padding: "6px",
          },
        },
        {
          selector: "node[focused = 1]",
          style: {
            "border-width": 3,
            "background-opacity": 0.32,
            "font-weight": "bold",
            width: "170px",
            height: "52px",
          },
        },
        {
          selector: "node[frontier = 1][focused = 0]",
          style: { "border-style": "double", "border-width": 3 },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1, 1, 3)",
            "line-color": "#b9b9ad",
            "target-arrow-color": "#b9b9ad",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            opacity: 0.75,
          },
        },
      ],
      // dagre only makes sense when there are edges to rank by. The default frontier view is
      // a set of independent nodes with no edges between them, and dagre puts every one of
      // them in a single rank — a tall useless column. A grid is the honest layout for an
      // edgeless set.
      layout: (elements.some((el) => "source" in (el.data as object))
        ? { name: "dagre", rankDir: "LR", nodeSep: 18, rankSep: 90, animate: false }
        : { name: "grid", avoidOverlap: true, condense: true, padding: 30 }) as never,
      wheelSensitivity: 0.2,
      maxZoom: 2.5,
      minZoom: 0.15,
    });

    instance.on("tap", "node", (event) => onFocus(event.target.id()));
    cy.current = instance;
    // dev-only handle so the headless smoke driver can select a node deterministically
    // instead of guessing pixel coordinates
    if (import.meta.env.DEV) {
      (window as unknown as { __cy?: Core }).__cy = instance;
    }
    return () => {
      instance.destroy();
      cy.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elements]);

  const isDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  useEffect(() => {
    cy.current?.style().selector("node").style({ color: isDark ? "#ececE6" : "#1a1a18" }).update();
  }, [isDark, elements]);

  return (
    <>
      <div className="graph-controls">
        <span className="label">Focus</span>
        {FOCUS_DEPTHS.map((option) => (
          <button
            key={option.value}
            className={depth === option.value ? "active" : ""}
            onClick={() => onDepthChange(option.value)}
            title={option.hint}
            disabled={!focusId}
          >
            {option.label}
          </button>
        ))}
        <button onClick={() => cy.current?.fit(undefined, 40)}>Fit</button>
        <span className="spacer" />
        <span className="legend tiny muted">
          {Object.entries(STATUS_COLOR).map(([status, color]) => (
            <span key={status}>
              <i className="dot" style={{ background: color }} />
              {status}
            </span>
          ))}
        </span>
      </div>
      {!focusId && (
        <div className="tiny muted" style={{ padding: "6px 14px" }}>
          Showing the learning frontier — concepts whose prerequisites are already met. Click any
          node to centre the graph on it.
        </div>
      )}
      <div id="cy" ref={container} />
    </>
  );
}
