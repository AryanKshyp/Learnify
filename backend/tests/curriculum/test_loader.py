"""Loading and validation (BUILD_SPEC.md Stage 1).

Stage 1's success criteria require that validation catch an injected cycle and a dangling
edge. Both are exercised here against defects injected into the real fixture, so the tests
prove the guard works on realistic data rather than on a toy graph built to fail.
"""

from __future__ import annotations

import copy
import json

import pytest

from knowledgeos.curriculum import (
    CurriculumValidationError,
    CyclicPrerequisiteError,
    load_curriculum,
)


@pytest.fixture
def raw(fixture_curriculum_path) -> dict:
    """The fixture curriculum as plain JSON, for defect injection."""
    with fixture_curriculum_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _node(raw: dict, node_id: str) -> dict:
    return next(n for n in raw["nodes"] if n["node_id"] == node_id)


class TestHappyPath:
    def test_fixture_loads(self, fixture_curriculum_path):
        graph = load_curriculum(fixture_curriculum_path)
        assert len(graph) == 26
        assert len(graph.edges) == 35
        assert len(graph.roles) == 6

    def test_accepts_an_already_parsed_mapping(self, raw):
        assert len(load_curriculum(raw)) == 26

    def test_roles_come_back_in_priority_order(self, fixture_curriculum_path):
        graph = load_curriculum(fixture_curriculum_path)
        assert [r.role_id for r in graph.roles][:2] == ["ai-research", "ai-engineer"]
        assert [r.priority_rank for r in graph.roles] == [1, 2, 3, 4, 5, 6]


