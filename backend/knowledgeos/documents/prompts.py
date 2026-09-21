"""The extraction prompt. The application owns it, an LLM executes it.

Same principle as `assessment/prompts.py`: the model reads the document, but *what counts as a
requirement*, *what the depth rungs mean* and *what a weight of 0.8 claims* are decided here.
The moment the model decides those, two documents stop being comparable and the readiness
number they produce stops meaning anything.

## The failure modes this fights

**Summarising instead of mapping.** Asked what a paper is about, a model writes prose. Asked to
emit ids from a fixed list, it still drifts back toward prose unless told plainly not to. The
output contract is restated at the end, where nothing has displaced it.

**Inventing ids.** A model that cannot find "softmax" in the catalogue will happily write
`dl-softmax` because it looks like the others. That single habit is why `out_of_curriculum`
exists: there has to be somewhere honest to put a concept, or the model will manufacture a
plausible id instead.

**Listing prerequisites.** Asked what a transformer paper requires, a model reaches for linear
algebra unprompted. It must not: the application computes the prerequisite closure from the DAG
and does it better, because it knows the edge weights. A model that also walks the tree makes
the same concept arrive twice at two different weights and drags the document's centre of
gravity toward whatever foundations it happened to name.

**Inflation, in both dimensions.** Left alone, a model marks most concepts `deep` and most
weights around 0.8 — every paper then looks like it demands everything, the harmonic mean
collapses, and every document reports the same near-zero readiness. Both scales are therefore
anchored, and both say out loud what inflation actually costs the user: hours spent studying an
incidental mention instead of the thing that was genuinely blocking them.
"""

from __future__ import annotations

import json

from .catalogue import Catalogue
from .schemas import SCHEMA_D_NAME, SCHEMA_VERSION

_DEPTH_LADDER = """\
- **`awareness`** — the document names it, assumes you recognise the term, and moves on. You
  need to know what it is and why it is mentioned. Most citations and related-work mentions.
- **`working`** — the document uses it as a tool and expects you to follow the usage. You need
  to be able to apply it correctly, but the document never opens it up.
- **`deep`** — the document argues about it: why it works, what it assumes, how it compares to
  alternatives, when it breaks. You cannot follow that argument by knowing the procedure.
- **`derivation`** — the document derives it, or its central claim cannot be checked without
  deriving it yourself. Reserve this for the actual mathematical core."""

_WEIGHT_SCALE = """\
- **0.90-1.00** — the document is *about* this. Remove it and there is no document. Typically
  one to three concepts, sometimes only one.
- **0.60-0.89** — load-bearing. A main section depends on it, and not knowing it means losing a
  substantial part of the argument.
- **0.30-0.59** — genuinely used, in one place. Not knowing it costs you a paragraph or a
  figure, not the paper.
- **0.10-0.29** — mentioned, compared against, or assumed in passing. Context, not content.
- **below 0.10** — do not list it at all."""

_CALIBRATION = """\
## Calibration — read this before you assign a single number

Both scales above are routinely inflated, and inflation here is not a harmless bias. These
weights become the importance terms in a bottleneck-weighted readiness score, and the depths
become mastery targets. Mark an incidental mention at 0.85 and the application will rank it
above the concept that is genuinely blocking this reader, and send them to spend hours on the
wrong thing. That is the specific harm to avoid.

Concretely, for a typical paper or report:

- **Most concepts belong below 0.50.** A document has a handful of load-bearing ideas and a
  long tail of things it uses once. If more than about a quarter of your list is above 0.60,
  you are inflating.
- **Most concepts belong at `awareness` or `working`.** `deep` means the document *argues*
  about the concept. `derivation` means it *derives* it. A paper that applies Adam and cites
  the Adam paper needs Adam at `working`, not at `derivation` — no matter how mathematical
  Adam is in general. The question is what THIS document demands, never what the concept
  deserves in the abstract.
- **A 10-page paper usually engages 5 to 15 concepts directly.** Forty means you are listing
  prerequisites, or listing everything the topic touches rather than what the document
  actually uses. Three usually means you mapped the title instead of reading the body.
- **When two catalogue entries could both fit, pick the more specific one.** If the document
  is about multi-head attention, say multi-head attention — not "deep learning".
- **Being unsure is not a reason to inflate.** If you cannot tell whether the document needs
  something at `working` or `deep`, choose `working`. The application measures the reader
  directly and will find out; a target set too high wastes their time on certainty they did
  not need."""


