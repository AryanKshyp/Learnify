"""Layer 1 - Curriculum (static).

The prerequisite DAG: nodes, edges, roles, per-role importance and required depth. Independent
of any user; never mutated as a side effect of user activity. Depends on nothing internal.

    from knowledgeos.curriculum import fixture_repository

    graph = fixture_repository().get()
    graph.prerequisites_of("ml-naive-bayes")   # direct prerequisites
    graph.ancestors("ml-naive-bayes")          # all transitive prerequisites
    graph.descendants("prob-conditional")      # everything that depends on it
    graph.topological_order()                  # prerequisites first

Read the edge-orientation note in `graph.py` before writing any traversal.
"""

from .errors import (
    CurriculumError,
    CurriculumValidationError,
    CyclicPrerequisiteError,
    NodeNotFoundError,
    RoleNotFoundError,
)
from .graph import CurriculumGraph
from .loader import load_curriculum
from .models import Depth, Edge, EdgeType, Node, NodeType, Role, RoleRequirement
from .repository import (
    DEFAULT_CURRICULUM_PATH,
    FIXTURE_CURRICULUM_PATH,
    CurriculumRepository,
    JsonCurriculumRepository,
    fixture_repository,
)

__all__ = [
    "DEFAULT_CURRICULUM_PATH",
    "FIXTURE_CURRICULUM_PATH",
    "CurriculumError",
    "CurriculumGraph",
    "CurriculumRepository",
    "CurriculumValidationError",
    "CyclicPrerequisiteError",
    "Depth",
    "Edge",
    "EdgeType",
    "JsonCurriculumRepository",
    "Node",
    "NodeNotFoundError",
    "NodeType",
    "Role",
    "RoleNotFoundError",
    "RoleRequirement",
    "fixture_repository",
    "load_curriculum",
]
