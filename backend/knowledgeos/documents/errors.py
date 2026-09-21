"""Document boundary errors.

Same discipline as Layer 4's: this boundary is crossed by copy-paste, so every rejection names
what was wrong and, where it can, what would have been right. A validator that only says
"invalid" makes the user re-run the extraction to guess.
"""

from __future__ import annotations


class DocumentError(Exception):
    """Base class for every document-boundary failure."""


class ExtractionValidationError(DocumentError):
    """A Schema D payload did not satisfy its schema. Reports every problem, not just the first.

    Every problem at once, deliberately. The user's next step is to go back to the chat window
    and ask for a correction; making them do that three times because we reported one field per
    attempt is the difference between a usable boundary and an abandoned one.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        count = len(self.problems)
        noun = "problem" if count == 1 else "problems"
        detail = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"Schema D rejected ({count} {noun}):\n{detail}")


class UnknownConceptError(DocumentError):
    """The extraction referenced node ids that are not in the curriculum.

    Never repaired by guessing. A fuzzy match that lands on the wrong concept would attach a
    document's requirements to something it never mentioned, and every number computed from
    that point on would be quietly wrong with no way to notice. Almost always a stale
    catalogue or a model that invented a plausible-looking id.
    """

    def __init__(self, node_ids: list[str]) -> None:
        self.node_ids = sorted(set(node_ids))
        joined = ", ".join(repr(n) for n in self.node_ids)
        super().__init__(
            f"extraction references {len(self.node_ids)} concept id(s) that are not in the "
            f"curriculum: {joined}. Re-download the concept catalogue and re-run the "
            f"extraction; anything genuinely missing belongs in `out_of_curriculum`."
        )


class DuplicateConceptError(DocumentError):
    """The same concept was listed more than once.

    Rejected rather than merged. A duplicate means the extraction lost track of what it had
    already reported, so the weights it assigned are no longer trustworthy — and silently
    keeping the stricter of two conflicting depths would hide that.
    """

    def __init__(self, node_ids: list[str]) -> None:
        self.node_ids = sorted(set(node_ids))
        joined = ", ".join(repr(n) for n in self.node_ids)
        super().__init__(f"extraction lists the same concept more than once: {joined}")


class EmptyExtractionError(DocumentError):
    """An extraction with no concepts.

    Usually means the model summarised the document instead of mapping it, or the catalogue
    was never attached. Either way there is nothing to plan from.
    """

    def __init__(self) -> None:
        super().__init__(
            "extraction lists no curriculum concepts; the catalogue was probably not attached, "
            "or the model summarised the document instead of mapping it to concept ids"
        )
