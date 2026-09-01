"""Tests for Industry training management (Phase 10B): /api/v1/trainings.

Route tests mock app.services.industry_training_service and use
tests.conftest.authenticated_as, exactly like tests/test_industry_projects.py.
Service tests drive the functions with a MagicMock Supabase client and
patched helpers -- no live project or real token.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import industry_trainings as training_routes
from app.main import app
from app.services import industry_training_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _row(**overrides):
    row = {
        "id": "training-1",
        "industry_id": "industry-1",
        "title": "Cloud Fundamentals Bootcamp",
        "description": "A hands-on introduction to cloud infrastructure.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "duration_months": 2,
        "capacity": 30,
        "eligibility_criteria": None,
        "application_deadline": "2026-12-01",
        "start_date": "2026-09-15",
        "status": "DRAFT",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {"title": "Cloud Fundamentals Bootcamp", "description": "A hands-on introduction."}
    body.update(overrides)
    return body


# ============================================================
# Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/trainings"),
    ("post", "/api/v1/trainings"),
    ("get", f"/api/v1/trainings/{uuid4()}"),
    ("put", f"/api/v1/trainings/{uuid4()}"),
    ("post", f"/api/v1/trainings/{uuid4()}/publish"),
    ("post", f"/api/v1/trainings/{uuid4()}/close"),
    ("post", f"/api/v1/trainings/{uuid4()}/archive"),
]


def _call(method: str, url: str, *, headers=None):
    if method in {"post", "put"}:
        return getattr(client, method)(url, json={"title": "x", "description": "y"}, headers=headers)
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


def test_list_returns_only_callers_trainings():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, search=None):
        captured.update({"industry_id": industry_id, "status": status, "search": search})
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_training_service, "list_trainings", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/trainings?status=PUBLISHED&search=cloud",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "PUBLISHED", "search": "cloud"}
    assert resp.json()["trainings"][0]["id"] == "training-1"


def test_list_rejects_unknown_status_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get("/api/v1/trainings?status=NONSENSE", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


# ============================================================
# Create
# ============================================================


def test_create_derives_owner_from_token_and_starts_draft():
    captured = {}

    def fake_create(_client, industry_id, data):
        captured.update({"industry_id": industry_id, "data": data})
        return _row(industry_id=industry_id, status="DRAFT")

    with (
        authenticated_as("INDUSTRY", user_id="industry-99"),
        patch.object(industry_training_service, "create_training", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/trainings",
            json=_create_body(location="Remote"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["industry_id"] == "industry-99"
    assert "industry_id" not in captured["data"]
    assert "status" not in captured["data"]
    assert resp.json()["status"] == "DRAFT"


def test_create_rejects_client_supplied_industry_id():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/trainings",
            json=_create_body(industry_id="attacker-owned"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_status():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/trainings",
            json=_create_body(status="PUBLISHED"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_missing_title():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/trainings",
            json={"description": "no title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_invalid_duration():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/trainings",
            json=_create_body(duration_months=48),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_zero_capacity():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/trainings",
            json=_create_body(capacity=0),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_unknown_work_mode():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/trainings",
            json=_create_body(work_mode="FROM_MARS"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ============================================================
# Detail / update -- ownership
# ============================================================


def test_get_detail_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(industry_training_service, "get_training", return_value=None) as mock_get,
    ):
        resp = client.get(f"/api/v1/trainings/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_update_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(industry_training_service, "update_training", return_value=None),
    ):
        resp = client.put(
            f"/api/v1/trainings/{uuid4()}",
            json={"title": "New title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_update_rejects_status_field():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            f"/api/v1/trainings/{uuid4()}",
            json={"status": "PUBLISHED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_passes_owner_id_to_service():
    captured = {}

    def fake_update(_client, industry_id, training_id, data):
        captured["industry_id"] = industry_id
        return _row()

    with (
        authenticated_as("INDUSTRY", user_id="industry-7"),
        patch.object(industry_training_service, "update_training", side_effect=fake_update),
    ):
        resp = client.put(
            f"/api/v1/trainings/{uuid4()}",
            json={"title": "Updated"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-7"


# ============================================================
# Lifecycle endpoints -- ownership + error mapping
# ============================================================


def test_publish_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(industry_training_service, "publish_training", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/trainings/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_publish_missing_fields_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_training_service,
            "publish_training",
            side_effect=industry_training_service.PublishValidationError(["location", "work_mode"]),
        ),
    ):
        resp = client.post(
            f"/api/v1/trainings/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422
    assert "location" in resp.json()["detail"]


def test_publish_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_training_service,
            "publish_training",
            side_effect=industry_training_service.InvalidStatusTransitionError("ARCHIVED", "PUBLISHED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/trainings/{uuid4()}/publish", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_close_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_training_service, "close_training", return_value=None),
    ):
        resp = client.post(f"/api/v1/trainings/{uuid4()}/close", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_archive_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_training_service, "archive_training", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/trainings/{uuid4()}/archive", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_archive_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_training_service,
            "archive_training",
            side_effect=industry_training_service.InvalidStatusTransitionError("ARCHIVED", "ARCHIVED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/trainings/{uuid4()}/archive", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Service layer
# ============================================================


def test_create_forces_draft_and_owner_and_drops_junk():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-1"}]

    with patch.object(industry_training_service, "get_training", return_value=_row(id="new-1")):
        industry_training_service.create_training(
            supabase,
            "industry-1",
            {"title": "T", "description": "D", "status": "PUBLISHED", "industry_id": "attacker", "id": "x"},
        )

    inserted = supabase.table.return_value.insert.call_args_list[0].args[0]
    assert inserted["status"] == "DRAFT"
    assert inserted["industry_id"] == "industry-1"
    assert "id" not in inserted


def test_update_never_writes_status():
    supabase = MagicMock()
    with patch.object(
        industry_training_service,
        "get_training",
        side_effect=[_row(id="training-1"), _row(id="training-1", title="Updated")],
    ):
        industry_training_service.update_training(
            supabase, "industry-1", "training-1", {"title": "Updated", "status": "PUBLISHED"}
        )
    updated = supabase.table.return_value.update.call_args.args[0]
    assert updated == {"title": "Updated"}


def test_update_returns_none_when_not_owned():
    supabase = MagicMock()
    with patch.object(industry_training_service, "get_training", return_value=None):
        result = industry_training_service.update_training(
            supabase, "industry-1", "training-x", {"title": "Updated"}
        )
    assert result is None
    supabase.table.return_value.update.assert_not_called()


def test_publish_blocks_when_required_fields_missing():
    supabase = MagicMock()
    with patch.object(
        industry_training_service, "get_training", return_value=_row(location=None, work_mode=None)
    ):
        try:
            industry_training_service.publish_training(supabase, "industry-1", "training-1")
            missing = None
        except industry_training_service.PublishValidationError as exc:
            missing = exc.missing
    assert missing is not None
    assert "location" in missing and "work_mode" in missing
    supabase.table.return_value.update.assert_not_called()


def test_publish_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        industry_training_service,
        "get_training",
        side_effect=[_row(status="DRAFT"), _row(status="PUBLISHED")],
    ):
        result = industry_training_service.publish_training(supabase, "industry-1", "training-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "PUBLISHED"}
    assert result["status"] == "PUBLISHED"


def test_publish_rejects_from_archived():
    supabase = MagicMock()
    with patch.object(industry_training_service, "get_training", return_value=_row(status="ARCHIVED")):
        try:
            industry_training_service.publish_training(supabase, "industry-1", "training-1")
            raised = False
        except industry_training_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_close_only_from_published():
    supabase = MagicMock()
    with patch.object(industry_training_service, "get_training", return_value=_row(status="DRAFT")):
        try:
            industry_training_service.close_training(supabase, "industry-1", "training-1")
            raised = False
        except industry_training_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_archive_allowed_from_draft():
    supabase = MagicMock()
    with patch.object(
        industry_training_service,
        "get_training",
        side_effect=[_row(status="DRAFT"), _row(status="ARCHIVED")],
    ):
        result = industry_training_service.archive_training(supabase, "industry-1", "training-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "ARCHIVED"}
    assert result["status"] == "ARCHIVED"


def test_archive_rejects_when_already_archived():
    supabase = MagicMock()
    with patch.object(industry_training_service, "get_training", return_value=_row(status="ARCHIVED")):
        try:
            industry_training_service.archive_training(supabase, "industry-1", "training-1")
            raised = False
        except industry_training_service.InvalidStatusTransitionError:
            raised = True
    assert raised


# ============================================================
# No service-role anywhere on this path
# ============================================================


def test_training_modules_do_not_use_service_role():
    assert not hasattr(industry_training_service, "get_supabase")
    assert not hasattr(training_routes, "get_supabase")
    assert hasattr(training_routes, "build_user_client")
