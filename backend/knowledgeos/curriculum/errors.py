"""Curriculum validation errors.

Validation fails loudly and precisely (BUILD_SPEC.md G.5). Every error names the offending
ids — a cycle report that does not print the cycle is not actionable.
"""

from __future__ import annotations


class CurriculumError(Exception):
    """Base class for every Layer 1 failure."""


class CurriculumValidationError(CurriculumError):
    """One or more validation problems. Reports all of them, not just the first.

    Loading is all-or-nothing, so there is no reason to make the author fix errors one run at
    a time.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        count = len(self.problems)
        noun = "problem" if count == 1 else "problems"
        detail = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"curriculum failed validation ({count} {noun}):\n{detail}")


class CyclicPrerequisiteError(CurriculumError):
    """The prerequisite subgraph contains a cycle.

    C.2 makes acyclicity a hard invariant: propagation walks prerequisites in topological
    order, which does not terminate on a cycle. The offending path is named.
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = list(cycle)
        super().__init__("cycle in prerequisite subgraph: " + " -> ".join(self.cycle))


class NodeNotFoundError(CurriculumError):
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__(f"no such node: {node_id!r}")


class RoleNotFoundError(CurriculumError):
    def __init__(self, role_id: str) -> None:
        self.role_id = role_id
        super().__init__(f"no such role: {role_id!r}")
