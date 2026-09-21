"""The document boundary: catalogue out, Schema D in.

The rejection tests carry most of the weight. This boundary is crossed by pasting text a
language model wrote, so the interesting question is never "does the happy path work" — it is
whether a plausible-looking wrong answer gets in. A fabricated node id that were accepted would
attach a document's requirements to a concept it never mentioned, and no number computed after
that point could be trusted or even suspected.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from knowledgeos.curriculum import fixture_repository
from knowledgeos.documents import (
    DocumentService,
    DuplicateConceptError,
    EmptyExtractionError,
    ExtractionValidationError,
    UnknownConceptError,
)
from knowledgeos.documents import catalogue as catalogue_module
from knowledgeos.state import DocumentNotFoundError, InMemoryDocumentRepository

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def curriculum():
    return fixture_repository().get()


@pytest.fixture
def service(curriculum):
    return DocumentService(curriculum, InMemoryDocumentRepository())


@pytest.fixture
def node_ids(curriculum):
    """Two real ids, the first one chosen to have prerequisites."""
    with_prereqs = [n.node_id for n in curriculum if curriculum.ancestors(n.node_id)]
    others = [n.node_id for n in curriculum if n.node_id not in with_prereqs]
    return with_prereqs[0], (others or with_prereqs)[-1]


def extraction(node_id, **overrides) -> dict:
    payload = {
        "schema": "knowledgeos.document.extraction",
        "schema_version": 1,
        "document": {"title": "A Paper", "kind": "paper", "source": "arXiv:0000.00000"},
        "summary": "A paper about something.",
        "concepts": [
            {
                "node_id": node_id,
                "required_depth": "deep",
                "document_weight": 0.9,
                "evidence": "Section 3.",
            }
        ],
        "out_of_curriculum": [{"label": "Byte-pair encoding", "evidence": "Section 5.1."}],
    }
    payload.update(overrides)
    return payload


# ------------------------------------------------------------------ catalogue


def test_the_full_catalogue_covers_every_concept(service, curriculum):
    schema_c = service.schema_c()
    assert schema_c.concept_count == len(curriculum)
    for node in curriculum:
        assert node.node_id in schema_c.catalogue


def test_a_scoped_catalogue_only_contains_its_sections(service, curriculum):
    section = curriculum.sections[0]
    schema_c = service.schema_c(sections=(section,))
    assert schema_c.sections == (section,)
    for node in curriculum:
        if node.section != section:
            assert f"{node.node_id} |" not in schema_c.catalogue


def test_the_prompt_tells_the_model_where_the_catalogue_is(service, curriculum):
    """A prompt that says "see the attached file" when the catalogue was inlined, or the
    reverse, sends the model looking for something that is not there."""
    inlined = service.schema_c(sections=(curriculum.sections[0],), inline=True)
    assert inlined.fits_inline
    assert inlined.catalogue in inlined.prompt

    attached = service.schema_c(inline=False)
    assert not attached.fits_inline
    assert attached.catalogue not in attached.prompt
    assert attached.catalogue_filename in attached.prompt


def test_a_big_catalogue_defaults_to_being_attached():
    """The real 566-concept catalogue is far too large to paste into a chat message."""
    from knowledgeos.curriculum import JsonCurriculumRepository

    real = JsonCurriculumRepository().get()
    built = catalogue_module.build(real)
    assert built.concept_count == len(real)
    assert not built.fits_inline
    assert len(built.text) > catalogue_module.INLINE_LIMIT_CHARS


def test_the_prompt_forbids_the_three_things_that_would_corrupt_the_result(service):
    """Not prose-checking the prompt — these three instructions are load-bearing.

    Inventing ids corrupts state silently; listing prerequisites double-counts against the
    closure; ranking asks the model to answer the one question it has no information for.
    """
    prompt = service.schema_c().prompt.lower()
    assert "out_of_curriculum" in prompt
    assert "do not invent" in prompt
    assert "do not list prerequisites" in prompt
    assert "do not rank" in prompt


def test_an_unknown_role_is_rejected(service):
    from knowledgeos.curriculum import RoleNotFoundError

    with pytest.raises(RoleNotFoundError):
        service.schema_c(role_id="not-a-role")


# ------------------------------------------------------------------- ingest


def test_a_valid_extraction_produces_a_plan(service, node_ids):
    node_id, _ = node_ids
    plan = service.ingest(extraction(node_id), now=NOW)

    assert plan.record.title == "A Paper"
    assert plan.record.created_at == NOW
    assert [r.node_id for r in plan.stated] == [node_id]
    assert plan.implied, "a concept with prerequisites must imply more concepts"
    assert plan.steps


def test_the_extraction_is_stored_verbatim(service, node_ids):
    """Evidence preservation: the plan is recomputed, so the raw claim must survive."""
    node_id, _ = node_ids
    payload = extraction(node_id)
    plan = service.ingest(payload, now=NOW)

    stored = plan.record.extraction
    assert stored["concepts"] == payload["concepts"]
    assert stored["out_of_curriculum"] == payload["out_of_curriculum"]


def test_an_invented_node_id_is_rejected_not_matched(service, node_ids):
    """The single most important rejection in this module."""
    node_id, _ = node_ids
    payload = extraction(node_id)
    payload["concepts"].append(
        {
            "node_id": f"{node_id}-extended",
            "required_depth": "deep",
            "document_weight": 0.5,
            "evidence": "Section 4.",
        }
    )
    with pytest.raises(UnknownConceptError) as error:
        service.ingest(payload, now=NOW)
    assert f"{node_id}-extended" in error.value.node_ids
    assert len(service.documents.all()) == 0, "nothing may be stored when ingestion fails"


def test_an_unknown_field_is_rejected_never_dropped(service, node_ids):
    """Schema discipline: a field we do not recognise means the two sides disagree."""
    node_id, _ = node_ids
    with pytest.raises(ExtractionValidationError):
        service.ingest(extraction(node_id, recommended_order=[node_id]), now=NOW)


def test_a_duplicated_concept_is_rejected(service, node_ids):
    node_id, _ = node_ids
    payload = extraction(node_id)
    payload["concepts"] = payload["concepts"] * 2
    with pytest.raises(DuplicateConceptError):
        service.ingest(payload, now=NOW)


def test_an_extraction_with_no_concepts_is_rejected(service, node_ids):
    node_id, _ = node_ids
    with pytest.raises(EmptyExtractionError):
        service.ingest(extraction(node_id, concepts=[]), now=NOW)


def test_an_out_of_range_weight_is_rejected(service, node_ids):
    node_id, _ = node_ids
    payload = extraction(node_id)
    payload["concepts"][0]["document_weight"] = 1.4
    with pytest.raises(ExtractionValidationError):
        service.ingest(payload, now=NOW)


def test_a_concept_with_no_evidence_is_rejected(service, node_ids):
    """"Why is this on my list?" must be answerable, so evidence is not optional."""
    node_id, _ = node_ids
    payload = extraction(node_id)
    del payload["concepts"][0]["evidence"]
    with pytest.raises(ExtractionValidationError):
        service.ingest(payload, now=NOW)


def test_every_validation_problem_is_reported_at_once(service, node_ids):
    """One paste, one list of fixes — not three round trips through a chat window."""
    node_id, _ = node_ids
    payload = extraction(node_id)
    payload["concepts"][0]["document_weight"] = 2.0
    payload["concepts"][0]["required_depth"] = "profound"
    del payload["document"]["title"]
    with pytest.raises(ExtractionValidationError) as error:
        service.ingest(payload, now=NOW)
    assert len(error.value.problems) >= 3


# -------------------------------------------------------------------- plans


def test_a_plan_is_recomputed_against_current_mastery_not_frozen(service, node_ids, curriculum):
    """The reason plans are not stored. Studying a prerequisite must move every document that
    needed it, with no re-extraction."""
    node_id, _ = node_ids
    cold = service.ingest(extraction(node_id), now=NOW)
    assert cold.readiness.readiness < 1.0

    record = service.get(cold.record.document_id)
    requirements = service.requirements(record)

    class _Snapshot:
        effective_mastery = {r.node_id: 1.0 for r in requirements}
        leverage = dict.fromkeys(effective_mastery, 0.0)
        current_importance = dict.fromkeys(effective_mastery, 0.0)

    warm = service.plan(record, snapshot=_Snapshot())
    assert warm.readiness.readiness == pytest.approx(1.0)
    assert warm.steps == ()


def test_documents_come_back_newest_first(service, node_ids):
    node_id, other = node_ids
    first = service.ingest(
        extraction(node_id, document={"title": "Older", "kind": "paper"}), now=NOW
    )
    second = service.ingest(
        extraction(other, document={"title": "Newer", "kind": "report"}),
        now=NOW.replace(hour=13),
    )
    titles = [p.record.title for p in service.all_plans(snapshot=None)]
    assert titles[0] == "Newer"
    assert {first.record.title, second.record.title} == {"Older", "Newer"}


def test_a_document_can_be_deleted(service, node_ids):
    node_id, _ = node_ids
    plan = service.ingest(extraction(node_id), now=NOW)
    service.delete(plan.record.document_id)
    with pytest.raises(DocumentNotFoundError):
        service.get(plan.record.document_id)


def test_deleting_something_that_is_not_there_fails_loudly(service):
    from uuid import uuid4

    with pytest.raises(DocumentNotFoundError):
        service.delete(uuid4())


def test_ingesting_the_same_extraction_twice_gives_identical_records(service, node_ids):
    """Determinism at the boundary: same payload, same `now`, same stored evidence."""
    node_id, _ = node_ids
    first = service.ingest(extraction(node_id), now=NOW)
    second = service.ingest(extraction(node_id), now=NOW)
    assert first.record.extraction == second.record.extraction
    assert first.record.created_at == second.record.created_at
    assert [r.node_id for r in first.requirements] == [r.node_id for r in second.requirements]
