/**
 * Readiness and knowledge health.
 *
 * Note this is NOT the landing view — the graph is (Part E, "home renders the interactive
 * graph, never analytics-first"). This lives behind its own tab so the numbers are available
 * without becoming the thing you stare at instead of studying.
 *
 * Every readiness score is shown with the node holding it back. Readiness is a bottleneck
 * measure, so "62%" alone is not actionable; "62%, held back by Self-Attention" is.
 */

import { api } from "../api/client";
import { useServerState } from "../api/server-state";
import type { Overview as OverviewData } from "../api/types";
import { pct } from "../lib/domain";

interface Props {
  onSelect: (nodeId: string) => void;
}

export function Overview({ onSelect }: Props) {
  const { data, problems } = useServerState<OverviewData>(() => api.overview(), []);

  if (problems.length > 0) {
    return (
      <div className="error">
        {problems.map((problem) => (
          <div key={problem}>{problem}</div>
        ))}
      </div>
    );
  }
  if (!data) return <div className="spinner">Loading…</div>;
  const h = data.health;

  return (
    <div className="scroll">
      <h2 style={{ marginBottom: 14 }}>Where you stand</h2>

      <div className="grid-2">
        <div className="card">
          <span className="label">Knowledge health</span>
          <div className="big-number" style={{ margin: "6px 0" }}>
            {h.score.toFixed(1)}
            <span className="muted" style={{ fontSize: 16 }}>
              {" "}
              / 100
            </span>
          </div>
          <dl className="kv" style={{ marginTop: 10 }}>
            <dt title="assessed critical nodes / all critical nodes">Coverage</dt>
            <dd>{pct(h.coverage)}</dd>
            <dt>Mean effective mastery</dt>
            <dd>{pct(h.mean_effective_mastery)}</dd>
            <dt>Mean retention</dt>
            <dd>{pct(h.mean_retention)}</dd>
            <dt title="critical nodes still below their depth target">Critical gaps</dt>
            <dd>{pct(h.critical_gap_ratio)}</dd>
          </dl>
          <p className="tiny muted" style={{ marginTop: 8 }}>
            Computed over {h.critical_node_count} critical concepts. Peripheral material is
            excluded, so grinding easy topics cannot inflate this.
          </p>
        </div>

        <div className="card">
          <span className="label">Progress</span>
          <dl className="kv" style={{ marginTop: 8 }}>
            <dt>Concepts in curriculum</dt>
            <dd>{data.total_nodes}</dd>
            <dt title="prerequisites met — available to learn right now">On the frontier</dt>
            <dd>{data.frontier_size}</dd>
            <dt title="never assessed">Unexplored</dt>
            <dd>{data.unexplored_count}</dd>
            <dt>Assessed</dt>
            <dd>{data.total_nodes - data.unexplored_count}</dd>
          </dl>
        </div>
      </div>

      <h3 style={{ margin: "20px 0 8px" }}>Readiness by role</h3>
      <p className="small muted" style={{ marginBottom: 10 }}>
        A weighted harmonic mean, not an average — one near-zero critical concept drags the
        score down, because that is what interviews actually do.
      </p>

      {data.readiness.map((role) => (
        <div className="card" key={role.role_id}>
          <div className="between">
            <strong>
              <span className="muted">{role.priority_rank}.</span> {role.role_name}
            </strong>
            <span style={{ fontVariantNumeric: "tabular-nums" }}>{pct(role.readiness)}</span>
          </div>
          <div className="meter" style={{ marginTop: 6 }}>
            <span style={{ width: `${role.readiness * 100}%` }} />
          </div>
          {role.bottleneck_node_id && (
            <div className="tiny muted" style={{ marginTop: 6 }}>
              Held back by{" "}
              <button
                className="section-link"
                style={{ display: "inline", padding: 0, color: "var(--accent)" }}
                onClick={() => onSelect(role.bottleneck_node_id!)}
              >
                {role.bottleneck_name}
              </button>{" "}
              · {role.node_count} concepts tracked
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
