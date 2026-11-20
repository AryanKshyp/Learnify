/**
 * "Connect OpenRouter": the one provider where a user can authorise the app against their own
 * account instead of pasting a key, using OAuth with PKCE.
 *
 * Flow: make a random verifier, send its SHA-256 hash to OpenRouter with the redirect, and when
 * OpenRouter sends the browser back with a one-time `code`, hand `code` + the verifier to our
 * server, which exchanges them for a key scoped to the user's own account. The verifier lives
 * only in this tab's sessionStorage for the length of the round trip.
 */

const VERIFIER_KEY = "knowledgeos.openrouter.verifier";
const MARKER = "connect";
const MARKER_VALUE = "openrouter";

const base64Url = (bytes: Uint8Array): string =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

export async function startOpenRouterConnect(): Promise<void> {
  const verifier = base64Url(crypto.getRandomValues(new Uint8Array(48)));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem(VERIFIER_KEY, verifier);

  const callback = `${window.location.origin}/?${MARKER}=${MARKER_VALUE}`;
  const url = new URL("https://openrouter.ai/auth");
  url.searchParams.set("callback_url", callback);
  url.searchParams.set("code_challenge", base64Url(new Uint8Array(digest)));
  url.searchParams.set("code_challenge_method", "S256");
  window.location.assign(url.toString());
}

/** If this page load is OpenRouter's redirect back, the code and verifier to exchange. */
export function takeOpenRouterCallback(): { code: string; verifier: string } | null {
  const params = new URLSearchParams(window.location.search);
  if (params.get(MARKER) !== MARKER_VALUE) return null;

  // Clear the URL first: a refresh must not replay a one-time code.
  window.history.replaceState({}, "", window.location.pathname);

  const code = params.get("code");
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  return code && verifier ? { code, verifier } : null;
}
