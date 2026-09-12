"""Tests for the AI router: GET /api/v1/ai/health (Phase 1),
GET /api/v1/ai/context (Phase 2), and POST /api/v1/ai/skill-gap (Phase 3).

No live Supabase project, Groq credentials, or network access -- auth is
mocked via tests.conftest.authenticated_as (see its own docstring), and
AISettings / build_student_career_context / analyze_student_skill_gap
are patched directly rather than touching real environment variables or
Supabase.
"""

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai.exceptions import AIProviderError
from app.ai.schemas.base import AIProvider, AIResponseMeta
from app.ai.schemas.skill_gap import (
    CanonicalSkillGapSummary,
    SkillGapAgentResponse,
    SkillGapAnalysis,
)
from app.ai.schemas.student_context import (
    ApplicationHistorySummary,
    AssessmentSummary,
    PortfolioSection,
    SkillGapSection,
    StudentBasicInfo,
    StudentCareerContext,
)
from app.main import app
from app.schemas.skill_gap import AnalysisMode, PersonalSkillCounts, SkillGapPersonalResponse
from tests.conftest import authenticated_as

client = TestClient(app)

_SID = "11111111-1111-1111-1111-111111111111"


def _fake_context(student_id: str = _SID) -> StudentCareerContext:
    return StudentCareerContext(
        student_id=student_id,
        generated_at=datetime.now(UTC),
        basic_info=StudentBasicInfo(student_id=student_id, full_name="Ada Lovelace"),
        target_job_role=None,
        skills=[],
        assessment_summary=AssessmentSummary(
            total_attempts=0, completed_attempts=0, passed_attempts=0, verified_skill_count=0
        ),
        skill_gap=SkillGapSection(
            mode=AnalysisMode.PERSONAL,
            personal_analysis=SkillGapPersonalResponse(
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
            ),
        ),
        portfolio=PortfolioSection(),
        learning_progress=[],
        application_history=ApplicationHistorySummary(total_applications=0, by_status={}),
        recommended_opportunities=[],
    )


def test_health_requires_authentication():
    response = client.get("/api/v1/ai/health")
    assert response.status_code == 401


def test_health_reports_unconfigured_when_no_api_key():
    with authenticated_as("STUDENT"), patch("app.api.ai.ai_settings") as mock_settings:
        mock_settings.is_configured = False
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        response = client.get(
            "/api/v1/ai/health", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["provider"] == "groq"
    assert body["model"] == "llama-3.3-70b-versatile"


def test_health_reports_configured_when_api_key_present():
    with authenticated_as("STUDENT"), patch("app.api.ai.ai_settings") as mock_settings:
        mock_settings.is_configured = True
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        response = client.get(
            "/api/v1/ai/health", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    assert response.json()["configured"] is True


def test_health_works_for_any_role_not_just_student():
    with authenticated_as("INDUSTRY"), patch("app.api.ai.ai_settings") as mock_settings:
        mock_settings.is_configured = True
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        response = client.get(
            "/api/v1/ai/health", headers={"Authorization": "Bearer valid-token"}
        )
    assert response.status_code == 200


def test_health_response_never_contains_api_key():
    with authenticated_as("STUDENT"), patch("app.api.ai.ai_settings") as mock_settings:
        mock_settings.is_configured = True
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.groq_api_key = "sk-super-secret-value"
        response = client.get(
            "/api/v1/ai/health", headers={"Authorization": "Bearer valid-token"}
        )

    assert "sk-super-secret-value" not in response.text


def test_health_registered_under_api_v1_ai_prefix_not_doubled():
    response = client.get("/api/v1/ai/ai/health")
    assert response.status_code == 404


# ============================================================
# GET /api/v1/ai/context (Phase 2)
# ============================================================


def test_context_requires_authentication():
    response = client.get("/api/v1/ai/context")
    assert response.status_code == 401


def test_context_rejects_non_student_role():
    with authenticated_as("INDUSTRY"):
        response = client.get(
            "/api/v1/ai/context", headers={"Authorization": "Bearer valid-token"}
        )
    assert response.status_code == 403


def test_context_works_for_student_role():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch("app.api.ai.build_student_career_context", return_value=_fake_context()) as mock_build,
    ):
        response = client.get(
            "/api/v1/ai/context", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == _SID
    assert body["basic_info"]["full_name"] == "Ada Lovelace"
    mock_build.assert_called_once()


def test_context_always_uses_authenticated_user_id_not_a_query_param():
    """IDOR guard: the route has no student_id parameter at all, so a
    caller cannot influence whose context is built by passing one --
    the mocked builder must still be called with the AUTHENTICATED
    user's id (_SID), never the id supplied in the query string."""
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.build_student_career_context", return_value=_fake_context()
        ) as mock_build,
    ):
        response = client.get(
            "/api/v1/ai/context?student_id=some-other-student",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    args, _ = mock_build.call_args
    assert args[1] == _SID
    assert "some-other-student" not in str(mock_build.call_args)


def test_context_response_contains_no_secrets():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch("app.api.ai.build_student_career_context", return_value=_fake_context()),
    ):
        response = client.get(
            "/api/v1/ai/context", headers={"Authorization": "Bearer valid-token"}
        )

    assert "gsk_" not in response.text
    assert "service_role" not in response.text.lower()
    assert "groq_api_key" not in response.text.lower()


