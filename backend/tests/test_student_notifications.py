"""Tests for the Student Notifications API: /api/v1/student/notifications.

Route tests mock app.services.student_notification_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_events.py
/ tests/test_student_learning.py. Service tests drive the functions with a
MagicMock Supabase client -- no live project or real token. Nothing here
claims real DB behaviour: RLS + the freeze trigger on
`student_notifications` (035_student_notifications.sql) are the real
ownership / immutability boundary and are asserted from the migration SQL,
not a live database.
"""

import inspect
import re
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import student_notification_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_NID = "11111111-1111-1111-1111-111111111111"
_NID2 = "22222222-2222-2222-2222-222222222222"


def _row(**overrides):
    row = {
        "id": _NID,
        "type": "APPLICATION_STATUS",
        "title": "Application update",
        "body": "Your application moved to Under Review.",
        "related_entity_type": "APPLICATION",
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


# ============================================================
# 1-2. Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/student/notifications"),
    ("get", f"/api/v1/student/notifications/{_NID}"),
    ("patch", f"/api/v1/student/notifications/{_NID}/read"),
    ("patch", f"/api/v1/student/notifications/{_NID}/unread"),
    ("post", "/api/v1/student/notifications/read-all"),
]


def _call(method, url, *, headers=None):
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# 3. No creation endpoint exists
# ============================================================


def test_there_is_no_student_notification_creation_endpoint():
    paths = app.openapi()["paths"]
    assert "/api/v1/student/notifications" in paths
    # the collection endpoint is GET-only: no POST to create a notification
    assert set(paths["/api/v1/student/notifications"]) == {"get"}
    # the ONLY POST anywhere under the notifications tree is the bounded
    # "mark all read" action -- never a create
    notif_posts = {
        p
        for p, method_map in paths.items()
        if p.startswith("/api/v1/student/notifications") and "post" in method_map
    }
    assert notif_posts == {"/api/v1/student/notifications/read-all"}


def test_router_registered_and_only_intended_methods():
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/student/notifications/{notification_id}"]) == {"get"}
    assert set(paths["/api/v1/student/notifications/{notification_id}/read"]) == {"patch"}
    assert set(paths["/api/v1/student/notifications/{notification_id}/unread"]) == {"patch"}


# ============================================================
# 4-9. List
# ============================================================


