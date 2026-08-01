/**
 * Node detail.
 *
 * Only **Mastery** and **Importance** are shown by default (BUILD_SPEC.md Part E). Everything
 * else — retention, stability, intrinsic vs effective, next review, the trace — lives behind
 * Advanced. That restraint is the product decision: eleven numbers on first sight teaches
 * nothing, and the two that matter get lost among them.
 */

import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { NodeDetail } from "../api/types";
import { STATUS_COLOR, STATUS_LABEL, formatHours, pct, sectionName } from "../lib/domain";

interface Props {
  nodeId: string | null;
  role: string | undefined;
  refreshKey: number;
  onSelect: (nodeId: string) => void;
  onAssess: (nodeId: string) => void;
}

export function NodeInspector({ nodeId, role, refreshKey, onSelect, onAssess }: Props) {
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!nodeId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .node(nodeId, role)
      .then((data) => !cancelled && setDetail(data))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [nodeId, role, refreshKey]);

  if (!nodeId) {
    return (
      <div className="muted small">
        Select a concept in the graph to see its detail, or start an assessment from a
        recommendation.
      </div>
    );
  }
  if (loading && !detail) return <div className="spinner">Loading…</div>;
  if (!detail) return null;

  const a = detail.advanced;
  const sufficient = a.effective_mastery >= a.target;

  return (
    <div className="stack">
      <div>
        <span className="chip">{sectionName(detail.section)}</span>{" "}
        <span className="chip">{detail.competency}</span>
      </div>
      <h2 style={{ fontSize: 19 }}>{detail.name}</h2>
      <p className="small muted">{detail.description}</p>

      {/* the two default metrics */}
      <div className="card">
        <div className="between">
          <span className="label">Mastery</span>
          <strong style={{ fontVariantNumeric: "tabular-nums" }}>{pct(detail.mastery)}</strong>
        </div>
        <div className="meter" style={{ marginTop: 6 }}>
          <span
            style={{
              width: `${detail.mastery * 100}%`,
              background: STATUS_COLOR[detail.status],
            }}
          />
        </div>
        <div className="tiny muted" style={{ marginTop: 6 }}>
          {STATUS_LABEL[detail.status]} · target {pct(a.target)}{" "}
          {sufficient ? "· sufficient" : `· ${pct(a.target - a.effective_mastery)} to go`}
        </div>
      </div>

      <div className="card">
        <div className="between">
          <span className="label">Importance</span>
          <strong style={{ fontVariantNumeric: "tabular-nums" }}>
            {detail.importance.toFixed(2)}
          </strong>
        </div>
        <div className="tiny muted" style={{ marginTop: 4 }}>
          {detail.roles.length} role{detail.roles.length === 1 ? "" : "s"}:{" "}
          {detail.roles
            .map((r) => `${r.role_id} (${r.required_depth})`)
            .join(", ")}
        </div>
      </div>

      <button className="primary" onClick={() => onAssess(detail.node_id)}>
        Start assessment
      </button>

      {detail.last_gaps.length > 0 && (
        <div className="card">
          <span className="label">Known gaps</span>
          <ul className="small" style={{ margin: "6px 0 0 18px" }}>
            {detail.last_gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      <NeighbourList
        title="Prerequisites"
        hint="must be understood first"
        nodes={detail.prerequisites}
        onSelect={onSelect}
      />
      <NeighbourList
        title="Unlocks"
        hint="depends on this"
        nodes={detail.dependents}
        onSelect={onSelect}
      />

      <details>
        <summary>Advanced</summary>
        <div className="card" style={{ marginTop: 8 }}>
          <dl className="kv">
            <dt title="M — evidence. Never altered by decay or prerequisites.">
              Intrinsic mastery
            </dt>
            <dd>{pct(a.intrinsic_mastery)}</dd>
            <dt title="EM = M · R · PC — what the system can currently trust">
              Effective mastery
            </dt>
            <dd>{pct(a.effective_mastery)}</dd>
            <dt title="probability of recall right now">Retention</dt>
            <dd>{pct(a.retention)}</dd>
            <dt title="how trustworthy this is given upstream health">Prerequisite confidence</dt>
            <dd>{pct(a.prerequisite_confidence)}</dd>
            <dt>Stability</dt>
            <dd>{a.stability === null ? "—" : `${a.stability.toFixed(1)} d`}</dd>
            <dt>Difficulty</dt>
            <dd>{a.difficulty === null ? "—" : a.difficulty.toFixed(2)}</dd>
            <dt>Assessment variance</dt>
            <dd>{a.assessment_variance.toFixed(2)}</dd>
            <dt>Engine confidence</dt>
            <dd>{pct(a.engine_confidence)}</dd>
            <dt>Sessions</dt>
            <dd>{a.session_count}</dd>
            <dt>Leverage</dt>
            <dd>{a.leverage.toFixed(2)}</dd>
            <dt>Critical path value</dt>
            <dd>{a.critical_path_value.toFixed(2)}</dd>
            <dt>Learning cost</dt>
            <dd>{formatHours(a.learning_cost)}</dd>
            <dt>Last assessed</dt>
            <dd>{a.last_assessed_at ? a.last_assessed_at.slice(0, 10) : "never"}</dd>
            <dt>Next review</dt>
            <dd>{a.next_review_at ? a.next_review_at.slice(0, 10) : "—"}</dd>
          </dl>
          {a.intrinsic_mastery > a.effective_mastery + 0.02 && (
            <p className="tiny muted" style={{ marginTop: 10 }}>
              Effective mastery is below intrinsic because retention has decayed or a
              prerequisite is weak. Your evidence is intact — restudying the prerequisite
              restores this automatically, with no reassessment here.
            </p>
          )}
        </div>
      </details>
    </div>
  );
}

function NeighbourList({
  title,
  hint,
  nodes,
  onSelect,
}: {
  title: string;
  hint: string;
  nodes: NodeDetail["prerequisites"];
  onSelect: (id: string) => void;
}) {
  if (nodes.length === 0) return null;
  return (
    <div className="card">
      <span className="label">
        {title} <span style={{ textTransform: "none", fontWeight: 400 }}>· {hint}</span>
      </span>
      <div style={{ marginTop: 6 }}>
        {nodes.map((n) => (
          <button
            key={n.node_id}
            className="section-link"
            onClick={() => onSelect(n.node_id)}
            title={`${pct(n.mastery)} mastery`}
          >
            <span
              className="dot"
              style={{
                background: STATUS_COLOR[n.status],
                width: 8,
                height: 8,
                borderRadius: "50%",
                display: "inline-block",
                marginRight: 6,
              }}
            />
            {n.name}
            <span className="muted tiny"> · {pct(n.mastery)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
