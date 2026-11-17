/**
 * An assessment run inside the app, on the user's own AI account.
 *
 * Same session, same prompts, same strict Schema B validation as the copy-paste route - this
 * only removes the copying. The application still owns every prompt; the model only converses
 * and then reports observations, which the server validates and the engine scores. Nothing the
 * model says in this window moves a number by itself.
 *
 * The transcript lives here and is sent whole each turn, so the server holds no conversation:
 * a deploy or a closed tab mid-session loses nothing the learner cannot see on screen.
 */

import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { problemsOf } from "../api/server-state";
import type { ChatTurn, IngestResponse } from "../api/types";

type Phase = "study" | "assess";

interface Props {
  sessionId: string;
  onRecorded: (result: IngestResponse) => void;
}

const PHASE_BLURB: Record<Phase, string> = {
  study:
    "Learn the concept to the depth your target role needs. Optional - skip it if you have already studied.",
  assess:
    "You will be tested, not taught. Answer as you would in an interview; you will not be told how you are doing.",
};

/** A finished assessment needs at least a few exchanges to measure anything. */
const MIN_ANSWERS_TO_FINISH = 3;

export function SessionChat({ sessionId, onRecorded }: Props) {
  const [phase, setPhase] = useState<Phase>("assess");
  const [transcripts, setTranscripts] = useState<Record<Phase, ChatTurn[]>>({
    study: [],
    assess: [],
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState<"chat" | "finish" | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const turns = transcripts[phase];
  const answers = transcripts.assess.filter((t) => t.role === "user").length;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [turns.length, busy]);

  const append = (which: Phase, turn: ChatTurn) =>
    setTranscripts((current) => ({ ...current, [which]: [...current[which], turn] }));

  const send = async (text: string | null) => {
    const which = phase;
    const history = transcripts[which];
    const outgoing = text === null ? history : [...history, { role: "user" as const, content: text }];
    if (text !== null) {
      append(which, { role: "user", content: text });
      setInput("");
    }

    setBusy("chat");
    setProblems([]);
    try {
      const { reply } = await api.chat(sessionId, which, outgoing);
      append(which, { role: "assistant", content: reply });
    } catch (error) {
      setProblems(problemsOf(error));
      // Put the words back so a failed send is not a lost message.
      if (text !== null) {
        setTranscripts((current) => ({ ...current, [which]: current[which].slice(0, -1) }));
        setInput(text);
      }
    } finally {
      setBusy(null);
    }
  };

  const finish = async () => {
    setBusy("finish");
    setProblems([]);
    try {
      onRecorded(await api.finish(sessionId, transcripts.assess));
    } catch (error) {
      // The session stays open and the transcript is untouched, so this is retryable as-is.
      setProblems(problemsOf(error));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="stack">
      <div className="row">
        {(["study", "assess"] as const).map((p) => (
          <button
            key={p}
            className={phase === p ? "active" : ""}
            onClick={() => setPhase(p)}
            disabled={busy !== null}
          >
            {p === "study" ? "1 · Study" : "2 · Assess"}
          </button>
        ))}
      </div>
      <p className="tiny muted">{PHASE_BLURB[phase]}</p>

      <div className="chat">
        {turns.length === 0 && (
          <div className="chat-empty">
            <button className="primary" onClick={() => void send(null)} disabled={busy !== null}>
              {busy === "chat" ? "Starting…" : phase === "study" ? "Start learning" : "Start the assessment"}
            </button>
          </div>
        )}
        {turns.map((turn, index) => (
          <div key={index} className={`msg ${turn.role}`}>
            {turn.content}
          </div>
        ))}
        {busy === "chat" && turns.length > 0 && <div className="msg assistant muted">Thinking…</div>}
        <div ref={endRef} />
      </div>

      {problems.length > 0 && (
        <div className="error">
          <strong>That did not work.</strong>
          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
          <p className="tiny muted" style={{ marginTop: 6 }}>
            Your session is still open — nothing is lost.
          </p>
        </div>
      )}

      {turns.length > 0 && (
        <form
          className="stack-tight"
          onSubmit={(event) => {
            event.preventDefault();
            if (input.trim() && busy === null) void send(input.trim());
          }}
        >
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Your answer…"
            rows={3}
            disabled={busy !== null}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                if (input.trim() && busy === null) void send(input.trim());
              }
            }}
          />
          <button className="primary" type="submit" disabled={busy !== null || !input.trim()}>
            Send
          </button>
        </form>
      )}

      {phase === "assess" && (
        <div className="card stack-tight">
          <p className="small">
            When you have answered enough questions, finish to record the result.
          </p>
          <button
            onClick={() => void finish()}
            disabled={busy !== null || answers < MIN_ANSWERS_TO_FINISH}
            title={
              answers < MIN_ANSWERS_TO_FINISH
                ? `Answer at least ${MIN_ANSWERS_TO_FINISH} questions first`
                : undefined
            }
          >
            {busy === "finish" ? "Scoring your session…" : "Finish and record"}
          </button>
          {answers < MIN_ANSWERS_TO_FINISH && (
            <p className="tiny muted">
              {answers}/{MIN_ANSWERS_TO_FINISH} answers so far.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
