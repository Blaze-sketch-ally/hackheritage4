"""Tests for the Project application/selection pipeline:
Student /api/v1/student/industry-projects[...] (app.api.student_projects)
and Industry /api/v1/projects/{id}/applications /
/api/v1/projects/applications/{id}/status (app.api.industry_projects).

Same shape as tests/test_workshop_applications.py.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    industry_project_application_service,
    notification_producer,
    student_project_service,
)
from tests.conftest import authenticated_as

client = TestClient(app)

_PROJECT_ID = "33333333-3333-3333-3333-333333333333"
_APPLICATION_ID = "44444444-4444-4444-4444-444444444444"


def _project_row(**overrides):
    row = {
        "id": _PROJECT_ID,
        "title": "Recommendation Engine",
        "description": "Build a recommender for our catalog.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "duration_months": 3,
        "team_size": 4,
        "eligibility_criteria": None,
        "application_deadline": "2026-12-01",
        "start_date": "2026-09-15",
        "status": "PUBLISHED",
        "created_at": "2026-09-01T00:00:00Z",
        "industry": {"id": "industry-1", "company_name": "Acme", "industry_sector": None, "logo_url": None},
        "has_applied": False,
    }
    row.update(overrides)
    return row


def _application_row(**overrides):
    row = {
        "id": _APPLICATION_ID,
        "student_id": "student-1",
        "student_name": "Ada Lovelace",
        "institution_name": "MIT",
        "department": "CS",
        "graduation_year": 2027,
        "skills": ["Python"],
        "industry_id": "industry-1",
        "project_id": _PROJECT_ID,
        "status": "APPLIED",
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "project": {"id": _PROJECT_ID, "title": "Recommendation Engine", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


# ============================================================
# Auth / role guards
# ============================================================


def test_student_apply_endpoint_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.post(
                f"/api/v1/student/industry-projects/{uuid4()}/applications",
                json={},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


def test_industry_applicants_endpoint_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                f"/api/v1/projects/{uuid4()}/applications",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


# ============================================================
# Student: apply / duplicate
# ============================================================


def test_student_apply_succeeds_and_notifies_industry():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_project_service, "get_project", return_value=_project_row()),
        patch.object(
            student_project_service, "apply_to_project", return_value=_application_row()
        ),
        patch.object(notification_producer, "emit_new_application") as emit,
        patch("app.api.student_projects._own_name", return_value="Ada Lovelace"),
    ):
        resp = client.post(
            (f"/api/v1/student/industry-projects/{_PROJECT_ID}/applications"),
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    emit.assert_called_once()
    assert emit.call_args.kwargs["kind"] == "PROJECT"
    assert emit.call_args.kwargs["industry_id"] == "industry-1"


def test_student_duplicate_application_returns_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_project_service, "get_project", return_value=_project_row()),
        patch.object(
            student_project_service,
            "apply_to_project",
            side_effect=student_project_service.DuplicateApplicationError(_PROJECT_ID),
        ),
    ):
        resp = client.post(
            (f"/api/v1/student/industry-projects/{_PROJECT_ID}/applications"),
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ============================================================
# Industry: applicants list is ownership-scoped; shortlist/select/reject
# ============================================================


def test_industry_lists_only_its_own_applicants():
    captured = {}

    def fake_list(_client, industry_id, **kwargs):
        captured.update({"industry_id": industry_id, **kwargs})
        return [_application_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_project_application_service, "list_applications", side_effect=fake_list
        ),
    ):
        resp = client.get(
            (f"/api/v1/projects/{_PROJECT_ID}/applications"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-1"
    assert captured["project_id"] == _PROJECT_ID


def test_unrelated_industry_gets_404_updating_status_it_does_not_own():
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(industry_project_application_service, "update_status", return_value=None),
    ):
        resp = client.patch(
            (f"/api/v1/projects/applications/{_APPLICATION_ID}/status"),
            json={"status": "SHORTLISTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_industry_shortlist_notifies_student():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_project_application_service,
            "update_status",
            return_value=_application_row(status="SHORTLISTED"),
        ),
        patch.object(notification_producer, "emit_project_status_change") as emit,
    ):
        resp = client.patch(
            (f"/api/v1/projects/applications/{_APPLICATION_ID}/status"),
            json={"status": "SHORTLISTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    emit.assert_called_once_with(
        student_id="student-1",
        project_id=_PROJECT_ID,
        new_status="SHORTLISTED",
        project_title="Recommendation Engine",
    )


def test_industry_can_select_directly_from_applied():
    """No interview stage: APPLIED -> SELECTED is a valid direct
    transition, unlike the Internship/Job pipeline."""
    assert "SELECTED" in industry_project_application_service._STATUS_TRANSITIONS["APPLIED"]


def test_invalid_transition_returns_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_project_application_service,
            "update_status",
            side_effect=industry_project_application_service.InvalidStatusTransitionError(
                "REJECTED", "SELECTED"
            ),
        ),
    ):
        resp = client.patch(
            (f"/api/v1/projects/applications/{_APPLICATION_ID}/status"),
            json={"status": "SELECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ============================================================
# Service-level: transition graph (no interview stage)
# ============================================================


def test_service_status_transitions_match_spec():
    transitions = industry_project_application_service._STATUS_TRANSITIONS
    assert transitions["APPLIED"] == {"SHORTLISTED", "SELECTED", "REJECTED"}
    assert transitions["SHORTLISTED"] == {"SELECTED", "REJECTED"}
    assert transitions["SELECTED"] == {"ACTIVE"}
    assert transitions["ACTIVE"] == {"COMPLETED"}
    assert transitions["REJECTED"] == set()
    assert transitions["WITHDRAWN"] == set()
    assert transitions["COMPLETED"] == set()


def test_service_update_status_raises_on_invalid_transition():
    fake_client = MagicMock()
    with patch.object(
        industry_project_application_service,
        "get_application",
        return_value=_application_row(status="ACTIVE"),
    ):
        try:
            industry_project_application_service.update_status(
                fake_client, "industry-1", _APPLICATION_ID, "SELECTED"
            )
            raised = False
        except industry_project_application_service.InvalidStatusTransitionError:
            raised = True
    assert raised
