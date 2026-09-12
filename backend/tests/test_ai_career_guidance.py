"""Phase 6 offline tests: Career Orchestrator + Career Advisor.

Every provider/network boundary is mocked; no live Groq call, no live
Supabase, no DB write anywhere in this file.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai import exceptions, orchestrator
from app.ai.agents import career_advisor_agent as advisor_agent
from app.ai.client import build_strict_json_schema
from app.ai.exceptions import AIProviderError
from app.ai.guardrails.career_advisor import ground_advisor, ref_namespace
from app.ai.schemas.base import AIResponseMeta
from app.ai.schemas.career_guidance import CareerAdvisorLLMOutput
from app.ai.schemas.course_recommendation import (
    CourseCandidate,
    CourseCanonical,
    CourseRecommendation,
    CourseRecommendationResponse,
    CourseResponseMeta,
    CourseSkill,
)
from app.ai.schemas.opportunity_recommendation import (
    OpportunityCanonical,
    OpportunityRecommendation,
    OpportunityRecommendationMeta,
    OpportunityRecommendationResponse,
)
from app.ai.schemas.skill_gap import (
    AssessmentAction,
    CanonicalSkillGapSummary,
    PriorityGapAnalysis,
    SkillGapAgentResponse,
    SkillGapAnalysis,
)
from app.main import app
from app.schemas.skill_gap import AnalysisMode
from app.schemas.student_opportunity import (
    MatchSkill,
    OpportunityMatchResponse,
    StudentOpportunityDetail,
)
from tests.conftest import authenticated_as

_SID = "authenticated-student"


def skill_gap_response(priority_gaps=None, assessment_actions=None, target_role="Backend Developer",
                        readiness=42, mode=AnalysisMode.JOB_ROLE):
    return SkillGapAgentResponse(
        canonical=CanonicalSkillGapSummary(
            mode=mode, target_role=target_role, readiness_score=readiness,
            matched_count=1, needs_improvement_count=1, missing_count=1, unverified_count=0,
        ),
        analysis=SkillGapAnalysis(
            summary="s", priority_gaps=priority_gaps or [], assessment_actions=assessment_actions or []
        ),
        meta=AIResponseMeta(model="test-model"),
    )


def priority_gap(skill_id="skill-py", skill_name="Python", status="MISSING", priority="HIGH",
                  importance="CORE", reason="Core requirement.", action="Start learning."):
    return PriorityGapAnalysis(
        skill_id=skill_id, skill_name=skill_name, canonical_status=status, canonical_priority=priority,
        canonical_importance=importance, reason=reason, suggested_action=action,
    )


def assessment_action(skill_id="skill-py", skill_name="Python", action="ADD_SKILL_THEN_ASSESS",
                       available=True, note="Context."):
    return AssessmentAction(
        skill_id=skill_id, skill_name=skill_name, action=action, assessment_available=available, note=note
    )


def course_rec(candidate_id="internal:1", title="Python Course", skill_id="skill-py", skill_name="Python"):
    return CourseRecommendation(
        course=CourseCandidate(
            candidate_id=candidate_id, source_type="INTERNAL", title=title,
            url="https://example.org/course", skill_ids=[skill_id], skill_names=[skill_name],
            metadata_source="test fixture",
        ),
        for_skill=CourseSkill(ref="G1", skill_id=skill_id, skill_name=skill_name, priority="HIGH", status="MISSING"),
        reason="Supports Python.", rank=1,
    )


def course_response(recs=None, ai=True, status="AI", message=None):
    return CourseRecommendationResponse(
        canonical=CourseCanonical(mode=AnalysisMode.JOB_ROLE, target_role="Backend Developer", skills_considered=[]),
        recommendations=recs or [],
        learning_plan=[],
        meta=CourseResponseMeta(
            model="test-model", ai_ranking_available=ai, ranking_status=status,
            external_discovery_status="CONFIGURATION_REQUIRED", message=message,
        ),
    )


def opportunity_rec(opp_id="internship_a", title="Backend Intern", score=80, band="STRONG"):
    return OpportunityRecommendation(
        candidate_ref="OP1",
        opportunity=StudentOpportunityDetail(
            id=opp_id, source_type="INTERNSHIP", title=title, description="Build things.",
            status="PUBLISHED", has_applied=False,
        ),
        match=OpportunityMatchResponse(
            opportunity_id=opp_id, score=score, recommendation=band, skill_coverage="1 / 1",
            required_count=1, matched_count=1, needs_improvement_count=0, missing_count=0,
            matched_skills=[MatchSkill(skill_id="skill-py", skill_name="Python", required_level="Advanced",
                                        importance="CORE", candidate_has=True, candidate_level="Intermediate",
                                        candidate_verified=False, status="NEEDS_IMPROVEMENT")],
            needs_improvement_skills=[], missing_skills=[],
        ),
        metadata_source="platform/student_opportunity_service", reason_codes=[], reason="Good fit.", rank=1,
    )


def opportunity_response(recs=None, ai=True, status="AI", message=None):
    return OpportunityRecommendationResponse(
        canonical=OpportunityCanonical(target_role="Backend Developer", candidate_count=len(recs or [])),
        recommendations=recs or [],
        application_order=[],
        meta=OpportunityRecommendationMeta(model="test-model", ai_available=ai, ranking_status=status, message=message),
    )


def flat_advisor_output(headline="Focus on Python before applying broadly.", focus=("G1",), courses=("C1",),
                         opportunities=("OP1",), actions=("G1: LEARN_SKILL", "C1: START_COURSE", "OP1: APPLY_OPPORTUNITY"),
                         sequence=("G1",)):
    return CareerAdvisorLLMOutput(
        headline=headline,
        focus_skill_refs=list(focus),
        course_refs=list(courses),
        opportunity_refs=list(opportunities),
        action_notes=list(actions),
        learning_sequence=list(sequence),
    )


@pytest.fixture
def full_scenario():
    sg = skill_gap_response(
        priority_gaps=[priority_gap()],
        assessment_actions=[assessment_action()],
    )
    course = course_response(recs=[course_rec()])
    opportunity = opportunity_response(recs=[opportunity_rec()])
    return sg, course, opportunity


# ============================================================
# A. Orchestrator
# ============================================================


def test_invokes_all_three_specialists_exactly_once(full_scenario):
    sg, course, opportunity = full_scenario
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg) as m1,
        patch.object(orchestrator, "recommend_courses", return_value=course) as m2,
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity) as m3,
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output()),
    ):
        orchestrator.build_career_guidance(MagicMock(), _SID)
    m1.assert_called_once()
    m2.assert_called_once()
    m3.assert_called_once()


def test_combines_outputs_into_rich_response(full_scenario):
    sg, course, opportunity = full_scenario
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output()),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    assert result.career_summary.target_role == "Backend Developer"
    assert result.career_summary.readiness_score == 42
    assert result.career_summary.headline == "Focus on Python before applying broadly."
    assert len(result.priority_skills) == 1
    assert result.priority_skills[0].skill_id == "skill-py"
    assert result.priority_skills[0].highlighted_by_advisor is True
    assert len(result.learning_recommendations) == 1
    assert result.learning_recommendations[0].course.candidate_id == "internal:1"
    assert len(result.opportunity_recommendations) == 1
    assert result.opportunity_recommendations[0].opportunity.id == "internship_a"
    assert len(result.assessment_recommendations) == 1
    assert len(result.next_actions) == 3
    assert result.meta.ai_available is True


def test_no_duplicate_specialist_calls_while_assembling_one_response(full_scenario):
    """Each specialist must be called exactly once, never re-invoked
    while reconstructing the rich response."""
    sg, course, opportunity = full_scenario
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg) as m1,
        patch.object(orchestrator, "recommend_courses", return_value=course) as m2,
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity) as m3,
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output()) as m4,
    ):
        orchestrator.build_career_guidance(MagicMock(), _SID)
    for mock in (m1, m2, m3, m4):
        assert mock.call_count == 1


def test_partial_failure_course_agent_down_others_survive(full_scenario):
    sg, _, opportunity = full_scenario
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", side_effect=RuntimeError("db exploded")),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output(courses=[])),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    assert result.meta.agents_used.course_agent.available is False
    assert result.learning_recommendations == []
    assert len(result.priority_skills) == 1
    assert len(result.opportunity_recommendations) == 1
    assert result.meta.agents_used.skill_gap_agent.available is True
    assert result.meta.agents_used.opportunity_agent.available is True


def test_all_specialists_unavailable_still_returns_200_shaped_response():
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", side_effect=RuntimeError("down")),
        patch.object(orchestrator, "build_canonical_summary_only", side_effect=RuntimeError("also down")),
        patch.object(orchestrator, "recommend_courses", side_effect=RuntimeError("down")),
        patch.object(orchestrator, "recommend_opportunities", side_effect=RuntimeError("down")),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    assert result.career_summary.target_role is None
    assert result.priority_skills == []
    assert result.learning_recommendations == []
    assert result.opportunity_recommendations == []
    assert result.meta.agents_used.skill_gap_agent.available is False
    assert result.meta.agents_used.course_agent.available is False
    assert result.meta.agents_used.opportunity_agent.available is False
    # The advisor itself never fails here -- it correctly recognizes
    # there is nothing grounded to synthesize and skips Groq entirely,
    # which is a legitimate "available but nothing to do" state, not a
    # provider failure. ai_available (the "did AI synthesis run" flag)
    # is still false either way.
    assert result.meta.agents_used.career_advisor.fallback_used is True
    assert result.meta.ai_available is False


def test_skill_gap_ai_failure_keeps_canonical_summary(full_scenario):
    """Skill Gap Agent's Groq portion fails, but its own canonical
    fallback still succeeds -- readiness/target role must still appear."""
    _, course, opportunity = full_scenario
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", side_effect=exceptions.AIProviderError("down")),
        patch.object(
            orchestrator,
            "build_canonical_summary_only",
            return_value=CanonicalSkillGapSummary(
                mode=AnalysisMode.JOB_ROLE, target_role="Backend Developer", readiness_score=42
            ),
        ),
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    assert result.career_summary.target_role == "Backend Developer"
    assert result.career_summary.readiness_score == 42
    assert result.meta.agents_used.skill_gap_agent.available is True
    assert result.meta.agents_used.skill_gap_agent.fallback_used is True
    assert result.priority_skills == []  # no grounded reasons to show without the AI pass


@pytest.mark.parametrize("failure", ["AIConfigurationError", "AIProviderError", "AIStructuredOutputError"])
def test_advisor_failure_falls_back_to_specialist_data_directly(failure, full_scenario):
    sg, course, opportunity = full_scenario
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(
            advisor_agent.groq_client, "complete_structured",
            side_effect=getattr(exceptions, failure)("private detail"),
        ),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    assert result.meta.ai_available is False
    assert result.meta.agents_used.career_advisor.available is False
    # Deterministic fallback: specialist data survives, ordered by canonical priority.
    assert len(result.priority_skills) == 1
    assert len(result.learning_recommendations) == 1
    assert len(result.opportunity_recommendations) == 1
    assert all(not s.highlighted_by_advisor for s in result.priority_skills)
    assert "private detail" not in result.model_dump_json()


def test_no_target_role_personal_mode_is_honest():
    sg = skill_gap_response(mode=AnalysisMode.PERSONAL, target_role=None, readiness=None)
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course_response()),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity_response()),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    assert result.career_summary.mode == AnalysisMode.PERSONAL
    assert result.career_summary.target_role is None
    assert result.career_summary.readiness_score is None


def test_empty_recommendations_skip_advisor_entirely():
    sg = skill_gap_response(priority_gaps=[], assessment_actions=[])
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course_response(recs=[])),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity_response(recs=[])),
        patch.object(advisor_agent.groq_client, "complete_structured") as llm,
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)

    llm.assert_not_called()
    assert result.priority_skills == []
    assert result.learning_recommendations == []
    assert result.opportunity_recommendations == []
    assert result.meta.agents_used.career_advisor.fallback_used is True


# ============================================================
# B. Advisor grounding
# ============================================================


def _indexes(full_scenario):
    sg, course, opportunity = full_scenario
    agent_input, indexes = advisor_agent.build_advisor_input(
        sg, course, opportunity, target_role="Backend Developer", readiness_score=42, mode=AnalysisMode.JOB_ROLE
    )
    return agent_input, indexes


def test_valid_refs_resolve(full_scenario):
    _, indexes = _indexes(full_scenario)
    output = flat_advisor_output()
    grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                               opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
    assert grounded.focus_skill_refs == ["G1"]
    assert grounded.course_refs == ["C1"]
    assert grounded.opportunity_refs == ["OP1"]
    assert ("G1", "LEARN_SKILL") in grounded.actions


def test_unknown_refs_dropped(full_scenario):
    _, indexes = _indexes(full_scenario)
    output = flat_advisor_output(focus=["G99"], courses=["C99"], opportunities=["OP99"],
                                  actions=["G99: LEARN_SKILL"], sequence=["G99"])
    grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                               opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
    assert grounded.focus_skill_refs == []
    assert grounded.course_refs == []
    assert grounded.opportunity_refs == []
    assert grounded.actions == []
    assert grounded.learning_sequence == []


def test_invented_course_is_impossible(full_scenario):
    """A course_ref not present in the index can never enter the final
    response -- there is no channel for the LLM to smuggle course
    metadata through, since it only ever supplies a bare ref."""
    _, indexes = _indexes(full_scenario)
    output = flat_advisor_output(courses=["C2"])
    grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                               opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
    assert grounded.course_refs == []


def test_invented_opportunity_is_impossible(full_scenario):
    _, indexes = _indexes(full_scenario)
    output = flat_advisor_output(opportunities=["OP2"])
    grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                               opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
    assert grounded.opportunity_refs == []


@pytest.mark.parametrize("field", ["match_score", "readiness_score", "canonical_status", "canonical_priority",
                                    "skill_id", "title", "url", "company", "assessment_available"])
def test_invented_score_or_canonical_field_is_impossible(field):
    """The LLM output schema has no field to carry a score/canonical
    fact at all -- attempting to supply one is a hard schema error."""
    with pytest.raises(ValidationError):
        CareerAdvisorLLMOutput.model_validate({**flat_advisor_output().model_dump(), field: "invented"})


@pytest.mark.parametrize(
    "note",
    [
        "G1: START_COURSE",  # wrong namespace for this code
        "C1: LEARN_SKILL",  # wrong namespace
        "OP1: LEARN_SKILL",  # wrong namespace
        "G1: FREE_LUNCH",  # not a real code
        "G99: LEARN_SKILL",  # unknown ref
    ],
)
def test_invalid_action_code_pairing_rejected(note, full_scenario):
    _, indexes = _indexes(full_scenario)
    output = flat_advisor_output(actions=[note])
    grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                               opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
    assert grounded.actions == []


def test_take_assessment_accepted_when_genuinely_actionable(full_scenario):
    """A1's underlying server-determined action is ADD_SKILL_THEN_ASSESS
    -- genuinely actionable -- so pairing it with TAKE_ASSESSMENT is
    accepted."""
    _, indexes = _indexes(full_scenario)
    output = flat_advisor_output(actions=["A1: TAKE_ASSESSMENT"])
    grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                               opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
    assert grounded.actions == [("A1", "TAKE_ASSESSMENT")]


def test_take_assessment_rejected_when_already_verified_or_unavailable(full_scenario):
    """A skill that is ALREADY_VERIFIED or has NO_ASSESSMENT_AVAILABLE
    is not actionable -- TAKE_ASSESSMENT must be rejected for either,
    even though the ref itself is real."""
    _sg, course, opportunity = full_scenario
    for action_value in ("ALREADY_VERIFIED", "NO_ASSESSMENT_AVAILABLE"):
        not_actionable = skill_gap_response(
            priority_gaps=[priority_gap()],
            assessment_actions=[assessment_action(action=action_value)],
        )
        _, indexes = advisor_agent.build_advisor_input(
            not_actionable, course, opportunity,
            target_role="Backend Developer", readiness_score=42, mode=AnalysisMode.JOB_ROLE,
        )
        output = flat_advisor_output(actions=["A1: TAKE_ASSESSMENT"])
        grounded = ground_advisor(output, skill_index=indexes["skill"], course_index=indexes["course"],
                                   opportunity_index=indexes["opportunity"], assessment_index=indexes["assessment"])
        assert grounded.actions == [], f"should reject for action={action_value}"


def test_ref_namespace_parsing():
    assert ref_namespace("G1") == "G"
    assert ref_namespace("C12") == "C"
    assert ref_namespace("OP3") == "OP"
    assert ref_namespace("A7") == "A"
    assert ref_namespace("XX1") is None
    assert ref_namespace("G") is None


def test_canonical_readiness_unchanged_regardless_of_advisor_output(full_scenario):
    sg, course, opportunity = full_scenario
    garbage = flat_advisor_output(headline="Nonsense text with no bearing on facts.")
    with (
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=garbage),
    ):
        result = orchestrator.build_career_guidance(MagicMock(), _SID)
    assert result.career_summary.readiness_score == 42


def test_llm_output_schema_is_flat_with_no_defs():
    schema = build_strict_json_schema(CareerAdvisorLLMOutput)
    assert "$defs" not in schema
    assert "$ref" not in str(schema)
    assert schema["additionalProperties"] is False
    assert len(schema["properties"]) == 6


# ============================================================
# C. API — POST /api/v1/ai/career-guidance
# ============================================================


def test_api_requires_authentication():
    assert TestClient(app).post("/api/v1/ai/career-guidance").status_code == 401


@pytest.mark.parametrize("role", ["INDUSTRY", "INSTITUTION", "FACULTY", "ADMIN", None])
def test_api_requires_student_role(role):
    with authenticated_as(role):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_api_uses_authenticated_user_id_never_a_supplied_one(full_scenario):
    sg, course, opportunity = full_scenario
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg) as m1,
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output()),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance?student_id=victim",
            json={"student_id": "victim"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert m1.call_args.args[1] == _SID
    assert "victim" not in response.text


def test_api_success(full_scenario):
    sg, course, opportunity = full_scenario
    with (
        authenticated_as("STUDENT"),
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output()),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["career_summary"]["readiness_score"] == 42
    assert len(body["priority_skills"]) == 1
    assert body["meta"]["ai_available"] is True


def test_api_partial_fallback_still_200(full_scenario):
    sg, _, opportunity = full_scenario
    with (
        authenticated_as("STUDENT"),
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", side_effect=RuntimeError("boom")),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(advisor_agent.groq_client, "complete_structured", return_value=flat_advisor_output(courses=[])),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["agents_used"]["course_agent"]["available"] is False
    assert body["learning_recommendations"] == []
    assert len(body["priority_skills"]) == 1


def test_api_full_ai_fallback_still_200_with_canonical_data(full_scenario):
    sg, course, opportunity = full_scenario
    with (
        authenticated_as("STUDENT"),
        patch.object(orchestrator, "analyze_student_skill_gap", return_value=sg),
        patch.object(orchestrator, "recommend_courses", return_value=course),
        patch.object(orchestrator, "recommend_opportunities", return_value=opportunity),
        patch.object(
            advisor_agent.groq_client, "complete_structured",
            side_effect=AIProviderError("gsk_LEAKED_SECRET"),
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["ai_available"] is False
    assert body["career_summary"]["readiness_score"] == 42
    assert "gsk_LEAKED_SECRET" not in response.text


def test_api_never_leaks_raw_provider_error_text():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            orchestrator, "analyze_student_skill_gap",
            side_effect=RuntimeError("internal secret: db-password-xyz"),
        ),
        patch.object(orchestrator, "build_canonical_summary_only", side_effect=RuntimeError("also down")),
        patch.object(orchestrator, "recommend_courses", side_effect=RuntimeError("down")),
        patch.object(orchestrator, "recommend_opportunities", side_effect=RuntimeError("down")),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/career-guidance", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert "db-password-xyz" not in response.text


def test_route_registered_exactly_once_no_doubling():
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/v1/ai/career-guidance" in schema["paths"]
    assert "/api/v1/ai/ai/career-guidance" not in schema["paths"]
    assert list(schema["paths"]["/api/v1/ai/career-guidance"].keys()) == ["post"]
