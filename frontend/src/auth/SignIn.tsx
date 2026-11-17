import type { SupabaseClient } from "@supabase/supabase-js";
import { useState } from "react";

type Mode = "signin" | "signup" | "link";

export function SignIn({ client }: { client: SupabaseClient }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "signin") {
        const { error } = await client.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else if (mode === "signup") {
        const { data, error } = await client.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) throw error;
        // With email confirmation on there is no session yet; say so rather than leave a
        // form that appears to have done nothing.
        if (!data.session) setNotice("Check your email to confirm your account, then sign in.");
      } else {
        const { error } = await client.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) throw error;
        setNotice("Check your email for a sign-in link.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const title = { signin: "Sign in", signup: "Create your account", link: "Email me a link" }[mode];

  return (
    <div className="auth-page">
      <form className="card auth-card stack" onSubmit={submit}>
        <div>
          <h1>KnowledgeOS</h1>
          <p className="small muted" style={{ marginTop: 6 }}>
            Find out what you actually know, what is holding it back, and what to study next.
          </p>
        </div>

        <h2 style={{ fontSize: 18 }}>{title}</h2>

        <label className="stack-tight">
          <span className="label">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        {mode !== "link" && (
          <label className="stack-tight">
            <span className="label">Password</span>
            <input
              type="password"
              required
              minLength={8}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
        )}

        {error && <div className="error">{error}</div>}
        {notice && <div className="card small">{notice}</div>}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? "One moment…" : title}
        </button>

        <div className="small muted auth-switch">
          {mode !== "signin" && (
            <button type="button" className="linklike" onClick={() => setMode("signin")}>
              I have an account
            </button>
          )}
          {mode !== "signup" && (
            <button type="button" className="linklike" onClick={() => setMode("signup")}>
              Create an account
            </button>
          )}
          {mode !== "link" && (
            <button type="button" className="linklike" onClick={() => setMode("link")}>
              Email me a sign-in link
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
