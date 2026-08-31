"""Tests for the Career Role / Skill Gap API (Phase 1L):
app.services.assessment_service.get_student_skill_scores,
app.services.career_role_service, and the /career-roles routes.

No live Supabase project or real token is used anywhere in this file --
the auth dependency chain is mocked (see conftest.py), and the Supabase
client/service layer is mocked directly, matching the existing pattern in
test_assessments.py.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import assessment_service, career_role_service
from app.services.skill_alignment_service import SkillRequirement
from tests.conftest import authenticated_as

client = TestClient(app)


# ============================================================
# get_student_skill_scores (Phase 1L, assessment_service.py)
# ============================================================


def _completed_attempt_row(skill_id: str, percentage: str):
    return {"percentage": percentage, "assessment": {"skill_id": skill_id}}


def test_skill_scores_only_from_completed_attempts():
    """Case 10: an IN_PROGRESS/ABANDONED attempt must never contribute --
    this is enforced by the .eq('status', 'COMPLETED') filter itself, so
    this test verifies that filter is actually applied."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [_completed_attempt_row("skill-1", "80.00")]
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    mock_client.table.assert_called_with("assessment_attempts")
    status_filter_call = mock_client.table.return_value.select.return_value.eq.call_args_list[0]
    assert status_filter_call.args == ("student_id", "student-1")
    assert scores == {"skill-1": Decimal("80.00")}


def test_skill_scores_takes_best_of_multiple_completed_attempts():
    """Case 9: multiple completed attempts for the same skill -> the
    documented 'best percentage' behavior, not the most recent or an
    average."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        _completed_attempt_row("skill-1", "55.00"),
        _completed_attempt_row("skill-1", "90.00"),
        _completed_attempt_row("skill-1", "70.00"),
    ]
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-1": Decimal("90.00")}


def test_skill_scores_excludes_rows_with_deactivated_assessment_embed():
    """A None 'assessment' embed (parent assessment deactivated after
    completion) is excluded from the aggregate, not treated as a crash --
    see the function's own docstring for why this differs from
    get_attempt_result_rows()'s hard-failure behavior."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        {"percentage": "80.00", "assessment": None},
        _completed_attempt_row("skill-2", "60.00"),
    ]
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {"skill-2": Decimal("60.00")}


def test_skill_scores_empty_when_no_completed_attempts():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = []
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response

    scores = assessment_service.get_student_skill_scores(mock_client, "student-1")

    assert scores == {}


# ============================================================
# career_role_service
# ============================================================


def test_get_career_role_requirements_skips_deactivated_skill_embed():
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        {"skill_id": "s1", "required_level": "70.00", "weight": "1.00", "skill": {"name": "Python"}},
        {"skill_id": "s2", "required_level": "60.00", "weight": "1.00", "skill": None},
    ]
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = response

    requirements = career_role_service.get_career_role_requirements(mock_client, uuid4())

    assert len(requirements) == 1
    assert requirements[0] == SkillRequirement(
        skill_id="s1", skill_name="Python", required_level=Decimal("70.00"), weight=Decimal("1.00")
    )


# ============================================================
# API: GET /career-roles, GET /career-roles/{id}
# ============================================================


def _role_row(**overrides):
    row = {
        "id": str(uuid4()),
        "title": "Software Engineer",
        "description": "Builds backend and full-stack applications.",
        "category": "Engineering",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_list_career_roles_requires_authentication():
    response = client.get("/api/v1/career-roles")
    assert response.status_code == 401


def test_list_career_roles_authenticated_student():
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "list_career_roles", return_value=[_role_row()]),
    ):
        response = client.get("/api/v1/career-roles", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["career_roles"][0]["title"] == "Software Engineer"


def test_list_career_roles_also_allowed_for_faculty():
    """Same precedent as GET /assessments -- reference-data reads are not
    role-restricted; RLS itself never restricts this by role."""
    with (
        authenticated_as("FACULTY"),
        patch.object(career_role_service, "list_career_roles", return_value=[]),
    ):
        response = client.get("/api/v1/career-roles", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_get_career_role_not_found():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=None),
    ):
        response = client.get(f"/api/v1/career-roles/{role_id}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 404


def test_get_career_role_found():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
    ):
        response = client.get(f"/api/v1/career-roles/{role_id}", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json()["id"] == str(role_id)


# ============================================================
# API: GET /career-roles/{id}/skill-gap
# ============================================================


def test_skill_gap_requires_student_role():
    role_id = uuid4()
    with authenticated_as("FACULTY"):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_skill_gap_nonexistent_role_returns_404():
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=None),
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_skill_gap_with_completed_attempts():
    role_id = uuid4()
    python_id, sql_id = str(uuid4()), str(uuid4())
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[
                SkillRequirement(python_id, "Python", Decimal(70), Decimal("1.0")),
                SkillRequirement(sql_id, "SQL", Decimal(60), Decimal("1.0")),
            ],
        ),
        patch.object(
            assessment_service, "get_student_skill_scores", return_value={python_id: Decimal(85)}
        ),
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )

    assert response.status_code == 200
    body = response.json()
    statuses = {row["skill_name"]: row["status"] for row in body["skills"]}
    assert statuses["Python"] == "STRONG"
    assert statuses["SQL"] == "NOT_ASSESSED"


def test_skill_gap_no_completed_assessments_still_returns_role_requirements():
    """A student with no completed assessments still sees the role's
    requirements -- every skill NOT_ASSESSED, never a fabricated score."""
    role_id = uuid4()
    with (
        authenticated_as("STUDENT"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[SkillRequirement(str(uuid4()), "Python", Decimal(70), Decimal("1.0"))],
        ),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap", headers={"Authorization": "Bearer token"}
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["status"] == "NOT_ASSESSED"


def test_skill_gap_never_accepts_client_supplied_student_id():
    """No request body/query param exists to override the authenticated
    identity -- the endpoint takes only the career_role_id from the path.
    A client-supplied student_id in the query string is simply ignored
    (FastAPI drops unrecognized query params for a route with no such
    parameter declared) -- this test proves get_student_skill_scores is
    still called with the AUTHENTICATED user's id, not anything from the
    request."""
    role_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="real-student-id"),
        patch.object(career_role_service, "get_career_role", return_value=_role_row(id=str(role_id))),
        patch.object(career_role_service, "get_career_role_requirements", return_value=[]),
        patch.object(
            assessment_service, "get_student_skill_scores", return_value={}
        ) as mock_scores,
    ):
        response = client.get(
            f"/api/v1/career-roles/{role_id}/skill-gap?student_id=someone-elses-id",
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 200
    mock_scores.assert_called_once()
    _called_client, called_student_id = mock_scores.call_args.args
    assert called_student_id == "real-student-id"
