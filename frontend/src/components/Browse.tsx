/**
 * Browse — search and filter every concept in the curriculum as a flat list.
 *
 * The graph view answers "what surrounds this?"; it cannot answer "where is the thing I am
 * thinking of?" — 566 nodes across 16 sections are not findable by panning a neighbourhood.
 * This view is the index: type a name, narrow by section, competency or status, and pick.
 *
 * It filters the graph the shell already loaded rather than fetching its own, so the role lens
 * and the section filter mean the same thing here as everywhere else — and so searching costs
 * no request. The section control writes back to that shared filter instead of keeping a
 * private copy, which is why the sidebar and this dropdown never disagree.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import type { NodeSummary, Status } from "../api/types";
import { DOMAINS, STATUS_COLOR, STATUS_LABEL, pct, sectionName } from "../lib/domain";

const STATUSES: Status[] = ["unassessed", "learning", "practiced", "retained", "mastered"];

type Sort = "importance" | "weakest" | "strongest" | "name" | "section";

const SORTS: { value: Sort; label: string }[] = [
  { value: "importance", label: "Most important" },
  { value: "weakest", label: "Lowest mastery" },
  { value: "strongest", label: "Highest mastery" },
  { value: "name", label: "Name (A–Z)" },
  { value: "section", label: "Section" },
];

interface Props {
  nodes: NodeSummary[];
  /** the shell's section filter — this view reads and writes it, never shadows it */
  section: string | undefined;
  availableSections: string[];
  focusId: string | null;
  onSectionChange: (section: string | undefined) => void;
  /** show the node in the inspector without leaving this list */
  onInspect: (nodeId: string) => void;
  /** focus the node in the graph view */
  onShowInGraph: (nodeId: string) => void;
  onAssess: (nodeId: string) => void;
}

