/**
 * Where a user connects their own AI account.
 *
 * KnowledgeOS never pays for the model and never uses a shared key: sessions run on the user's
 * own credentials. The key is sent once, encrypted on the server, and never sent back - this
 * panel only ever shows the last four characters.
 */

import { useEffect, useState } from "react";

import { api } from "../api/client";
import { problemsOf } from "../api/server-state";
import type { LlmProvider, LlmSettings } from "../api/types";
import { useAccount } from "../auth/AuthGate";
import { startOpenRouterConnect } from "../lib/openrouter";

interface Props {
  onClose: () => void;
  /** Called after a key is saved or removed, so views that depend on it re-read. */
  onChanged: () => void;
  notice?: string | null;
}

export function Settings({ onClose, onChanged, notice }: Props) {
  const account = useAccount();
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [saved, setSaved] = useState<LlmSettings | null>(null);
  const [providerId, setProviderId] = useState("openrouter");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  useEffect(() => {
    api.llmProviders().then(setProviders, (e) => setProblems(problemsOf(e)));
    api.llmSettings().then(setSaved, (e) => setProblems(problemsOf(e)));
  }, []);

  const provider = providers.find((p) => p.id === providerId);

  const save = async () => {
    setBusy(true);
    setProblems([]);
    try {
      const next = await api.saveLlmSettings({
        provider: providerId,
        api_key: apiKey,
        ...(model.trim() ? { model: model.trim() } : {}),
      });
      setSaved(next);
      setApiKey("");
      onChanged();
    } catch (error) {
      setProblems(problemsOf(error));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await api.deleteLlmSettings();
      setSaved({ configured: false, provider: null, model: null, key_hint: null });
      onChanged();
    } catch (error) {
      setProblems(problemsOf(error));
    } finally {
      setBusy(false);
    }
  };

  const labelOf = (id: string | null) => providers.find((p) => p.id === id)?.label ?? id;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal card stack"
        role="dialog"
        aria-label="Settings"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="between">
          <h2 style={{ fontSize: 18 }}>Settings</h2>
          <button onClick={onClose}>Close</button>
        </div>

        {notice && <div className="card small">{notice}</div>}

        <section className="stack">
          <h3 style={{ fontSize: 15 }}>AI provider</h3>
          <p className="small muted">
            Sessions are run by an AI model using <strong>your own</strong> account, so you stay in
            control of the cost. Your key is encrypted on our server and used only to run your
            sessions.
          </p>

          {saved?.configured && (
            <div className="card row between">
              <div>
                <div>{labelOf(saved.provider)}</div>
                <div className="tiny muted">
                  {saved.model} · key {saved.key_hint}
                </div>
              </div>
              <button onClick={remove} disabled={busy}>
                Remove
              </button>
            </div>
          )}

          <label className="stack-tight">
            <span className="label">{saved?.configured ? "Replace with" : "Provider"}</span>
            <select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>

          {provider?.oauth && (
            <div className="stack-tight">
              <button className="primary" onClick={() => void startOpenRouterConnect()}>
                Connect OpenRouter
              </button>
              <p className="tiny muted">
                Sign in at OpenRouter and approve access; sessions then use your OpenRouter
                credits. Or paste a key below instead.
              </p>
            </div>
          )}

          <label className="stack-tight">
            <span className="label">API key</span>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              placeholder="Paste your key"
              onChange={(e) => setApiKey(e.target.value)}
            />
            {provider && (
              <a className="tiny" href={provider.key_help_url} target="_blank" rel="noreferrer">
                Where do I get a key?
              </a>
            )}
          </label>

          <label className="stack-tight">
            <span className="label">Model (optional)</span>
            <input
              value={model}
              placeholder={provider?.default_model ?? ""}
              onChange={(e) => setModel(e.target.value)}
            />
          </label>

          {problems.length > 0 && (
            <div className="error">
              {problems.map((problem) => (
                <div key={problem}>{problem}</div>
              ))}
            </div>
          )}

          <button className="primary" onClick={save} disabled={busy || apiKey.trim().length < 8}>
            {busy ? "Checking the key…" : "Save and test"}
          </button>
        </section>

        {account.signOut && (
          <section className="stack">
            <h3 style={{ fontSize: 15 }}>Account</h3>
            <div className="row between">
              <span className="small muted">{account.email}</span>
              <button onClick={() => void account.signOut?.()}>Sign out</button>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
