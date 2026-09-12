"""Tests for the Skill Gap Analysis Agent orchestrator
(app.ai.agents.skill_gap_agent).

No live Supabase project, Groq credentials, or network access -- every
Phase 2 tool and the Phase 1 Groq client are mocked directly. These
tests exercise the FULL pipeline (canonical data -> minimal input ->
mocked structured LLM output -> grounding) except the actual network
call, which is exactly what Phase 1's own tests already cover.
"""

import inspect
import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents import skill_gap_agent
from app.ai.client import groq_client
from app.ai.schemas.skill_gap import (
    SkillGapAgentResponse,
    SkillGapLLMOutput,
)
from app.ai.schemas.student_context import (
    AssessmentSummary,
    PortfolioSection,
    SkillGapSection,
    StudentSkillSummary,
)
from app.ai.tools import assessment_tools, portfolio_tools, skill_gap_tools, skill_tools
from app.schemas.assessment import AssessmentResponse, AttemptHistoryItemResponse, Difficulty
from app.schemas.skill_gap import (
    AnalysisMode,
    GapStatus,
    Importance,
    JobRoleResponse,
    PersonalSkillCounts,
    Priority,
    ProgressableSkill,
    Recommendation,
    SkillGapItem,
    SkillGapJobRoleResponse,
    SkillGapPersonalResponse,
    SkillGapSummary,
    VerificationStatus,
)
from app.schemas.student_portfolio import ProjectResponse, ProjectSkillRef

