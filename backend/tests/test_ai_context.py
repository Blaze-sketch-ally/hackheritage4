"""Tests for the Phase 2 AI context/tools layer: app.ai.context and
app.ai.tools.* (the read-only data layer future agents will call).

No live Supabase project, Groq credentials, or network access anywhere
in this file. Two test styles, matching this project's own convention
(see tests/test_student_portfolio.py's module docstring):
  - "Composer" tests mock each app.ai.tools function directly to verify
    app.ai.context.build_student_career_context assembles them
    correctly and calls each exactly once (no N+1, no repeated calls).
  - "Tool" tests drive individual tool functions with either a
    MagicMock Supabase client (for the few tools with real query-shaping
    logic of their own) or a mocked underlying app.services function
    (for tools that are thin wrappers over an existing service).
"""

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.ai import context
from app.ai.schemas.student_context import (
    ApplicationHistorySummary,
    AssessmentSummary,
    PortfolioSection,
    SkillGapSection,
    StudentBasicInfo,
    StudentCareerContext,
)
from app.ai.tools import (
    assessment_tools,
    learning_tools,
    opportunity_tools,
    portfolio_tools,
    skill_gap_tools,
    skill_tools,
    student_tools,
)
from app.schemas.skill_gap import AnalysisMode, PersonalSkillCounts, SkillGapPersonalResponse
from app.services import (
    assessment_service,
    skill_gap_service,
    student_learning_service,
    student_opportunity_service,
    student_portfolio_service,
    student_recommendation_service,
)

_SID = "11111111-1111-1111-1111-111111111111"
_SKILL_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_SKILL_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _fluent(final_data):
    """Same helper as tests/test_student_portfolio.py: a MagicMock whose
    chain methods all return itself, ending in .execute().data."""
    q = MagicMock()
    for m in ("select", "eq", "in_", "order", "maybe_single", "insert", "update", "delete"):
        getattr(q, m).return_value = q
    q.execute.return_value.data = final_data
    return q


def _fake_personal_skill_gap():
    return SkillGapPersonalResponse(
        mode=AnalysisMode.PERSONAL,
        counts=PersonalSkillCounts(
            total_active_skills=0,
            verified_skills=0,
            unverified_skills=0,
            beginner_skills=0,
            intermediate_skills=0,
            advanced_skills=0,
            expert_skills=0,
        ),
        progressable_skills=[],
        recommendations=[],
        prerequisite_gaps=[],
    )


# ============================================================
# Composer: app.ai.context.build_student_career_context
# ============================================================


def _patched_tools(**overrides):
    """Patch every app.ai.tools function context.py calls, with sensible
    empty-but-valid defaults, overridable per test."""
    defaults = {
        "basic_info": StudentBasicInfo(student_id=_SID),
        "target_job_role": None,
        "skills": [],
        "assessment_summary": AssessmentSummary(
            total_attempts=0, completed_attempts=0, passed_attempts=0, verified_skill_count=0
        ),
        "skill_gap": SkillGapSection(
            mode=AnalysisMode.PERSONAL, personal_analysis=_fake_personal_skill_gap()
        ),
        "portfolio": PortfolioSection(),
        "learning_progress": [],
        "application_history": ApplicationHistorySummary(total_applications=0, by_status={}),
        "recommended_opportunities": [],
    }
    defaults.update(overrides)
    return defaults