class TestDanglingEdges:
    """Stage 1 success criterion: validation catches a dangling edge."""

    def test_edge_to_a_missing_node_is_rejected(self, raw):
        raw["edges"].append(
            {
                "from_node_id": "ml-naive-bayes",
                "to_node_id": "prob-does-not-exist",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CurriculumValidationError) as exc:
            load_curriculum(raw)
        assert "prob-does-not-exist" in str(exc.value)
        assert "does not exist" in str(exc.value)

    def test_edge_from_a_missing_node_is_rejected(self, raw):
        raw["edges"].append(
            {
                "from_node_id": "ghost-node",
                "to_node_id": "prob-bayes",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CurriculumValidationError, match="ghost-node"):
            load_curriculum(raw)

    def test_deleting_a_referenced_node_is_caught(self, raw):
        """The realistic form of this bug: a node is removed, its edges are forgotten."""
        raw["nodes"] = [n for n in raw["nodes"] if n["node_id"] != "prob-bayes"]
        with pytest.raises(CurriculumValidationError, match="prob-bayes"):
            load_curriculum(raw)


class TestCycles:
    """Stage 1 success criterion: validation catches an injected cycle, naming the path."""

    def test_two_node_cycle_is_rejected(self, raw):
        # prob-bayes already requires prob-conditional; make prob-conditional require it back
        raw["edges"].append(
            {
                "from_node_id": "prob-conditional",
                "to_node_id": "prob-bayes",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CyclicPrerequisiteError) as exc:
            load_curriculum(raw)
        assert {"prob-bayes", "prob-conditional"} <= set(exc.value.cycle)

    def test_long_range_cycle_is_rejected(self, raw):
        """A cycle closed across sections - the kind parallel authoring actually produces."""
        raw["edges"].append(
            {
                "from_node_id": "prob-axioms",
                "to_node_id": "ml-naive-bayes",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CyclicPrerequisiteError) as exc:
            load_curriculum(raw)
        assert "ml-naive-bayes" in exc.value.cycle

    def test_the_reported_path_is_actionable(self, raw):
        raw["edges"].append(
            {
                "from_node_id": "prob-conditional",
                "to_node_id": "prob-bayes",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CyclicPrerequisiteError) as exc:
            load_curriculum(raw)
        message = str(exc.value)
        assert "->" in message, "a cycle report must show the path"
        # the path closes on itself, so it can be followed and broken
        assert exc.value.cycle[0] == exc.value.cycle[-1]

    def test_part_of_edges_cannot_create_a_prerequisite_cycle(self, raw):
        """`part_of` is hierarchy, not dependency - it must stay out of the DAG check."""
        raw["edges"].append(
            {
                "from_node_id": "prob-conditional",
                "to_node_id": "prob-bayes",
                "type": "part_of",
                "weight": 1.0,
            }
        )
        graph = load_curriculum(raw)  # must NOT raise
        assert len(graph.part_of_edges) == 1
        assert len(graph.prerequisite_edges) == 35


class TestStructuralIntegrity:
    def test_duplicate_node_id_is_rejected(self, raw):
        raw["nodes"].append(copy.deepcopy(_node(raw, "prob-bayes")))
        with pytest.raises(CurriculumValidationError, match="duplicate node_id"):
            load_curriculum(raw)

    def test_self_loop_is_rejected(self, raw):
        raw["edges"].append(
            {
                "from_node_id": "prob-bayes",
                "to_node_id": "prob-bayes",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CurriculumValidationError, match="self-loop"):
            load_curriculum(raw)

    def test_duplicate_edge_is_rejected(self, raw):
        raw["edges"].append(copy.deepcopy(raw["edges"][0]))
        with pytest.raises(CurriculumValidationError, match="duplicate edge"):
            load_curriculum(raw)

    def test_unknown_role_on_a_node_is_rejected(self, raw):
        _node(raw, "prob-bayes")["roles"].append(
            {"role_id": "astronaut", "importance": 0.9, "required_depth": "deep"}
        )
        with pytest.raises(CurriculumValidationError, match="astronaut"):
            load_curriculum(raw)

    def test_same_role_tagged_twice_is_rejected(self, raw):
        node = _node(raw, "prob-bayes")
        node["roles"].append(copy.deepcopy(node["roles"][0]))
        with pytest.raises(CurriculumValidationError, match="tagged more than once"):
            load_curriculum(raw)

    def test_duplicate_concept_name_is_rejected(self, raw):
        """A.5.4: a shared concept is ONE node with several role tags, never two nodes."""
        clone = copy.deepcopy(_node(raw, "prob-bayes"))
        clone["node_id"] = "fq-bayes-theorem"
        clone["section"] = "finance-quant"
        raw["nodes"].append(clone)
        with pytest.raises(CurriculumValidationError, match="duplicate concept name"):
            load_curriculum(raw)

    def test_duplicate_priority_rank_is_rejected(self, raw):
        raw["roles"][1]["priority_rank"] = raw["roles"][0]["priority_rank"]
        with pytest.raises(CurriculumValidationError, match="duplicate priority_rank"):
            load_curriculum(raw)


class TestErrorReporting:
    def test_all_problems_are_reported_not_just_the_first(self, raw):
        raw["nodes"].append(copy.deepcopy(_node(raw, "prob-bayes")))
        raw["edges"].append(
            {
                "from_node_id": "ghost-a",
                "to_node_id": "ghost-b",
                "type": "prerequisite",
                "weight": 1.0,
            }
        )
        with pytest.raises(CurriculumValidationError) as exc:
            load_curriculum(raw)
        assert len(exc.value.problems) >= 3  # dup id + two missing endpoints

    def test_out_of_range_weight_names_the_edge(self, raw):
        raw["edges"][0]["weight"] = 4.2
        with pytest.raises(CurriculumValidationError) as exc:
            load_curriculum(raw)
        assert "weight" in str(exc.value)

    @pytest.mark.parametrize("key", ["roles", "nodes", "edges"])
    def test_missing_top_level_key_is_reported(self, raw, key):
        del raw[key]
        with pytest.raises(CurriculumValidationError, match=key):
            load_curriculum(raw)

    def test_missing_file_is_reported_clearly(self, tmp_path):
        with pytest.raises(CurriculumValidationError, match="not found"):
            load_curriculum(tmp_path / "nope.json")

    def test_malformed_json_is_reported_clearly(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(CurriculumValidationError, match="not valid JSON"):
            load_curriculum(bad)