export function Browse({
  nodes,
  section,
  availableSections,
  focusId,
  onSectionChange,
  onInspect,
  onShowInGraph,
  onAssess,
}: Props) {
  const [query, setQuery] = useState("");
  const [competency, setCompetency] = useState("");
  const [statuses, setStatuses] = useState<Set<Status>>(new Set());
  const [frontierOnly, setFrontierOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("importance");
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    search.current?.focus();
  }, []);

  // A competency belongs to a section, so this list has to follow the section filter —
  // otherwise the dropdown offers choices that can only ever return nothing.
  const competencies = useMemo(
    () => Array.from(new Set(nodes.map((n) => n.competency))).sort(),
    [nodes],
  );
  useEffect(() => {
    if (competency && !competencies.includes(competency)) setCompetency("");
  }, [competencies, competency]);

  const orderedSections = DOMAINS.flatMap((d) => d.sections).filter((s) =>
    availableSections.includes(s),
  );

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const terms = needle ? needle.split(/\s+/) : [];
    const matches = (node: NodeSummary) => {
      if (terms.length === 0) return true;
      const haystack =
        `${node.name} ${node.competency} ${sectionName(node.section)} ${node.node_id}`.toLowerCase();
      // every term, not the whole phrase: "bayes naive" should find "Naive Bayes"
      return terms.every((term) => haystack.includes(term));
    };

    const filtered = nodes.filter(
      (node) =>
        matches(node) &&
        (!competency || node.competency === competency) &&
        (statuses.size === 0 || statuses.has(node.status)) &&
        (!frontierOnly || node.is_frontier),
    );

    const by: Record<Sort, (a: NodeSummary, b: NodeSummary) => number> = {
      importance: (a, b) => b.importance - a.importance || a.name.localeCompare(b.name),
      weakest: (a, b) => a.mastery - b.mastery || b.importance - a.importance,
      strongest: (a, b) => b.mastery - a.mastery || b.importance - a.importance,
      name: (a, b) => a.name.localeCompare(b.name),
      section: (a, b) =>
        a.section.localeCompare(b.section) ||
        a.competency.localeCompare(b.competency) ||
        a.name.localeCompare(b.name),
    };
    return [...filtered].sort(by[sort]);
  }, [nodes, query, competency, statuses, frontierOnly, sort]);

  const toggleStatus = (status: Status) =>
    setStatuses((current) => {
      const next = new Set(current);
      if (!next.delete(status)) next.add(status);
      return next;
    });

  const anyFilter =
    query !== "" ||
    competency !== "" ||
    statuses.size > 0 ||
    frontierOnly ||
    section !== undefined;

  const clear = () => {
    setQuery("");
    setCompetency("");
    setStatuses(new Set());
    setFrontierOnly(false);
    onSectionChange(undefined);
    search.current?.focus();
  };

  return (
    <div className="browse">
      <div className="browse-filters">
        <div className="row">
          <input
            ref={search}
            className="search"
            type="search"
            value={query}
            placeholder="Search concepts — name, competency, section…"
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            onClick={clear}
            disabled={!anyFilter}
            title="Reset every filter, including the section"
          >
            Clear
          </button>
        </div>

        <div className="row" style={{ flexWrap: "wrap" }}>
          <select
            value={section ?? ""}
            onChange={(event) => onSectionChange(event.target.value || undefined)}
          >
            <option value="">All sections</option>
            {orderedSections.map((s) => (
              <option key={s} value={s}>
                {sectionName(s)}
              </option>
            ))}
          </select>
          <select value={competency} onChange={(event) => setCompetency(event.target.value)}>
            <option value="">All competencies</option>
            {competencies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select value={sort} onChange={(event) => setSort(event.target.value as Sort)}>
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>
                Sort: {option.label}
              </option>
            ))}
          </select>
          <button
            className={frontierOnly ? "active" : ""}
            onClick={() => setFrontierOnly((on) => !on)}
            title="Only concepts whose prerequisites are already met — what you can actually learn next"
          >
            Ready to learn
          </button>
        </div>

        <div className="row" style={{ flexWrap: "wrap" }}>
          {STATUSES.map((status) => (
            <button
              key={status}
              className={`status-filter ${statuses.has(status) ? "active" : ""}`}
              onClick={() => toggleStatus(status)}
            >
              <span className="dot" style={{ background: STATUS_COLOR[status] }} />
              {STATUS_LABEL[status]}
            </button>
          ))}
          <span className="spacer" />
          <span className="tiny muted">
            {results.length} of {nodes.length} concepts
          </span>
        </div>
      </div>

      <div className="browse-list">
        {results.length === 0 && (
          <div className="card muted small">
            Nothing matches. Widen the filters, or clear them to see all {nodes.length} concepts
            in scope.
          </div>
        )}
        {results.map((node) => (
          <div
            key={node.node_id}
            className={`browse-row ${focusId === node.node_id ? "selected" : ""}`}
            onClick={() => onInspect(node.node_id)}
          >
            <span
              className="dot"
              style={{ background: STATUS_COLOR[node.status] }}
              title={STATUS_LABEL[node.status]}
            />
            <div className="browse-name">
              <span>{node.name}</span>
              <span className="tiny muted">
                {sectionName(node.section)} · {node.competency}
                {node.is_frontier ? " · ready to learn" : ""}
              </span>
            </div>
            <div className="browse-mastery" title={`Mastery ${pct(node.mastery)}`}>
              <div className="meter">
                <span style={{ width: pct(node.mastery) }} />
              </div>
              <span className="tiny muted">{pct(node.mastery)}</span>
            </div>
            <div className="browse-actions">
              <button
                onClick={(event) => {
                  event.stopPropagation();
                  onShowInGraph(node.node_id);
                }}
              >
                Graph
              </button>
              <button
                className="primary"
                onClick={(event) => {
                  event.stopPropagation();
                  onAssess(node.node_id);
                }}
              >
                Assess
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
