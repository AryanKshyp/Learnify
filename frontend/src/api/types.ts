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

/** The API's single error envelope. */
export interface ApiErrorBody {
  type: string;
  message: string;
  problems?: string[];
  node_ids?: string[];
  field?: string;
  expected?: string;
  received?: string;
}
