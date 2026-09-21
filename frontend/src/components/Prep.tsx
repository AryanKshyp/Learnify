/**
 * Prep — "what do I need to know to read this?"
 *
 * The same shape as the assessment loop, because it is the same kind of boundary: the app hands
 * out a prompt, an LLM in any chat window does the reading, and one paste comes back. The
 * document is never uploaded here. KnowledgeOS stores what a paper *requires*, not what it
 * says, which is why this needs no file upload and no metered API call.
 *
 * What the screen has to make obvious is the division of labour, because it is the whole point:
 * the model said which concepts appear, and the application worked out the prerequisites the
 * document never mentioned, the gaps, the order, and the effort. Concepts the document named
 * and concepts the closure pulled in are therefore always visually distinct — collapsing them
 * into one list would hide the thing the user is actually paying for.
 */

import { useEffect, useState } from "react";

import { api } from "../api/client";
import { problemsOf, useInvalidate, useServerState } from "../api/server-state";
import type { Catalogue, DocumentPlan, DocumentSummary, Role } from "../api/types";
import { DOMAINS, formatHours, pct, sectionName } from "../lib/domain";

interface Props {
  roles: Role[];
  sections: string[];
  onSelect: (nodeId: string) => void;
  onAssess: (nodeId: string) => void;
}

type View = { kind: "list" } | { kind: "new" } | { kind: "plan"; id: string };

const KIND_LABEL: Record<string, string> = {
  paper: "Paper",
  report: "Report",
  "job-description": "Job description",
  course: "Course",
  book: "Book",
  slides: "Slides",
  notes: "Notes",
  other: "Document",
};

/** Readiness colour, matching the status ramp so progress reads on one axis throughout. */
const readinessColor = (value: number): string =>
  value >= 0.85 ? "#2f6b4f" : value >= 0.6 ? "#5b8c5a" : value >= 0.35 ? "#c9a227" : "#c2703d";

