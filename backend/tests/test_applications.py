"""Tests for the Application API (Phase 1M):
app.services.application_service and the /applications +
/opportunities/{id}/applications, /opportunities/{id}/applicants routes.

No live Supabase project or real token is used anywhere in this file --
see test_opportunities.py's own docstring for why cross-account
ownership/RLS proofs live in tests/integration/ instead of here.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import application_service, assessment_service, opportunity_service
from app.services.skill_alignment_service import SkillRequirement
from tests.conftest import authenticated_as

client = TestClient(app)


def _application_row(**overrides):
    row = {
        "id": str(uuid4()),
        "opportunity_id": str(uuid4()),
        "student_id": str(uuid4()),
        "status": "APPLIED",
        "cover_note": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ============================================================
# Student can apply
# ============================================================


def test_student_can_apply():
    opportunity_id = uuid4()
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(application_service, "create_application", return_value=_application_row()),
    ):
        response = client.post(
            f"/api/v1/opportunities/{opportunity_id}/applications",
            json={"cover_note": "I'm excited to apply."},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert response.json()["status"] == "APPLIED"


def test_apply_never_accepts_client_supplied_student_id():
    """ApplicationCreateRequest has no student_id field at all --
    extra="forbid" rejects any attempt to smuggle one in."""
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.post(
            f"/api/v1/opportunities/{uuid4()}/applications",
            json={"cover_note": "hi", "student_id": "someone-elses-id"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_industry_cannot_apply():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.post(
            f"/api/v1/opportunities/{uuid4()}/applications",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ============================================================
# Duplicate blocked
# ============================================================


def test_duplicate_application_returns_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            application_service,
            "create_application",
            side_effect=application_service.DuplicateApplicationError(),
        ),
    ):
        response = client.post(
            f"/api/v1/opportunities/{uuid4()}/applications",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_service_translates_unique_violation_to_duplicate_error():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"message": "duplicate key value violates unique constraint", "code": "23505"}
    )
    try:
        application_service.create_application(mock_client, "student-1", uuid4(), None)
        raised = False
    except application_service.DuplicateApplicationError:
        raised = True
    assert raised


# ============================================================
# Draft/closed opportunities cannot receive applications
# ============================================================


def test_applying_to_non_published_opportunity_returns_409():
    """RLS's own INSERT WITH CHECK (opportunity must be PUBLISHED)
    raises 42501 -- the service translates this into
    OpportunityNotPublishedError, and the route into a clean 409."""
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            application_service,
            "create_application",
            side_effect=application_service.OpportunityNotPublishedError(),
        ),
    ):
        response = client.post(
            f"/api/v1/opportunities/{uuid4()}/applications",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_service_translates_rls_violation_to_not_published_error():
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.side_effect = APIError(
        {"message": "new row violates row-level security policy", "code": "42501"}
    )
    try:
        application_service.create_application(mock_client, "student-1", uuid4(), None)
        raised = False
    except application_service.OpportunityNotPublishedError:
        raised = True
    assert raised


# ============================================================
# Student sees own applications
# ============================================================


def test_student_lists_own_applications():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(application_service, "list_student_applications", return_value=[_application_row()]),
    ):
        response = client.get("/api/v1/applications", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert len(response.json()["applications"]) == 1


def test_industry_cannot_list_student_applications_endpoint():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.get("/api/v1/applications", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ============================================================
# Application status: industry owner can update, unrelated cannot,
# student cannot update at all
# ============================================================


def test_industry_owner_can_update_status():
    application_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            application_service,
            "update_application_status",
            return_value=_application_row(id=str(application_id), status="SHORTLISTED"),
        ),
    ):
        response = client.patch(
            f"/api/v1/applications/{application_id}/status",
            json={"status": "SHORTLISTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "SHORTLISTED"


def test_unrelated_industry_status_update_returns_404():
    """RLS matches zero rows for an application belonging to another
    industry's opportunity -- update_application_status() returns None."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(application_service, "update_application_status", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "REJECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_student_cannot_update_application_status():
    with authenticated_as("STUDENT", user_id="student-1"):
        response = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "SELECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_status_update_never_accepts_other_fields():
    """ApplicationStatusUpdateRequest has only `status` -- extra="forbid"
    means a client can never smuggle opportunity_id/student_id/cover_note
    through this endpoint, independent of the DB trigger that also blocks
    it."""
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "SELECTED", "student_id": "someone-elses-id"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ============================================================
# Matching: applicant list uses real evidence, only aggregate score
# leaves the service
# ============================================================


def test_list_opportunity_applicants_computes_score_and_hides_raw_evidence():
    mock_client = MagicMock()
    mock_service_client = MagicMock()
    opportunity_id = uuid4()

    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        _application_row(opportunity_id=str(opportunity_id), student_id="student-1")
    ]
    mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": "student-1", "full_name": "Ada Lovelace", "username": "ada"}
    ]

    with (
        patch.object(
            opportunity_service,
            "get_requirements",
            return_value=[SkillRequirement("s1", "Python", Decimal(70), Decimal("1.0"))],
        ),
        patch.object(assessment_service, "get_student_skill_scores", return_value={"s1": Decimal(90)}) as mock_scores,
    ):
        applicants = application_service.list_opportunity_applicants(mock_client, mock_service_client, opportunity_id)

    assert len(applicants) == 1
    assert applicants[0]["student_name"] == "Ada Lovelace"
    assert applicants[0]["overall_match_score"] == Decimal("100.00")
    # The service-role client, not the caller's own, is what reads
    # cross-student assessment evidence -- proves ownership is
    # established via the caller's own RLS-scoped applications query
    # FIRST (already executed above), then evidence is read narrowly.
    mock_scores.assert_called_once_with(mock_service_client, "student-1")
    # Nothing in the returned dict exposes raw assessment data.
    assert "assessment_attempts" not in applicants[0]
    assert set(applicants[0].keys()) == {
        "id", "student_id", "student_name", "status", "cover_note", "overall_match_score", "created_at", "updated_at",
    }


def test_list_applicants_returns_empty_when_caller_owns_nothing():
    """If the caller doesn't own this opportunity, RLS's own SELECT
    policy on `applications` returns zero rows -- the service must never
    fall through to a service-role read in that case."""
    mock_client = MagicMock()
    mock_service_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

    with patch.object(assessment_service, "get_student_skill_scores") as mock_scores:
        applicants = application_service.list_opportunity_applicants(mock_client, mock_service_client, uuid4())

    assert applicants == []
    mock_scores.assert_not_called()


def test_get_applicants_endpoint_requires_industry():
    with authenticated_as("STUDENT"):
        response = client.get(
            f"/api/v1/opportunities/{uuid4()}/applicants", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403
