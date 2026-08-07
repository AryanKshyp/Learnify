"""Prompts for the external assessment engine.

The load-bearing test here is `TestTheTemplateActuallyValidates`: a model that fills in the
wrap-up template exactly as instructed must produce a Schema B the ingestion pipeline accepts.
If the template and the validator ever disagree, every session fails at the last step — after
the learner has done all the work — which is the worst possible place to discover it.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import pytest

from knowledgeos.assessment import AssessmentService, prompts
from knowledgeos.curriculum import Depth, fixture_repository
from knowledgeos.state import (
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    StateOverlay,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def curriculum():
    return fixture_repository().get()


@pytest.fixture
def service(curriculum):
    overlay = StateOverlay(curriculum, InMemoryKnowledgeStateRepository())
    return AssessmentService(curriculum, overlay, InMemorySessionHistoryRepository())


@pytest.fixture
def schema_a(service):
    return service.generate("ml-naive-bayes", now=NOW)


ALL_PHASES = ("study", "assess", "wrapup", "full")


def build(phase: str, schema_a) -> str:
    if phase == "wrapup":
        return prompts.wrapup(schema_a, completed_at=NOW)
    return {"study": prompts.study, "assess": prompts.assessment, "full": prompts.full_session}[
        phase
    ](schema_a)


class TestEveryPhaseIsUsable:
    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_produces_substantial_text(self, phase, schema_a):
        text = build(phase, schema_a)
        assert len(text) > 800
        assert "{" not in text.split("```")[0], "no unrendered format placeholders"

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_names_the_concept(self, phase, schema_a):
        assert "Naive Bayes" in build(phase, schema_a)

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_is_utf8_clean(self, phase, schema_a):
        text = build(phase, schema_a)
        assert "�" not in text
        assert text.encode("utf-8").decode("utf-8") == text

    def test_phases_are_registered(self):
        assert set(prompts.PHASES) == set(ALL_PHASES)


class TestScoringIsPinnedByTheApp:
    """The rubric must live in the prompt, not in the model's judgement.

    If the LLM decides what `depth` means, two sessions are no longer comparable and the
    mastery number stops being evidence of anything.
    """

    @pytest.mark.parametrize("phase", ["assess", "wrapup"])
    def test_all_three_dimensions_are_defined(self, phase, schema_a):
        text = build(phase, schema_a)
        for dimension in ("recall", "depth", "transfer"):
            assert f"**{dimension}**" in text

    @pytest.mark.parametrize("phase", ["assess", "wrapup"])
    def test_anchors_are_numeric_and_complete(self, phase, schema_a):
        text = build(phase, schema_a)
        for anchor in ("0.00", "0.25", "0.50", "0.75", "1.00"):
            assert text.count(anchor) >= 3, f"{anchor} missing for some dimension"

    @pytest.mark.parametrize("phase", ["assess", "wrapup"])
    def test_fights_score_inflation(self, phase, schema_a):
        """Left alone an LLM scores everything ~0.75 and calls it great."""
        text = build(phase, schema_a).lower()
        assert "do not be" in text or "inflat" in text
        assert "below **0.50**" in text or "below 0.50" in text
        assert "hint" in text, "needing a hint must lower the score"

    def test_says_delivery_is_not_content(self, schema_a):
        assert "never delivery" in prompts.assessment(schema_a)


class TestDepthAwareness:
    """Teaching and testing must adapt to the required depth, or the ladder means nothing."""

    def _for_depth(self, curriculum, service, depth: Depth) -> str:
        # ml-naive-bayes serves several roles at different depths; pick the role that wants
        # `depth` so the generated Schema A carries it.
        node = curriculum.node("ml-naive-bayes")
        role = next((r.role_id for r in node.roles if r.required_depth is depth), None)
        if role is None:
            pytest.skip(f"fixture has no role requiring {depth}")
        schema_a = service.generate("ml-naive-bayes", now=NOW)
        return schema_a

    @pytest.mark.parametrize("depth", list(Depth))
    def test_teaching_instruction_differs_per_depth(self, depth):
        assert prompts._TEACH_BY_DEPTH[depth]
        others = [v for d, v in prompts._TEACH_BY_DEPTH.items() if d is not depth]
        assert prompts._TEACH_BY_DEPTH[depth] not in others

    @pytest.mark.parametrize("depth", list(Depth))
    def test_assessment_instruction_differs_per_depth(self, depth):
        assert prompts._ASSESS_BY_DEPTH[depth]
        others = [v for d, v in prompts._ASSESS_BY_DEPTH.items() if d is not depth]
        assert prompts._ASSESS_BY_DEPTH[depth] not in others

    def test_awareness_does_not_demand_derivation(self):
        assert "do not derive" in prompts._TEACH_BY_DEPTH[Depth.AWARENESS].lower()

    def test_derivation_demands_first_principles(self):
        assert "first principles" in prompts._TEACH_BY_DEPTH[Depth.DERIVATION].lower()

    def test_the_target_depth_appears_in_the_prompt(self, schema_a):
        depth = schema_a.role_context.required_depth.value
        assert f"`{depth}`" in prompts.assessment(schema_a)


class TestContextIsCarriedIn:
    def test_prerequisites_are_listed_with_their_standing(self, schema_a):
        text = prompts.assessment(schema_a)
        for prerequisite in schema_a.prerequisite_context:
            assert prerequisite.node_id in text
            assert prerequisite.name in text

    def test_a_root_node_says_there_are_no_prerequisites(self, service):
        text = prompts.assessment(service.generate("prob-axioms", now=NOW))
        assert "no prerequisites" in text

    def test_first_session_is_stated_as_such(self, schema_a):
        assert "first session" in prompts.assessment(schema_a)

    def test_prior_gaps_are_surfaced_for_a_repeat_session(self, curriculum, service):
        """Known gaps are the highest-value thing to re-probe."""
        service.overlay.save(
            service.overlay.state_for("prob-axioms").replace(
                intrinsic_mastery=0.5,
                session_count=2,
                last_gaps=("cannot state countable additivity",),
            )
        )
        text = prompts.assessment(service.generate("prob-axioms", now=NOW))
        assert "cannot state countable additivity" in text
        assert "probe these specifically" in text

    def test_prior_mastery_is_not_offered_as_a_target(self, curriculum, service):
        """Telling a model the previous score invites it to confirm that score."""
        service.overlay.save(
            service.overlay.state_for("prob-axioms").replace(
                intrinsic_mastery=0.8, session_count=3
            )
        )
        text = prompts.assessment(service.generate("prob-axioms", now=NOW))
        assert "not** a target" in text or "not a target" in text
        assert "floor" in text


class TestPhaseSeparation:
    def test_study_does_not_assess(self, schema_a):
        text = prompts.study(schema_a).lower()
        assert "do not test them yet" in text
        assert "do not output json" in text

    def test_assessment_does_not_emit_json(self, schema_a):
        assert "Do not output JSON in this phase" in prompts.assessment(schema_a)

    def test_assessment_does_not_teach(self, schema_a):
        assert "not to teach" in prompts.assessment(schema_a)

    def test_full_session_keeps_the_boundary(self, schema_a):
        """Sliding from teaching into testing measures what was just said."""
        text = prompts.full_session(schema_a)
        assert "Stop after the study phase and wait" in text
        assert text.index("Study session") < text.index("# Assessment")

    def test_wrapup_demands_json_only(self, schema_a):
        text = prompts.wrapup(schema_a, completed_at=NOW)
        assert "one JSON object and nothing else" in text
        assert "no markdown fence" in text


class TestStudyPhase:
    def test_asks_for_reading_material(self, schema_a):
        text = prompts.study(schema_a)
        assert "## Reading and practice" in text
        assert "**Read**" in text
        assert "**Practise**" in text

    def test_guards_against_invented_sources(self, schema_a):
        """A hallucinated citation is worse than no citation."""
        assert "rather than inventing" in prompts.study(schema_a)

    def test_frames_it_for_the_interview(self, schema_a):
        assert "interview" in prompts.study(schema_a).lower()


class TestWrapupTemplate:
    def test_identifiers_are_prefilled(self, schema_a):
        text = prompts.wrapup(schema_a, completed_at=NOW)
        assert str(schema_a.session_id) in text
        assert f'"node_id": "{schema_a.target.node_id}"' in text

    def test_timestamp_is_prefilled(self, schema_a):
        """Models hallucinate dates; there is no reason to ask for one."""
        assert "2026-08-07T12:00:00Z" in prompts.wrapup(schema_a, completed_at=NOW)

    def test_only_valid_prerequisite_ids_are_offered(self, schema_a):
        """An unrecognised id is a hard rejection, so the valid set must be explicit."""
        text = prompts.wrapup(schema_a, completed_at=NOW)
        assert "Only these exact ids are valid" in text
        for prerequisite in schema_a.prerequisite_context:
            assert f"`{prerequisite.node_id}`" in text

    def test_root_node_wrapup_says_leave_it_empty(self, service):
        text = prompts.wrapup(service.generate("prob-axioms", now=NOW), completed_at=NOW)
        assert "leave as `[]`" in text

    def test_recommended_next_is_delegated_back_to_the_app(self, schema_a):
        """The app ranks by leverage, cost and readiness. The model cannot see any of that."""
        text = prompts.wrapup(schema_a, completed_at=NOW)
        assert "recommended_next_concepts" in text
        assert "The application decides what comes next" in text

    def test_explains_that_llm_confidence_is_capped(self, schema_a):
        """Otherwise a model has an incentive to overstate it."""
        assert "caps this at 20%" in prompts.wrapup(schema_a, completed_at=NOW)


class TestTheTemplateActuallyValidates:
    """The template and the validator must agree, or every session fails at the last step."""

    def extract(self, text: str) -> dict:
        block = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
        assert block, "the wrap-up must contain a fenced JSON template"
        return json.loads(block.group(1))

    def test_template_is_valid_json(self, schema_a):
        assert self.extract(prompts.wrapup(schema_a, completed_at=NOW))

    def test_template_has_exactly_the_contract_fields(self, schema_a):
        from knowledgeos.assessment import SchemaB

        template = self.extract(prompts.wrapup(schema_a, completed_at=NOW))
        expected = set(SchemaB.model_fields) - {"schema_name"} | {"schema"}
        assert set(template) == expected, "template and Schema B have drifted apart"

    def test_a_filled_in_template_is_accepted(self, service, schema_a):
        """The end-to-end guarantee: follow the instructions, get an accepted submission."""
        template = self.extract(prompts.wrapup(schema_a, completed_at=NOW))

        # exactly what a compliant model would return
        template["observations"] = {"recall": 0.7, "depth": 0.45, "transfer": 0.3}
        template["response_time_rating"] = 0.6
        template["llm_confidence"] = 0.75
        template["gaps_identified"] = ["cannot state the conditional independence assumption"]
        template["prerequisite_flags"] = [schema_a.prerequisite_context[0].node_id]
        template["evidence_summary"] = "Stated the rule; could not justify the assumption."

        result = service.ingest(template, now=NOW)
        assert result.state_after.session_count == 1
        assert result.state_after.intrinsic_mastery > 0

    def test_a_filled_in_root_node_template_is_accepted(self, service):
        """No prerequisites means an empty flag list must also validate."""
        schema_a = service.generate("prob-axioms", now=NOW)
        template = self.extract(prompts.wrapup(schema_a, completed_at=NOW))
        template["observations"] = {"recall": 0.9, "depth": 0.8, "transfer": 0.7}
        template["response_time_rating"] = 0.9
        template["llm_confidence"] = 0.8
        template["gaps_identified"] = []
        template["evidence_summary"] = "Solid."

        assert service.ingest(template, now=NOW).state_after.session_count == 1
