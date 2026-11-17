/**
 * Application shell.
 *
 * The graph is the landing view, never a dashboard (BUILD_SPEC.md Part E). Readiness and health
 * live behind their own tab so they are available without becoming the thing you look at
 * instead of studying.
 *
 * Server reads go through `useServerState`, which owns fetching, cancellation and errors, and
 * re-reads everything when `invalidate()` fires. One assessment changes effective mastery
 * across the whole graph through prerequisite propagation, so every open view has to re-read —
 * caching a node's state locally would show stale numbers on exactly the nodes the user just
 * affected.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "./api/client";
import { useInvalidate, useServerState } from "./api/server-state";
import type { GraphOut, Role } from "./api/types";
import { Browse } from "./components/Browse";
import { GraphView } from "./components/GraphView";
import { NodeInspector } from "./components/NodeInspector";
import { Overview } from "./components/Overview";
import { Prep } from "./components/Prep";
import { Recommendations } from "./components/Recommendations";
import { SessionFlow } from "./components/SessionFlow";
import { Settings } from "./components/Settings";
import { DOMAINS, sectionName } from "./lib/domain";
import { takeOpenRouterCallback } from "./lib/openrouter";

type Tab = "graph" | "browse" | "recommendations" | "prep" | "overview";

export default function App() {
  const [tab, setTab] = useState<Tab>("graph");
  const [role, setRole] = useState<string | undefined>();
  const [section, setSection] = useState<string | undefined>();
  const [focusId, setFocusId] = useState<string | null>(null);
  const [depth, setDepth] = useState(1);
  const [assessing, setAssessing] = useState<string | null>(null);
  const invalidate = useInvalidate();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsNotice, setSettingsNotice] = useState<string | null>(null);
  const [llmVersion, setLlmVersion] = useState(0);

  // Returning from "Connect OpenRouter": trade the one-time code for a key and say what happened.
  useEffect(() => {
    const callback = takeOpenRouterCallback();
    if (!callback) return;
    setSettingsOpen(true);
    api.openrouterExchange(callback.code, callback.verifier).then(
      () => {
        setSettingsNotice("OpenRouter is connected. Sessions will now run in the app.");
        setLlmVersion((n) => n + 1);
      },
      () => setSettingsNotice("Could not connect OpenRouter. Please try again."),
    );
  }, []);

  const rolesRead = useServerState<Role[]>(() => api.roles(), []);
  // Every section, fetched once. `graph.sections` narrows to whatever the current filter
  // returned, so using it to build the section filter would leave you unable to switch
  // sections once you picked one.
  const sectionsRead = useServerState<string[]>(() => api.sections(), []);
  const graphRead = useServerState<GraphOut>(() => api.graph({ role, section }), [role, section]);

  const roles = rolesRead.data ?? [];
  const allSections = sectionsRead.data ?? [];
  const graph = graphRead.data;
  const problems = [...rolesRead.problems, ...sectionsRead.problems, ...graphRead.problems];

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
    invalidate();
  }, [invalidate]);

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
          <button className={tab === "prep" ? "active" : ""} onClick={() => setTab("prep")}>
            Prep
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
        <button onClick={() => setSettingsOpen(true)}>Settings</button>
      </header>

      {settingsOpen && (
        <Settings
          notice={settingsNotice}
          onClose={() => {
            setSettingsOpen(false);
            setSettingsNotice(null);
          }}
          onChanged={() => setLlmVersion((n) => n + 1)}
        />
      )}

      {problems.length > 0 && (
        <div className="error" style={{ margin: 12 }}>
          {problems.map((problem) => (
            <div key={problem}>{problem}</div>
          ))}
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
              onSelect={select}
              onAssess={assess}
            />
          )}
          {tab === "prep" && (
            <Prep
              roles={roles}
              sections={allSections}
              onSelect={select}
              onAssess={assess}
            />
          )}
          {tab === "overview" && <Overview onSelect={select} />}
        </main>

        <aside className="inspector">
          {assessing ? (
            <SessionFlow
              nodeId={assessing}
              role={role}
              roles={roles}
              onDone={finish}
              onCancel={() => setAssessing(null)}
              onOpenSettings={() => setSettingsOpen(true)}
              llmVersion={llmVersion}
            />
          ) : (
            <NodeInspector
              nodeId={focusId}
              role={role}
              onSelect={setFocusId}
              onAssess={assess}
            />
          )}
        </aside>
      </div>
    </div>
  );
}
