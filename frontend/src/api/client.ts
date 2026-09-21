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
  Catalogue,
  DocumentPlan,
  DocumentSummary,
  GraphOut,
  IngestResponse,
  NodeDetail,
  Overview,
  PromptOut,
  RecommendationGroup,
  Role,
  SchemaAPayload,
  SessionRequest,
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

  /** Every validation failure, for display as a list.

   * The envelope's extra keys are part of the message, not decoration: a rejection naming the
   * roles a node actually serves is actionable, and one that drops them is not.
   */
  get problems(): string[] {
    if (this.body.problems?.length) return this.body.problems;
    if (this.body.node_ids?.length) {
      return [`${this.body.field ?? "reference"}: unknown node(s) ${this.body.node_ids.join(", ")}`];
    }
    if (this.body.valid_roles?.length) {
      return [`${this.body.message} — valid roles: ${this.body.valid_roles.join(", ")}`];
    }
    if (this.body.session_id) {
      return [`${this.body.message} (session ${this.body.session_id})`];
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
  roles: () => request<Role[]>("/roles"),
  sections: () => request<string[]>("/sections"),

  graph: (opts: { role?: string; section?: string; competency?: string } = {}) =>
    request<GraphOut>(`/graph${query(opts)}`),

  node: (nodeId: string, role?: string) =>
    request<NodeDetail>(`/nodes/${encodeURIComponent(nodeId)}${query({ role })}`),

  overview: (role?: string) => request<Overview>(`/overview${query({ role })}`),

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

  /**
   * `roleId` is the role the session is for. It decides the depth taught and probed, so it is
   * sent explicitly rather than left to the server's default whenever the learner has picked
   * one — the same concept is a passing mention for one role and a derivation for another.
   */
  openSession: (nodeId: string, roleId?: string, minQuestions = 5) => {
    const body: SessionRequest = {
      node_id: nodeId,
      min_questions: minQuestions,
      ...(roleId ? { role_id: roleId } : {}),
    };
    return request<SchemaAPayload>("/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** The prompt to paste into an external LLM. The app owns these, not the model. */
  prompt: (sessionId: string, phase: string) =>
    request<PromptOut>(`/sessions/open/${sessionId}/prompt${query({ phase })}`),

  ingest: (payload: unknown) =>
    request<IngestResponse>("/sessions/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /**
   * The extraction prompt plus the concept catalogue it refers to. Fetched together because
   * they are one artefact: a prompt saying "use the attached catalogue" is wrong if the
   * catalogue was scoped differently.
   *
   * `sections` is repeatable, so it is appended by hand rather than through `query`.
   */
  catalogue: (opts: { role?: string; sections?: string[]; inline?: boolean } = {}) => {
    const search = new URLSearchParams();
    if (opts.role) search.set("role", opts.role);
    if (opts.inline !== undefined) search.set("inline", String(opts.inline));
    for (const section of opts.sections ?? []) search.append("section", section);
    const rendered = search.toString();
    return request<Catalogue>(`/documents/catalogue${rendered ? `?${rendered}` : ""}`);
  },

  ingestDocument: (payload: unknown) =>
    request<DocumentPlan>("/documents/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  documents: () => request<DocumentSummary[]>("/documents"),

  document: (documentId: string) =>
    request<DocumentPlan>(`/documents/${encodeURIComponent(documentId)}`),

  deleteDocument: (documentId: string) =>
    fetch(`/api/documents/${encodeURIComponent(documentId)}`, { method: "DELETE" }).then(
      (response) => {
        if (!response.ok) throw new Error(`delete failed: ${response.status}`);
      },
    ),
};
