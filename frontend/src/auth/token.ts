/**
 * The seam between the API client and whatever signs the user in.
 *
 * `client.ts` must not import the sign-in library (it would drag a browser auth client into
 * every module that calls the API), so the gate registers two functions here instead: one that
 * returns the current access token, and one to call when the server says it is no longer valid.
 * In local mode nothing registers, the token is always null, and no header is sent.
 */

type TokenProvider = () => Promise<string | null>;

let provider: TokenProvider = async () => null;
let onExpired: () => void = () => {};

export function registerAuth(getToken: TokenProvider, expired: () => void): void {
  provider = getToken;
  onExpired = expired;
}

export const currentToken = (): Promise<string | null> => provider();
export const sessionExpired = (): void => onExpired();

/** Headers for a request, including the bearer token when someone is signed in. */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = await currentToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
