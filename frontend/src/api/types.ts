/**
 * Response shapes, mirroring `knowledgeos/api/schemas.py`.
 *
 * Hand-written rather than generated from OpenAPI: the surface is small, and having the types
 * in one readable file makes the two-mastery distinction visible at the point of use. If this
 * grows much further, generate them instead.
 */

export type Status =
  | "unassessed"
  | "learning"
  | "practiced"
  | "retained"
  | "mastered";

export type Depth = "awareness" | "working" | "deep" | "derivation";

export interface Role {
  role_id: string;
  name: string;
  priority_rank: number;
}

export interface RoleRequirement {
  role_id: string;
  importance: number;
  required_depth: Depth;
}

export interface Edge {
  edge_id: string;
  /** the DEPENDENT */
  from_node_id: string;
  /** the PREREQUISITE */
  to_node_id: string;
  type: string;
  weight: number;
}

export interface NodeSummary {
  node_id: string;
  name: string;
  section: string;
  competency: string;
  type: string;
  /** effective mastery — reflects decay and prerequisites */
  mastery: number;
  importance: number;
  status: Status;
  is_frontier: boolean;
}

/** Everything the default node view deliberately hides (BUILD_SPEC Part E). */
export interface AdvancedMetrics {
  /** M — evidence. Never altered by decay or prerequisites. */
  intrinsic_mastery: number;
  /** EM = M · R · PC */
  effective_mastery: number;
  retention: number;
  prerequisite_confidence: number;
  stability: number | null;
  difficulty: number | null;
  assessment_variance: number;
  engine_confidence: number;
  session_count: number;
  last_assessed_at: string | null;
  next_review_at: string | null;
  critical_path_value: number;
  leverage: number;
  learning_cost: number;
  /** τ — the level at which this node counts as sufficient */
  target: number;
}

export interface NodeDetail extends NodeSummary {
  description: string;
  tags: string[];
  roles: RoleRequirement[];
  prerequisites: NodeSummary[];
  dependents: NodeSummary[];
  advanced: AdvancedMetrics;
  last_gaps: string[];
}

export interface GraphOut {
  nodes: NodeSummary[];
  edges: Edge[];
  roles: Role[];
  sections: string[];
}

export interface Recommendation {
  node_id: string;
  name: string;
  section: string;
  competency: string;
  priority: number;
  expected_readiness_gain: number;
  learning_cost_hours: number;
  leverage: number;
  current_importance: number;
  /** why this was chosen — every recommendation must be interrogable */
  reason: string;
}

export interface RecommendationGroup {
  lens: string;
  key: string | null;
  recommendations: Recommendation[];
}

export interface Readiness {
  role_id: string;
  role_name: string;
  priority_rank: number;
  readiness: number;
  bottleneck_node_id: string | null;
  bottleneck_name: string | null;
  node_count: number;
}

export interface KnowledgeHealth {
  score: number;
  coverage: number;
  mean_effective_mastery: number;
  mean_retention: number;
  critical_gap_ratio: number;
  critical_node_count: number;
  frontier_size: number;
}

export interface Overview {
  health: KnowledgeHealth;
  readiness: Readiness[];
  frontier_size: number;
  unexplored_count: number;
  total_nodes: number;
}

export interface SessionRecord {
  session_id: string;
  node_id: string;
  role_context: string;
  created_at: string;
  completed_at: string | null;
  mastery_before: number;
  mastery_after: number;
}

export interface IngestResponse {
  node_id: string;
  intrinsic_mastery_before: number;
  intrinsic_mastery_after: number;
  status_before: Status;
  status_after: Status;
  next_review_at: string | null;
  session: SessionRecord;
  computation_trace: Record<string, unknown>;
}

// --------------------------------------------------------------------- documents

/** Schema C: the prompt to paste, and the catalogue it refers to. */
export interface Catalogue {
  prompt: string;
  catalogue: string;
  catalogue_filename: string;
  concept_count: number;
  sections: string[];
  role_id: string | null;
  /** true when the catalogue is embedded in the prompt rather than needing an attachment */
  fits_inline: boolean;
  approx_tokens: number;
}

/** One concept a document needs — named by it, or implied by the prerequisite closure. */
export interface Requirement {
  node_id: string;
  name: string;
  section: string;
  competency: string;
  /** the mastery THIS DOCUMENT demands, not what a role demands */
  target: number;
  weight: number;
  /** false means the closure pulled it in; the document never mentioned it */
  stated: boolean;
  required_for: string | null;
  required_for_name: string | null;
  distance: number;
  mastery: number;
  /** min(mastery / target, 1) — 1.0 means no gap here */
  sufficiency: number;
  status: Status;
}

export interface PlanStep {
  node_id: string;
  name: string;
  section: string;
  target: number;
  mastery: number;
  sufficiency: number;
  weight: number;
  stated: boolean;
  required_for_name: string | null;
  expected_gain: number;
  learning_cost_hours: number;
  priority: number;
  blocked_by: string[];
  reason: string;
}

export interface OutOfCurriculum {
  label: string;
  evidence: string;
}

export interface DocumentSummary {
  document_id: string;
  title: string;
  kind: string;
  source: string | null;
  summary: string;
  created_at: string;
  readiness: number;
  bottleneck_node_id: string | null;
  bottleneck_name: string | null;
  concept_count: number;
  gap_count: number;
  stated_count: number;
  implied_count: number;
  total_hours: number;
}

export interface DocumentPlan extends DocumentSummary {
  requirements: Requirement[];
  steps: PlanStep[];
  out_of_curriculum: OutOfCurriculum[];
}

/** The API's single error envelope. */
/**
 * The one error envelope, matching `api/errors.py`.
 *
 * Every optional key below is one the backend actually attaches, checked against the handlers
 * rather than guessed. `session_id`, `node_id`, `role_id` and `valid_roles` were missing, so an
 * unknown-session or wrong-role rejection degraded to the bare message and silently dropped the
 * one detail that said which session or which roles were valid.
 */
export interface ApiErrorBody {
  type: string;
  message: string;
  problems?: string[];
  node_ids?: string[];
  field?: string;
  expected?: string;
  received?: string;
  session_id?: string;
  node_id?: string;
  role_id?: string;
  valid_roles?: string[];
}

// ----------------------------------------------------------------- sessions

/** Body of `POST /sessions`. Mirrors `SessionRequest` in `api/schemas.py`. */
export interface SessionRequest {
  node_id: string;
  /** 1..50, enforced by the backend. */
  min_questions?: number;
  role_id?: string;
}

/**
 * Schema A, as far as the frontend reads it.
 *
 * Typed loosely on purpose, and no further: this is the payload the learner hands to an
 * external engine verbatim, so the app must not depend on more of its shape than it displays.
 * It used to cross as `Record<string, unknown>` and be cast blind at three call sites.
 */
export interface SchemaAPayload {
  session_id: string;
  target: { node_id: string; name: string };
  role_context: { role_id: string };
  [key: string]: unknown;
}

/** Response of `GET /sessions/open/{id}/prompt`. Six keys, not the three declared before. */
export interface PromptOut {
  session_id: string;
  node_id: string;
  node_name: string;
  phase: string;
  description: string;
  prompt: string;
}

// --------------------------------------------------------------------- AI provider

export interface LlmProvider {
  id: string;
  label: string;
  default_model: string;
  key_help_url: string;
  /** Can the user connect an account instead of pasting a key? */
  oauth: boolean;
}

/** Never contains the key itself - only enough to recognise which one is saved. */
export interface LlmSettings {
  configured: boolean;
  provider: string | null;
  model: string | null;
  key_hint: string | null;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}
