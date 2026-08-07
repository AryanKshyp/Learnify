/**
 * The assessment loop: study → assess → paste the result back.
 *
 * Three prompts rather than one, because they are three different moments. An LLM told up
 * front to "teach, then test, then emit JSON" reliably emits the JSON early or drifts from the
 * contract over a long conversation — and the learner, not the model, should decide when they
 * are done being tested.
 *
 * This is the only surface in the application that changes knowledge state, and it takes
 * exactly one paste — no manual number entry anywhere (BUILD_SPEC.md Part E). Letting someone
 * type a mastery score would make the number an opinion rather than evidence, which is the
 * failure the whole system exists to prevent.
 */

import { useEffect, useState } from "react";

import { ApiError, api } from "../api/client";
import type { IngestResponse } from "../api/types";
import { STATUS_LABEL, pct } from "../lib/domain";

interface Props {
  nodeId: string;
  onDone: (result: IngestResponse) => void;
  onCancel: () => void;
}

type Phase = "study" | "assess" | "wrapup" | "full";

const STEPS: { phase: Phase; label: string; blurb: string }[] = [
  {
    phase: "study",
    label: "1 · Study",
    blurb:
      "Teaches the concept to the depth your target role needs, then gives reading and practice. Skip this if you have already studied.",
  },
  {
    phase: "assess",
    label: "2 · Assess",
    blurb:
      "Tests you. It will not teach, hint freely, or tell you how you are doing — all three would corrupt the measurement.",
  },
  {
    phase: "wrapup",
    label: "3 · Wrap up",
    blurb:
      "Paste when the questions are done. The LLM replies with one JSON object; paste that into the box below.",
  },
];

export function SessionFlow({ nodeId, onDone, onCancel }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [nodeName, setNodeName] = useState("");
  const [step, setStep] = useState<Phase>("study");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [pasted, setPasted] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  // open the session once
  useEffect(() => {
    let cancelled = false;
    api
      .openSession(nodeId)
      .then((schemaA) => {
        if (cancelled) return;
        setSessionId(String(schemaA.session_id));
        const target = schemaA.target as { name?: string } | undefined;
        setNodeName(target?.name ?? nodeId);
      })
      .catch((error) =>
        setProblems(error instanceof ApiError ? error.problems : [String(error)]),
      );
    return () => {
      cancelled = true;
    };
  }, [nodeId]);

  // fetch the prompt for whichever step is showing
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setLoading(true);
    api
      .prompt(sessionId, step)
      .then((data) => !cancelled && setPrompt(data.prompt))
      .catch((error) =>
        setProblems(error instanceof ApiError ? error.problems : [String(error)]),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [sessionId, step]);

  const copy = async () => {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const submit = async () => {
    setBusy(true);
    setProblems([]);
    let parsed: unknown;
    try {
      // Models often wrap JSON in a fence despite being told not to. Strip it rather than
      // rejecting — the contract that matters is the object's shape, not the packaging.
      const cleaned = pasted.trim().replace(/^```(?:json)?\s*/i, "").replace(/```$/, "");
      parsed = JSON.parse(cleaned);
    } catch (error) {
      // Caught before the request: a syntax error is a paste problem, and saying so is more
      // useful than a 422 about a missing field.
      setProblems([`That is not valid JSON — ${(error as Error).message}`]);
      setBusy(false);
      return;
    }
    try {
      const response = await api.ingest(parsed);
      setResult(response);
      onDone(response);
    } catch (error) {
      setProblems(error instanceof ApiError ? error.problems : [String(error)]);
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    return (
      <div className="stack">
        <div className="between">
          <h2 style={{ fontSize: 18 }}>Recorded</h2>
          <button onClick={onCancel}>Close</button>
        </div>
        <div className="card">
          <span className="label">{nodeName}</span>
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
      </div>
    );
  }

  const current = STEPS.find((s) => s.phase === step) ?? STEPS[0]!;

  return (
    <div className="stack">
      <div className="between">
        <h2 style={{ fontSize: 18 }}>{nodeName || "Session"}</h2>
        <button onClick={onCancel}>Close</button>
      </div>

      <div className="row" style={{ flexWrap: "wrap" }}>
        {STEPS.map((s) => (
          <button
            key={s.phase}
            className={step === s.phase ? "active" : ""}
            onClick={() => setStep(s.phase)}
            disabled={!sessionId}
          >
            {s.label}
          </button>
        ))}
      </div>
      <p className="tiny muted">{current.blurb}</p>

      {problems.length > 0 && (
        <div className="error">
          <strong>Rejected — nothing was saved.</strong>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
          <p className="tiny muted" style={{ marginTop: 6 }}>
            The session is still open. Fix it and submit again.
          </p>
        </div>
      )}

      <button className="primary" onClick={copy} disabled={loading || !prompt}>
        {copied ? "Copied" : loading ? "Loading…" : `Copy the ${current.label.split("· ")[1]} prompt`}
      </button>

      <details>
        <summary>Preview the prompt</summary>
        <pre className="payload">{prompt}</pre>
      </details>

      {step === "wrapup" && (
        <>
          <p className="small muted">Paste the LLM's JSON reply:</p>
          <textarea
            value={pasted}
            onChange={(event) => setPasted(event.target.value)}
            placeholder='{"schema": "knowledgeos.assessment.output", ...}'
            spellCheck={false}
          />
          <button className="primary" onClick={submit} disabled={busy || !pasted.trim()}>
            {busy ? "Validating…" : "Submit"}
          </button>
        </>
      )}
    </div>
  );
}
