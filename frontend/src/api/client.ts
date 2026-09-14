/**
 * Thin fetch wrapper.
 *
 * The API has exactly one error envelope, so unwrapping it once here means every caller can
 * `catch (e) { if (e instanceof ApiError) ... }` and reach `problems` directly — which matters
 * for Schema B, where the whole point is showing the user *every* validation failure at once
 * rather than making them fix one, re-paste, and discover the next.
 */

import type {
  ApiErrorBody,
  GraphOut,
  IngestResponse,
  NodeDetail,
  NodeSummary,
  Overview,
  Readiness,
  RecommendationGroup,
  Role,
  SessionRecord,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  /** Every validation failure, for display as a list. */
  get problems(): string[] {
    if (this.body.problems?.length) return this.body.problems;
    if (this.body.node_ids?.length) {
      return [`${this.body.field ?? "reference"}: unknown node(s) ${this.body.node_ids.join(", ")}`];
    }
    return [this.body.message];
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      const parsed = await response.json();
      body = parsed.error ?? { type: "Error", message: response.statusText };
    } catch {
      body = { type: "Error", message: `${response.status} ${response.statusText}` };
    }
    throw new ApiError(response.status, body);
  }

  return response.json() as Promise<T>;
}

const query = (params: Record<string, string | number | undefined>): string => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
};

export const api = {
  health: () => request<{ status: string; curriculum_nodes: number }>("/health"),
  roles: () => request<Role[]>("/roles"),
  sections: () => request<string[]>("/sections"),

  graph: (opts: { role?: string; section?: string; competency?: string } = {}) =>
    request<GraphOut>(`/graph${query(opts)}`),

  node: (nodeId: string, role?: string) =>
    request<NodeDetail>(`/nodes/${encodeURIComponent(nodeId)}${query({ role })}`),

  overview: (role?: string) => request<Overview>(`/overview${query({ role })}`),
  readiness: () => request<Readiness[]>("/readiness"),

  recommendations: (limit = 5) =>
    request<RecommendationGroup>(`/recommendations${query({ limit })}`),
  recommendationsByRole: (roleId: string, limit = 5) =>
    request<RecommendationGroup>(
      `/recommendations/role/${encodeURIComponent(roleId)}${query({ limit })}`,
    ),
  recommendationsByCompetency: (section: string, limit = 5) =>
    request<RecommendationGroup>(
      `/recommendations/competency/${encodeURIComponent(section)}${query({ limit })}`,
    ),

  unexplored: (limit = 20) => request<NodeSummary[]>(`/unexplored${query({ limit })}`),

  /**
   * `roleId` is the role the session is for. It decides the depth taught and probed, so it is
   * sent explicitly rather than left to the server's default whenever the learner has picked
   * one — the same concept is a passing mention for one role and a derivation for another.
   */
  openSession: (nodeId: string, roleId?: string, minQuestions = 5) =>
    request<Record<string, unknown>>("/sessions", {
      method: "POST",
      body: JSON.stringify({
        node_id: nodeId,
        min_questions: minQuestions,
        ...(roleId ? { role_id: roleId } : {}),
      }),
    }),

  /** The prompt to paste into an external LLM. The app owns these, not the model. */
  prompt: (sessionId: string, phase: "study" | "assess" | "wrapup" | "full") =>
    request<{ phase: string; description: string; prompt: string }>(
      `/sessions/open/${sessionId}/prompt${query({ phase })}`,
    ),

  ingest: (payload: unknown) =>
    request<IngestResponse>("/sessions/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  sessions: (nodeId?: string) =>
    request<SessionRecord[]>(`/sessions${query({ node_id: nodeId })}`),
};
