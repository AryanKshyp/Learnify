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
 *
 * The protocol itself lives in `lib/session-protocol` — what the stages are, which requests
 * each makes, and which failures are recoverable. This file renders whichever stage it is
 * handed and owns nothing but the textarea and the copy-button flash.
 */

import { useState } from "react";

import { api } from "../api/client";
import { useServerState } from "../api/server-state";

import type { IngestResponse, Role } from "../api/types";
import { STATUS_LABEL, pct } from "../lib/domain";
import { SessionChat } from "./SessionChat";
import {
  STEPS,
  isLoading,
  problemsIn,
  promptOf,
  useSession,
} from "../lib/session-protocol";

interface Props {
  nodeId: string;
  /** The globally selected role, used as the default for this session when the node serves it. */
  role: string | undefined;
  /** Every role in the curriculum, for display names. */
  roles: Role[];
  onDone: (result: IngestResponse) => void;
  onCancel: () => void;
  /** Opens Settings, where an AI provider key is added to run sessions in the app. */
  onOpenSettings: () => void;
  /** Bumped when the AI provider changes, so this re-reads whether one is configured. */
  llmVersion: number;
}

export function SessionFlow({
  nodeId,
  role,
  roles,
  onDone,
  onCancel,
  onOpenSettings,
  llmVersion,
}: Props) {
  const session = useSession(nodeId, role, onDone);
  const { stage, nodeName, nodeRoles, chosenRole, usedRole } = session;

  const [step, setStep] = useState(STEPS[0]!.phase);
  const [pasted, setPasted] = useState("");
  const [copied, setCopied] = useState(false);
  // Sessions run in the app when the user has connected an AI account; otherwise the original
  // copy-paste loop is what they get, unchanged. `manual` is the user choosing paste anyway.
  const llm = useServerState(() => api.llmSettings(), [llmVersion]);
  const [manual, setManual] = useState(false);
  const [appResult, setAppResult] = useState<IngestResponse | null>(null);
  const inApp = llm.data?.configured === true && !manual;
  // Until we know whether an AI account is connected - and, when it is, until the session has
  // opened - show a spinner rather than briefly flashing the copy-paste layout.
  // If that lookup itself fails, fall back to the paste layout rather than spin forever.
  const settling =
    (llm.data === undefined && llm.problems.length === 0) || (inApp && stage.kind !== "ready");

  const prompt = promptOf(stage);
  const loading = isLoading(stage);
  const problems = problemsIn(stage);
  const busy = stage.kind === "submitting";

  const copy = async () => {
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const choose = (phase: (typeof STEPS)[number]["phase"]) => {
    setStep(phase);
    session.choosePhase(phase);
  };

  const recorded = stage.kind === "recorded" ? stage.result : appResult;
  if (recorded) {
    const result = recorded;
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

  // Could not open a session at all — nothing else on this panel can work, so it offers the
  // one action that can. Previously this state rendered the error beside a permanently
  // disabled "Loading…" button, and the only way out was closing the panel.
  if (stage.kind === "unopened") {
    return (
      <div className="stack">
        <div className="between">
          <h2 style={{ fontSize: 18 }}>{nodeName || "Session"}</h2>
          <button onClick={onCancel}>Close</button>
        </div>
        <div className="error">
          <strong>Could not start the session.</strong>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
        <button className="primary" onClick={session.retry}>
          Try again
        </button>
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
            onChange={(event) => session.chooseRole(event.target.value || null)}
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
            Changing this starts a fresh session, so choose before you begin.
          </p>
        </div>
      )}

      {settling && !problems.length && <div className="spinner">Opening session…</div>}

      {inApp && stage.kind === "ready" && (
        <>
          <SessionChat
            sessionId={stage.sessionId}
            onRecorded={(result) => {
              setAppResult(result);
              onDone(result);
            }}
          />
          <button className="linklike" onClick={() => setManual(true)}>
            Use my own chat window instead (copy and paste)
          </button>
        </>
      )}

      {!settling && !inApp && llm.data && !llm.data.configured && (
        <div className="card stack-tight">
          <strong className="small">Run this session right here</strong>
          <p className="tiny muted">
            Connect your own AI account once and sessions run in the app, with no copying and
            pasting. Or carry on below with any chat window.
          </p>
          <button onClick={onOpenSettings}>Connect an AI account</button>
        </div>
      )}

      {manual && llm.data?.configured && (
        <button className="linklike" onClick={() => setManual(false)}>
          Run the session in the app instead
        </button>
      )}

      {!settling && !inApp && (
      <>
      <div className="row" style={{ flexWrap: "wrap" }}>
        {STEPS.map((s) => (
          <button
            key={s.phase}
            className={step === s.phase ? "active" : ""}
            onClick={() => choose(s.phase)}
            disabled={stage.kind === "opening"}
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
          <button
            className="primary"
            onClick={() => session.submit(pasted)}
            disabled={busy || !pasted.trim()}
          >
            {busy ? "Validating…" : "Submit"}
          </button>
        </>
      )}
      </>
      )}
    </div>
  );
}
