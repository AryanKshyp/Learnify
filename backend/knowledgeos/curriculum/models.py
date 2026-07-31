"""Layer 1 data contracts — BUILD_SPEC.md C.1 (node), C.2 (edge), C.3 (role), C.4 (depth).

Every model is frozen. The curriculum is static: it must never be mutated as a side effect of
user activity, and making that a type-level guarantee is cheaper than remembering it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

Score = Annotated[float, Field(ge=0.0, le=1.0)]

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class Depth(StrEnum):
    """The depth ladder (C.4), ordered low → high.

    Ordering is meaningful: a higher required depth implies a higher mastery threshold before
    a node counts as sufficient for that role. The engine turns each level into a target τ
    (CALC_ENGINE_SPEC.md §5); Layer 1 only fixes the ladder and its order.

    Comparison is by LADDER POSITION, not by string value. This has to be spelled out
    explicitly: `StrEnum` inherits `str`'s comparison operators, so without these overrides
    `max(...)` would compare alphabetically and rank "working" above "derivation" — silently
    returning the wrong mastery target rather than failing. `functools.total_ordering` cannot
    help, since it only supplies operators a class is *missing* and `str` already has them all.

    Ordering against a non-Depth raises rather than returning NotImplemented: falling back to
    `str` comparison is exactly the silent-wrong-answer this class exists to prevent.
    """

    AWARENESS = "awareness"
    WORKING = "working"
    DEEP = "deep"
    DERIVATION = "derivation"

    @property
    def rank(self) -> int:
        """Position on the ladder; 0 = awareness."""
        return _DEPTH_ORDER.index(self)

    def _rank_of(self, other: object) -> int:
        if not isinstance(other, Depth):
            raise TypeError(
                f"Depth is ordered by ladder position and cannot be compared with "
                f"{type(other).__name__!r}; convert it to a Depth first"
            )
        return other.rank

    def __lt__(self, other: object) -> bool:
        return self.rank < self._rank_of(other)

    def __le__(self, other: object) -> bool:
        return self.rank <= self._rank_of(other)

    def __gt__(self, other: object) -> bool:
        return self.rank > self._rank_of(other)

    def __ge__(self, other: object) -> bool:
        return self.rank >= self._rank_of(other)


_DEPTH_ORDER: tuple[Depth, ...] = (
    Depth.AWARENESS,
    Depth.WORKING,
    Depth.DEEP,
    Depth.DERIVATION,
)


class NodeType(StrEnum):
    ASSESSABLE = "assessable"  # can be assessed directly
    CONCEPT = "concept"  # grouping only


class EdgeType(StrEnum):
    PREREQUISITE = "prerequisite"  # to_node must be understood before from_node
    PART_OF = "part_of"  # hierarchy


#: infix used when deriving edge_id, per the C.2 example
_EDGE_ID_INFIX = {EdgeType.PREREQUISITE: "requires", EdgeType.PART_OF: "part_of"}


class Role(BaseModel):
    """C.3 — a target role, with this user's fixed priority order."""

    model_config = _FROZEN

    role_id: str
    name: str
    priority_rank: int = Field(ge=1)
    schema_version: int = 1


class RoleRequirement(BaseModel):
    """One entry of a node's `roles[]`: what this node is worth *for that role*.

    The same concept legitimately carries different importance and depth per role — that is
    the whole point of shared nodes (A.5.4), and why this is a list rather than two scalars.
    """

    model_config = _FROZEN

    role_id: str
    importance: Score
    required_depth: Depth


class Node(BaseModel):
    """C.1 — a curriculum node."""

    model_config = _FROZEN

    node_id: str
    type: NodeType
    name: str
    section: str
    competency: str
    description: str
    roles: tuple[RoleRequirement, ...] = ()
    tags: tuple[str, ...] = ()
    schema_version: int = 1

    def requirement_for(self, role_id: str) -> RoleRequirement | None:
        """This node's importance/depth for `role_id`, or None if it does not serve that role."""
        for requirement in self.roles:
            if requirement.role_id == role_id:
                return requirement
        return None

    def serves_role(self, role_id: str) -> bool:
        return self.requirement_for(role_id) is not None

    @property
    def role_ids(self) -> frozenset[str]:
        return frozenset(requirement.role_id for requirement in self.roles)

    @property
    def max_required_depth(self) -> Depth | None:
        """Deepest requirement across all roles.

        CALC_ENGINE_SPEC.md §5 uses the max τ over roles when judging absolute sufficiency,
        and the per-role τ when computing that role's readiness.
        """
        if not self.roles:
            return None
        return max(requirement.required_depth for requirement in self.roles)


class Edge(BaseModel):
    """C.2 — a directed edge.

    Direction follows the contract: `from_node_id` is the DEPENDENT, `to_node_id` is the
    PREREQUISITE (or parent). Read it as "from requires to".
    """

    model_config = _FROZEN

    from_node_id: str
    to_node_id: str
    type: EdgeType
    weight: Score
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def edge_id(self) -> str:
        """Deterministic identity, derived rather than stored.

        Storing an edge_id alongside from/to would let the two disagree; deriving it means the
        id and the edge it names can never drift apart.
        """
        return f"{self.from_node_id}__{_EDGE_ID_INFIX[self.type]}__{self.to_node_id}"

    @property
    def dependent_id(self) -> str:
        return self.from_node_id

    @property
    def prerequisite_id(self) -> str:
        return self.to_node_id
