"""Joining Layer 1 and Layer 2 — "give me each node with its state".

The overlay is read-only in one direction by construction: it holds a `CurriculumGraph` and a
state repository, and hands back pairs. There is no code path here that can write to the
curriculum, which is how "state never mutates the curriculum" stops being a rule anyone has to
remember.

A node with no stored record reads back as `KnowledgeState.cold(node_id)`. That default is
applied on read rather than by pre-seeding rows, so adding nodes to the curriculum never
requires a migration of user state — a new node is simply cold until it is assessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph, Node

from .errors import UnknownNodeError
from .models import KnowledgeState
from .repository import KnowledgeStateRepository


@dataclass(frozen=True, slots=True)
class NodeState:
    """One curriculum node together with the user's state for it."""

    node: Node
    state: KnowledgeState

    @property
    def node_id(self) -> str:
        return self.node.node_id

    @property
    def is_assessed(self) -> bool:
        return self.state.is_assessed


class StateOverlay:
    """Read/write access to knowledge state, scoped to a curriculum.

    Three methods, because it enforces exactly two rules and callers only ever need those:

    * **Writes are validated against the curriculum.** State for an unknown node is refused
      rather than silently stored, so the overlay cannot drift from the graph it describes.
    * **Cold defaults are applied on read.** A node with no stored record reads back cold,
      which is why adding curriculum nodes never needs a migration of user state.

    It deliberately offers no lenses — `for_role`, `for_section`, `assessed`, `with_status` and
    friends existed here and were called by nothing but their own tests. Each was a one-line
    filter over `all()` that made the interface wider than the rules it protects, and callers
    that wanted a slice already had `CurriculumGraph` to slice by. Selecting and ranking are
    the engine's job; this joins two layers and guards the join.
    """

    def __init__(
        self, curriculum: CurriculumGraph, repository: KnowledgeStateRepository
    ) -> None:
        self._curriculum = curriculum
        self._repository = repository

    # ---------------------------------------------------------------- reading

    def state_for(self, node_id: str) -> KnowledgeState:
        """State for `node_id`, cold if it has never been assessed.

        Raises UnknownNodeError if the node is not in the curriculum.
        """
        self._require_known(node_id)
        return self._repository.get(node_id) or KnowledgeState.cold(node_id)

    def _stored(self) -> dict[str, KnowledgeState]:
        """Every persisted state, in ONE repository call.

        Bulk reads go through here rather than looping over `get()`. Against the in-memory
        repository the difference is invisible, but against Postgres a per-node loop is 566
        separate round-trips — measured at ~635ms versus ~5ms for a single query. Any method
        that touches more than a couple of nodes must use this.
        """
        return {state.node_id: state for state in self._repository.all()}

    def _join(self, nodes, stored: dict[str, KnowledgeState]) -> tuple[NodeState, ...]:
        return tuple(
            NodeState(
                node=node,
                state=stored.get(node.node_id) or KnowledgeState.cold(node.node_id),
            )
            for node in nodes
        )

    def all(self) -> tuple[NodeState, ...]:
        """Every curriculum node with its state, cold where unassessed."""
        return self._join(self._curriculum, self._stored())

    # ---------------------------------------------------------------- writing

    def save(self, state: KnowledgeState) -> None:
        self._require_known(state.node_id)
        self._repository.save(state)

    def _require_known(self, node_id: str) -> None:
        if node_id not in self._curriculum:
            raise UnknownNodeError(node_id)
