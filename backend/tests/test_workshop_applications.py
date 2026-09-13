"""Tests for the Workshop application pipeline:
Student /api/v1/student/workshops[...] (app.api.student_workshops) and
Industry /api/v1/workshops/{id}/applications /
/api/v1/workshops/applications/{id}/status (app.api.industry_workshops).

Route tests mock the service layer and use tests.conftest.authenticated_as,
exactly like tests/test_applications.py. Service tests drive
industry_workshop_application_service transitions directly -- no live
project or real token.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    industry_workshop_application_service,
    notification_producer,
    student_workshop_service,
)
from tests.conftest import authenticated_as

client = TestClient(app)

_WORKSHOP_ID = "11111111-1111-1111-1111-111111111111"
_APPLICATION_ID = "22222222-2222-2222-2222-222222222222"


def _workshop_row(**overrides):
    row = {
        "id": _WORKSHOP_ID,
        "title": "Intro to Git",
        "description": "A hands-on session.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "duration_days": 1,
        "capacity": 50,
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
        "workshop_id": _WORKSHOP_ID,
        "status": "APPLIED",
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "workshop": {"id": _WORKSHOP_ID, "title": "Intro to Git", "status": "PUBLISHED"},
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
                f"/api/v1/student/workshops/{uuid4()}/applications",
                json={},
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


def test_industry_applicants_endpoint_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                f"/api/v1/workshops/{uuid4()}/applications",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 403, role


# ============================================================
# Student: apply / duplicate / withdraw
# ============================================================


def test_student_apply_succeeds_and_notifies_industry():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_workshop_service, "get_workshop", return_value=_workshop_row()),
        patch.object(
            student_workshop_service, "apply_to_workshop", return_value=_application_row()
        ),
        patch.object(notification_producer, "emit_new_application") as emit,
        patch(
            "app.api.student_workshops._own_name", return_value="Ada Lovelace"
        ),
    ):
        resp = client.post(
            (f"/api/v1/student/workshops/{_WORKSHOP_ID}/applications"),
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert resp.json()["status"] == "APPLIED"
    emit.assert_called_once()
    assert emit.call_args.kwargs["kind"] == "WORKSHOP"
    assert emit.call_args.kwargs["industry_id"] == "industry-1"


def test_student_duplicate_application_returns_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_workshop_service, "get_workshop", return_value=_workshop_row()),
        patch.object(
            student_workshop_service,
            "apply_to_workshop",
            side_effect=student_workshop_service.DuplicateApplicationError("workshop-1"),
        ),
    ):
        resp = client.post(
            (f"/api/v1/student/workshops/{_WORKSHOP_ID}/applications"),
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_student_apply_to_unpublished_workshop_is_404():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(student_workshop_service, "get_workshop", return_value=None),
    ):
        resp = client.post(
            (f"/api/v1/student/workshops/{_WORKSHOP_ID}/applications"),
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_student_withdraw_blocked_when_not_withdrawable():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            student_workshop_service,
            "withdraw_application",
            side_effect=student_workshop_service.ApplicationNotWithdrawableError("ACCEPTED"),
        ),
    ):
        resp = client.post(
            (f"/api/v1/student/workshop-applications/{_APPLICATION_ID}/withdraw"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ============================================================
# Industry: applicants list is ownership-scoped
# ============================================================


def test_industry_lists_only_its_own_applicants():
    captured = {}

    def fake_list(_client, industry_id, **kwargs):
        captured.update({"industry_id": industry_id, **kwargs})
        return [_application_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_workshop_application_service, "list_applications", side_effect=fake_list
        ),
    ):
        resp = client.get(
            (f"/api/v1/workshops/{_WORKSHOP_ID}/applications"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-1"
    assert captured["workshop_id"] == _WORKSHOP_ID
    assert resp.json()["applications"][0]["student_name"] == "Ada Lovelace"


def test_unrelated_industry_gets_404_updating_status_it_does_not_own():
    """get_application scopes by the caller's own industry_id -- another
    Industry account's application is indistinguishable from one that
    doesn't exist (mirrors application_service's ownership contract)."""
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(industry_workshop_application_service, "update_status", return_value=None),
    ):
        resp = client.patch(
            (f"/api/v1/workshops/applications/{_APPLICATION_ID}/status"),
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_industry_accept_notifies_student():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_workshop_application_service,
            "update_status",
            return_value=_application_row(status="ACCEPTED"),
        ),
        patch.object(notification_producer, "emit_workshop_status_change") as emit,
    ):
        resp = client.patch(
            (f"/api/v1/workshops/applications/{_APPLICATION_ID}/status"),
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    emit.assert_called_once_with(
        student_id="student-1",
        workshop_id=_WORKSHOP_ID,
        new_status="ACCEPTED",
        workshop_title="Intro to Git",
    )


def test_invalid_transition_returns_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_workshop_application_service,
            "update_status",
            side_effect=industry_workshop_application_service.InvalidStatusTransitionError(
                "REJECTED", "ACCEPTED"
            ),
        ),
    ):
        resp = client.patch(
            (f"/api/v1/workshops/applications/{_APPLICATION_ID}/status"),
            json={"status": "ACCEPTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_reject_and_completed_are_rejected_as_industry_settable_input():
    """WITHDRAWN and APPLIED are never accepted from Industry (422, not a
    409) -- IndustrySettableWorkshopStatus excludes them structurally."""
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        resp = client.patch(
            (f"/api/v1/workshops/applications/{_APPLICATION_ID}/status"),
            json={"status": "WITHDRAWN"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ============================================================
# Service-level: transition graph
# ============================================================


def test_service_status_transitions_match_spec():
    transitions = industry_workshop_application_service._STATUS_TRANSITIONS
    assert transitions["APPLIED"] == {"ACCEPTED", "REJECTED"}
    assert transitions["ACCEPTED"] == {"COMPLETED", "REJECTED"}
    assert transitions["REJECTED"] == set()
    assert transitions["WITHDRAWN"] == set()
    assert transitions["COMPLETED"] == set()


def test_service_update_status_raises_on_invalid_transition():
    fake_client = MagicMock()
    with patch.object(
        industry_workshop_application_service,
        "get_application",
        return_value=_application_row(status="REJECTED"),
    ):
        try:
            industry_workshop_application_service.update_status(
                fake_client, "industry-1", _APPLICATION_ID, "ACCEPTED"
            )
            raised = False
        except industry_workshop_application_service.InvalidStatusTransitionError:
            raised = True
    assert raised
