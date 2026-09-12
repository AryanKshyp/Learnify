/**
 * Application shell.
 *
 * The graph is the landing view, never a dashboard (BUILD_SPEC.md Part E). Readiness and health
 * live behind their own tab so they are available without becoming the thing you look at
 * instead of studying.
 *
 * `refreshKey` is bumped after every ingestion. One assessment changes effective mastery
 * across the whole graph through prerequisite propagation, so every open view has to re-read —
 * caching a node's state locally would show stale numbers on exactly the nodes the user just
 * affected.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "./api/client";
import type { GraphOut, Role } from "./api/types";
import { Browse } from "./components/Browse";
import { GraphView } from "./components/GraphView";
import { NodeInspector } from "./components/NodeInspector";
import { Overview } from "./components/Overview";
import { Recommendations } from "./components/Recommendations";
import { SessionFlow } from "./components/SessionFlow";
import { DOMAINS, sectionName } from "./lib/domain";

type Tab = "graph" | "browse" | "recommendations" | "overview";

export default function App() {
  const [tab, setTab] = useState<Tab>("graph");
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  // Every section, fetched once. `graph.sections` narrows to whatever the current filter
  // returned, so using it to build the section filter would leave you unable to switch
  // sections once you picked one.
  const [allSections, setAllSections] = useState<string[]>([]);
  const [role, setRole] = useState<string | undefined>();
  const [section, setSection] = useState<string | undefined>();
  const [focusId, setFocusId] = useState<string | null>(null);
  const [depth, setDepth] = useState(1);
  const [assessing, setAssessing] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.roles().then(setRoles).catch((e) => setError(String(e)));
    api.sections().then(setAllSections).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .graph({ role, section })
      .then((data) => !cancelled && setGraph(data))
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [role, section, refreshKey]);

  const select = useCallback((nodeId: string) => {
    setFocusId(nodeId);
    setTab("graph");
  }, []);

  const assess = useCallback((nodeId: string) => {
    setFocusId(nodeId);
    setAssessing(nodeId);
  }, []);

  const finish = useCallback(() => {
    // propagation touches far more than the assessed node, so everything re-reads
    setRefreshKey((key) => key + 1);
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">KnowledgeOS</span>
        <nav className="tabs">
          <button className={tab === "graph" ? "active" : ""} onClick={() => setTab("graph")}>
            Graph
          </button>
          <button className={tab === "browse" ? "active" : ""} onClick={() => setTab("browse")}>
            Browse
          </button>
          <button
            className={tab === "recommendations" ? "active" : ""}
            onClick={() => setTab("recommendations")}
          >
            What next
          </button>
          <button
            className={tab === "overview" ? "active" : ""}
            onClick={() => setTab("overview")}
          >
            Readiness
          </button>
        </nav>
        <span className="spacer" />
        <select
          value={role ?? ""}
          onChange={(event) => setRole(event.target.value || undefined)}
          title="Filtering by role also re-weights importance through that role's lens"
        >
          <option value="">All roles</option>
          {roles.map((r) => (
            <option key={r.role_id} value={r.role_id}>
              {r.priority_rank}. {r.name}
            </option>
          ))}
        </select>
        {graph && (
          <span className="tiny muted">
            {graph.nodes.length} concepts · {graph.edges.length} links
          </span>
        )}
      </header>

      {error && (
        <div className="error" style={{ margin: 12 }}>
          {error}
        </div>
      )}

      <div className="workspace">
        <aside className="sidebar">
          <button
            className={`section-link ${!section ? "active" : ""}`}
            onClick={() => setSection(undefined)}
          >
            All sections
          </button>
          {DOMAINS.map((domain) => {
            const available = domain.sections.filter((s) => allSections.includes(s));
            if (available.length === 0) return null;
            return (
              <div className="domain-group" key={domain.label}>
                <span className="label">{domain.label}</span>
                {available.map((s) => (
                  <button
                    key={s}
                    className={`section-link ${section === s ? "active" : ""}`}
                    onClick={() => setSection(section === s ? undefined : s)}
                  >
                    {sectionName(s)}
                  </button>
                ))}
              </div>
            );
          })}
        </aside>

        <main className="main">
          {tab === "graph" && graph && (
            <GraphView
              nodes={graph.nodes}
              edges={graph.edges}
              focusId={focusId}
              depth={depth}
              onFocus={setFocusId}
              onDepthChange={setDepth}
            />
          )}
          {tab === "graph" && !graph && <div className="spinner">Loading graph…</div>}
          {tab === "browse" && graph && (
            <Browse
              nodes={graph.nodes}
              section={section}
              availableSections={allSections}
              focusId={focusId}
              onSectionChange={setSection}
              onInspect={setFocusId}
              onShowInGraph={select}
              onAssess={assess}
            />
          )}
          {tab === "browse" && !graph && <div className="spinner">Loading concepts…</div>}
          {tab === "recommendations" && (
            <Recommendations
              roles={roles}
              sections={graph?.sections ?? []}
              refreshKey={refreshKey}
              onSelect={select}
              onAssess={assess}
            />
          )}
          {tab === "overview" && <Overview refreshKey={refreshKey} onSelect={select} />}
        </main>

        <aside className="inspector">
          {assessing ? (
            <SessionFlow
              nodeId={assessing}
              onDone={finish}
              onCancel={() => setAssessing(null)}
            />
          ) : (
            <NodeInspector
              nodeId={focusId}
              role={role}
              refreshKey={refreshKey}
              onSelect={setFocusId}
              onAssess={assess}
            />
          )}
        </aside>
      </div>
    </div>
  );
}