def test_context_endpoint_never_calls_groq():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch("app.api.ai.build_student_career_context", return_value=_fake_context()),
        patch(
            "app.ai.client.GroqClient._create_completion",
            side_effect=AssertionError("GET /context must never call Groq"),
        ),
    ):
        response = client.get(
            "/api/v1/ai/context", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200


def test_context_build_failure_returns_generic_500_not_a_raw_error():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.build_student_career_context",
            side_effect=RuntimeError("supabase connection refused: internal detail"),
        ),
    ):
        response = client.get(
            "/api/v1/ai/context", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 500
    assert "internal detail" not in response.text
    assert "supabase connection refused" not in response.text


def test_context_registered_exactly_once_no_doubling():
    schema = client.get("/openapi.json").json()
    assert "/api/v1/ai/context" in schema["paths"]
    assert "/api/v1/ai/ai/context" not in schema["paths"]


# ============================================================
# POST /api/v1/ai/skill-gap (Phase 3)
# ============================================================


def _fake_skill_gap_response() -> SkillGapAgentResponse:
    return SkillGapAgentResponse(
        canonical=CanonicalSkillGapSummary(
            mode=AnalysisMode.JOB_ROLE,
            target_role="Backend Developer",
            readiness_score=21,
            matched_count=1,
            needs_improvement_count=1,
            missing_count=1,
            unverified_count=0,
        ),
        analysis=SkillGapAnalysis(summary="Python is your main gap."),
        meta=AIResponseMeta(provider=AIProvider.GROQ, model="openai/gpt-oss-20b"),
    )


def test_skill_gap_requires_authentication():
    response = client.post("/api/v1/ai/skill-gap")
    assert response.status_code == 401


def test_skill_gap_rejects_non_student_role():
    with authenticated_as("INDUSTRY"):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )
    assert response.status_code == 403


def test_skill_gap_works_for_student_role():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.analyze_student_skill_gap", return_value=_fake_skill_gap_response()
        ) as mock_analyze,
    ):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["canonical"]["readiness_score"] == 21
    assert body["analysis"]["summary"] == "Python is your main gap."
    args, _ = mock_analyze.call_args
    assert args[1] == _SID
    mock_analyze.assert_called_once()