_SID = "student-1"
_PYTHON_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_SQL_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_ROLE_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _job_role():
    return JobRoleResponse(
        id=_ROLE_ID,
        name="Backend Developer",
        description=None,
        category="Engineering",
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _job_role_section():
    return SkillGapSection(
        mode=AnalysisMode.JOB_ROLE,
        job_role_analysis=SkillGapJobRoleResponse(
            mode=AnalysisMode.JOB_ROLE,
            job_role=_job_role(),
            readiness_percentage=21,
            summary=SkillGapSummary(matched=1, needs_improvement=1, missing=1, unverified=0),
            skills=[
                SkillGapItem(
                    skill_id=_PYTHON_ID,
                    skill_name="Python",
                    current_level=None,
                    required_level=Difficulty.ADVANCED,
                    gap=3,
                    status=GapStatus.MISSING,
                    verification_status=VerificationStatus.UNVERIFIED,
                    importance=Importance.CORE,
                    priority=Priority.HIGH,
                    assessment_available=True,
                    assessment_id=None,
                ),
                SkillGapItem(
                    skill_id=_SQL_ID,
                    skill_name="SQL",
                    current_level=Difficulty.INTERMEDIATE,
                    required_level=Difficulty.INTERMEDIATE,
                    gap=0,
                    status=GapStatus.MATCHED,
                    verification_status=VerificationStatus.VERIFIED,
                    importance=Importance.IMPORTANT,
                    priority=Priority.LOW,
                    assessment_available=True,
                    assessment_id=None,
                ),
            ],
            recommendations=[],
        ),
    )


def _personal_section(recommendations=None, progressable=None):
    return SkillGapSection(
        mode=AnalysisMode.PERSONAL,
        personal_analysis=SkillGapPersonalResponse(
            mode=AnalysisMode.PERSONAL,
            counts=PersonalSkillCounts(
                total_active_skills=1,
                verified_skills=0,
                unverified_skills=1,
                beginner_skills=1,
                intermediate_skills=0,
                advanced_skills=0,
                expert_skills=0,
            ),
            progressable_skills=progressable or [],
            recommendations=recommendations or [],
            prerequisite_gaps=[],
        ),
    )


def _empty_llm_output(summary="A generated summary grounded in the supplied data."):
    return SkillGapLLMOutput(summary=summary)


@contextmanager
def _mock_tools(
    section,
    owned_skills=None,
    portfolio=None,
    assessment_summary=None,
    availability=None,
):
    """Patches every Phase 2 tool the agent calls. Yields nothing --
    used as `with _mock_tools(...), patch.object(groq_client, ...):`."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(assessment_tools, "get_assessment_availability", return_value=availability or {}))
        stack.enter_context(
            patch.object(skill_gap_tools, "get_current_skill_gap", return_value=section)
        )
        stack.enter_context(
            patch.object(skill_tools, "get_student_skills", return_value=owned_skills or [])
        )
        stack.enter_context(
            patch.object(
                portfolio_tools, "get_student_portfolio", return_value=portfolio or PortfolioSection()
            )
        )
        stack.enter_context(
            patch.object(
                assessment_tools,
                "get_assessment_summary",
                return_value=assessment_summary
                or AssessmentSummary(
                    total_attempts=0, completed_attempts=0, passed_attempts=0, verified_skill_count=0
                ),
            )
        )
        yield


# ============================================================
# A. Agent behavior
# ============================================================


def test_valid_grounded_response_job_role_mode():
    section = _job_role_section()
    llm_output = SkillGapLLMOutput(
        summary="Python is the main gap for this role.",
        strengths=["SQL is already matched at the required level."],
        priority_gap_reasons=["G1: Focused practice may help."],
        priority_gap_actions=["G1: Start learning."],
    )
    with (
        _mock_tools(section),
        patch.object(groq_client, "complete_structured", return_value=llm_output) as mock_llm,
    ):
        result = skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    assert isinstance(result, SkillGapAgentResponse)
    # Canonical fields come from the section, untouched by the LLM.
    assert result.canonical.readiness_score == 21
    assert result.canonical.target_role == "Backend Developer"
    assert result.canonical.matched_count == 1
    assert result.canonical.missing_count == 1
    # The one grounded priority gap, with server-attached canonical facts.
    assert len(result.analysis.priority_gaps) == 1
    gap = result.analysis.priority_gaps[0]
    assert gap.skill_id == _PYTHON_ID
    assert gap.canonical_status == "MISSING"
    assert gap.canonical_priority == "HIGH"
    assert gap.canonical_importance == "CORE"
    mock_llm.assert_called_once()


def test_readiness_score_is_identical_regardless_of_llm_content():
    """However garbage-but-valid the LLM's free text is, canonical.readiness_score
    is always exactly skill_gap_service's own number."""
    section = _job_role_section()
    with (
        _mock_tools(section),
        patch.object(
            groq_client, "complete_structured", return_value=_empty_llm_output("irrelevant text")
        ),
    ):
        result = skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    assert result.canonical.readiness_score == 21


def test_minimal_input_excludes_application_history_and_recommended_opportunities():
    """The agent must never touch opportunity/learning tools -- see the
    Phase 3 brief's minimal-input requirement. Verified structurally:
    the agent module's source never imports them."""
    source = Path(inspect.getfile(skill_gap_agent)).read_text(encoding="utf-8")
    assert "opportunity_tools" not in source
    assert "learning_tools" not in source
    assert "student_tools" not in source


def test_portfolio_evidence_is_included_in_the_prompt_sent_to_groq():
    section = _job_role_section()
    portfolio = PortfolioSection(
        projects=[
            ProjectResponse(
                id="p1",
                title="Student Performance Predictor",
                skills=[ProjectSkillRef(skill_id=_PYTHON_ID, skill_name="Python")],
            )
        ]
    )
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return _empty_llm_output()

    with (
        _mock_tools(section, portfolio=portfolio),
        patch.object(groq_client, "complete_structured", side_effect=_capture),
    ):
        skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    assert "Student Performance Predictor" in captured["user"]


def test_only_relevant_assessment_evidence_is_included():
    """An attempt at a skill NOT in the current gap set is excluded --
    only gap-relevant assessment history is passed to the LLM."""
    section = _job_role_section()
    relevant_assessment = AssessmentResponse(
        id=_PYTHON_ID,
        skill_id=_PYTHON_ID,
        title="Python Basics",
        description=None,
        difficulty=Difficulty.BEGINNER,
        duration_minutes=30,
        question_count=10,
        passing_percentage="60.00",
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    unrelated_assessment = AssessmentResponse(
        id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        skill_id="99999999-9999-9999-9999-999999999999",
        title="Unrelated Skill",
        description=None,
        difficulty=Difficulty.BEGINNER,
        duration_minutes=30,
        question_count=10,
        passing_percentage="60.00",
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    assessment_summary = AssessmentSummary(
        total_attempts=2,
        completed_attempts=2,
        passed_attempts=1,
        verified_skill_count=0,
        recent_attempts=[
            AttemptHistoryItemResponse(
                id="dddddddd-dddd-dddd-dddd-dddddddddddd",
                status="COMPLETED",
                started_at="2026-01-01T00:00:00Z",
                submitted_at="2026-01-01T00:10:00Z",
                score="4",
                total_marks="10",
                percentage="40.00",
                passed=False,
                skill_verified=False,
                assessment=relevant_assessment,
            ),
            AttemptHistoryItemResponse(
                id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                status="COMPLETED",
                started_at="2026-01-02T00:00:00Z",
                submitted_at="2026-01-02T00:10:00Z",
                score="9",
                total_marks="10",
                percentage="90.00",
                passed=True,
                skill_verified=True,
                assessment=unrelated_assessment,
            ),
        ],
    )
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        return _empty_llm_output()

    with (
        _mock_tools(section, assessment_summary=assessment_summary),
        patch.object(groq_client, "complete_structured", side_effect=_capture),
    ):
        skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    assert '"skill_name": "Python"' in captured["user"]
    assert "Unrelated Skill" not in captured["user"]


# ============================================================
# C. Empty states / personal mode
# ============================================================


def test_no_target_role_and_no_skills_at_all_skips_groq_entirely():
    section = _personal_section()  # no recommendations, no progressable skills
    with (
        _mock_tools(section, owned_skills=[]),
        patch.object(groq_client, "complete_structured") as mock_llm,
    ):
        result = skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    mock_llm.assert_not_called()
    assert result.canonical.mode == AnalysisMode.PERSONAL
    assert "Add some skills" in result.analysis.summary


def test_personal_mode_with_recommendations_calls_groq_and_grounds():
    recommendation = Recommendation(
        skill_id=_PYTHON_ID,
        skill_name="Python",
        reason="A natural next step.",
        current_level=None,
        target_level=Difficulty.BEGINNER,
        gap=None,
        priority=Priority.MEDIUM,
        relationship_type="NEXT_STEP",
        is_missing=True,
        is_verified=False,
        assessment_available=True,
        assessment_id=None,
    )
    section = _personal_section(recommendations=[recommendation])
    llm_output = SkillGapLLMOutput(
        summary="Python is a good next skill to learn.",
        priority_gap_reasons=["G1: Natural next step."],
        priority_gap_actions=["G1: Learn it."],
    )
    with (
        _mock_tools(section),
        patch.object(groq_client, "complete_structured", return_value=llm_output) as mock_llm,
    ):
        result = skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    mock_llm.assert_called_once()
    assert result.canonical.mode == AnalysisMode.PERSONAL
    assert result.canonical.target_role is None
    assert len(result.analysis.priority_gaps) == 1
    assert result.analysis.priority_gaps[0].canonical_importance is None


def test_personal_mode_progressable_skill_grounds_as_take_assessment():
    progressable = ProgressableSkill(
        skill_id=_SQL_ID,
        skill_name="SQL",
        current_level=Difficulty.BEGINNER,
        next_level=Difficulty.INTERMEDIATE,
        assessment_available=True,
        assessment_id=None,
    )
    section = _personal_section(progressable=[progressable])
    owned = [
        StudentSkillSummary(
            skill_id=_SQL_ID, skill_name="SQL", proficiency_level="Beginner", is_verified=False
        )
    ]

    llm_output = SkillGapLLMOutput(
        summary="You can progress your SQL skill.",
        assessment_notes=["G1: Focused practice may help."],
    )
    with (
        _mock_tools(section, owned_skills=owned),
        patch.object(groq_client, "complete_structured", return_value=llm_output),
    ):
        result = skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)

    assert len(result.analysis.assessment_actions) == 1
    action = result.analysis.assessment_actions[0]
    assert action.skill_id == _SQL_ID
    assert action.action.value == "TAKE_ASSESSMENT"


# ============================================================
# D. Provider failures propagate, never swallowed into fake advice
# ============================================================


def test_provider_failure_propagates_unmodified():
    from app.ai.exceptions import AIProviderError

    section = _job_role_section()
    with (
        _mock_tools(section),
        patch.object(groq_client, "complete_structured", side_effect=AIProviderError("down")),
    ):
        try:
            skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)
            raised = False
        except AIProviderError:
            raised = True
    assert raised


# ============================================================
# build_canonical_summary_only -- used by the route's fallback path
# ============================================================


def test_build_canonical_summary_only_never_calls_groq():
    section = _job_role_section()
    with (
        patch.object(skill_gap_tools, "get_current_skill_gap", return_value=section),
        patch.object(groq_client, "complete_structured") as mock_llm,
    ):
        summary = skill_gap_agent.build_canonical_summary_only(MagicMock(), _SID)

    mock_llm.assert_not_called()
    assert summary.readiness_score == 21
    assert summary.target_role == "Backend Developer"


def _synthetic_owned():
    return [StudentSkillSummary(skill_id=_SQL_ID, skill_name="SQL",
                                proficiency_level="Intermediate", is_verified=False)]


def _synthetic_portfolio():
    from app.schemas.student_portfolio import AchievementResponse, CertificationResponse
    return PortfolioSection(
        projects=[ProjectResponse(id="project", title="Synthetic SQL project",
                                  skills=[ProjectSkillRef(skill_id=_SQL_ID, skill_name="SQL")])],
        certifications=[CertificationResponse(id="cert", name="Synthetic course")],
        achievements=[AchievementResponse(id="award", title="Synthetic demo")],
    )


def _synthetic_flat_output():
    return SkillGapLLMOutput(
        summary="Focused practice may help connect these skills.",
        priority_gap_reasons=["G1: Focused practice may build fluency."],
        priority_gap_actions=["G1: Try a small exercise."],
        transferable_skill_notes=["O1 -> G1: Data experience may help."],
        learning_sequence=["G1"],
        portfolio_notes=["P1 -> O1: Suggests exposure only."],
        assessment_notes=["G1: Practice can help preparation.", "O1: Reflect on practice."],
    )


def test_populated_raw_json_through_client_agent_and_api():
    from fastapi.testclient import TestClient

    from app.ai.config import AISettings
    from app.main import app
    from tests.conftest import authenticated_as

    completion = MagicMock()
    completion.choices[0].message.content = _synthetic_flat_output().model_dump_json()
    with (
        _mock_tools(_job_role_section(), owned_skills=_synthetic_owned(),
                    portfolio=_synthetic_portfolio(),
                    availability={(_SQL_ID, "Intermediate"): "assessment"}),
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(groq_client, "_settings", AISettings(groq_api_key="synthetic-test-key")),
        patch.object(groq_client, "_create_completion", return_value=completion) as network,
    ):
        response = TestClient(app).post("/api/v1/ai/skill-gap?student_id=other",
                                       json={"student_id": "other"},
                                       headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    result = SkillGapAgentResponse.model_validate(response.json())
    assert result.canonical.readiness_score == 21
    assert result.analysis.priority_gaps[0].canonical_priority == "HIGH"
    assert result.analysis.transferable_skills[0].from_skill_id == _SQL_ID
    assert result.analysis.portfolio_insights[0].source_title == "Synthetic SQL project"
    assert result.analysis.assessment_actions[1].action.value == "TAKE_ASSESSMENT"
    network.assert_called_once()
    request = network.call_args.kwargs
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True
    payload = json.loads(request["messages"][1]["content"].split("\n\n", 1)[1])
    assert [x["ref"] for x in payload["gap_skills"]] == ["G1", "G2"]
    assert [x["ref"] for x in payload["owned_skills"]] == ["O1"]
    assert [x["ref"] for x in payload["portfolio_items"]] == ["P1", "P2", "P3"]
    assert payload["owned_skills"][0]["assessment_available"] is True
    assert "student_id" not in payload


def test_ref_generation_is_repeatable_and_duplicate_names_do_not_collide():
    owned = _synthetic_owned() + [_synthetic_owned()[0].model_copy(update={"skill_id": "other"})]
    with (_mock_tools(_job_role_section(), owned_skills=owned, portfolio=_synthetic_portfolio()),
          patch.object(groq_client, "complete_structured", return_value=_synthetic_flat_output()) as llm):
        for _ in range(2):
            skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)
    assert llm.call_args_list[0].kwargs == llm.call_args_list[1].kwargs
    payload = json.loads(llm.call_args.kwargs["user"].split("\n\n", 1)[1])
    assert [x["ref"] for x in payload["owned_skills"]] == ["O1", "O2"]
    assert "O1 -> G1" in llm.call_args.kwargs["system"]
    assert "P1 -> G1" in llm.call_args.kwargs["system"]


@pytest.mark.parametrize("verified", [False, True])
def test_personal_progression_preserves_verification_and_null_canonical_fields(verified):
    owned = [StudentSkillSummary(skill_id=_SQL_ID, skill_name="SQL",
                                proficiency_level="Beginner", is_verified=verified)]
    section = _personal_section(progressable=[ProgressableSkill(
        skill_id=_SQL_ID, skill_name="SQL", current_level="Beginner", next_level="Intermediate",
        assessment_available=True, assessment_id=None)])
    output = SkillGapLLMOutput(summary="Practice may help.", learning_sequence=["G1"],
                              priority_gap_reasons=["G1: Practice."],
                              priority_gap_actions=["G1: Try an exercise."],
                              assessment_notes=["G1: Supporting context."])
    with (_mock_tools(section, owned_skills=owned),
          patch.object(groq_client, "complete_structured", return_value=output) as llm):
        result = skill_gap_agent.analyze_student_skill_gap(MagicMock(), _SID)
    payload = json.loads(llm.call_args.kwargs["user"].split("\n\n", 1)[1])
    assert payload["gap_skills"][0]["is_verified"] is verified
    assert payload["gap_skills"][0]["status"] is None
    assert payload["gap_skills"][0]["priority"] is None
    assert result.analysis.priority_gaps[0].canonical_status is None
    assert result.analysis.priority_gaps[0].canonical_priority is None
    assert result.canonical.readiness_score is None
    assert "target role's requirements" not in result.model_dump_json()
    assert "no target role exists" in llm.call_args.kwargs["user"]
    assert result.analysis.assessment_actions[0].action.value == (
        "ALREADY_VERIFIED" if verified else "TAKE_ASSESSMENT")


def test_availability_tool_reuses_canonical_lookup():
    from app.services import skill_gap_service
    client = MagicMock()
    with patch.object(skill_gap_service, "get_assessment_availability",
                      return_value={(_SQL_ID, "Intermediate"): "assessment"}) as lookup:
        result = assessment_tools.get_assessment_availability(client, [_SQL_ID])
    lookup.assert_called_once_with(client, [_SQL_ID])
    assert (_SQL_ID, "Intermediate") in result


@pytest.mark.parametrize("error_type", ["AIConfigurationError", "AIProviderError", "AIStructuredOutputError"])
def test_populated_agent_failure_returns_canonical_fallback(error_type):
    from fastapi.testclient import TestClient

    from app.ai import exceptions
    from app.main import app
    from tests.conftest import authenticated_as
    with (_mock_tools(_job_role_section(), owned_skills=_synthetic_owned()),
          authenticated_as("STUDENT", user_id=_SID),
          patch.object(groq_client, "complete_structured",
                       side_effect=getattr(exceptions, error_type)("private provider detail"))):
        response = TestClient(app).post("/api/v1/ai/skill-gap",
                                       headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert response.json()["ai_available"] is False
    assert response.json()["canonical"]["readiness_score"] == 21
    assert "private provider detail" not in response.text
