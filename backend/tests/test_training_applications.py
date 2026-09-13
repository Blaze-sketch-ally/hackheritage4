"""Tests for the Training application pipeline:
Student /api/v1/student/trainings[...] (app.api.student_trainings) and
Industry /api/v1/trainings/{id}/applications /
/api/v1/trainings/applications/{id}/status (app.api.industry_trainings).

Exact mirror of tests/test_workshop_applications.py.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    industry_training_application_service,
    notification_producer,
    student_training_service,
)
from tests.conftest import authenticated_as

client = TestClient(app)

_TRAINING_ID = "55555555-5555-5555-5555-555555555555"
_APPLICATION_ID = "66666666-6666-6666-6666-666666666666"


def _training_row(**overrides):
    row = {
        "id": _TRAINING_ID,
        "title": "Python Bootcamp",
        "description": "An 8-week upskilling program.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "duration_months": 2,
        "capacity": 30,
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
        "training_id": _TRAINING_ID,
        "status": "APPLIED",
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "training": {"id": _TRAINING_ID, "title": "Python Bootcamp", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


def test_student_apply_endpoint_forbids_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.post(
                f"/api/v1/student/trainings/{uuid4()}/applications",
                json={},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


def test_industry_applicants_endpoint_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                f"/api/v1/trainings/{uuid4()}/applications",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


def test_student_apply_succeeds_and_notifies_industry():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_training_service, "get_training", return_value=_training_row()),
        patch.object(
            student_training_service, "apply_to_training", return_value=_application_row()
        ),
        patch.object(notification_producer, "emit_new_application") as emit,
        patch("app.api.student_trainings._own_name", return_value="Ada Lovelace"),
    ):
        resp = client.post(
            f"/api/v1/student/trainings/{_TRAINING_ID}/applications",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    emit.assert_called_once()
    assert emit.call_args.kwargs["kind"] == "TRAINING"
    assert emit.call_args.kwargs["industry_id"] == "industry-1"


def test_student_duplicate_application_returns_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_training_service, "get_training", return_value=_training_row()),
        patch.object(
            student_training_service,
            "apply_to_training",
            side_effect=student_training_service.DuplicateApplicationError(_TRAINING_ID),
        ),
    ):
        resp = client.post(
            f"/api/v1/student/trainings/{_TRAINING_ID}/applications",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_industry_lists_only_its_own_applicants():
    captured = {}

    def fake_list(_client, industry_id, **kwargs):
        captured.update({"industry_id": industry_id, **kwargs})
        return [_application_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_training_application_service, "list_applications", side_effect=fake_list
        ),
    ):
        resp = client.get(
            f"/api/v1/trainings/{_TRAINING_ID}/applications",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-1"
    assert captured["training_id"] == _TRAINING_ID
    assert resp.json()["applications"][0]["student_name"] == "Ada Lovelace"


def test_unrelated_industry_gets_404_updating_status_it_does_not_own():
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(industry_training_application_service, "update_status", return_value=None),
    ):
        resp = client.patch(
            f"/api/v1/trainings/applications/{_APPLICATION_ID}/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_industry_accept_notifies_student():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_training_application_service,
            "update_status",
            return_value=_application_row(status="ACCEPTED"),
        ),
        patch.object(notification_producer, "emit_training_status_change") as emit,
    ):
        resp = client.patch(
            f"/api/v1/trainings/applications/{_APPLICATION_ID}/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    emit.assert_called_once_with(
        student_id="student-1",
        training_id=_TRAINING_ID,
        new_status="ACCEPTED",
        training_title="Python Bootcamp",
    )


def test_invalid_transition_returns_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_training_application_service,
            "update_status",
            side_effect=industry_training_application_service.InvalidStatusTransitionError(
                "REJECTED", "ACCEPTED"
            ),
        ),
    ):
        resp = client.patch(
            f"/api/v1/trainings/applications/{_APPLICATION_ID}/status",
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_service_status_transitions_match_spec():
    transitions = industry_training_application_service._STATUS_TRANSITIONS
    assert transitions["APPLIED"] == {"ACCEPTED", "REJECTED"}
    assert transitions["ACCEPTED"] == {"COMPLETED", "REJECTED"}
    assert transitions["REJECTED"] == set()
    assert transitions["WITHDRAWN"] == set()
    assert transitions["COMPLETED"] == set()


def test_service_update_status_raises_on_invalid_transition():
    fake_client = MagicMock()
    with patch.object(
        industry_training_application_service,
        "get_application",
        return_value=_application_row(status="REJECTED"),
    ):
        try:
            industry_training_application_service.update_status(
                fake_client, "industry-1", _APPLICATION_ID, "ACCEPTED"
            )
            raised = False
        except industry_training_application_service.InvalidStatusTransitionError:
            raised = True
    assert raised