def test_build_student_career_context_calls_each_tool_exactly_once():
    values = _patched_tools()
    with (
        patch.object(student_tools, "get_student_basic_info", return_value=values["basic_info"]) as m1,
        patch.object(skill_tools, "get_target_job_role", return_value=values["target_job_role"]) as m2,
        patch.object(skill_tools, "get_student_skills", return_value=values["skills"]) as m3,
        patch.object(
            assessment_tools, "get_assessment_summary", return_value=values["assessment_summary"]
        ) as m4,
        patch.object(skill_gap_tools, "get_current_skill_gap", return_value=values["skill_gap"]) as m5,
        patch.object(portfolio_tools, "get_student_portfolio", return_value=values["portfolio"]) as m6,
        patch.object(
            learning_tools, "get_learning_progress", return_value=values["learning_progress"]
        ) as m7,
        patch.object(
            opportunity_tools,
            "get_application_history",
            return_value=values["application_history"],
        ) as m8,
        patch.object(
            opportunity_tools,
            "get_recommended_opportunities",
            return_value=values["recommended_opportunities"],
        ) as m9,
    ):
        result = context.build_student_career_context(MagicMock(), _SID)

    assert isinstance(result, StudentCareerContext)
    assert result.student_id == _SID
    for mock in (m1, m2, m3, m4, m5, m6, m7, m8, m9):
        mock.assert_called_once()


def test_build_student_career_context_works_with_empty_optional_sections():
    """A brand-new student: no target role, no skills, no assessment
    history, no portfolio, no learning progress, no applications. The
    builder must still return a valid, complete StudentCareerContext --
    never raise just because everything is empty."""
    values = _patched_tools()
    with (
        patch.object(student_tools, "get_student_basic_info", return_value=values["basic_info"]),
        patch.object(skill_tools, "get_target_job_role", return_value=None),
        patch.object(skill_tools, "get_student_skills", return_value=[]),
        patch.object(
            assessment_tools, "get_assessment_summary", return_value=values["assessment_summary"]
        ),
        patch.object(skill_gap_tools, "get_current_skill_gap", return_value=values["skill_gap"]),
        patch.object(portfolio_tools, "get_student_portfolio", return_value=PortfolioSection()),
        patch.object(learning_tools, "get_learning_progress", return_value=[]),
        patch.object(
            opportunity_tools,
            "get_application_history",
            return_value=values["application_history"],
        ),
        patch.object(opportunity_tools, "get_recommended_opportunities", return_value=[]),
    ):
        result = context.build_student_career_context(MagicMock(), _SID)

    assert result.target_job_role is None
    assert result.skills == []
    assert result.assessment_summary.total_attempts == 0
    assert result.skill_gap.mode == AnalysisMode.PERSONAL
    assert result.portfolio.projects == []
    assert result.learning_progress == []
    assert result.application_history.total_applications == 0
    assert result.recommended_opportunities == []


def test_get_student_context_is_the_same_function_as_build_student_career_context():
    """The Phase 2 brief's suggested tool name is a genuine alias, not a
    second implementation."""
    assert context.get_student_context is context.build_student_career_context


# ============================================================
# Tool: skill_tools -- verified/unverified preservation
# ============================================================


def _skill_row(skill_id, name, level, verified, verified_at=None):
    return {
        "skill_id": skill_id,
        "proficiency_level": level,
        "is_verified": verified,
        "verified_at": verified_at,
        "skill": {"name": name, "category": {"name": "Programming"}},
    }


def test_get_student_skills_preserves_verification_fields_accurately():
    rows = [
        _skill_row(_SKILL_A, "Python", "Advanced", True, "2026-01-01T00:00:00Z"),
        _skill_row(_SKILL_B, "SQL", "Beginner", False, None),
    ]
    supabase = MagicMock()
    supabase.table.return_value = _fluent(rows)

    skills = skill_tools.get_student_skills(supabase, _SID)

    assert len(skills) == 2
    by_name = {s.skill_name: s for s in skills}
    assert by_name["Python"].is_verified is True
    assert by_name["Python"].verified_at == "2026-01-01T00:00:00Z"
    assert by_name["SQL"].is_verified is False
    assert by_name["SQL"].verified_at is None


