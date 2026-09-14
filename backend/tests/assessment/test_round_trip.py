"""The Layer 4 boundary end to end (BUILD_SPEC.md Stage 4).

Success criteria: any concept yields a valid Schema A; a valid Schema B updates state
deterministically and appends history; malformed input is rejected precisely; the full
round-trip is reproducible.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from knowledgeos.assessment import (
    AssessmentService,
    RoleNotApplicableError,
    SchemaA,
    SchemaValidationError,
    SessionMismatchError,
    UnknownNodeReferenceError,
    UnknownSessionError,
    days_between,
)
from knowledgeos.curriculum import Depth, RoleNotFoundError, fixture_repository
from knowledgeos.state import (
    InMemoryKnowledgeStateRepository,
    InMemorySessionHistoryRepository,
    StateOverlay,
    Status,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def curriculum():
    return fixture_repository().get()


@pytest.fixture
def service(curriculum):
    overlay = StateOverlay(curriculum, InMemoryKnowledgeStateRepository())
    return AssessmentService(curriculum, overlay, InMemorySessionHistoryRepository())


def schema_b_payload(schema_a: SchemaA, **overrides):
    """A well-formed Schema B answering `schema_a`."""
    payload = {
        "schema": "knowledgeos.assessment.output",
        "schema_version": 1,
        "session_id": str(schema_a.session_id),
        "node_id": schema_a.target.node_id,
        "completed_at": (schema_a.generated_at + timedelta(minutes=45)).isoformat(),
        "observations": {"recall": 0.70, "depth": 0.55, "transfer": 0.40},
        "response_time_rating": 0.6,
        "llm_confidence": 0.85,
        "gaps_identified": ["cannot derive it from first principles"],
        "prerequisite_flags": [],
        "recommended_next_concepts": [],
        "evidence_summary": "Solid recall, weaker on mechanism.",
    }
    payload.update(overrides)
    return payload


class TestSchemaAGeneration:
    def test_every_concept_yields_a_valid_schema_a(self, service, curriculum):
        """Stage 4 success criterion: ANY concept works."""
        for node in curriculum:
            schema_a = service.generate(node.node_id, now=NOW)
            assert schema_a.target.node_id == node.node_id
            assert schema_a.schema_version == 1
            assert schema_a.assessment_directives.must_probe_depth

    def test_role_context_defaults_to_the_most_important_role(self, service, curriculum):
        """C.7 selection rule: highest importance, ties broken on priority rank."""
        for node in curriculum:
            schema_a = service.generate(node.node_id, now=NOW)
            chosen = schema_a.role_context.role_id
            best = max(r.importance for r in node.roles)
            assert schema_a.role_context.importance == best
            tied = [r.role_id for r in node.roles if r.importance == best]
            ranks = {r: curriculum.role(r).priority_rank for r in tied}
            assert ranks[chosen] == min(ranks.values())

    def test_default_role_selection_is_deterministic(self, service, curriculum):
        """Same node, same Schema A role — every time, or scores stop being comparable."""
        for node in curriculum:
            chosen = {
                service.generate(node.node_id, now=NOW).role_context.role_id
                for _ in range(3)
            }
            assert len(chosen) == 1

    def test_explicit_role_overrides_the_default(self, service, curriculum):
        """The learner, not the graph, says which role today's session is for."""
        node = curriculum.node("prob-axioms")
        for requirement in node.roles:
            context = service.generate(
                "prob-axioms", now=NOW, role_id=requirement.role_id
            ).role_context
            assert context.role_id == requirement.role_id
            assert context.importance == requirement.importance
            assert context.required_depth == requirement.required_depth

    def test_explicit_role_sets_the_depth_to_probe(self, service):
        """The depth follows the chosen role — this is the whole point of choosing."""
        shallow = service.generate("prob-axioms", now=NOW, role_id="software-engineering")
        deep = service.generate("prob-axioms", now=NOW, role_id="finance-quant")
        assert shallow.assessment_directives.must_probe_depth == Depth.AWARENESS
        assert deep.assessment_directives.must_probe_depth == Depth.DERIVATION

    def test_role_the_node_does_not_serve_is_rejected(self, service):
        """A node with no importance or depth for a role cannot be assessed for it."""
        with pytest.raises(RoleNotApplicableError) as caught:
            service.generate("ml-naive-bayes", now=NOW, role_id="finance-quant")
        assert caught.value.node_id == "ml-naive-bayes"
        assert "finance-quant" not in caught.value.valid_roles
        assert "data-science" in caught.value.valid_roles

    def test_unknown_role_is_a_curriculum_error(self, service):
        with pytest.raises(RoleNotFoundError):
            service.generate("prob-axioms", now=NOW, role_id="astronaut")

    def test_prerequisite_context_comes_from_the_graph(self, service, curriculum):
        schema_a = service.generate("ml-naive-bayes", now=NOW)
        listed = {p.node_id for p in schema_a.prerequisite_context}
        expected = {n.node_id for n in curriculum.prerequisites_of("ml-naive-bayes")}
        assert listed == expected

    def test_root_node_has_no_prerequisite_context(self, service):
        assert service.generate("prob-axioms", now=NOW).prerequisite_context == ()

    def test_cold_node_reports_cold_state(self, service):
        state = service.generate("prob-bayes", now=NOW).current_state
        assert state.intrinsic_mastery == 0.0
        assert state.session_count == 0
        assert state.last_gaps == ()

    def test_payload_uses_the_wire_field_name(self, service):
        payload = service.generate("prob-bayes", now=NOW).to_payload()
        assert payload["schema"] == "knowledgeos.assessment.input"
        assert "schema_name" not in payload

    def test_generation_is_deterministic_given_a_session_id(self, service):
        sid = uuid4()
        a = service.generate("prob-bayes", now=NOW, session_id=sid).to_payload()
        b = service.generate("prob-bayes", now=NOW, session_id=sid).to_payload()
        assert a == b


