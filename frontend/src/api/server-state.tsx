/**
 * Reading server state, in one place.
 *
 * Every view here reads numbers the backend derives, and one ingestion moves almost all of
 * them: prerequisite propagation means assessing a single node changes effective mastery,
 * status, recommendations and readiness across the whole graph. So invalidation is global by
 * nature — there is no useful per-view cache key — and every view has to re-read together.
 *
 * That was previously done by threading a `refreshKey` integer as a prop into four components,
 * each of which then re-implemented the same fetch-and-cancel effect. It worked, but the
 * convention was invisible: a new view that forgot to accept the prop, add it to its dependency
 * array, or guard against a late response showed stale numbers rather than raising anything.
 * Three of the four also had no rejection handler at all, so a failed request left a permanent
 * spinner or a blank panel with the reason only in the console.
 *
 *     const roles = useServerState(() => api.roles(), []);
 *     const invalidate = useInvalidate();      // call after a mutation
 *
 * Cancellation, error unwrapping and re-reading on invalidation are the module's job, not the
 * caller's. In particular `problems` is always populated from the API's error envelope, which
 * is the one the backend goes to trouble to produce — a caller cannot opt out of handling a
 * failure by leaving a `.catch` off, because there is no `.catch` to leave off.
 *
 * Deliberately not a query library. There is no cache to share, no deduplication worth having
 * at this scale, and one counter expresses "everything is stale now" exactly.
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "./client";

const VersionContext = createContext(0);
const InvalidateContext = createContext<() => void>(() => {});

export function ServerStateProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0);
  const invalidate = useCallback(() => setVersion((current) => current + 1), []);

  return (
    <InvalidateContext.Provider value={invalidate}>
      <VersionContext.Provider value={version}>{children}</VersionContext.Provider>
    </InvalidateContext.Provider>
  );
}

/** Mark every server read stale. Call after anything that writes. */
export function useInvalidate(): () => void {
  return useContext(InvalidateContext);
}

/** Every validation failure the API reported, or one line describing whatever else went wrong. */
export function problemsOf(error: unknown): string[] {
  return error instanceof ApiError ? error.problems : [String(error)];
}

export interface Read<T> {
  data: T | null;
  problems: string[];
  loading: boolean;
  /** True once a response has arrived, successfully or not. Distinguishes "empty" from "not yet". */
  settled: boolean;
}

/**
 * Read something from the API, re-reading when `deps` change or anything invalidates.
 *
 * Pass `null` for `load` when there is nothing to read yet — a node inspector with no node
 * selected — rather than calling the hook conditionally.
 *
 * `data` is kept across a re-read so a view can show the previous values while the next ones
 * are in flight, instead of flashing a spinner every time the user touches a filter.
 */
export function useServerState<T>(
  load: (() => Promise<T>) | null,
  deps: readonly unknown[],
): Read<T> {
  const version = useContext(VersionContext);
  const [state, setState] = useState<Read<T>>({
    data: null,
    problems: [],
    loading: load !== null,
    settled: false,
  });

  // `load` is a fresh closure every render; `deps` is what actually decides when to re-read.
  const latest = useRef(load);
  latest.current = load;

  useEffect(() => {
    const run = latest.current;
    if (!run) {
      setState({ data: null, problems: [], loading: false, settled: true });
      return;
    }

    let cancelled = false;
    setState((previous) => ({ ...previous, loading: true, problems: [] }));

    run().then(
      (data) => {
        if (!cancelled) setState({ data, problems: [], loading: false, settled: true });
      },
      (error: unknown) => {
        if (!cancelled) {
          setState({ data: null, problems: problemsOf(error), loading: false, settled: true });
        }
      },
    );

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  return state;
}
