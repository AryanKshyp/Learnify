/**
 * The assessment protocol, as one module.
 *
 * A session is a multi-step exchange that leaves the application in the middle: open it, fetch
 * the prompt for a phase, the learner takes it to an LLM somewhere else, they come back and
 * paste a Schema B, it is validated and ingested. That is a small state machine with five legal
 * states, and it used to live as twelve independent `useState` calls inside the component that
 * renders it.
 *
 * Twelve booleans and strings can express far more combinations than the protocol has states,
 * and one of the illegal ones was reachable: `loading` started `true` and was only cleared by
 * the prompt effect, which returned early when there was no session id. So if opening the
 * session failed, the error rendered *and* the primary button stayed disabled reading
 * "Loading…" forever — no retry, the panel had to be closed and reopened. Here `loading` is not
 * a flag at all; it is a question you ask the stage, and a failure to open is its own stage
 * with a retry on it.
 *
 * The distinction the union makes that the flags could not: **failing to open a session** is
 * terminal and needs a retry, while **a rejected paste** is not — the session is still open and
 * the learner should fix the JSON and submit again. Those were the same `problems` array
 * before, which is why the UI had to say "the session is still open" in prose rather than in
 * its shape.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { problemsOf } from "../api/server-state";
import type { IngestResponse, RoleRequirement } from "../api/types";

/** The three prompts, declared once. Previously repeated in the component, the client and the API. */
export const PHASES = ["study", "assess", "wrapup"] as const;

export type Phase = (typeof PHASES)[number];

