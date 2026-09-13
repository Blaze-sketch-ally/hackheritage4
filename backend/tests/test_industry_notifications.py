"""Tests for the Industry Notifications API: /api/v1/industry/notifications.

Exact mirror of tests/test_student_notifications.py's route-level shape,
for the Industry side (app.api.industry_notifications /
app.services.industry_notification_service /
database/migrations/055_industry_notifications.sql).
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import industry_notification_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_NID = "11111111-1111-1111-1111-111111111111"


def _row(**overrides):
    row = {
        "id": _NID,
        "type": "NEW_APPLICATION",
        "title": "New workshop application",
        "body": "Ada Lovelace applied to your workshop.",
        "related_entity_type": "WORKSHOP_APPLICATION",
        "related_entity_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "read_at": None,
        "created_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _shaped(**overrides):
    row = svc._shape(_row())
    row.update(overrides)
    return row


_ENDPOINTS = [
    ("get", "/api/v1/industry/notifications"),
    ("get", f"/api/v1/industry/notifications/{_NID}"),
    ("patch", f"/api/v1/industry/notifications/{_NID}/read"),
    ("patch", f"/api/v1/industry/notifications/{_NID}/unread"),
    ("post", "/api/v1/industry/notifications/read-all"),
]


def _call(method, url, *, headers=None):
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


def test_list_returns_caller_notifications_and_unread_count():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "list_notifications", return_value=[_shaped()]),
        patch.object(svc, "unread_count", return_value=3),
    ):
        resp = client.get(
            "/api/v1/industry/notifications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 3
    assert body["notifications"][0]["id"] == _NID
    assert body["notifications"][0]["is_read"] is False


def test_mark_read_toggles_and_returns_updated_row():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "set_read", return_value=_shaped(read_at="2026-09-02T00:00:00Z", is_read=True)),
    ):
        resp = client.patch(
            f"/api/v1/industry/notifications/{_NID}/read",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


def test_get_notification_not_owned_is_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-2"),
        patch.object(svc, "get_notification", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/industry/notifications/{_NID}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_mark_all_read_returns_updated_count():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "mark_all_read", return_value=5),
    ):
        resp = client.post(
            "/api/v1/industry/notifications/read-all", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 5


# ============================================================
# Service-level: shape / unread semantics
# ============================================================


def test_shape_derives_is_read_from_read_at():
    assert svc._shape(_row(read_at=None))["is_read"] is False
    assert svc._shape(_row(read_at="2026-09-02T00:00:00Z"))["is_read"] is True


def test_clamp_limit_bounds_to_default_and_max():
    assert svc._clamp_limit(None) == svc.DEFAULT_LIMIT
    assert svc._clamp_limit(0) == svc.DEFAULT_LIMIT
    assert svc._clamp_limit(10_000) == svc.MAX_LIMIT