def _rules(inline: bool) -> str:
    where = (
        "the catalogue printed below"
        if inline
        else "the attached catalogue file (`knowledgeos-concepts.txt`)"
    )
    return f"""\
1. **Every `node_id` must be copied exactly from {where}.** Do not invent, abbreviate, correct,
   or guess an id. An id that is not in the catalogue is rejected outright and the whole
   extraction fails — there is no partial credit and no fuzzy matching, by design.
2. **If the document needs something that is not in the catalogue, put it in
   `out_of_curriculum` as free text.** Do not find the "closest" id. A near match attaches this
   document's requirements to a concept it never mentioned, and nothing downstream can detect
   that. An honest gap is useful information; a wrong id is silent corruption.
3. **Do NOT list prerequisites.** List only what the document itself defines, uses, derives, or
   explicitly assumes the reader already knows *at the surface*. The application walks the
   prerequisite graph itself, with edge weights you cannot see, and will pull in the
   foundations — including ones you would not have thought of. If you list them too, the same
   concept arrives twice at two different weights and the result is worse than either.
4. **Do not rank, order, or recommend.** No study order, no "start here", no time estimates,
   no difficulty judgements about the reader. You cannot see what they already know; the
   application can, and that is the entire question it is answering.
5. **Cite evidence for every concept.** A section number, a figure, an equation, or a short
   quote. If you cannot point at where in the document it comes from, it does not belong on
   the list."""


def extraction(catalogue: Catalogue, *, inline: bool | None = None) -> str:
    """The prompt to paste into a chat window alongside the document.

    `inline` embeds the catalogue in the prompt instead of referring to an attached file.
    Defaults to whether the catalogue is actually small enough for that — a full 566-concept
    catalogue pasted into a message buries the instructions it is supposed to serve.
    """
    embed = catalogue.fits_inline if inline is None else inline

    template = {
        "schema": SCHEMA_D_NAME,
        "schema_version": SCHEMA_VERSION,
        "document": {
            "title": "<the document's actual title>",
            "kind": "paper | report | job-description | course | book | slides | notes | other",
            "source": "<arXiv id, URL, company, or null>",
        },
        "summary": "<one or two sentences on what this document is>",
        "concepts": [
            {
                "node_id": "<exact id from the catalogue>",
                "required_depth": "awareness | working | deep | derivation",
                "document_weight": 0.0,
                "evidence": "<where in the document this comes from>",
            }
        ],
        "out_of_curriculum": [
            {
                "label": "<concept name, in your own words>",
                "evidence": "<where in the document this comes from>",
            }
        ],
    }

    scope = (
        f"all {catalogue.concept_count} concepts"
        if catalogue.role_id is None and len(catalogue.sections) > 6
        else f"{catalogue.concept_count} concepts across: {', '.join(catalogue.sections)}"
    )

    catalogue_block = (
        f"\n\n## The catalogue ({scope})\n\n```\n{catalogue.text}```\n"
        if embed
        else (
            f"\n\n## The catalogue\n\nAttached as `knowledgeos-concepts.txt` — {scope}. "
            f"Read it before you begin. Every id you emit must appear in it verbatim.\n"
        )
    )

    attach_line = (
        "the document you want to prepare for"
        if embed
        else "the document you want to prepare for, **and** the catalogue file"
    )

    return f"""\
# Map this document onto a fixed concept catalogue

You are the extraction step of KnowledgeOS, a system that models what someone knows and works
out what they should study next. Your job is narrow and mechanical: read the attached document
and report **which concepts from a fixed catalogue a reader would need in order to understand
it, and how deeply**.

You are not summarising the document, reviewing it, or teaching it. You are mapping it.

Attach {attach_line}, then follow the rules below exactly.

## Rules

{_rules(embed)}

## How deep does the document go?

Judge the depth **this document demands**, not how deep the concept can go in general.

{_DEPTH_LADDER}

## How central is it to the document?

`document_weight` is 0-1, and it means "how much of this document rests on this concept".

{_WEIGHT_SCALE}
{catalogue_block}
{_CALIBRATION}

## Output

One JSON object. Nothing before it, nothing after it — no preamble, no commentary, no
explanation of your choices. `concepts` and `out_of_curriculum` are arrays of any length;
`out_of_curriculum` may be empty (`[]`), and often should be.

```json
{json.dumps(template, indent=2, ensure_ascii=False)}
```

Notice what is *not* in this schema: no ids, no dates, no ordering, no recommendations, no
estimates of what the reader knows. The application fills all of that in. Adding a field that
is not in the template above causes the whole extraction to be rejected.

Read the document now, then output the JSON.
"""


__all__ = ["extraction"]