export const STEPS: { phase: Phase; label: string; blurb: string }[] = [
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

export type ParsedPaste = { ok: true; value: unknown } | { ok: false; problem: string };

/**
 * Turn what the learner pasted into a payload, or say why it is not one.
 *
 * Models routinely wrap the object in a ``` fence despite being told not to. Stripping it is
 * right rather than lenient: the contract is the object's shape, which the backend validates
 * strictly — the packaging is not part of it. A syntax error is caught here rather than sent,
 * because "that is not valid JSON" is a more useful thing to read than a 422 about a missing
 * field in a body that was never parseable.
 *
 * Pure, and exported, because it is the single most failure-prone line in the frontend and it
 * used to be unreachable except by mounting a browser and pasting into a textarea.
 */
export function parseSchemaB(pasted: string): ParsedPaste {
  const cleaned = pasted
    .trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/```$/, "");
  try {
    return { ok: true, value: JSON.parse(cleaned) };
  } catch (error) {
    return { ok: false, problem: `That is not valid JSON — ${(error as Error).message}` };
  }
}

/**
 * Where the session is.
 *
 * `ready.prompt === null` means the prompt for the current phase is still in flight — the one
 * legitimate "loading" in the protocol, and it cannot outlive the stage it belongs to.
 */
export type Stage =
  | { kind: "opening" }
  | { kind: "ready"; sessionId: string; prompt: string | null; problems: string[] }
  | { kind: "submitting"; sessionId: string; prompt: string }
  | { kind: "recorded"; result: IngestResponse }
  /** Could not open a session at all. Terminal until retried — nothing else is possible yet. */
  | { kind: "unopened"; problems: string[] };

export interface Session {
  readonly stage: Stage;
  readonly nodeName: string;
  /** Roles this node is tagged for, with the depth each needs. */
  readonly nodeRoles: RoleRequirement[];
  /** What the learner picked: `null` = let the application choose, `undefined` = not known yet. */
  readonly chosenRole: string | null | undefined;
  /** What the application actually used, read back from the Schema A. */
  readonly usedRole: string | null;

  chooseRole(roleId: string | null): void;
  choosePhase(phase: Phase): void;
  submit(pasted: string): void;
  retry(): void;
}

/** The prompt currently shown, or "" while it loads. */
export function promptOf(stage: Stage): string {
  if (stage.kind === "ready") return stage.prompt ?? "";
  if (stage.kind === "submitting") return stage.prompt;
  return "";
}

/** Derived, never stored — which is why it cannot get stuck. */
export function isLoading(stage: Stage): boolean {
  return stage.kind === "opening" || (stage.kind === "ready" && stage.prompt === null);
}

/** Problems with the last paste. Empty unless the session is open and a submission was refused. */
export function problemsIn(stage: Stage): string[] {
  if (stage.kind === "ready") return stage.problems;
  if (stage.kind === "unopened") return stage.problems;
  return [];
}

export function sessionIdOf(stage: Stage): string | null {
  if (stage.kind === "ready" || stage.kind === "submitting") return stage.sessionId;
  return null;
}

/**
 * Drive one session for one node.
 *
 * Owns all four requests — node detail, open, prompt, ingest — and every transition between
 * them. The component that uses this renders `stage` and calls the four actions; it holds no
 * server state and no flags of its own beyond the textarea's contents.
 *
 * Re-opens whenever the chosen role changes, because the role is baked into the Schema A at
 * generation time and decides every depth in the prompt.
 */
export function useSession(
  nodeId: string,
  preferredRole: string | undefined,
  onDone: (result: IngestResponse) => void,
): Session {
  const [stage, setStage] = useState<Stage>({ kind: "opening" });
  const [nodeName, setNodeName] = useState("");
  const [nodeRoles, setNodeRoles] = useState<RoleRequirement[]>([]);
  const [chosenRole, setChosenRole] = useState<string | null | undefined>(undefined);
  const [usedRole, setUsedRole] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("study");
  const [attempt, setAttempt] = useState(0);

  const done = useRef(onDone);
  done.current = onDone;

  // Which roles this node is even tagged for. Fetched before opening: asking for a role the
  // node does not serve is a hard rejection, so the default is only applied once it is known
  // to be valid.
  useEffect(() => {
    let cancelled = false;
    setStage({ kind: "opening" });
    setChosenRole(undefined);

    api.node(nodeId).then(
      (detail) => {
        if (cancelled) return;
        setNodeName(detail.name);
        setNodeRoles(detail.roles);
        const serves = detail.roles.some((r) => r.role_id === preferredRole);
        setChosenRole(preferredRole && serves ? preferredRole : null);
      },
      (error: unknown) => {
        if (!cancelled) setStage({ kind: "unopened", problems: problemsOf(error) });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [nodeId, preferredRole, attempt]);

  useEffect(() => {
    if (chosenRole === undefined) return;
    let cancelled = false;
    setStage({ kind: "opening" });

    api.openSession(nodeId, chosenRole ?? undefined).then(
      (schemaA) => {
        if (cancelled) return;
        setNodeName(schemaA.target.name);
        // Read back what was actually used, so the selector shows the application's own choice
        // rather than a blank when no role was asked for.
        setUsedRole(schemaA.role_context.role_id);
        setStage({
          kind: "ready",
          sessionId: schemaA.session_id,
          prompt: null,
          problems: [],
        });
      },
      (error: unknown) => {
        if (!cancelled) setStage({ kind: "unopened", problems: problemsOf(error) });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [nodeId, chosenRole, attempt]);

  // The prompt for whichever phase is showing. Keyed on the session id rather than the stage
  // object, so nulling the prompt below cannot re-trigger it.
  const openSessionId = sessionIdOf(stage);
  useEffect(() => {
    if (openSessionId === null) return;
    let cancelled = false;
    setStage((current) =>
      current.kind === "ready" ? { ...current, prompt: null } : current,
    );

    api.prompt(openSessionId, phase).then(
      (data) => {
        if (cancelled) return;
        setStage((current) =>
          current.kind === "ready" && current.sessionId === openSessionId
            ? { ...current, prompt: data.prompt }
            : current,
        );
      },
      (error: unknown) => {
        if (!cancelled) setStage({ kind: "unopened", problems: problemsOf(error) });
      },
    );

    return () => {
      cancelled = true;
    };
  }, [openSessionId, phase]);

  // Read through a ref rather than inside a `setStage` updater: updaters must stay pure, and
  // StrictMode double-invokes them in development — which would ingest the same paste twice.
  const current = useRef(stage);
  current.current = stage;

  const submit = useCallback((pasted: string) => {
    const open = current.current;
    if (open.kind !== "ready" || open.prompt === null) return;

    const parsed = parseSchemaB(pasted);
    if (!parsed.ok) {
      // A bad paste leaves the session open — the learner fixes it and submits again.
      setStage({ ...open, problems: [parsed.problem] });
      return;
    }

    const { sessionId, prompt } = open;
    setStage({ kind: "submitting", sessionId, prompt });
    api.ingest(parsed.value).then(
      (result) => {
        setStage({ kind: "recorded", result });
        done.current(result);
      },
      (error: unknown) => {
        setStage({ kind: "ready", sessionId, prompt, problems: problemsOf(error) });
      },
    );
  }, []);

  return {
    stage,
    nodeName,
    nodeRoles,
    chosenRole,
    usedRole,
    chooseRole: setChosenRole,
    choosePhase: setPhase,
    submit,
    retry: useCallback(() => setAttempt((n) => n + 1), []),
  };
}