export function Prep({ roles, sections, onSelect, onAssess }: Props) {
  const [view, setView] = useState<View>({ kind: "list" });
  // Saving or deleting a document changes server state, so it invalidates like any other write
  // rather than carrying a private reload path.
  const reload = useInvalidate();
  const read = useServerState<DocumentSummary[]>(() => api.documents(), []);
  const documents = read.data ?? [];
  const { problems, loading } = read;

  if (view.kind === "new") {
    return (
      <NewDocument
        roles={roles}
        sections={sections}
        onCancel={() => setView({ kind: "list" })}
        onIngested={(plan) => {
          reload();
          setView({ kind: "plan", id: plan.document_id });
        }}
      />
    );
  }

  if (view.kind === "plan") {
    return (
      <PlanView
        documentId={view.id}
        onBack={() => {
          reload();
          setView({ kind: "list" });
        }}
        onDeleted={() => {
          reload();
          setView({ kind: "list" });
        }}
        onSelect={onSelect}
        onAssess={onAssess}
      />
    );
  }

  return (
    <div className="scroll">
      <div className="between" style={{ marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>Prep for a document</h2>
        <button className="primary" onClick={() => setView({ kind: "new" })}>
          + New document
        </button>
      </div>
      <p className="small muted" style={{ marginBottom: 14 }}>
        Paste a paper, report or job description into any LLM with the prompt below, and it
        reports which concepts it needs. This app then works out the prerequisites the document
        never mentions, what you are missing, and what order to study in — from your own graph,
        which the model cannot see.
      </p>

      {problems.length > 0 && (
        <div className="error">
          {problems.map((problem) => (
            <div key={problem}>{problem}</div>
          ))}
        </div>
      )}
      {loading && <div className="spinner">Loading…</div>}

      {!loading && documents.length === 0 && (
        <div className="card muted small">
          No documents yet. Start with a paper you have been putting off — the plan tells you
          what to learn first, not just what you are missing.
        </div>
      )}

      {!loading &&
        documents.map((doc) => (
          <button
            key={doc.document_id}
            className="doc-card"
            onClick={() => setView({ kind: "plan", id: doc.document_id })}
          >
            <div className="between">
              <h4>{doc.title}</h4>
              <span className="chip">{KIND_LABEL[doc.kind] ?? doc.kind}</span>
            </div>
            {doc.summary && <p className="reason">{doc.summary}</p>}

            <div className="doc-readiness">
              <div className="between">
                <span className="label">Readiness for this document</span>
                <strong style={{ color: readinessColor(doc.readiness) }}>
                  {pct(doc.readiness)}
                </strong>
              </div>
              <div className="meter">
                <span
                  style={{
                    width: `${doc.readiness * 100}%`,
                    background: readinessColor(doc.readiness),
                  }}
                />
              </div>
              {doc.bottleneck_name && (
                <div className="tiny muted" style={{ marginTop: 4 }}>
                  Held back by <strong>{doc.bottleneck_name}</strong>
                </div>
              )}
            </div>

            <div className="tiny muted" style={{ marginTop: 8 }}>
              {doc.concept_count} concepts ({doc.stated_count} named, {doc.implied_count}{" "}
              assumed) · {doc.gap_count} gaps · {formatHours(doc.total_hours)} to close
            </div>
          </button>
        ))}
    </div>
  );
}

// --------------------------------------------------------------------- new

/**
 * Get the prompt, run it elsewhere, paste the result.
 *
 * Scope is offered up front rather than buried, because it is a genuine trade-off the user has
 * to make: the full 566-concept catalogue must be attached as a file, while a couple of
 * sections fit inside the prompt itself — but a concept outside the scope cannot be reported at
 * all, and comes back looking like a gap in the curriculum rather than a gap in the scope.
 */
function NewDocument({
  roles,
  sections,
  onCancel,
  onIngested,
}: {
  roles: Role[];
  sections: string[];
  onCancel: () => void;
  onIngested: (plan: DocumentPlan) => void;
}) {
  const [role, setRole] = useState<string>("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState<"prompt" | "catalogue" | null>(null);
  const [pasted, setPasted] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .catalogue({ role: role || undefined, sections: chosen })
      .then((data) => !cancelled && setCatalogue(data))
      .catch((e) =>
        setProblems(problemsOf(e)),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [role, chosen]);

  const copy = async (what: "prompt" | "catalogue") => {
    if (!catalogue) return;
    await navigator.clipboard.writeText(
      what === "prompt" ? catalogue.prompt : catalogue.catalogue,
    );
    setCopied(what);
    setTimeout(() => setCopied(null), 1800);
  };

  /**
   * The catalogue is downloaded rather than copied when it is large. 36 KB of ids pasted into a
   * chat message buries the instructions it is supposed to serve; as an attachment the model
   * reads it without it ever entering the conversation as text.
   */
  const download = () => {
    if (!catalogue) return;
    const blob = new Blob([catalogue.catalogue], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = catalogue.catalogue_filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const submit = async () => {
    setBusy(true);
    setProblems([]);
    let parsed: unknown;
    try {
      // Models add a fence despite being told not to. Strip it rather than rejecting — the
      // contract that matters is the object's shape, not the packaging.
      const cleaned = pasted
        .trim()
        .replace(/^```(?:json)?\s*/i, "")
        .replace(/```$/, "");
      parsed = JSON.parse(cleaned);
    } catch (e) {
      setProblems([`That is not valid JSON — ${(e as Error).message}`]);
      setBusy(false);
      return;
    }
    try {
      onIngested(await api.ingestDocument(parsed));
    } catch (e) {
      setProblems(problemsOf(e));
    } finally {
      setBusy(false);
    }
  };

  // Ordered by domain rather than alphabetically, matching the sidebar. The same sixteen
  // sections listed two different ways in one app makes them feel like two different sets.
  const ordered = DOMAINS.flatMap((d) => d.sections).filter((s) => sections.includes(s));

  const toggle = (section: string) =>
    setChosen((current) =>
      current.includes(section)
        ? current.filter((s) => s !== section)
        : [...current, section],
    );

  return (
    <div className="scroll">
      <div className="between" style={{ marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>New document</h2>
        <button onClick={onCancel}>Cancel</button>
      </div>
      <p className="small muted" style={{ marginBottom: 14 }}>
        Your document never comes here. Upload it to an LLM along with the prompt below; only
        the JSON it returns comes back to this app.
      </p>

      <div className="card">
        <span className="label">1 · Narrow the catalogue (optional)</span>
        <p className="small muted" style={{ margin: "6px 0 10px" }}>
          A narrower catalogue fits inside the prompt, so there is nothing to attach. But a
          concept outside it cannot be reported at all — it comes back as "not in the
          curriculum" when really it was just out of scope. When in doubt, leave it wide.
        </p>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">All roles</option>
          {roles.map((r) => (
            <option key={r.role_id} value={r.role_id}>
              {r.priority_rank}. {r.name}
            </option>
          ))}
        </select>
        <div className="row" style={{ flexWrap: "wrap", marginTop: 10 }}>
          {ordered.map((section) => (
            <button
              key={section}
              className={`chip-toggle ${chosen.includes(section) ? "on" : ""}`}
              onClick={() => toggle(section)}
            >
              {sectionName(section)}
            </button>
          ))}
        </div>
        {catalogue && (
          <div className="tiny muted" style={{ marginTop: 10 }}>
            {catalogue.concept_count} concepts · ~{catalogue.approx_tokens.toLocaleString()}{" "}
            tokens ·{" "}
            {catalogue.fits_inline
              ? "small enough to sit inside the prompt — nothing to attach"
              : "too large to paste; attach it as a file"}
          </div>
        )}
      </div>

      <div className="card">
        <span className="label">2 · Copy the prompt</span>
        <p className="small muted" style={{ margin: "6px 0 10px" }}>
          Paste this into any chat window, attach your document
          {catalogue && !catalogue.fits_inline ? " and the catalogue file" : ""}, and it returns
          one JSON object.
        </p>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <button className="primary" onClick={() => copy("prompt")} disabled={!catalogue}>
            {copied === "prompt" ? "Copied ✓" : "Copy prompt"}
          </button>
          {catalogue && !catalogue.fits_inline && (
            <>
              <button onClick={download}>Download {catalogue.catalogue_filename}</button>
              <button onClick={() => copy("catalogue")}>
                {copied === "catalogue" ? "Copied ✓" : "Copy catalogue"}
              </button>
            </>
          )}
        </div>
        {loading && <div className="spinner">Building prompt…</div>}
        {catalogue && (
          <details style={{ marginTop: 10 }}>
            <summary>Show the prompt</summary>
            <pre className="payload">{catalogue.prompt}</pre>
          </details>
        )}
      </div>

      <div className="card">
        <span className="label">3 · Paste what it gave you</span>
        <p className="small muted" style={{ margin: "6px 0 10px" }}>
          One JSON object. A concept id that is not in the curriculum is rejected rather than
          guessed at — a near match would attach this document's requirements to something it
          never mentioned.
        </p>
        <textarea
          value={pasted}
          onChange={(e) => setPasted(e.target.value)}
          placeholder={'{\n  "schema": "knowledgeos.document.extraction",\n  ...\n}'}
          rows={10}
          className="prep-textarea"
        />
        {problems.length > 0 && (
          <div className="error">
            <strong>Rejected</strong>
            <ul>
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          className="primary"
          onClick={submit}
          disabled={busy || pasted.trim().length === 0}
          style={{ marginTop: 10 }}
        >
          {busy ? "Working…" : "Build my plan"}
        </button>
      </div>
    </div>
  );
}

// -------------------------------------------------------------------- plan

function PlanView({
  documentId,
  onBack,
  onDeleted,
  onSelect,
  onAssess,
}: {
  documentId: string;
  onBack: () => void;
  onDeleted: () => void;
  onSelect: (nodeId: string) => void;
  onAssess: (nodeId: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const { data: plan, problems, loading } = useServerState<DocumentPlan>(
    () => api.document(documentId),
    [documentId],
  );

  if (loading) return <div className="scroll"><div className="spinner">Loading plan…</div></div>;
  if (problems.length > 0) {
    return (
      <div className="scroll">
        <div className="error">
          {problems.map((problem) => (
            <div key={problem}>{problem}</div>
          ))}
        </div>
      </div>
    );
  }
  if (!plan) return null;

  const implied = plan.requirements.filter((r) => !r.stated);
  const stated = plan.requirements.filter((r) => r.stated);

  return (
    <div className="scroll">
      <div className="between" style={{ marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>{plan.title}</h2>
        <div className="row">
          <button onClick={onBack}>← All documents</button>
          <button
            className="danger"
            onClick={async () => {
              await api.deleteDocument(plan.document_id);
              onDeleted();
            }}
          >
            Delete
          </button>
        </div>
      </div>
      {plan.summary && <p className="small muted">{plan.summary}</p>}
      {plan.source && <p className="tiny muted">{plan.source}</p>}

      <div className="card">
        <div className="between">
          <span className="label">Readiness for this document</span>
          <strong className="big-number" style={{ color: readinessColor(plan.readiness) }}>
            {pct(plan.readiness)}
          </strong>
        </div>
        <div className="meter" style={{ marginTop: 6 }}>
          <span
            style={{
              width: `${plan.readiness * 100}%`,
              background: readinessColor(plan.readiness),
            }}
          />
        </div>
        <p className="small muted" style={{ marginTop: 8 }}>
          {plan.bottleneck_name ? (
            <>
              Held back by <strong>{plan.bottleneck_name}</strong>. This is a bottleneck score,
              not an average — one missing concept gates a document the way it gates a
              conversation about it.
            </>
          ) : (
            "No concepts recorded for this document."
          )}
        </p>
        <div className="tiny muted">
          {plan.gap_count} of {plan.concept_count} concepts below what this document needs ·{" "}
          {formatHours(plan.total_hours)} of study to close them
        </div>
      </div>

      {implied.length > 0 && (
        <div className="card">
          <span className="label">
            {implied.length} concepts this document assumes but never mentions
          </span>
          <p className="small muted" style={{ margin: "6px 0 0" }}>
            Found by walking your prerequisite graph from the {stated.length} concepts the
            document names. These are where people actually get stuck — the document will not
            warn you about them because it takes them for granted.
          </p>
        </div>
      )}

      <h3 style={{ margin: "18px 0 6px" }}>What to study, in order</h3>
      <p className="small muted" style={{ marginBottom: 10 }}>
        Ranked by how much each would raise <em>this document's</em> readiness per hour of
        effort, then reordered so nothing appears before its prerequisites.
      </p>

      {plan.steps.length === 0 && (
        <div className="card muted small">
          Nothing to study — you already meet everything this document needs.
        </div>
      )}

      {plan.steps.map((step, index) => (
        <div className="rec" key={step.node_id}>
          <div className="between">
            <h4>
              <span className="muted">{index + 1}.</span> {step.name}
            </h4>
            <div className="row">
              {!step.stated && <span className="chip implied">assumed</span>}
              <span className="chip">{sectionName(step.section)}</span>
            </div>
          </div>
          <p className="reason">{step.reason}</p>
          <div className="row" style={{ marginTop: 8, alignItems: "center" }}>
            <div className="meter" style={{ flex: 1, maxWidth: 180 }}>
              <span
                style={{
                  width: `${step.sufficiency * 100}%`,
                  background: readinessColor(step.sufficiency),
                }}
              />
            </div>
            <span className="tiny muted">
              {pct(step.sufficiency)} of what this document needs
            </span>
          </div>
          <div className="row" style={{ marginTop: 10, flexWrap: "wrap" }}>
            <button onClick={() => onAssess(step.node_id)} className="primary">
              Assess
            </button>
            <button onClick={() => onSelect(step.node_id)}>Show in graph</button>
            <span className="spacer" />
            <span className="tiny muted">{formatHours(step.learning_cost_hours)}</span>
          </div>
        </div>
      ))}

      {plan.out_of_curriculum.length > 0 && (
        <div className="card" style={{ marginTop: 18 }}>
          <span className="label">Not in your curriculum</span>
          <p className="small muted" style={{ margin: "6px 0 8px" }}>
            The document needs these and your graph has no concept for them. Recorded as text,
            never matched to a node — a near match would be worse than an honest gap.
          </p>
          <ul className="small">
            {plan.out_of_curriculum.map((item) => (
              <li key={item.label}>
                <strong>{item.label}</strong> <span className="muted">— {item.evidence}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <details style={{ marginTop: 18 }} open={showAll} onToggle={(e) => setShowAll(e.currentTarget.open)}>
        <summary>Every concept this document needs ({plan.requirements.length})</summary>
        <div className="req-table">
          {plan.requirements.map((req) => (
            <div className="req-row" key={req.node_id}>
              <button className="req-name" onClick={() => onSelect(req.node_id)}>
                {req.name}
              </button>
              <span className="tiny muted">
                {req.stated ? "named by the document" : `assumed — for ${req.required_for_name}`}
              </span>
              <div className="meter" style={{ width: 90 }}>
                <span
                  style={{
                    width: `${req.sufficiency * 100}%`,
                    background: readinessColor(req.sufficiency),
                  }}
                />
              </div>
              <span className="tiny muted">
                {pct(req.mastery)} / needs {pct(req.target)}
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
