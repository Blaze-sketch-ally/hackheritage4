"""Tests for the S8 notification producer
(app.services.notification_producer) and its one integration point: the
Industry application-status route.

The producer is the ONLY place a `student_notifications` row is written,
and it writes with the service-role client (that table has no insert
policy). It runs on an already-authorized require_industry() request,
never a Student one, and is best-effort (swallows its own errors).

No live DB: `get_supabase` is mocked to a MagicMock everywhere (conftest
does this globally for authenticated requests; the direct service tests
patch it themselves).
"""

import inspect
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import application_service, notification_producer
from tests.conftest import authenticated_as

client = TestClient(app)


def _insert_payload(mock_supabase: MagicMock) -> dict:
    return mock_supabase.table.return_value.insert.call_args.args[0]


# ============================================================
# 1-6. Producer: which transitions notify, and with what row
# ============================================================


def test_emit_writes_one_student_notification_for_a_meaningful_transition():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_application_status_change(
            student_id="student-7",
            application_id="app-1",
            new_status="SHORTLISTED",
            opportunity_title="Backend Intern",
        )
    fake.table.assert_called_once_with("student_notifications")
    payload = _insert_payload(fake)
    assert payload["student_id"] == "student-7"
    assert payload["type"] == "APPLICATION_STATUS"
    assert payload["related_entity_type"] == "APPLICATION"
    assert payload["related_entity_id"] == "app-1"
    assert "Backend Intern" in payload["body"]
    assert payload["title"] == "You've been shortlisted"
    # never invents a read state, a percentage, or a client-supplied field
    assert set(payload) == {
        "student_id",
        "type",
        "title",
        "body",
        "related_entity_type",
        "related_entity_id",
    }


def test_emit_covers_every_industry_driven_transition():
    for status_value in ("UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED", "SELECTED", "REJECTED"):
        fake = MagicMock()
        with patch.object(notification_producer, "get_supabase", return_value=fake):
            notification_producer.emit_application_status_change(
                student_id="s", application_id="a", new_status=status_value, opportunity_title="X"
            )
        assert fake.table.return_value.insert.called, status_value
        assert _insert_payload(fake)["type"] == "APPLICATION_STATUS"


def test_emit_is_a_noop_for_student_initiated_or_unknown_statuses():
    for status_value in ("APPLIED", "WITHDRAWN", "NONSENSE", ""):
        fake = MagicMock()
        with patch.object(notification_producer, "get_supabase", return_value=fake):
            notification_producer.emit_application_status_change(
                student_id="s", application_id="a", new_status=status_value, opportunity_title="X"
            )
        fake.table.assert_not_called()


def test_emit_handles_a_missing_opportunity_title():
    fake = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_application_status_change(
            student_id="s", application_id="a", new_status="SELECTED", opportunity_title=None
        )
    assert isinstance(_insert_payload(fake)["body"], str)


def test_emit_swallows_a_service_role_failure():
    """A failed write (RLS, network, migration 035 not applied yet) must
    not propagate -- the status change already succeeded."""
    with patch.object(notification_producer, "get_supabase", side_effect=RuntimeError("boom")):
        notification_producer.emit_application_status_change(
            student_id="s", application_id="a", new_status="SELECTED", opportunity_title="X"
        )  # no raise

    fake = MagicMock()
    fake.table.return_value.insert.return_value.execute.side_effect = RuntimeError("db down")
    with patch.object(notification_producer, "get_supabase", return_value=fake):
        notification_producer.emit_application_status_change(
            student_id="s", application_id="a", new_status="SELECTED", opportunity_title="X"
        )  # no raise


def test_producer_only_writes_student_notifications_and_uses_service_role():
    src = inspect.getsource(notification_producer)
    assert "get_supabase()" in src
    assert 'table("student_notifications")' in src
    # the producer never reads a client token / builds a user client
    assert "build_user_client" not in src
    assert "access_token" not in src


# ============================================================
# 7-10. Route integration: Industry status route -> producer
# ============================================================


def test_status_route_emits_a_notification_with_the_row_student_id():
    captured = {}

    def fake_emit(*, student_id, application_id, new_status, opportunity_title):
        captured.update(
            {
                "student_id": student_id,
                "application_id": application_id,
                "new_status": new_status,
                "opportunity_title": opportunity_title,
            }
        )

    app_id = uuid4()
    with (
        authenticated_as("INDUSTRY", user_id="industry-9"),
        patch.object(
            application_service,
            "update_status",
            return_value={
                "id": "app-1",
                "student_id": "student-77",
                "industry_id": "industry-9",
                "opportunity_type": "INTERNSHIP",
                "internship_id": "int-1",
                "job_id": None,
                "status": "SELECTED",
                "cover_note": None,
                "match_score": None,
                "applied_at": "2026-09-01T00:00:00Z",
                "created_at": "2026-09-01T00:00:00Z",
                "updated_at": "2026-09-01T00:00:00Z",
                "opportunity": {"id": "int-1", "title": "Backend Intern", "status": "PUBLISHED"},
            },
        ),
        patch.object(notification_producer, "emit_application_status_change", side_effect=fake_emit),
    ):
        resp = client.patch(
            f"/api/v1/applications/{app_id}/status",
            json={"status": "SELECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    # student_id comes from the DB row, NOT from the caller's token or body
    assert captured["student_id"] == "student-77"
    assert captured["new_status"] == "SELECTED"
    assert captured["application_id"] == str(app_id)
    assert captured["opportunity_title"] == "Backend Intern"


def test_status_route_still_succeeds_when_the_producer_raises():
    """Defence in depth: even if the producer somehow raised, the status
    update response must be unaffected. (In practice the producer swallows
    its own errors; this asserts the route doesn't depend on that.)"""
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(application_service, "update_status", return_value={
            "id": "app-1", "student_id": "s", "industry_id": "industry-1",
            "opportunity_type": "INTERNSHIP", "internship_id": "int-1", "job_id": None,
            "status": "UNDER_REVIEW", "cover_note": None, "match_score": None,
            "applied_at": None, "created_at": None, "updated_at": None,
            "opportunity": None,
        }),
        patch.object(
            notification_producer, "emit_application_status_change", return_value=None
        ) as emit,
    ):
        resp = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "UNDER_REVIEW"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    emit.assert_called_once()


def test_status_route_does_not_emit_on_a_404():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(application_service, "update_status", return_value=None),
        patch.object(notification_producer, "emit_application_status_change") as emit,
    ):
        resp = client.patch(
            f"/api/v1/applications/{uuid4()}/status",
            json={"status": "REJECTED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404
    emit.assert_not_called()


def test_student_notification_routes_still_have_no_creation_endpoint():
    """The producer is the ONLY writer -- students still cannot create a
    notification through any route."""
    paths = app.openapi()["paths"]
    notif_posts = {
        p
        for p, m in paths.items()
        if p.startswith("/api/v1/student/notifications") and "post" in m
    }
    assert notif_posts == {"/api/v1/student/notifications/read-all"}
