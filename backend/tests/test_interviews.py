"""Tests for Industry interview scheduling: /api/v1/interviews.

Route tests mock app.services.interview_service and use
tests.conftest.authenticated_as; service tests drive the functions with a
MagicMock Supabase client and patched helpers -- no live project or real
token.

RLS isolation (an Industry account can never read/write another's
interview rows) is enforced at the database layer by 030's policies
(auth.uid() = industry_id AND public.is_industry(auth.uid())), exactly
like every prior Industry module -- not re-verified against a live DB
here. What IS verified: the Python service always scopes its query by the
caller's own industry_id, the require_industry guard gates every route,
identity fields (industry_id/student_id/status) can never be supplied by
the client, and the lifecycle/eligibility/conflict rules hold.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import interview_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _future_iso(hours: int = 48) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _row(**overrides):
    row = {
        "id": "interview-1",
        "application_id": "app-1",
        "industry_id": "industry-1",
        "student_id": "student-1",
        "scheduled_at": _future_iso(),
        "duration_minutes": 30,
        "mode": "ONLINE",
        "location": "https://meet.example.com/abc",
        "notes": None,
        "status": "SCHEDULED",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "opportunity": {"id": "job-1", "title": "Backend Engineer", "status": "PUBLISHED"},
        "opportunity_type": "JOB",
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {
        "application_id": str(uuid4()),
        "scheduled_at": _future_iso(),
        "duration_minutes": 45,
        "mode": "ONLINE",
        "location": "https://meet.example.com/xyz",
    }
    body.update(overrides)
    return body


_ENDPOINTS = [
    ("get", "/api/v1/interviews"),
    ("post", "/api/v1/interviews"),
    ("get", f"/api/v1/interviews/{uuid4()}"),
    ("patch", f"/api/v1/interviews/{uuid4()}"),
    ("post", f"/api/v1/interviews/{uuid4()}/complete"),
    ("post", f"/api/v1/interviews/{uuid4()}/cancel"),
]


def _call(method: str, url: str, *, headers=None, json=None):
    kwargs = {"headers": headers}
    if method in {"post", "patch"}:
        kwargs["json"] = json if json is not None else _create_body()
    return getattr(client, method)(url, **kwargs)


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# Create: ownership + immutable fields
# ============================================================


def test_create_derives_owner_and_starts_scheduled():
    captured = {}

    def fake_create(_client, industry_id, data):
        captured.update({"industry_id": industry_id, "data": data})
        return _row(industry_id=industry_id, status="SCHEDULED")

    with (
        authenticated_as("INDUSTRY", user_id="industry-77"),
        patch.object(interview_service, "create_interview", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 201
    assert captured["industry_id"] == "industry-77"
    assert "industry_id" not in captured["data"]
    assert "student_id" not in captured["data"]
    assert "status" not in captured["data"]
    assert resp.json()["status"] == "SCHEDULED"


def test_create_rejects_client_supplied_industry_id():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/interviews",
            json=_create_body(industry_id="attacker"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_student_id_and_status():
    for smuggled in ({"student_id": "s-9"}, {"status": "COMPLETED"}):
        with authenticated_as("INDUSTRY"):
            resp = client.post(
                "/api/v1/interviews",
                json=_create_body(**smuggled),
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 422, smuggled


def test_create_rejects_missing_required_fields():
    for drop in ("application_id", "scheduled_at", "mode"):
        body = _create_body()
        del body[drop]
        with authenticated_as("INDUSTRY"):
            resp = client.post(
                "/api/v1/interviews", json=body, headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 422, drop


def test_create_rejects_bad_mode_and_out_of_range_duration():
    for bad in ({"mode": "TELEPATHY"}, {"duration_minutes": 3}, {"duration_minutes": 9000}):
        with authenticated_as("INDUSTRY"):
            resp = client.post(
                "/api/v1/interviews",
                json=_create_body(**bad),
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 422, bad


def test_create_ineligible_application_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "create_interview",
            side_effect=interview_service.IneligibleApplicationError("not shortlisted"),
        ),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_past_time_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "create_interview",
            side_effect=interview_service.InvalidInterviewTimeError("in the past"),
        ),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_conflict_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "create_interview",
            side_effect=interview_service.SchedulingConflictError("already scheduled"),
        ),
    ):
        resp = client.post(
            "/api/v1/interviews", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Ownership isolation on read / update / lifecycle
# ============================================================


def test_get_detail_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(interview_service, "get_interview", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/interviews/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_list_passes_owner_and_filters_to_service():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, application_id=None, upcoming=None):
        captured.update(
            {"industry_id": industry_id, "status": status, "upcoming": upcoming}
        )
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(interview_service, "list_interviews", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/interviews?status=SCHEDULED&upcoming=true",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "SCHEDULED", "upcoming": True}


def test_reschedule_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(interview_service, "reschedule_interview", return_value=None),
    ):
        resp = client.patch(
            f"/api/v1/interviews/{uuid4()}",
            json={"scheduled_at": _future_iso()},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_reschedule_rejects_application_id_change():
    with authenticated_as("INDUSTRY"):
        resp = client.patch(
            f"/api/v1/interviews/{uuid4()}",
            json={"application_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_reschedule_on_terminal_interview_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "reschedule_interview",
            side_effect=interview_service.InvalidStatusTransitionError("COMPLETED", "SCHEDULED"),
        ),
    ):
        resp = client.patch(
            f"/api/v1/interviews/{uuid4()}",
            json={"notes": "x"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_complete_and_cancel_404_when_not_owned():
    for action in ("complete", "cancel"):
        with (
            authenticated_as("INDUSTRY", user_id="industry-A"),
            patch.object(interview_service, f"{action}_interview", return_value=None),
        ):
            resp = client.post(
                f"/api/v1/interviews/{uuid4()}/{action}",
                headers={"Authorization": "Bearer token"},
            )
        assert resp.status_code == 404, action


def test_complete_invalid_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            interview_service,
            "complete_interview",
            side_effect=interview_service.InvalidStatusTransitionError("CANCELLED", "COMPLETED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/interviews/{uuid4()}/complete", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Service layer -- eligibility / lifecycle / scoping
# ============================================================


def test_service_create_rejects_unowned_or_missing_application():
    mock = MagicMock()
    with patch(
        "app.services.interview_service.application_service.get_application", return_value=None
    ):
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-x", "scheduled_at": _future_iso()}
            )
            raise AssertionError("expected IneligibleApplicationError")
        except interview_service.IneligibleApplicationError:
            pass


def test_service_create_rejects_application_not_shortlisted():
    mock = MagicMock()
    with patch(
        "app.services.interview_service.application_service.get_application",
        return_value={"id": "app-1", "status": "APPLIED"},
    ):
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-1", "scheduled_at": _future_iso()}
            )
            raise AssertionError("expected IneligibleApplicationError")
        except interview_service.IneligibleApplicationError:
            pass


def test_service_create_rejects_past_time():
    mock = MagicMock()
    with patch(
        "app.services.interview_service.application_service.get_application",
        return_value={"id": "app-1", "status": "SHORTLISTED"},
    ):
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-1", "scheduled_at": past}
            )
            raise AssertionError("expected InvalidInterviewTimeError")
        except interview_service.InvalidInterviewTimeError:
            pass


def test_service_create_rejects_when_application_already_has_live_interview():
    mock = MagicMock()
    with (
        patch(
            "app.services.interview_service.application_service.get_application",
            return_value={"id": "app-1", "status": "INTERVIEW_SCHEDULED"},
        ),
        patch.object(interview_service, "list_interviews", return_value=[_row()]),
    ):
        try:
            interview_service.create_interview(
                mock, "industry-1", {"application_id": "app-1", "scheduled_at": _future_iso()}
            )
            raise AssertionError("expected SchedulingConflictError")
        except interview_service.SchedulingConflictError:
            pass


def test_service_overlap_detection():
    base = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    others = [{"scheduled_at": base.isoformat(), "duration_minutes": 60}]
    # 10:30 start, 30 min -> overlaps 10:00-11:00
    assert interview_service._overlaps(base + timedelta(minutes=30), 30, others) is True
    # 11:30 start -> no overlap
    assert interview_service._overlaps(base + timedelta(minutes=90), 30, others) is False


def test_service_transitions_are_scheduled_only():
    assert interview_service._COMPLETE_FROM == frozenset({"SCHEDULED"})
    assert interview_service._CANCEL_FROM == frozenset({"SCHEDULED"})


def test_service_complete_rejects_non_scheduled():
    mock = MagicMock()
    with patch.object(interview_service, "get_interview", return_value=_row(status="CANCELLED")):
        try:
            interview_service.complete_interview(mock, "industry-1", "interview-1")
            raise AssertionError("expected InvalidStatusTransitionError")
        except interview_service.InvalidStatusTransitionError:
            pass


def test_service_list_scopes_by_industry_id():
    mock = MagicMock()
    table = mock.table.return_value
    table.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    interview_service.list_interviews(mock, "industry-42")
    mock.table.assert_called_with("interviews")
    table.select.return_value.eq.assert_called_with("industry_id", "industry-42")