def test_get_verified_skills_returns_only_the_verified_subset():
    rows = [
        _skill_row(_SKILL_A, "Python", "Advanced", True, "2026-01-01T00:00:00Z"),
        _skill_row(_SKILL_B, "SQL", "Beginner", False, None),
    ]
    supabase = MagicMock()
    supabase.table.return_value = _fluent(rows)

    verified = skill_tools.get_verified_skills(supabase, _SID)

    assert len(verified) == 1
    assert verified[0].skill_name == "Python"
    assert verified[0].is_verified is True


def test_get_target_job_role_none_when_unset():
    supabase = MagicMock()
    with patch.object(skill_gap_service, "get_target_job_role", return_value=None):
        assert skill_tools.get_target_job_role(supabase, _SID) is None


# ============================================================
# Tool: skill_gap_tools -- the deterministic result is reused, not
# recomputed differently
# ============================================================


def test_get_current_skill_gap_personal_mode_reuses_service_output_verbatim():
    fake_analysis = {
        "counts": {
            "total_active_skills": 3,
            "verified_skills": 1,
            "unverified_skills": 2,
            "beginner_skills": 1,
            "intermediate_skills": 1,
            "advanced_skills": 1,
            "expert_skills": 0,
        },
        "progressable_skills": [],
        "recommendations": [],
        "prerequisite_gaps": [],
    }
    supabase = MagicMock()
    with (
        patch.object(skill_gap_service, "get_target_job_role", return_value=None),
        patch.object(skill_gap_service, "compute_personal_analysis", return_value=fake_analysis) as mock_compute,
    ):
        section = skill_gap_tools.get_current_skill_gap(supabase, _SID)

    mock_compute.assert_called_once_with(supabase, _SID)
    assert section.mode == AnalysisMode.PERSONAL
    assert section.personal_analysis.counts.total_active_skills == 3
    assert section.personal_analysis.counts.verified_skills == 1
    assert section.job_role_analysis is None


