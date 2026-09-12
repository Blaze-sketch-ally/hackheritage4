"""Flat output grounding: canonical fields are always server-owned."""

import pytest
from pydantic import ValidationError

from app.ai.client import build_strict_json_schema
from app.ai.guardrails.skill_gap import CanonicalSkillRef, _determine_assessment_action, ground
from app.ai.schemas.skill_gap import SkillGapLLMOutput


@pytest.fixture
def indexes():
    return {
        "gap_index": {
            "G1": CanonicalSkillRef(skill_id="python", skill_name="Python", status="MISSING",
                                    priority="HIGH", importance="CORE", assessment_available=True),
            "G2": CanonicalSkillRef(skill_id="sql", skill_name="SQL", status="MATCHED",
                                    priority="LOW", is_tracked=True, is_verified=True),
        },
        "owned_index": {"O1": CanonicalSkillRef(skill_id="fastapi", skill_name="FastAPI",
                                             is_tracked=True, assessment_available=True)},
        "portfolio_index": {"P1": "Demo project"},
    }


def test_flat_schema_has_no_nested_objects():
    schema = build_strict_json_schema(SkillGapLLMOutput)
    assert "$defs" not in schema
    assert "$ref" not in str(schema)
    assert schema["additionalProperties"] is False
    assert len(schema["properties"]) == 9
    for field in schema["properties"].values():
        assert field["type"] in {"string", "array"}
        if field["type"] == "array":
            assert field["items"]["type"] == "string"


@pytest.mark.parametrize("field", [
    "readiness_score", "matched_count", "missing_count", "is_verified", "proficiency_level",
    "required_level", "status", "priority", "importance", "assessment_available", "action",
    "assessment_result", "canonical_priority", "skill_id",
])
def test_canonical_fields_cannot_be_supplied(field):
    with pytest.raises(ValidationError):
        SkillGapLLMOutput.model_validate({"summary": "s", field: "invented"})


def test_rich_response_attaches_canonical_facts(indexes):
    output = SkillGapLLMOutput(
        summary="Practice may help.",
        priority_gap_reasons=["G1: Build fluency."], priority_gap_actions=["G1: Practice."],
        transferable_skill_notes=["O1 -> G1: Experience may help."],
        learning_sequence=["G1"], portfolio_notes=["P1 -> G1: Exposure only."],
        assessment_notes=["G1: Supporting context.", "O1: More context."],
    )
    result = ground(output, **indexes)
    gap = result.priority_gaps[0]
    assert (gap.skill_id, gap.canonical_status, gap.canonical_priority, gap.canonical_importance) == (
        "python", "MISSING", "HIGH", "CORE")
    assert result.transferable_skills[0].from_skill_id == "fastapi"
    assert result.transferable_skills[0].supports_skill_id == "python"
    assert result.recommended_sequence[0].order == 1
    assert result.portfolio_insights[0].source_title == "Demo project"
    assert result.portfolio_insights[0].related_skill_id == "python"
    assert [a.action.value for a in result.assessment_actions] == [
        "ADD_SKILL_THEN_ASSESS", "TAKE_ASSESSMENT"]


@pytest.mark.parametrize("ref", ["G99", "O1", "P1", "Python", "G2", "G0", "G1 -> O1"])
def test_invalid_or_matched_gap_refs_dropped(indexes, ref):
    output = SkillGapLLMOutput(summary="s", priority_gap_reasons=[f"{ref}: reason"],
                              priority_gap_actions=[f"{ref}: action"], learning_sequence=[ref])
    result = ground(output, **indexes)
    assert result.priority_gaps == []
    assert result.recommended_sequence == []


def test_incomplete_pairs_and_blank_notes_dropped(indexes):
    output = SkillGapLLMOutput(summary="s", priority_gap_reasons=["G1: reason"],
                              priority_gap_actions=["G1:   "], assessment_notes=["O1:   "])
    result = ground(output, **indexes)
    assert result.priority_gaps == result.assessment_actions == []


@pytest.mark.parametrize("line", ["O99 -> G1: e", "G1 -> G2: e", "O1 -> G2: e",
                                  "O1 -> G99: e", "FastAPI -> Python: e", "P1 -> G1: e"])
def test_invalid_transfer_dropped(indexes, line):
    assert ground(SkillGapLLMOutput(summary="s", transferable_skill_notes=[line]),
                  **indexes).transferable_skills == []


def test_matched_gap_can_be_transfer_source(indexes):
    result = ground(SkillGapLLMOutput(summary="s", transferable_skill_notes=["G2 -> G1: May help."]),
                    **indexes)
    assert result.transferable_skills[0].from_skill_id == "sql"


def test_sequence_normalizes_refs_deduplicates_and_reorders(indexes):
    result = ground(SkillGapLLMOutput(summary="s", learning_sequence=["G99", " g1 ", "G1", "G2"]),
                    **indexes)
    assert [(s.order, s.skill_id) for s in result.recommended_sequence] == [(1, "python")]


@pytest.mark.parametrize("tracked,available,verified,expected", [
    (True, True, False, "TAKE_ASSESSMENT"),
    (False, True, False, "ADD_SKILL_THEN_ASSESS"),
    (True, False, False, "NO_ASSESSMENT_AVAILABLE"),
    (False, False, False, "NO_ASSESSMENT_AVAILABLE"),
    (True, True, True, "ALREADY_VERIFIED"),
    (True, False, True, "ALREADY_VERIFIED"),
])
def test_assessment_action_truth_table(tracked, available, verified, expected):
    ref = CanonicalSkillRef(skill_id="s", skill_name="S", is_tracked=tracked,
                            assessment_available=available, is_verified=verified)
    assert _determine_assessment_action(ref).value == expected


def test_assessment_notes_do_not_choose_action_and_unknowns_are_dropped(indexes):
    result = ground(SkillGapLLMOutput(summary="s", assessment_notes=[
        "G1: ALREADY_VERIFIED", "G99: invented", "P1: wrong kind", "G1: duplicate"]), **indexes)
    assert len(result.assessment_actions) == 1
    assert result.assessment_actions[0].action.value == "ADD_SKILL_THEN_ASSESS"


@pytest.mark.parametrize("line", ["P99: n", "P1 -> G99: n", "P1 -> P1: n", "Demo project: n"])
def test_unknown_portfolio_or_skill_ref_dropped(indexes, line):
    assert ground(SkillGapLLMOutput(summary="s", portfolio_notes=[line]),
                  **indexes).portfolio_insights == []


def test_portfolio_without_skill_is_valid(indexes):
    result = ground(SkillGapLLMOutput(summary="s", portfolio_notes=["P1: Exposure only."]), **indexes)
    assert result.portfolio_insights[0].related_skill_id is None


def test_personal_progression_has_no_fabricated_canonical_fields(indexes):
    indexes["gap_index"]["G3"] = CanonicalSkillRef(skill_id="next", skill_name="Next")
    result = ground(SkillGapLLMOutput(summary="s", priority_gap_reasons=["G3: Practice."],
                    priority_gap_actions=["G3: Try an exercise."], learning_sequence=["G3"]), **indexes)
    assert result.priority_gaps[0].canonical_status is None
    assert result.priority_gaps[0].canonical_priority is None
    assert result.recommended_sequence[0].canonical_priority is None
    assert "target role" not in result.recommended_sequence[0].rationale


@pytest.mark.parametrize("field", list(SkillGapLLMOutput.model_fields)[1:])
def test_output_list_caps(field):
    with pytest.raises(ValidationError):
        SkillGapLLMOutput.model_validate({"summary": "s", field: ["G1: note"] * 11})