def test_skill_gap_ignores_any_client_supplied_student_id():
    """IDOR guard: the route has no student_id parameter, so a caller
    cannot influence whose analysis is built."""
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.analyze_student_skill_gap", return_value=_fake_skill_gap_response()
        ) as mock_analyze,
    ):
        response = client.post(
            "/api/v1/ai/skill-gap?student_id=some-other-student",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 200
    args, _ = mock_analyze.call_args
    assert args[1] == _SID
    assert "some-other-student" not in str(mock_analyze.call_args)


def test_skill_gap_degrades_gracefully_when_groq_fails_and_keeps_canonical_data():
    """The core Phase 3 requirement: when the AI layer fails, canonical
    data is still returned (HTTP 200), never a fabricated analysis and
    never a hard failure of the whole request."""
    canonical = CanonicalSkillGapSummary(
        mode=AnalysisMode.JOB_ROLE, target_role="Backend Developer", readiness_score=21
    )
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.analyze_student_skill_gap",
            side_effect=AIProviderError("Groq is down"),
        ),
        patch("app.api.ai.build_canonical_summary_only", return_value=canonical) as mock_canonical,
    ):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_available"] is False
    assert body["canonical"]["readiness_score"] == 21
    assert "reason" in body
    assert "Groq is down" not in response.text
    mock_canonical.assert_called_once()


def test_skill_gap_failure_reason_never_leaks_raw_exception_text():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.analyze_student_skill_gap",
            side_effect=AIProviderError("secret internal detail: rate limit key xyz"),
        ),
        patch(
            "app.api.ai.build_canonical_summary_only",
            return_value=CanonicalSkillGapSummary(mode=AnalysisMode.PERSONAL),
        ),
    ):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 200
    assert "secret internal detail" not in response.text
    assert "rate limit key xyz" not in response.text


def test_skill_gap_hard_failure_when_canonical_fallback_also_fails():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.analyze_student_skill_gap", side_effect=AIProviderError("down")
        ),
        patch(
            "app.api.ai.build_canonical_summary_only",
            side_effect=RuntimeError("supabase also down: internal detail"),
        ),
    ):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 500
    assert "internal detail" not in response.text


def test_skill_gap_unrelated_failure_returns_generic_500():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch(
            "app.api.ai.analyze_student_skill_gap",
            side_effect=RuntimeError("unexpected internal detail"),
        ),
    ):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )

    assert response.status_code == 500
    assert "unexpected internal detail" not in response.text


def test_skill_gap_response_contains_no_secrets():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch("app.api.ai.analyze_student_skill_gap", return_value=_fake_skill_gap_response()),
    ):
        response = client.post(
            "/api/v1/ai/skill-gap", headers={"Authorization": "Bearer valid-token"}
        )

    assert "gsk_" not in response.text
    assert "service_role" not in response.text.lower()


def test_skill_gap_registered_exactly_once_no_doubling():
    schema = client.get("/openapi.json").json()
    assert "/api/v1/ai/skill-gap" in schema["paths"]
    assert "/api/v1/ai/ai/skill-gap" not in schema["paths"]
    assert schema["paths"]["/api/v1/ai/skill-gap"].get("get") is None
    assert "post" in schema["paths"]["/api/v1/ai/skill-gap"]


# ============================================================
# Regression: /health and /context still work after Phase 3
# ============================================================


def test_health_still_works_after_phase_3():
    with authenticated_as("STUDENT"), patch("app.api.ai.ai_settings") as mock_settings:
        mock_settings.is_configured = True
        mock_settings.groq_model = "openai/gpt-oss-20b"
        response = client.get(
            "/api/v1/ai/health", headers={"Authorization": "Bearer valid-token"}
        )
    assert response.status_code == 200
    assert response.json()["configured"] is True


def test_context_still_works_after_phase_3():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch("app.api.ai.build_student_career_context", return_value=_fake_context()),
    ):
        response = client.get(
            "/api/v1/ai/context", headers={"Authorization": "Bearer valid-token"}
        )
    assert response.status_code == 200
    assert response.json()["student_id"] == _SID
