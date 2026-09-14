"""API response models.

Separate from the Layer 1/2 contracts on purpose: the wire format is free to change without
touching the domain, and the domain is free to hold fields the API does not expose.

The split between `NodeSummary` and `NodeDetail` encodes a product decision from `BUILD_SPEC.md`
Part E — a node shows **Mastery and Importance only** by default, with everything else behind an
Advanced view. The graph endpoint returns summaries so the default view cannot accidentally
become a dashboard; detail is opt-in, one node at a time.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from knowledgeos.curriculum import CurriculumGraph, Depth, Node
from knowledgeos.engine import EngineSnapshot
from knowledgeos.state import KnowledgeState, Status


class RoleOut(BaseModel):
    role_id: str
    name: str
    priority_rank: int


class RoleRequirementOut(BaseModel):
    role_id: str
    importance: float
    required_depth: Depth


class EdgeOut(BaseModel):
    edge_id: str
    from_node_id: str = Field(description="the DEPENDENT")
    to_node_id: str = Field(description="the PREREQUISITE")
    type: str
    weight: float


class NodeSummary(BaseModel):
    """What the graph view shows: identity, mastery, importance. Nothing else."""

    node_id: str
    name: str
    section: str
    competency: str
    type: str
    mastery: float = Field(description="effective mastery — the score reflecting time+prereqs")
    importance: float = Field(description="current importance, for the active role lens")
    status: Status
    is_frontier: bool

    @classmethod
    def build(
        cls, node: Node, snapshot: EngineSnapshot, state: KnowledgeState
    ) -> NodeSummary:
        return cls(
            node_id=node.node_id,
            name=node.name,
            section=node.section,
            competency=node.competency,
            type=node.type.value,
            mastery=snapshot.effective_mastery[node.node_id],
            importance=snapshot.current_importance[node.node_id],
            status=snapshot.status[node.node_id],
            is_frontier=snapshot.frontier[node.node_id],
        )


class AdvancedMetrics(BaseModel):
    """The Advanced view (Part E). Everything the default node view deliberately hides."""

    intrinsic_mastery: float = Field(description="M — evidence. Never altered by decay/prereqs")
    effective_mastery: float = Field(description="EM = M · R · PC")
    retention: float
    prerequisite_confidence: float
    stability: float | None
    difficulty: float | None
    assessment_variance: float
    engine_confidence: float
    session_count: int
    last_assessed_at: datetime | None
    next_review_at: datetime | None
    critical_path_value: float
    leverage: float
    learning_cost: float
    target: float = Field(description="τ — mastery level at which this node counts as sufficient")


class NodeDetail(BaseModel):
    """One node in full, including why it stands where it does."""

    node_id: str
    name: str
    section: str
    competency: str
    type: str
    description: str
    tags: tuple[str, ...]
    roles: tuple[RoleRequirementOut, ...]

    mastery: float
    importance: float
    status: Status
    is_frontier: bool

    prerequisites: tuple[NodeSummary, ...]
    dependents: tuple[NodeSummary, ...]
    advanced: AdvancedMetrics
    last_gaps: tuple[str, ...]


class GraphOut(BaseModel):
    """The graph, as the home view needs it."""

    nodes: tuple[NodeSummary, ...]
    edges: tuple[EdgeOut, ...]
    roles: tuple[RoleOut, ...]
    sections: tuple[str, ...]


class RecommendationOut(BaseModel):
    """One recommendation, with the reason it was chosen.

    A recommendation that cannot explain itself is indistinguishable from a guess, so the
    factors that produced the ranking travel with it (A.5.6).
    """

    node_id: str
    name: str
    section: str
    competency: str
    priority: float
    expected_readiness_gain: float
    learning_cost_hours: float
    leverage: float
    current_importance: float
    reason: str


class RecommendationGroup(BaseModel):
    """Recommendations under one lens — Overall, a Role, or a Competency."""

    lens: str
    key: str | None = None
    recommendations: tuple[RecommendationOut, ...]


class ReadinessOut(BaseModel):
    """Readiness for one role, and the node holding it back."""

    role_id: str
    role_name: str
    priority_rank: int
    readiness: float
    bottleneck_node_id: str | None
    bottleneck_name: str | None
    node_count: int


class KnowledgeHealthOut(BaseModel):
    """The single dashboard number, always with its components."""

    score: float
    coverage: float
    mean_effective_mastery: float
    mean_retention: float
    critical_gap_ratio: float
    critical_node_count: int
    frontier_size: int


class OverviewOut(BaseModel):
    """Everything the home view needs in one call."""

    health: KnowledgeHealthOut
    readiness: tuple[ReadinessOut, ...]
    frontier_size: int
    unexplored_count: int
    total_nodes: int


class SessionRequest(BaseModel):
    """Ask for a Schema A."""

    node_id: str
    min_questions: int = Field(default=5, ge=1, le=50)
    role_id: str | None = Field(
        default=None,
        description=(
            "The role this session is for. Decides the depth taught and probed, and the lens "
            "the prompt is written through. Omitted, the node's most important role is used."
        ),
    )


class SessionRecordOut(BaseModel):
    session_id: str
    node_id: str
    role_context: str
    created_at: datetime
    completed_at: datetime | None
    mastery_before: float
    mastery_after: float


class IngestResponse(BaseModel):
    """What changed as a result of one assessment."""

    node_id: str
    intrinsic_mastery_before: float
    intrinsic_mastery_after: float
    status_before: Status
    status_after: Status
    next_review_at: datetime | None
    session: SessionRecordOut
    computation_trace: dict


def build_readiness(
    curriculum: CurriculumGraph, snapshot: EngineSnapshot
) -> tuple[ReadinessOut, ...]:
    out = []
    for role in curriculum.roles:
        readiness = snapshot.readiness[role.role_id]
        bottleneck = readiness.bottleneck_node_id
        out.append(
            ReadinessOut(
                role_id=role.role_id,
                role_name=role.name,
                priority_rank=role.priority_rank,
                readiness=readiness.readiness,
                bottleneck_node_id=bottleneck,
                bottleneck_name=curriculum.node(bottleneck).name if bottleneck else None,
                node_count=readiness.node_count,
            )
        )
    return tuple(out)
