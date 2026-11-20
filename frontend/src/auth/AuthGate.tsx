/**
 * Decides what the visitor sees first.
 *
 * Asks the server whether accounts are on. If not (local use) the app opens straight away, as it
 * always has. If so, nothing from the app renders until there is a session; the sign-in screen
 * is the whole page until then.
 *
 * The Supabase project URL and public key come from the server at runtime (`/api/config`), not
 * from build-time variables, so one built bundle works against any environment.
 */

import { createClient } from "@supabase/supabase-js";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { registerAuth } from "./token";
import { SignIn } from "./SignIn";

interface Account {
  /** null in local mode, where there are no accounts. */
  email: string | null;
  signOut: (() => Promise<void>) | null;
}

const AccountContext = createContext<Account>({ email: null, signOut: null });
export const useAccount = (): Account => useContext(AccountContext);

type Phase =
  | { kind: "loading" }
  | { kind: "local" }
  | { kind: "hosted"; client: SupabaseClient; session: Session | null }
  | { kind: "failed"; message: string };

export function AuthGate({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;

    (async () => {
      try {
        const response = await fetch("/api/config");
        if (!response.ok) throw new Error(`config request failed (${response.status})`);
        const config = await response.json();
        if (cancelled) return;
        if (!config.auth) {
          setPhase({ kind: "local" });
          return;
        }

        const client = createClient(config.supabase_url, config.supabase_anon_key);
        registerAuth(
          async () => (await client.auth.getSession()).data.session?.access_token ?? null,
          () => void client.auth.signOut(),
        );
        const { data } = await client.auth.getSession();
        if (cancelled) return;
        setPhase({ kind: "hosted", client, session: data.session });

        const { data: listener } = client.auth.onAuthStateChange((_event, session) => {
          setPhase((current) =>
            current.kind === "hosted" ? { ...current, session } : current,
          );
        });
        unsubscribe = () => listener.subscription.unsubscribe();
      } catch (error) {
        if (!cancelled) {
          setPhase({
            kind: "failed",
            message: error instanceof Error ? error.message : "Could not reach the server.",
          });
        }
      }
    })();

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  const account = useMemo<Account>(() => {
    if (phase.kind !== "hosted" || !phase.session) return { email: null, signOut: null };
    return {
      email: phase.session.user.email ?? null,
      signOut: async () => {
        await phase.client.auth.signOut();
      },
    };
  }, [phase]);

  if (phase.kind === "loading") return <div className="spinner">Loading…</div>;
  if (phase.kind === "failed") {
    return (
      <div className="auth-page">
        <div className="card auth-card stack">
          <h1>KnowledgeOS</h1>
          <div className="error">Could not start: {phase.message}</div>
          <button onClick={() => window.location.reload()}>Try again</button>
        </div>
      </div>
    );
  }
  if (phase.kind === "hosted" && !phase.session) return <SignIn client={phase.client} />;

  return <AccountContext.Provider value={account}>{children}</AccountContext.Provider>;
}
