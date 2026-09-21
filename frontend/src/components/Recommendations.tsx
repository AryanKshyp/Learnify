/**
 * The recommendations page, grouped Overall / Role / Competency (BUILD_SPEC.md Part E).
 *
 * Three lenses rather than one list so the user can follow interest without losing guidance —
 * bored of one section, pull the top item from another, and either way the path stays sensible.
 *
 * Every card shows the reason and the cost. The ranking optimises expected readiness gain per
 * unit of effort, so hiding the effort would make the ranking impossible to sanity-check.
 */

import { useState } from "react";

import { api } from "../api/client";
import { useServerState } from "../api/server-state";
import type { RecommendationGroup, Role } from "../api/types";
import { DOMAINS, formatHours, sectionName } from "../lib/domain";

type Lens = { kind: "overall" } | { kind: "role"; key: string } | { kind: "competency"; key: string };

interface Props {
  roles: Role[];
  sections: string[];
  onSelect: (nodeId: string) => void;
  onAssess: (nodeId: string) => void;
}

export function Recommendations({ roles, sections, onSelect, onAssess }: Props) {
  const [lens, setLens] = useState<Lens>({ kind: "overall" });

  const { data: group, problems, loading } = useServerState<RecommendationGroup>(
    () =>
      lens.kind === "overall"
        ? api.recommendations(8)
        : lens.kind === "role"
          ? api.recommendationsByRole(lens.key, 8)
          : api.recommendationsByCompetency(lens.key, 8),
    [lens.kind, lens.kind === "overall" ? "" : lens.key],
  );

  const orderedSections = DOMAINS.flatMap((d) => d.sections).filter((s) => sections.includes(s));

  return (
    <div className="scroll">
      <h2 style={{ marginBottom: 4 }}>What to study next</h2>
      <p className="small muted" style={{ marginBottom: 14 }}>
        Ranked by expected readiness gain per unit of effort — not by biggest gap. A cheap
        prerequisite that unblocks three things beats an expensive topic you happen to be
        weakest at.
      </p>

      <div className="row" style={{ flexWrap: "wrap", marginBottom: 8 }}>
        <button
          className={lens.kind === "overall" ? "active" : ""}
          onClick={() => setLens({ kind: "overall" })}
        >
          Overall
        </button>
        <select
          value={lens.kind === "role" ? lens.key : ""}
          onChange={(e) => e.target.value && setLens({ kind: "role", key: e.target.value })}
        >
          <option value="">By role…</option>
          {roles.map((role) => (
            <option key={role.role_id} value={role.role_id}>
              {role.priority_rank}. {role.name}
            </option>
          ))}
        </select>
        <select
          value={lens.kind === "competency" ? lens.key : ""}
          onChange={(e) =>
            e.target.value && setLens({ kind: "competency", key: e.target.value })
          }
        >
          <option value="">By competency…</option>
          {orderedSections.map((section) => (
            <option key={section} value={section}>
              {sectionName(section)}
            </option>
          ))}
        </select>
      </div>

      {problems.length > 0 && (
        <div className="error">
          {problems.map((problem) => (
            <div key={problem}>{problem}</div>
          ))}
        </div>
      )}

      {loading && <div className="spinner">Loading…</div>}

      {!loading && group && group.recommendations.length === 0 && (
        <div className="card muted small">
          Nothing to recommend here — either everything in this lens is already sufficient, or
          its prerequisites are not yet met. Try the Overall list.
        </div>
      )}

      {!loading &&
        group?.recommendations.map((rec, index) => (
          <div className="rec" key={rec.node_id}>
            <div className="between">
              <h4>
                <span className="muted">{index + 1}.</span> {rec.name}
              </h4>
              <span className="chip">{sectionName(rec.section)}</span>
            </div>
            <p className="reason">{rec.reason}</p>
            <div className="row" style={{ marginTop: 10, flexWrap: "wrap" }}>
              <button onClick={() => onAssess(rec.node_id)} className="primary">
                Assess
              </button>
              <button onClick={() => onSelect(rec.node_id)}>Show in graph</button>
              <span className="spacer" />
              <span className="tiny muted">
                {formatHours(rec.learning_cost_hours)} · leverage {rec.leverage.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
    </div>
  );
}
