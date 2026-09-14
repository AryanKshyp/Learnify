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
import type { IngestResponse, Role, RoleRequirement } from "../api/types";
import { STATUS_LABEL, pct } from "../lib/domain";

interface Props {
  nodeId: string;
  /** The globally selected role, used as the default for this session when the node serves it. */
  role: string | undefined;
  /** Every role in the curriculum, for display names. */
  roles: Role[];
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

export function SessionFlow({ nodeId, role, roles, onDone, onCancel }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [nodeName, setNodeName] = useState("");
  // `undefined` = the node's roles have not loaded yet, so we do not know what to ask for;
  // `null` = ask for nothing and let the application pick the node's most important role.
  const [chosenRole, setChosenRole] = useState<string | null | undefined>(undefined);
  const [nodeRoles, setNodeRoles] = useState<RoleRequirement[]>([]);
  const [usedRole, setUsedRole] = useState<string | null>(null);
  const [step, setStep] = useState<Phase>("study");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [pasted, setPasted] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  // Which roles this node is even tagged for, and at what depth. Fetched before the session
  // is opened: asking for a role the node does not serve is a hard rejection, so the default
  // is only applied once we know it is valid.
  useEffect(() => {
    let cancelled = false;
    setChosenRole(undefined);
    api
      .node(nodeId)
      .then((detail) => {
        if (cancelled) return;
        setNodeRoles(detail.roles);
        setNodeName(detail.name);
        const serves = detail.roles.some((r) => r.role_id === role);
        setChosenRole(role && serves ? role : null);
      })
      .catch((error) =>
        setProblems(error instanceof ApiError ? error.problems : [String(error)]),
      );
    return () => {
      cancelled = true;
    };
  }, [nodeId, role]);

  // Open the session — again whenever the role changes, because the role is baked into the
  // Schema A at generation time and decides every depth in the prompt.
  useEffect(() => {
    if (chosenRole === undefined) return;
    let cancelled = false;
    api
      .openSession(nodeId, chosenRole ?? undefined)
      .then((schemaA) => {
        if (cancelled) return;
        setSessionId(String(schemaA.session_id));
        const target = schemaA.target as { name?: string } | undefined;
        setNodeName(target?.name ?? nodeId);
        // Read back what was actually used, so the selector shows the application's own
        // choice rather than a blank when no role was asked for.
        const context = schemaA.role_context as { role_id?: string } | undefined;
        setUsedRole(context?.role_id ?? null);
      })
      .catch((error) =>
        setProblems(error instanceof ApiError ? error.problems : [String(error)]),
      );
    return () => {
      cancelled = true;
    };
  }, [nodeId, chosenRole]);

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
  const roleName = (roleId: string) =>
    roles.find((r) => r.role_id === roleId)?.name ?? roleId;
  const depthForUsedRole = nodeRoles.find((r) => r.role_id === usedRole)?.required_depth;

  return (
    <div className="stack">
      <div className="between">
        <h2 style={{ fontSize: 18 }}>{nodeName || "Session"}</h2>
        <button onClick={onCancel}>Close</button>
      </div>

      {nodeRoles.length > 0 && (
        <div className="card">
          <span className="label">Assessing for</span>
          <select
            value={chosenRole ?? ""}
            onChange={(event) => setChosenRole(event.target.value || null)}
            style={{ width: "100%", marginTop: 6 }}
            title="The role decides how deep this session goes and how the concept is framed"
          >
            <option value="">
              Most important role{usedRole ? ` — ${roleName(usedRole)}` : ""}
            </option>
            {nodeRoles.map((r) => (
              <option key={r.role_id} value={r.role_id}>
                {roleName(r.role_id)} · {r.required_depth}
              </option>
            ))}
          </select>
          <p className="tiny muted" style={{ marginTop: 6 }}>
            {depthForUsedRole ? (
              <>
                Teaching and testing to <strong>{depthForUsedRole}</strong>. The same concept is
                a passing mention for one role and a derivation for another — pick the role you
                are actually interviewing for.
              </>
            ) : (
              "The role decides how deep this session goes and how the concept is framed."
            )}
          </p>
          <p className="tiny muted" style={{ marginTop: 4 }}>
            Changing this starts a fresh session, so choose before you paste the prompt.
          </p>
        </div>
      )}

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