class TestRoundTrip:
    def test_valid_schema_b_updates_state_and_appends_history(self, service, curriculum):
        schema_a = service.generate("prob-axioms", now=NOW)
        result = service.ingest(schema_b_payload(schema_a), now=NOW)

        assert result.state_before.intrinsic_mastery == 0.0
        assert result.state_after.intrinsic_mastery > 0.0
        assert result.state_after.session_count == 1
        assert result.state_after.last_assessed_at is not None
        assert result.state_after.next_review_at is not None
        assert result.mastery_delta > 0

    def test_history_records_the_whole_session(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        result = service.ingest(schema_b_payload(schema_a), now=NOW)

        record = result.record
        assert record.is_complete
        assert record.node_id == "prob-axioms"
        assert record.role_context == schema_a.role_context.role_id
        assert record.schema_a["schema"] == "knowledgeos.assessment.input"
        assert record.schema_b["schema"] == "knowledgeos.assessment.output"
        assert record.mastery_before == 0.0
        assert record.mastery_after > 0.0
        assert record.computation_trace, "every score must carry its trace"

    def test_trace_explains_how_the_score_was_reached(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        trace = service.ingest(schema_b_payload(schema_a), now=NOW).record.computation_trace
        assert set(trace) == {
            "stage_1_observation",
            "stage_2_evidence",
            "stage_3_mastery",
            "stage_4_stability",
        }
        assert trace["stage_2_evidence"]["llm_weight_cap"] == 0.20

    def test_gaps_are_carried_into_state_and_back_into_the_next_schema_a(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        service.ingest(schema_b_payload(schema_a), now=NOW)

        follow_up = service.generate("prob-axioms", now=NOW + timedelta(days=1))
        assert follow_up.current_state.last_gaps == (
            "cannot derive it from first principles",
        )
        assert "target the previously identified gaps" in (
            follow_up.assessment_directives.focus_hints
        )

    def test_ingestion_is_reproducible(self, curriculum):
        """Same inputs ⇒ same resulting state, run twice from scratch."""
        results = []
        for _ in range(2):
            overlay = StateOverlay(curriculum, InMemoryKnowledgeStateRepository())
            service = AssessmentService(
                curriculum, overlay, InMemorySessionHistoryRepository()
            )
            sid = uuid4()
            schema_a = service.generate("prob-axioms", now=NOW, session_id=sid)
            results.append(service.ingest(schema_b_payload(schema_a), now=NOW).state_after)

        a, b = results
        assert a.intrinsic_mastery == b.intrinsic_mastery
        assert a.stability == b.stability
        assert a.assessment_variance == b.assessment_variance
        assert a.observation_mean == b.observation_mean

    def test_recompute_updates_downstream_nodes(self, service):
        """Assessing a prerequisite must lift its dependents' trust."""
        before = service.recompute(now=NOW).prerequisite_confidence["prob-conditional"]
        schema_a = service.generate("prob-axioms", now=NOW)
        result = service.ingest(
            schema_b_payload(
                schema_a, observations={"recall": 0.95, "depth": 0.95, "transfer": 0.9}
            ),
            now=NOW,
        )
        after = result.snapshot.prerequisite_confidence["prob-conditional"]
        assert after > before

    def test_status_is_derived_not_left_unassessed(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        result = service.ingest(schema_b_payload(schema_a), now=NOW)
        assert result.state_after.status is not Status.UNASSESSED

    def test_a_session_can_only_be_ingested_once(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        payload = schema_b_payload(schema_a)
        service.ingest(payload, now=NOW)
        with pytest.raises(UnknownSessionError):
            service.ingest(payload, now=NOW)

    def test_running_mean_persists_across_sessions(self, service):
        """Without persisted μ, σ² would restart every session and never see disagreement."""
        first = service.generate("prob-axioms", now=NOW)
        service.ingest(
            schema_b_payload(
                first, observations={"recall": 0.9, "depth": 0.9, "transfer": 0.9}
            ),
            now=NOW,
        )
        state_1 = service._overlay.state_for("prob-axioms")

        later = NOW + timedelta(days=2)
        second = service.generate("prob-axioms", now=later)
        result = service.ingest(
            schema_b_payload(
                second,
                observations={"recall": 0.1, "depth": 0.1, "transfer": 0.1},
                completed_at=later.isoformat(),
            ),
            now=later,
        )
        assert result.state_after.observation_mean != state_1.observation_mean
        assert result.state_after.assessment_variance > state_1.assessment_variance, (
            "wildly inconsistent sessions must raise variance"
        )


class TestRejection:
    """Hard-fail on anything malformed. Never coerce, never partially apply."""

    def test_mismatched_session_id_is_rejected(self, service):
        service.generate("prob-axioms", now=NOW)
        with pytest.raises(UnknownSessionError):
            service.ingest(
                schema_b_payload(
                    service.generate("prob-bayes", now=NOW), session_id=str(uuid4())
                ),
                now=NOW,
            )

    def test_mismatched_node_id_is_rejected(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(SessionMismatchError) as exc:
            service.ingest(schema_b_payload(schema_a, node_id="prob-bayes"), now=NOW)
        assert exc.value.expected == "prob-axioms"
        assert exc.value.received == "prob-bayes"

    @pytest.mark.parametrize("field", ["recall", "depth", "transfer"])
    @pytest.mark.parametrize("bad", [-0.1, 1.1])
    def test_out_of_range_observations_are_rejected(self, service, field, bad):
        schema_a = service.generate("prob-axioms", now=NOW)
        observations = {"recall": 0.5, "depth": 0.5, "transfer": 0.5}
        observations[field] = bad
        with pytest.raises(SchemaValidationError, match=field):
            service.ingest(schema_b_payload(schema_a, observations=observations), now=NOW)

    @pytest.mark.parametrize("field", ["response_time_rating", "llm_confidence"])
    def test_out_of_range_scalars_are_rejected(self, service, field):
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(SchemaValidationError, match=field):
            service.ingest(schema_b_payload(schema_a, **{field: 1.5}), now=NOW)

    @pytest.mark.parametrize(
        "missing", ["observations", "response_time_rating", "llm_confidence", "node_id"]
    )
    def test_missing_required_fields_are_rejected(self, service, missing):
        schema_a = service.generate("prob-axioms", now=NOW)
        payload = schema_b_payload(schema_a)
        del payload[missing]
        with pytest.raises(SchemaValidationError, match=missing):
            service.ingest(payload, now=NOW)

    def test_unknown_fields_are_rejected_not_dropped(self, service):
        """G.5: never silently drop unknown fields on Schema B ingestion."""
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(SchemaValidationError, match="mastery_score"):
            service.ingest(
                schema_b_payload(schema_a, mastery_score=0.9), now=NOW
            )

    def test_unknown_prerequisite_flag_is_rejected(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(UnknownNodeReferenceError, match="ghost-node"):
            service.ingest(
                schema_b_payload(schema_a, prerequisite_flags=["ghost-node"]), now=NOW
            )

    def test_unknown_recommended_concept_is_rejected(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(UnknownNodeReferenceError, match="not-a-real-node"):
            service.ingest(
                schema_b_payload(schema_a, recommended_next_concepts=["not-a-real-node"]),
                now=NOW,
            )

    def test_wrong_schema_name_is_rejected(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(SchemaValidationError):
            service.ingest(schema_b_payload(schema_a, schema="something.else"), now=NOW)

    def test_rejection_reports_every_problem_at_once(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        payload = schema_b_payload(
            schema_a,
            observations={"recall": 5.0, "depth": -1.0, "transfer": 0.5},
            llm_confidence=9.0,
        )
        with pytest.raises(SchemaValidationError) as exc:
            service.ingest(payload, now=NOW)
        assert len(exc.value.problems) >= 3

    def test_a_rejected_payload_leaves_state_untouched(self, service):
        """A partially-applied assessment would be worse than a refused one."""
        schema_a = service.generate("prob-axioms", now=NOW)
        before = service._overlay.state_for("prob-axioms")
        with pytest.raises(UnknownNodeReferenceError):
            service.ingest(
                schema_b_payload(schema_a, prerequisite_flags=["ghost"]), now=NOW
            )
        assert service._overlay.state_for("prob-axioms") == before
        assert len(service._history.all()) == 0

    def test_a_rejected_payload_leaves_the_session_open(self, service):
        """The user should be able to fix the paste and retry, not lose the session."""
        schema_a = service.generate("prob-axioms", now=NOW)
        with pytest.raises(SchemaValidationError):
            service.ingest(schema_b_payload(schema_a, llm_confidence=3.0), now=NOW)
        result = service.ingest(schema_b_payload(schema_a), now=NOW)
        assert result.state_after.session_count == 1


class TestElapsedTimeConversion:
    """This layer owns the clock; the engine never sees a timestamp."""

    def test_days_between_basic(self):
        assert days_between(NOW, NOW + timedelta(days=3)) == pytest.approx(3.0)

    def test_never_assessed_has_no_elapsed_time(self):
        assert days_between(None, NOW) == 0.0

    def test_clock_skew_clamps_to_zero(self):
        assert days_between(NOW, NOW - timedelta(days=5)) == 0.0

    def test_partial_days(self):
        assert days_between(NOW, NOW + timedelta(hours=12)) == pytest.approx(0.5)

    def test_decay_shows_up_in_a_later_recompute(self, service):
        schema_a = service.generate("prob-axioms", now=NOW)
        service.ingest(
            schema_b_payload(
                schema_a, observations={"recall": 0.95, "depth": 0.95, "transfer": 0.95}
            ),
            now=NOW,
        )
        fresh = service.recompute(now=NOW).retention["prob-axioms"]
        stale = service.recompute(now=NOW + timedelta(days=365)).retention["prob-axioms"]
        assert stale < fresh
