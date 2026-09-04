"""Tests for the Industry side of applications (Phase 7):
/api/v1/applications.

Route tests mock app.services.application_service and use
tests.conftest.authenticated_as, exactly like tests/test_jobs.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import applications as application_routes
from app.main import app
from app.services import application_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _row(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-7",
        "industry_id": "industry-1",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "int-1",
        "job_id": None,
        "status": "APPLIED",
        "cover_note": "I'd love to join.",
        "match_score": None,
        "applied_at": "2026-09-01T00:00:00Z",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "opportunity": {"id": "int-1", "title": "Backend Intern", "status": "PUBLISHED"},
    }
    row.update(overrides)
    return row


# ============================================================
# Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/applications"),
    ("get", f"/api/v1/applications/{uuid4()}"),
    ("patch", f"/api/v1/applications/{uuid4()}/status"),
]


def _call(method: str, url: str, *, headers=None):
    if method == "patch":
        return client.patch(url, json={"status": "SHORTLISTED"}, headers=headers)
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# List
# ============================================================


def test_list_returns_only_callers_applications_with_filters():
    captured = {}

    def fake_list(_client, industry_id, **kwargs):
        captured.update({"industry_id": industry_id, **kwargs})
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "list_applications", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/applications?status=SHORTLISTED&opportunity_type=INTERNSHIP",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-1"
    assert captured["status"] == "SHORTLISTED"
    assert captured["opportunity_type"] == "INTERNSHIP"
    assert resp.json()["applications"][0]["id"] == "app-1"


def test_list_rejects_unknown_status_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/applications?status=NONSENSE", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_list_rejects_unknown_opportunity_type():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/applications?opportunity_type=GIG", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_list_response_never_exposes_student_profile_fields():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "list_applications", return_value=[_row()]),
    ):
        resp = client.get("/api/v1/applications", headers={"Authorization": "Bearer token"})
    body = resp.json()["applications"][0]
    assert body["student_id"] == "student-7"
    for leaked in ("email", "full_name", "avatar_url", "username", "password", "access_token"):
        assert leaked not in body


# ============================================================
# Detail -- ownership
# ============================================================


def test_get_detail_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(application_service, "get_application", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/applications/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_get_detail_returns_owned_application():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_row()),
    ):
        resp = client.get(
            f"/api/v1/applications/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["opportunity"]["title"] == "Backend Intern"


def test_get_detail_response_includes_resolved_student_name():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            application_service,
            "get_application",
            return_value=_row(student_name="Arunangshu Pal"),
        ),
    ):
        resp = client.get(
            f"/api/v1/applications/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["student_name"] == "Arunangshu Pal"


def test_get_detail_response_student_name_defaults_to_none():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "get_application", return_value=_row()),
    ):
        resp = client.get(
            f"/api/v1/applications/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.json()["student_name"] is None


# ============================================================
# Status update
# ============================================================


def test_status_update_passes_owner_id_and_target_to_service():
    captured = {}

    def fake_update(_client, industry_id, application_id, target):
        captured.update({"industry_id": industry_id, "target": target})
        return _row(status="SHORTLISTED")

    with (
        authenticated_as("INDUSTRY", user_id="industry-9"),
        patch.object(application_service, "update_status", side_effect=fake_update),
    ):
        resp = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "SHORTLISTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-9", "target": "SHORTLISTED"}
    assert resp.json()["status"] == "SHORTLISTED"


def test_status_update_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(application_service, "update_status", return_value=None),
    ):
        resp = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "REJECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_status_update_invalid_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            application_service,
            "update_status",
            side_effect=application_service.InvalidStatusTransitionError("SELECTED", "APPLIED"),
        ),
    ):
        resp = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "REJECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_status_update_rejects_withdrawn():
    """WITHDRAWN is the student's transition, never Industry's."""
    with authenticated_as("INDUSTRY"):
        resp = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "WITHDRAWN"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_status_update_rejects_applied_and_garbage():
    with authenticated_as("INDUSTRY"):
        for bad in ("APPLIED", "definitely-not-a-status", ""):
            resp = client.patch(
                f"/api/v1/applications/{uuid4()}/status",
                json={"status": bad},
                headers={"Authorization": "Bearer token"},
            )
            assert resp.status_code == 422, bad


def test_status_update_rejects_smuggled_identity_fields():
    with authenticated_as("INDUSTRY"):
        for payload in (
            {"status": "SHORTLISTED", "student_id": "victim"},
            {"status": "SHORTLISTED", "industry_id": "attacker"},
            {"status": "SHORTLISTED", "internship_id": "other-posting"},
            {"status": "SHORTLISTED", "match_score": 99},
        ):
            resp = client.patch(
                f"/api/v1/applications/{uuid4()}/status",
                json=payload,
                headers={"Authorization": "Bearer token"},
            )
            assert resp.status_code == 422, payload


# ============================================================
# Service layer
# ============================================================


def test_shape_collapses_internship_embed():
    row = application_service._shape(
        {
            "id": "a",
            "internship": {"id": "int-1", "title": "Intern", "status": "PUBLISHED"},
            "job": None,
        }
    )
    assert row["opportunity"] == {"id": "int-1", "title": "Intern", "status": "PUBLISHED"}
    assert "internship" not in row and "job" not in row


def test_shape_collapses_job_embed():
    row = application_service._shape(
        {"id": "a", "internship": None, "job": {"id": "job-1", "title": "Eng", "status": "CLOSED"}}
    )
    assert row["opportunity"]["title"] == "Eng"


def test_shape_opportunity_is_none_when_no_embed():
    row = application_service._shape({"id": "a", "internship": None, "job": None})
    assert row["opportunity"] is None


def test_list_applications_attaches_resolved_student_names():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        _row(id="app-1"),
        _row(id="app-2"),
    ]
    supabase.rpc.return_value.execute.return_value.data = [
        {"application_id": "app-1", "student_name": "Arunangshu Pal"},
        {"application_id": "app-2", "student_name": None},
    ]
    rows = application_service.list_applications(supabase, "industry-1")
    assert rows[0]["student_name"] == "Arunangshu Pal"
    assert rows[1]["student_name"] is None
    supabase.rpc.assert_called_once_with(
        "application_applicant_names", {"application_ids": ["app-1", "app-2"]}
    )


def test_list_applications_tolerates_name_rpc_failure():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        _row(id="app-1")
    ]
    supabase.rpc.side_effect = Exception("rpc unavailable")
    rows = application_service.list_applications(supabase, "industry-1")
    assert rows[0]["student_name"] is None


def test_get_application_attaches_resolved_student_name():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = _row(
        id="app-1"
    )
    supabase.rpc.return_value.execute.return_value.data = [
        {"application_id": "app-1", "student_name": "Arunangshu Pal"}
    ]
    row = application_service.get_application(supabase, "industry-1", "app-1")
    assert row["student_name"] == "Arunangshu Pal"


def test_list_passes_all_filters_to_query():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    application_service.list_applications(
        supabase,
        "industry-1",
        status="SHORTLISTED",
        opportunity_type="JOB",
        internship_id=None,
        job_id="job-9",
    )
    eq_calls = supabase.table.return_value.select.return_value.eq.call_args_list
    assert ("industry_id", "industry-1") == eq_calls[0].args


def test_update_status_returns_none_when_not_owned():
    supabase = MagicMock()
    with patch.object(application_service, "get_application", return_value=None):
        result = application_service.update_status(supabase, "industry-1", "app-x", "SHORTLISTED")
    assert result is None
    supabase.table.return_value.update.assert_not_called()


def test_update_status_only_writes_status_field():
    supabase = MagicMock()
    with patch.object(
        application_service,
        "get_application",
        side_effect=[_row(status="APPLIED"), _row(status="SHORTLISTED")],
    ):
        application_service.update_status(supabase, "industry-1", "app-1", "SHORTLISTED")
    written = supabase.table.return_value.update.call_args.args[0]
    assert written == {"status": "SHORTLISTED"}


def test_update_status_valid_pipeline_transition():
    supabase = MagicMock()
    with patch.object(
        application_service,
        "get_application",
        side_effect=[_row(status="SHORTLISTED"), _row(status="INTERVIEW_SCHEDULED")],
    ):
        result = application_service.update_status(
            supabase, "industry-1", "app-1", "INTERVIEW_SCHEDULED"
        )
    assert result["status"] == "INTERVIEW_SCHEDULED"


def test_update_status_rejects_invalid_transition():
    supabase = MagicMock()
    with patch.object(application_service, "get_application", return_value=_row(status="SELECTED")):
        try:
            application_service.update_status(supabase, "industry-1", "app-1", "REJECTED")
            raised = False
        except application_service.InvalidStatusTransitionError:
            raised = True
    assert raised
    supabase.table.return_value.update.assert_not_called()


def test_update_status_rejects_backwards_transition():
    supabase = MagicMock()
    with patch.object(
        application_service, "get_application", return_value=_row(status="INTERVIEW_SCHEDULED")
    ):
        try:
            application_service.update_status(supabase, "industry-1", "app-1", "SHORTLISTED")
            raised = False
        except application_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_transition_map_terminals_have_no_outgoing_edges():
    for terminal in ("SELECTED", "REJECTED", "WITHDRAWN"):
        assert application_service._STATUS_TRANSITIONS[terminal] == set()


def test_transition_map_never_targets_withdrawn_or_applied():
    for targets in application_service._STATUS_TRANSITIONS.values():
        assert "WITHDRAWN" not in targets
        assert "APPLIED" not in targets


# ============================================================
# Filtering
# ============================================================


def test_list_filters_by_specific_internship():
    captured = {}

    def fake_list(_client, industry_id, **kwargs):
        captured.update(kwargs)
        return []

    internship_id = str(uuid4())
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "list_applications", side_effect=fake_list),
    ):
        resp = client.get(
            f"/api/v1/applications?internship_id={internship_id}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["internship_id"] == internship_id
    assert captured["job_id"] is None


def test_list_rejects_non_uuid_internship_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/applications?internship_id=not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ============================================================
# Recruitment summary (funnel)
# ============================================================


def test_summary_unauthenticated_returns_401():
    assert client.get("/api/v1/applications/summary").status_code == 401


def test_summary_forbids_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        with authenticated_as(role):
            resp = client.get(
                "/api/v1/applications/summary", headers={"Authorization": "Bearer token"}
            )
        assert resp.status_code == 403, role


def test_summary_derives_owner_from_token():
    captured = {}

    def fake_summary(_client, industry_id):
        captured["industry_id"] = industry_id
        return {"counts": {"APPLIED": 2, "SHORTLISTED": 1}, "total": 3}

    with (
        authenticated_as("INDUSTRY", user_id="industry-77"),
        patch.object(application_service, "get_status_summary", side_effect=fake_summary),
    ):
        resp = client.get(
            "/api/v1/applications/summary", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-77"
    body = resp.json()
    assert body["total"] == 3
    assert body["counts"]["APPLIED"] == 2


def test_summary_route_matches_before_application_id():
    """GET /applications/summary must not be swallowed by /{application_id}."""
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            application_service,
            "get_status_summary",
            return_value={"counts": {}, "total": 0},
        ) as mock_summary,
        patch.object(application_service, "get_application") as mock_get,
    ):
        resp = client.get(
            "/api/v1/applications/summary", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    mock_summary.assert_called_once()
    mock_get.assert_not_called()


def test_get_status_summary_counts_every_status():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"status": "APPLIED"},
        {"status": "APPLIED"},
        {"status": "SHORTLISTED"},
        {"status": "REJECTED"},
    ]
    result = application_service.get_status_summary(supabase, "industry-1")
    assert result["total"] == 4
    assert result["counts"]["APPLIED"] == 2
    assert result["counts"]["SHORTLISTED"] == 1
    assert result["counts"]["REJECTED"] == 1
    # every known status is present, even at 0
    for name in application_service._ALL_STATUSES:
        assert name in result["counts"]
    assert result["counts"]["SELECTED"] == 0


def test_get_status_summary_scopes_to_caller():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    application_service.get_status_summary(supabase, "industry-9")
    assert supabase.table.return_value.select.return_value.eq.call_args.args == (
        "industry_id",
        "industry-9",
    )


# ============================================================
# No service-role anywhere on this path
# ============================================================


def test_application_modules_do_not_use_service_role():
    assert not hasattr(application_service, "get_supabase")
    assert not hasattr(application_routes, "get_supabase")
    assert hasattr(application_routes, "build_user_client")