def test_list_returns_shaped_rows_and_unread_count():
    def fake_list(_client, student_id, **kwargs):
        assert student_id == "student-9"
        return [_shaped(), _shaped(id=_NID2, read_at="2026-09-02T00:00:00Z", is_read=True)]

    with (
        authenticated_as("STUDENT", user_id="student-9"),
        patch.object(svc, "list_notifications", side_effect=fake_list),
        patch.object(svc, "unread_count", return_value=1),
    ):
        resp = client.get(
            "/api/v1/student/notifications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 1
    assert [n["is_read"] for n in body["notifications"]] == [False, True]
    # internal columns aren't invented / leaked
    assert set(body["notifications"][0]) == {
        "id",
        "type",
        "title",
        "body",
        "related_entity_type",
        "related_entity_id",
        "is_read",
        "read_at",
        "created_at",
    }


def test_list_passes_unread_and_limit_through():
    captured = {}

    def fake_list(_client, student_id, **kwargs):
        captured.update({"student_id": student_id, **kwargs})
        return []

    with (
        authenticated_as("STUDENT", user_id="s-1"),
        patch.object(svc, "list_notifications", side_effect=fake_list),
        patch.object(svc, "unread_count", return_value=0),
    ):
        resp = client.get(
            "/api/v1/student/notifications?unread=true&limit=10",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"student_id": "s-1", "unread_only": True, "limit": 10}


def test_list_rejects_out_of_range_limit():
    with authenticated_as("STUDENT"):
        assert (
            client.get(
                "/api/v1/student/notifications?limit=0",
                headers={"Authorization": "Bearer token"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/student/notifications?limit=100000",
                headers={"Authorization": "Bearer token"},
            ).status_code
            == 422
        )


def test_service_list_filters_by_student_and_orders_newest_first():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_notifications(supabase, "student-1", unread_only=True, limit=5)
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("student_id", "student-1") in eq_calls
    q.is_.assert_any_call("read_at", "null")
    q.order.assert_any_call("created_at", desc=True)
    q.limit.assert_any_call(5)


def test_service_list_clamps_limit():
    assert svc._clamp_limit(None) == svc.DEFAULT_LIMIT
    assert svc._clamp_limit(0) == svc.DEFAULT_LIMIT
    assert svc._clamp_limit(-3) == svc.DEFAULT_LIMIT
    assert svc._clamp_limit(999) == svc.MAX_LIMIT
    assert svc._clamp_limit(7) == 7


def test_service_unread_count_reads_count_field():
    supabase = MagicMock()
    q = _fluent([])
    q.execute.return_value.count = 4
    supabase.table.return_value = q
    assert svc.unread_count(supabase, "student-1") == 4
    q.is_.assert_any_call("read_at", "null")


# ============================================================
# 10-13. Detail + IDOR
# ============================================================


def test_get_detail_returns_row():
    with (
        authenticated_as("STUDENT", user_id="s-1"),
        patch.object(svc, "get_notification", return_value=_shaped()),
    ):
        resp = client.get(
            f"/api/v1/student/notifications/{_NID}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Application update"


def test_get_detail_404_when_not_the_callers():
    """None from the service -- another student's notification is
    indistinguishable from one that doesn't exist, even to a caller who
    knows the UUID (IDOR)."""
    with (
        authenticated_as("STUDENT", user_id="attacker"),
        patch.object(svc, "get_notification", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/student/notifications/{uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404
    # the service was asked for the row *as the caller*, never a client id
    assert mock_get.call_args.args[1] == "attacker"


def test_get_detail_rejects_non_uuid():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/notifications/not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_get_filters_id_and_student():
    supabase = MagicMock()
    q = _fluent(None)
    supabase.table.return_value = q
    assert svc.get_notification(supabase, "student-1", _NID) is None
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("id", _NID) in eq_calls
    assert ("student_id", "student-1") in eq_calls


# ============================================================
# 14-19. Mark read / unread / read-all
# ============================================================


def test_mark_read_uses_caller_id_not_a_client_value():
    captured = {}

    def fake_set(_client, student_id, notification_id, *, read):
        captured.update(
            {"student_id": student_id, "notification_id": notification_id, "read": read}
        )
        return _shaped(read_at="2026-09-02T00:00:00Z", is_read=True)

    with (
        authenticated_as("STUDENT", user_id="s-42"),
        patch.object(svc, "set_read", side_effect=fake_set),
    ):
        resp = client.patch(
            f"/api/v1/student/notifications/{_NID}/read",
            json={"student_id": "victim", "is_read": False, "title": "hacked"},
            headers={"Authorization": "Bearer token"},
        )
    # body is ignored entirely -- the route takes no request model
    assert resp.status_code == 200
    assert captured == {"student_id": "s-42", "notification_id": _NID, "read": True}
    assert resp.json()["is_read"] is True


def test_mark_unread_sets_read_false():
    captured = {}

    def fake_set(_client, student_id, notification_id, *, read):
        captured["read"] = read
        return _shaped()

    with (
        authenticated_as("STUDENT", user_id="s-1"),
        patch.object(svc, "set_read", side_effect=fake_set),
    ):
        resp = client.patch(
            f"/api/v1/student/notifications/{_NID}/unread",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["read"] is False


def test_mark_read_404_for_another_students_notification():
    with (
        authenticated_as("STUDENT", user_id="attacker"),
        patch.object(svc, "set_read", return_value=None),
    ):
        resp = client.patch(
            f"/api/v1/student/notifications/{uuid4()}/read",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_service_set_read_only_writes_read_at():
    supabase = MagicMock()
    with patch.object(svc, "get_notification", side_effect=[_shaped(), _shaped(is_read=True)]):
        upd = _fluent([_row(read_at="x")])
        supabase.table.return_value = upd
        svc.set_read(supabase, "s-1", _NID, read=True)
    payload = supabase.table.return_value.update.call_args.args[0]
    assert set(payload) == {"read_at"}


def test_service_set_read_is_noop_when_already_in_target_state():
    supabase = MagicMock()
    with patch.object(svc, "get_notification", return_value=_shaped(is_read=True, read_at="t")):
        result = svc.set_read(supabase, "s-1", _NID, read=True)
    supabase.table.return_value.update.assert_not_called()
    assert result["is_read"] is True


def test_service_mark_all_read_filters_student_and_unread():
    supabase = MagicMock()
    q = _fluent([_row(), _row(id=_NID2)])
    supabase.table.return_value = q
    assert svc.mark_all_read(supabase, "s-1") == 2
    payload = q.update.call_args.args[0]
    assert set(payload) == {"read_at"}
    q.eq.assert_any_call("student_id", "s-1")
    q.is_.assert_any_call("read_at", "null")


# ============================================================
# 20-24. Service / architecture security
# ============================================================


def test_routes_never_declare_an_owner_id_parameter():
    from app.api import student_notifications as routes

    for name in dir(routes):
        fn = getattr(routes, name)
        if callable(fn) and getattr(fn, "__module__", "") == routes.__name__:
            params = set(inspect.signature(fn).parameters) if hasattr(fn, "__code__") else set()
            for banned in ("student_id", "recipient_id", "user_id", "owner_id"):
                assert banned not in params, f"{name} must not take a {banned} parameter"


def test_routes_take_no_request_body_model():
    """mark read / unread / read-all accept nothing from the client body --
    no field of a notification is client-settable."""
    from app.api import student_notifications as routes

    for fn in (
        routes.mark_notification_read,
        routes.mark_notification_unread,
        routes.mark_all_notifications_read,
    ):
        params = inspect.signature(fn).parameters
        assert "body" not in params and "payload" not in params, fn.__name__


def test_modules_do_not_use_service_role():
    from app.api import student_notifications as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_service_only_touches_student_notifications_table():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    tables = set(re.findall(r'\.table\("([a-z_]+)"\)', compact))
    assert tables == {"student_notifications"}, tables


def test_service_never_inserts_or_deletes():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    for m in re.finditer(r'\.table\("student_notifications"\)(\.[a-z_]+\()', compact):
        assert m.group(1) not in (".insert(", ".delete(", ".upsert("), m.group(1)


def test_routes_pass_only_current_user_id_to_the_service():
    from app.api import student_notifications as routes

    code = re.sub(r'""".*?"""', "", inspect.getsource(routes), flags=re.DOTALL)
    for call in re.findall(
        r"student_notification_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")
    ):
        assert "current_user.id" in call, call
        for banned in ("student_id=", "recipient_id=", "user_id="):
            assert banned not in call, call


# ============================================================
# 25-33. Migration 035 schema guard (read from SQL, no live DB)
# ============================================================

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
_M035 = (_MIGRATIONS_DIR / "035_student_notifications.sql").read_text(encoding="utf-8")
_M035_CODE = "\n".join(
    ln for ln in _M035.splitlines() if not ln.strip().startswith("--")
).lower()


def test_migration_035_exists_and_numbering_is_contiguous():
    names = sorted(p.name for p in _MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    numbers = sorted(int(n[:3]) for n in names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap: {numbers}"
    assert 35 in numbers
    assert "035_student_notifications.sql" in names
    # the placeholder is left exactly as-is, not superseded in place
    assert "010_notifications.sql" in names
    assert (
        "not implemented yet"
        in (_MIGRATIONS_DIR / "010_notifications.sql").read_text(encoding="utf-8").lower()
    )


def test_migration_035_creates_one_table_with_pk_and_fk():
    assert "create table if not exists student_notifications" in _M035_CODE
    assert "id uuid primary key default gen_random_uuid()" in _M035_CODE
    assert "student_id uuid not null references profiles (id) on delete cascade" in _M035_CODE


def test_migration_035_type_and_related_entity_constraints():
    assert "check (type in (" in _M035_CODE
    for t in ("application_status", "interview", "assessment", "learning", "mentorship", "event", "system"):
        assert f"'{t}'" in _M035_CODE
    assert "check (related_entity_type in (" in _M035_CODE
    # a pointer is all-or-nothing
    assert "student_notifications_related_entity_paired" in _M035_CODE


def test_migration_035_read_state_column():
    assert "read_at timestamptz" in _M035_CODE
    # notifications are immutable except read_at -> no updated_at column,
    # and set_updated_at is deliberately NOT attached
    assert "updated_at" not in _M035_CODE
    assert "set_updated_at" not in _M035_CODE


def test_migration_035_indexes():
    assert "student_notifications_student_created_idx" in _M035_CODE
    assert "on student_notifications (student_id, created_at desc)" in _M035_CODE
    assert "student_notifications_unread_idx" in _M035_CODE
    assert "where read_at is null" in _M035_CODE


def test_migration_035_rls_enabled_select_and_update_only():
    assert "alter table student_notifications enable row level security" in _M035_CODE
    assert "for select" in _M035_CODE
    assert "for update" in _M035_CODE
    # NO insert policy (system-only writes) and NO delete policy
    assert "for insert" not in _M035_CODE
    assert "for delete" not in _M035_CODE


def test_migration_035_ownership_predicate():
    assert _M035_CODE.count("auth.uid() = student_id and public.is_student(auth.uid())") >= 2


def test_migration_035_freeze_trigger_pins_every_content_column():
    assert "before update on student_notifications" in _M035_CODE
    assert "enforce_student_notification_immutability" in _M035_CODE
    # service_role steps aside, matching 002/023/032
    assert "current_setting('role', true) = 'service_role'" in _M035_CODE
    for col in ("student_id", "type", "title", "body", "related_entity_type", "related_entity_id", "created_at"):
        assert f"new.{col} is distinct from old.{col}" in _M035_CODE
    # read_at is the ONE column NOT frozen
    assert "new.read_at is distinct from old.read_at" not in _M035_CODE


def test_migration_035_is_additive_and_non_destructive():
    assert "drop table" not in _M035_CODE
    for existing in ("profiles", "applications", "assessments", "learning_resources"):
        assert f"alter table {existing} " not in _M035_CODE
    assert "create or replace function public.set_updated_at" not in _M035_CODE


def test_migration_035_not_applied_marker_is_a_human_step():
    """This suite reads the SQL; it does not and cannot apply it. The
    phase contract requires the migration to stay unapplied."""
    assert _M035  # sanity: file is present and non-empty


# ============================================================
# helpers
# ============================================================


def _fluent(final_data):
    q = MagicMock()
    for method in ("select", "eq", "in_", "is_", "order", "limit", "ilike", "maybe_single", "update"):
        getattr(q, method).return_value = q
    q.execute.return_value.data = final_data
    q.execute.return_value.count = len(final_data) if isinstance(final_data, list) else 0
    return q
