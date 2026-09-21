"""The concept catalogue — the vocabulary the extraction is allowed to use.

Without this, an LLM reading a paper returns topic names in its own words ("attention
mechanism", "scaled dot product attention", "self-attention") and something has to guess which
node each one meant. Guessing is exactly what this project forbids: a fuzzy match that lands on
the wrong concept attaches a document's requirements to something it never mentioned, and
nothing downstream can detect it. Hand the model the ids and the guess disappears.

## Full or scoped

566 concepts is about 36 KB — nothing for a chat window to read as an attached file, too much
to paste into a message. So the catalogue comes in two sizes:

    full        every concept. Downloaded as a .txt and attached alongside the document.
    scoped      one role and/or a few sections. Small enough to sit inside the prompt itself.

Scoping is a real trade-off and the caller makes it, not this module: a scoped catalogue is one
less attachment, but a concept outside the scope cannot be reported at all — it lands in
`out_of_curriculum` and looks like a curriculum gap when it is really a scoping mistake.

Sections are kept as headers rather than flattened. The grouping costs a few hundred bytes and
gives the model somewhere to look: asked for the prerequisites of a transformer paper it can
scan `linear-algebra` and `calculus-optimization` directly instead of pattern-matching over
five hundred unsorted lines.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledgeos.curriculum import CurriculumGraph, Node

#: Above this many characters the catalogue is served as a file rather than pasted into the
#: prompt. Roughly 2,000 tokens — comfortably inside any chat window's message box, and small
#: enough that the prompt's own instructions are not buried under a wall of ids.
INLINE_LIMIT_CHARS = 8_000

#: Rough chars-per-token for this kind of text (short identifiers, heavy punctuation). Used
#: only to show the user a size estimate, never in a decision.
_CHARS_PER_TOKEN = 3.6

CATALOGUE_FILENAME = "knowledgeos-concepts.txt"


@dataclass(frozen=True, slots=True)
class Catalogue:
    """A rendered catalogue and the facts a client needs to present it."""

    text: str
    concept_count: int
    sections: tuple[str, ...]
    role_id: str | None
    filename: str

    @property
    def fits_inline(self) -> bool:
        return len(self.text) <= INLINE_LIMIT_CHARS

    @property
    def approx_tokens(self) -> int:
        return int(len(self.text) / _CHARS_PER_TOKEN)


def _line(node: Node) -> str:
    return f"{node.node_id} | {node.name}"


def build(
    curriculum: CurriculumGraph,
    *,
    role_id: str | None = None,
    sections: tuple[str, ...] = (),
) -> Catalogue:
    """Render the catalogue, optionally narrowed to a role and/or a set of sections.

    Filtering by role here means *nodes tagged for that role*, not a re-weighting. The
    importance lens that `GET /graph` applies is irrelevant to extraction: the model is being
    asked what the document contains, not what matters to the user, and showing it importance
    scores would invite it to report the concepts it thinks are wanted.
    """
    nodes = curriculum.nodes_by_role(role_id) if role_id else curriculum.nodes
    if sections:
        wanted = set(sections)
        nodes = tuple(n for n in nodes if n.section in wanted)

    by_section: dict[str, list[Node]] = {}
    for node in nodes:
        by_section.setdefault(node.section, []).append(node)

    blocks: list[str] = []
    for section in sorted(by_section):
        members = sorted(by_section[section], key=lambda n: n.node_id)
        body = "\n".join(_line(n) for n in members)
        blocks.append(f"## {section}  ({len(members)})\n{body}")

    scope = "all roles" if role_id is None else f"role: {role_id}"
    header = (
        "# KnowledgeOS concept catalogue\n"
        f"# {len(nodes)} concepts · {len(by_section)} sections · {scope}\n"
        "# Format: node_id | name\n"
        "# Use these ids EXACTLY. Never invent one. Anything missing goes in "
        "out_of_curriculum.\n"
    )

    return Catalogue(
        text=header + "\n" + "\n\n".join(blocks) + "\n",
        concept_count=len(nodes),
        sections=tuple(sorted(by_section)),
        role_id=role_id,
        filename=CATALOGUE_FILENAME,
    )


__all__ = ["CATALOGUE_FILENAME", "INLINE_LIMIT_CHARS", "Catalogue", "build"]