def test_get_current_skill_gap_job_role_mode_reuses_service_output_verbatim():
    job_role = {
        "id": _SKILL_A,
        "name": "Backend Developer",
        "description": None,
        "category": "Engineering",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    target = {
        "id": _SKILL_B,
        "job_role": job_role,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    fake_gap = {
        "readiness_percentage": 42,
        "summary": {"matched": 1, "needs_improvement": 1, "missing": 1, "unverified": 0},
        "skills": [],
        "recommendations": [],
    }
    supabase = MagicMock()
    with (
        patch.object(skill_gap_service, "get_target_job_role", return_value=target),
        patch.object(skill_gap_service, "get_job_role_requirements", return_value=[]),
        patch.object(skill_gap_service, "compute_job_role_gap", return_value=fake_gap) as mock_compute,
    ):
        section = skill_gap_tools.get_current_skill_gap(supabase, _SID)

    mock_compute.assert_called_once()
    assert section.mode == AnalysisMode.JOB_ROLE
    # The exact readiness_percentage the service computed, untouched.
    assert section.job_role_analysis.readiness_percentage == 42
    assert section.personal_analysis is None


# ============================================================
# Tool: student_tools -- basic info, empty-state handling
# ============================================================


def test_get_student_basic_info_handles_no_student_profiles_row():
    """A student who has never saved their profile: student_profiles
    has no row yet. Must return career fields as None/[], not raise."""
    supabase = MagicMock()
    profiles_q = _fluent({"email": "ada@example.com", "full_name": "Ada Lovelace"})
    student_profiles_q = _fluent(None)
    supabase.table.side_effect = lambda name: {
        "profiles": profiles_q,
        "student_profiles": student_profiles_q,
    }[name]

    info = student_tools.get_student_basic_info(supabase, _SID)

    assert info.full_name == "Ada Lovelace"
    assert info.email == "ada@example.com"
    assert info.degree is None
    assert info.preferred_roles == []
    assert info.preferred_locations == []


def test_get_student_basic_info_with_full_student_profile():
    supabase = MagicMock()
    profiles_q = _fluent({"email": "ada@example.com", "full_name": "Ada Lovelace"})
    student_profiles_q = _fluent(
        {
            "degree": "B.Tech",
            "graduation_year": 2027,
            "institution_name": "Example University",
            "career_goals": "Become a backend engineer",
            "preferred_roles": ["Backend Developer"],
            "preferred_locations": ["Remote"],
        }
    )
    supabase.table.side_effect = lambda name: {
        "profiles": profiles_q,
        "student_profiles": student_profiles_q,
    }[name]

    info = student_tools.get_student_basic_info(supabase, _SID)

    assert info.degree == "B.Tech"
    assert info.graduation_year == 2027
    assert info.preferred_roles == ["Backend Developer"]
    assert info.preferred_locations == ["Remote"]


# ============================================================
# Tool: assessment_tools -- summary counts over real service output
# ============================================================


def test_get_assessment_summary_counts_and_caches_verification_lookups():
    rows = [
        {
            "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "status": "COMPLETED",
            "started_at": "2026-01-01T00:00:00Z",
            "submitted_at": "2026-01-01T00:10:00Z",
            "score": "8",
            "total_marks": "10",
            "percentage": "80.00",
            "assessment": {
                "id": _SKILL_A,
                "skill_id": _SKILL_A,
                "title": "Python Basics",
                "description": None,
                "difficulty": "Beginner",
                "duration_minutes": 30,
                "question_count": 10,
                "passing_percentage": "60.00",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        },
        {
            "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "status": "COMPLETED",
            "started_at": "2026-01-02T00:00:00Z",
            "submitted_at": "2026-01-02T00:10:00Z",
            "score": "3",
            "total_marks": "10",
            "percentage": "30.00",
            "assessment": {
                "id": _SKILL_A,
                "skill_id": _SKILL_A,
                "title": "Python Basics",
                "description": None,
                "difficulty": "Beginner",
                "duration_minutes": 30,
                "question_count": 10,
                "passing_percentage": "60.00",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        },
    ]
    supabase = MagicMock()
    with (
        patch.object(assessment_service, "list_own_attempts", return_value=rows),
        patch.object(assessment_service, "get_skill_verification", return_value=True) as mock_verify,
    ):
        summary = assessment_tools.get_assessment_summary(supabase, _SID)

    assert summary.total_attempts == 2
    assert summary.completed_attempts == 2
    assert summary.passed_attempts == 1
    assert summary.verified_skill_count == 1
    # Same (skill_id, difficulty) pair on both rows -> looked up once, not
    # twice (matches app.api.attempts.list_history's own caching).
    mock_verify.assert_called_once()


def test_get_assessment_summary_empty_history_is_not_an_error():
    supabase = MagicMock()
    with patch.object(assessment_service, "list_own_attempts", return_value=[]):
        summary = assessment_tools.get_assessment_summary(supabase, _SID)

    assert summary.total_attempts == 0
    assert summary.recent_attempts == []


# ============================================================
# Tool: portfolio_tools / learning_tools -- thin wrappers
# ============================================================


def test_get_student_portfolio_wraps_existing_service_output():
    fake_portfolio = {"projects": [], "certifications": [], "achievements": [], "skills": []}
    supabase = MagicMock()
    with patch.object(student_portfolio_service, "get_portfolio", return_value=fake_portfolio) as mock:
        section = portfolio_tools.get_student_portfolio(supabase, _SID)

    mock.assert_called_once_with(supabase, _SID)
    assert section.projects == []
    assert section.certifications == []
    assert section.achievements == []


def test_get_learning_progress_wraps_existing_service_output():
    supabase = MagicMock()
    with patch.object(student_learning_service, "list_my_progress", return_value=[]) as mock:
        progress = learning_tools.get_learning_progress(supabase, _SID)

    mock.assert_called_once_with(supabase, _SID)
    assert progress == []


# ============================================================
# Tool: opportunity_tools
# ============================================================


def test_get_application_history_empty_is_not_an_error():
    supabase = MagicMock()
    with patch.object(student_opportunity_service, "list_my_applications", return_value=[]):
        summary = opportunity_tools.get_application_history(supabase, _SID)

    assert summary.total_applications == 0
    assert summary.by_status == {}
    assert summary.recent_applications == []


def test_get_application_history_groups_by_status():
    rows = [
        {"id": "app-1", "student_id": _SID, "opportunity_type": "INTERNSHIP", "status": "APPLIED"},
        {"id": "app-2", "student_id": _SID, "opportunity_type": "JOB", "status": "APPLIED"},
        {"id": "app-3", "student_id": _SID, "opportunity_type": "JOB", "status": "SELECTED"},
    ]
    supabase = MagicMock()
    with patch.object(student_opportunity_service, "list_my_applications", return_value=rows):
        summary = opportunity_tools.get_application_history(supabase, _SID)

    assert summary.total_applications == 3
    assert summary.by_status == {"APPLIED": 2, "SELECTED": 1}


def test_get_recommended_opportunities_wraps_existing_service_output():
    supabase = MagicMock()
    with patch.object(
        student_recommendation_service, "recommend_opportunities", return_value=[]
    ) as mock:
        result = opportunity_tools.get_recommended_opportunities(supabase, _SID)

    mock.assert_called_once_with(supabase, _SID, limit=None)
    assert result == []


def test_get_opportunity_match_returns_none_when_opportunity_not_found():
    supabase = MagicMock()
    with patch.object(student_opportunity_service, "get_opportunity", return_value=None):
        result = opportunity_tools.get_opportunity_match(supabase, _SID, "internship_missing")

    assert result is None


def test_get_opportunity_match_returns_none_on_invalid_id():
    supabase = MagicMock()
    with patch.object(
        student_opportunity_service,
        "get_opportunity",
        side_effect=student_opportunity_service.InvalidOpportunityIdError("bad id"),
    ):
        result = opportunity_tools.get_opportunity_match(supabase, _SID, "not-a-real-id")

    assert result is None


# ============================================================
# Static guarantees: no service_role, no mutation, anywhere in app.ai
# (excluding client.py/config.py/exceptions.py, which are Phase 1 and
# legitimately construct their own Groq client -- not a Supabase concern)
# ============================================================

_AI_PACKAGE_DIR = Path(inspect.getfile(context)).parent
_READ_ONLY_SOURCE_FILES = [
    _AI_PACKAGE_DIR / "context.py",
    # __init__.py is excluded: it is documentation only (explains the
    # package's own no-service_role/no-mutation guarantees in prose,
    # which would otherwise false-positive this exact scan).
    *sorted(p for p in (_AI_PACKAGE_DIR / "tools").glob("*.py") if p.name != "__init__.py"),
]


def test_no_tool_or_context_module_uses_service_role():
    """app.ai.tools/context must never bypass RLS via get_supabase()
    (service_role) -- every read stays scoped to the caller's own
    user-scoped client, passed in as `client`."""
    offenders = []
    for path in _READ_ONLY_SOURCE_FILES:
        text = path.read_text(encoding="utf-8")
        if "get_supabase" in text:
            offenders.append(str(path))
    assert offenders == [], f"service_role usage found in: {offenders}"


def test_no_tool_or_context_module_has_a_mutation_path():
    """Phase 2 is read-only from the AI perspective: no insert/update/
    delete/upsert call anywhere in app.ai.context or app.ai.tools."""
    mutation_calls = (".insert(", ".update(", ".delete(", ".upsert(")
    offenders = []
    for path in _READ_ONLY_SOURCE_FILES:
        text = path.read_text(encoding="utf-8")
        if any(call in text for call in mutation_calls):
            offenders.append(str(path))
    assert offenders == [], f"mutation call found in: {offenders}"
