/**
 * The assessment loop: generate Schema A, copy it out, paste Schema B back.
 *
 * This is the only surface in the entire application that changes knowledge state, and it takes
 * exactly one paste — no manual number entry anywhere (BUILD_SPEC.md Part E). Letting someone
 * type a mastery score would make the number an opinion rather than evidence, which is the
 * failure the whole system exists to prevent.
 *
 * Validation failures are shown as a list, because the API reports every problem at once and a
 * copy-paste boundary is exactly where fixing one error at a time is most painful.
 */

import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { IngestResponse } from "../api/types";
import { STATUS_LABEL, pct } from "../lib/domain";

interface Props {
  nodeId: string;
  onDone: (result: IngestResponse) => void;
  onCancel: () => void;
}

type Phase = "generating" | "copy" | "paste" | "done";

export function SessionFlow({ nodeId, onDone, onCancel }: Props) {
  const [phase, setPhase] = useState<Phase>("generating");
  const [schemaA, setSchemaA] = useState<Record<string, unknown> | null>(null);
  const [pasted, setPasted] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const start = async () => {
    setBusy(true);
    setProblems([]);
    try {
      const payload = await api.openSession(nodeId);
      setSchemaA(payload);
      setPhase("copy");
    } catch (error) {
      setProblems(error instanceof ApiError ? error.problems : [String(error)]);
    } finally {
      setBusy(false);
    }
  };

  if (phase === "generating" && !busy && !schemaA) {
    void start();
  }

  const copy = async () => {
    if (!schemaA) return;
    await navigator.clipboard.writeText(JSON.stringify(schemaA, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const submit = async () => {
    setBusy(true);
    setProblems([]);
    let parsed: unknown;
    try {
      parsed = JSON.parse(pasted);
    } catch (error) {
      // Caught before the request: a JSON syntax error is the user's typo, not a contract
      // violation, and saying so is more useful than a 422 about a missing field.
      setProblems([`That is not valid JSON — ${(error as Error).message}`]);
      setBusy(false);
      return;
    }
    try {
      const response = await api.ingest(parsed);
      setResult(response);
      setPhase("done");
      onDone(response);
    } catch (error) {
      setProblems(error instanceof ApiError ? error.problems : [String(error)]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="between">
        <h2 style={{ fontSize: 18 }}>Assessment session</h2>
        <button onClick={onCancel}>Close</button>
      </div>

      {problems.length > 0 && (
        <div className="error">
          <strong>Rejected — nothing was saved.</strong>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
          <p className="tiny muted" style={{ marginTop: 6 }}>
            The session is still open. Fix the payload and submit again.
          </p>
        </div>
      )}

      {phase === "copy" && schemaA && (
        <>
          <p className="small muted">
            Step 1 — copy this into your assessment engine. It says what to probe and to what
            depth.
          </p>
          <pre className="payload">{JSON.stringify(schemaA, null, 2)}</pre>
          <div className="row">
            <button className="primary" onClick={copy}>
              {copied ? "Copied" : "Copy Schema A"}
            </button>
            <button onClick={() => setPhase("paste")}>Next — paste the result</button>
          </div>
        </>
      )}

      {phase === "paste" && (
        <>
          <p className="small muted">
            Step 2 — paste the Schema B the engine returned. One paste; nothing is typed by hand.
          </p>
          <textarea
            value={pasted}
            onChange={(event) => setPasted(event.target.value)}
            placeholder='{"schema": "knowledgeos.assessment.output", ...}'
            spellCheck={false}
          />
          <div className="row">
            <button className="primary" onClick={submit} disabled={busy || !pasted.trim()}>
              {busy ? "Validating…" : "Submit"}
            </button>
            <button onClick={() => setPhase("copy")}>Back to Schema A</button>
          </div>
        </>
      )}

      {phase === "done" && result && (
        <div className="card">
          <span className="label">Recorded</span>
          <div className="big-number" style={{ margin: "8px 0" }}>
            {pct(result.intrinsic_mastery_before)} → {pct(result.intrinsic_mastery_after)}
          </div>
          <div className="small muted">
            {STATUS_LABEL[result.status_before]} → {STATUS_LABEL[result.status_after]}
            {result.next_review_at && ` · review by ${result.next_review_at.slice(0, 10)}`}
          </div>
          <details style={{ marginTop: 10 }}>
            <summary>How was this calculated?</summary>
            <pre className="payload">{JSON.stringify(result.computation_trace, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}
