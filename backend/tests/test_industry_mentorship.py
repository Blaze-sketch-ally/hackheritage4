"""Tests for Industry mentorship opportunity management (Phase 10D):
/api/v1/mentorship-opportunities.

Route tests mock app.services.industry_mentorship_service and use
tests.conftest.authenticated_as, exactly like tests/test_industry_workshops.py.
Service tests drive the functions with a MagicMock Supabase client and
patched helpers -- no live project or real token.

Unlike industry_project/industry_training/industry_workshop,
`location`/`work_mode`/`duration_months`/`capacity` are REQUIRED on
create (matching the migration's NOT NULL columns), so _create_body()
always includes them and there are dedicated tests for each being
rejected when missing.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import industry_mentorship_opportunities as mentorship_routes
from app.main import app
from app.services import industry_mentorship_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _row(**overrides):
    row = {
        "id": "mentorship-1",
        "industry_id": "industry-1",
        "title": "Frontend Career Mentorship",
        "description": "A 3-month 1:1 mentorship on frontend engineering.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "duration_months": 3,
        "capacity": 5,
        "eligibility_criteria": None,
        "application_deadline": "2026-12-01T00:00:00Z",
        "start_date": "2026-09-15",
        "status": "DRAFT",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {
        "title": "Frontend Career Mentorship",
        "description": "A 3-month 1:1 mentorship on frontend engineering.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "duration_months": 3,
        "capacity": 5,
    }
    body.update(overrides)
    return body


# ============================================================
# Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/mentorship-opportunities"),
    ("post", "/api/v1/mentorship-opportunities"),
    ("get", f"/api/v1/mentorship-opportunities/{uuid4()}"),
    ("put", f"/api/v1/mentorship-opportunities/{uuid4()}"),
    ("post", f"/api/v1/mentorship-opportunities/{uuid4()}/publish"),
    ("post", f"/api/v1/mentorship-opportunities/{uuid4()}/close"),
    ("post", f"/api/v1/mentorship-opportunities/{uuid4()}/archive"),
]


def _call(method: str, url: str, *, headers=None):
    if method in {"post", "put"}:
        return getattr(client, method)(url, json=_create_body(), headers=headers)
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


def test_router_is_registered_under_expected_prefix():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/mentorship-opportunities", headers={"Authorization": "Bearer token"}
        )
    # Not a 404 -- the router exists and is mounted; the actual data call
    # goes through to the (unmocked here) service, so this just proves
    # routing/registration, not behavior.
    assert resp.status_code != 404


# ============================================================
# List
# ============================================================


def test_list_returns_only_callers_mentorships():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, search=None):
        captured.update({"industry_id": industry_id, "status": status, "search": search})
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_mentorship_service, "list_mentorships", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/mentorship-opportunities?status=PUBLISHED&search=frontend",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "PUBLISHED", "search": "frontend"}
    assert resp.json()["mentorship_opportunities"][0]["id"] == "mentorship-1"


def test_list_rejects_unknown_status_filter():
    with authenticated_as("INDUSTRY"):
        resp = client.get(
            "/api/v1/mentorship-opportunities?status=NONSENSE",
            headers={"Authorization": "Bearer token"},
        )
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
        patch.object(industry_mentorship_service, "create_mentorship", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/mentorship-opportunities",
            json=_create_body(),
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
            "/api/v1/mentorship-opportunities",
            json=_create_body(industry_id="attacker-owned"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_status():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities",
            json=_create_body(status="PUBLISHED"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_missing_title():
    body = _create_body()
    del body["title"]
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities", json=body, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_missing_location():
    body = _create_body()
    del body["location"]
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities", json=body, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_missing_work_mode():
    body = _create_body()
    del body["work_mode"]
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities", json=body, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_missing_duration_months():
    body = _create_body()
    del body["duration_months"]
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities", json=body, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_missing_capacity():
    body = _create_body()
    del body["capacity"]
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities", json=body, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_invalid_duration():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities",
            json=_create_body(duration_months=48),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_zero_capacity():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities",
            json=_create_body(capacity=0),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_unknown_work_mode():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/mentorship-opportunities",
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
        patch.object(industry_mentorship_service, "get_mentorship", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/mentorship-opportunities/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_update_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(industry_mentorship_service, "update_mentorship", return_value=None),
    ):
        resp = client.put(
            f"/api/v1/mentorship-opportunities/{uuid4()}",
            json={"title": "New title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_update_rejects_status_field():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            f"/api/v1/mentorship-opportunities/{uuid4()}",
            json={"status": "PUBLISHED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_passes_owner_id_to_service():
    captured = {}

    def fake_update(_client, industry_id, mentorship_id, data):
        captured["industry_id"] = industry_id
        return _row()

    with (
        authenticated_as("INDUSTRY", user_id="industry-7"),
        patch.object(industry_mentorship_service, "update_mentorship", side_effect=fake_update),
    ):
        resp = client.put(
            f"/api/v1/mentorship-opportunities/{uuid4()}",
            json={"title": "Updated"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["industry_id"] == "industry-7"


def test_update_allows_partial_body_without_required_fields():
    """PUT is a partial update -- omitting location/work_mode/etc. must
    not be treated as clearing a NOT NULL column; MentorshipUpdate makes
    them optional so exclude_unset keeps them untouched."""
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_mentorship_service, "update_mentorship", return_value=_row()),
    ):
        resp = client.put(
            f"/api/v1/mentorship-opportunities/{uuid4()}",
            json={"title": "Updated title only"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200


# ============================================================
# Lifecycle endpoints -- ownership + error mapping
# ============================================================


def test_publish_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(industry_mentorship_service, "publish_mentorship", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/mentorship-opportunities/{uuid4()}/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_publish_missing_fields_maps_to_422():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_mentorship_service,
            "publish_mentorship",
            side_effect=industry_mentorship_service.PublishValidationError(["application_deadline"]),
        ),
    ):
        resp = client.post(
            f"/api/v1/mentorship-opportunities/{uuid4()}/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422
    assert "application_deadline" in resp.json()["detail"]


def test_publish_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_mentorship_service,
            "publish_mentorship",
            side_effect=industry_mentorship_service.InvalidStatusTransitionError(
                "ARCHIVED", "PUBLISHED"
            ),
        ),
    ):
        resp = client.post(
            f"/api/v1/mentorship-opportunities/{uuid4()}/publish",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_close_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_mentorship_service, "close_mentorship", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/mentorship-opportunities/{uuid4()}/close",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_archive_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_mentorship_service, "archive_mentorship", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/mentorship-opportunities/{uuid4()}/archive",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_archive_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_mentorship_service,
            "archive_mentorship",
            side_effect=industry_mentorship_service.InvalidStatusTransitionError(
                "ARCHIVED", "ARCHIVED"
            ),
        ),
    ):
        resp = client.post(
            f"/api/v1/mentorship-opportunities/{uuid4()}/archive",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


# ============================================================
# Service layer
# ============================================================


def test_create_forces_draft_and_owner_and_drops_junk():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-1"}]

    with patch.object(
        industry_mentorship_service, "get_mentorship", return_value=_row(id="new-1")
    ):
        industry_mentorship_service.create_mentorship(
            supabase,
            "industry-1",
            {
                "title": "T",
                "description": "D",
                "location": "Remote",
                "work_mode": "REMOTE",
                "duration_months": 3,
                "capacity": 5,
                "status": "PUBLISHED",
                "industry_id": "attacker",
                "id": "x",
            },
        )

    inserted = supabase.table.return_value.insert.call_args_list[0].args[0]
    assert inserted["status"] == "DRAFT"
    assert inserted["industry_id"] == "industry-1"
    assert "id" not in inserted


def test_update_never_writes_status():
    supabase = MagicMock()
    with patch.object(
        industry_mentorship_service,
        "get_mentorship",
        side_effect=[_row(id="mentorship-1"), _row(id="mentorship-1", title="Updated")],
    ):
        industry_mentorship_service.update_mentorship(
            supabase, "industry-1", "mentorship-1", {"title": "Updated", "status": "PUBLISHED"}
        )
    updated = supabase.table.return_value.update.call_args.args[0]
    assert updated == {"title": "Updated"}


def test_update_returns_none_when_not_owned():
    supabase = MagicMock()
    with patch.object(industry_mentorship_service, "get_mentorship", return_value=None):
        result = industry_mentorship_service.update_mentorship(
            supabase, "industry-1", "mentorship-x", {"title": "Updated"}
        )
    assert result is None
    supabase.table.return_value.update.assert_not_called()


def test_publish_blocks_when_required_fields_missing():
    supabase = MagicMock()
    with patch.object(
        industry_mentorship_service, "get_mentorship", return_value=_row(application_deadline=None)
    ):
        try:
            industry_mentorship_service.publish_mentorship(supabase, "industry-1", "mentorship-1")
            missing = None
        except industry_mentorship_service.PublishValidationError as exc:
            missing = exc.missing
    assert missing == ["application_deadline"]
    supabase.table.return_value.update.assert_not_called()


def test_publish_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        industry_mentorship_service,
        "get_mentorship",
        side_effect=[_row(status="DRAFT"), _row(status="PUBLISHED")],
    ):
        result = industry_mentorship_service.publish_mentorship(supabase, "industry-1", "mentorship-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "PUBLISHED"}
    assert result["status"] == "PUBLISHED"


def test_publish_rejects_from_archived():
    supabase = MagicMock()
    with patch.object(
        industry_mentorship_service, "get_mentorship", return_value=_row(status="ARCHIVED")
    ):
        try:
            industry_mentorship_service.publish_mentorship(supabase, "industry-1", "mentorship-1")
            raised = False
        except industry_mentorship_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_close_only_from_published():
    supabase = MagicMock()
    with patch.object(industry_mentorship_service, "get_mentorship", return_value=_row(status="DRAFT")):
        try:
            industry_mentorship_service.close_mentorship(supabase, "industry-1", "mentorship-1")
            raised = False
        except industry_mentorship_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_archive_allowed_from_draft():
    supabase = MagicMock()
    with patch.object(
        industry_mentorship_service,
        "get_mentorship",
        side_effect=[_row(status="DRAFT"), _row(status="ARCHIVED")],
    ):
        result = industry_mentorship_service.archive_mentorship(supabase, "industry-1", "mentorship-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "ARCHIVED"}
    assert result["status"] == "ARCHIVED"


def test_archive_rejects_when_already_archived():
    supabase = MagicMock()
    with patch.object(
        industry_mentorship_service, "get_mentorship", return_value=_row(status="ARCHIVED")
    ):
        try:
            industry_mentorship_service.archive_mentorship(supabase, "industry-1", "mentorship-1")
            raised = False
        except industry_mentorship_service.InvalidStatusTransitionError:
            raised = True
    assert raised


# ============================================================
# No service-role anywhere on this path
# ============================================================


def test_mentorship_modules_do_not_use_service_role():
    assert not hasattr(industry_mentorship_service, "get_supabase")
    assert not hasattr(mentorship_routes, "get_supabase")
    assert hasattr(mentorship_routes, "build_user_client")
