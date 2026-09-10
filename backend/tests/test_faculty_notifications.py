"""Tests for the Faculty Notifications API: /api/v1/faculty/notifications,
and its producer side (app.services.faculty_notification_producer).

Mirrors tests/test_student_notifications.py's own structure and
conventions exactly. Route tests mock app.services.faculty_notification_service
and use tests.conftest.authenticated_as. Service tests drive the functions
with a MagicMock Supabase client -- no live project or real token. Nothing
here claims real DB behaviour: RLS + the freeze trigger on
`faculty_notifications` (066_faculty_notifications.sql) are the real
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
from app.services import faculty_notification_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_NID = "11111111-1111-1111-1111-111111111111"
_NID2 = "22222222-2222-2222-2222-222222222222"


def _row(**overrides):
    row = {
        "id": _NID,
        "type": "EVALUATION_ASSIGNED",
        "title": "You have been assigned an evaluation",
        "body": "A new evaluation is waiting for you in the Evaluation Workspace.",
        "related_entity_type": "EVALUATION",
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
    ("get", "/api/v1/faculty/notifications"),
    ("get", "/api/v1/faculty/notifications/unread-count"),
    ("get", f"/api/v1/faculty/notifications/{_NID}"),
    ("patch", f"/api/v1/faculty/notifications/{_NID}/read"),
    ("patch", f"/api/v1/faculty/notifications/{_NID}/unread"),
    ("post", "/api/v1/faculty/notifications/read-all"),
]


def _call(method, url, *, headers=None):
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_faculty_roles():
    for role in ("STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# 3. No creation endpoint exists
# ============================================================


def test_there_is_no_faculty_notification_creation_endpoint():
    paths = app.openapi()["paths"]
    assert "/api/v1/faculty/notifications" in paths
    assert set(paths["/api/v1/faculty/notifications"]) == {"get"}
    notif_posts = {
        p
        for p, method_map in paths.items()
        if p.startswith("/api/v1/faculty/notifications") and "post" in method_map
    }
    assert notif_posts == {"/api/v1/faculty/notifications/read-all"}


def test_router_registered_and_only_intended_methods():
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/faculty/notifications/unread-count"]) == {"get"}
    assert set(paths["/api/v1/faculty/notifications/{notification_id}"]) == {"get"}
    assert set(paths["/api/v1/faculty/notifications/{notification_id}/read"]) == {"patch"}
    assert set(paths["/api/v1/faculty/notifications/{notification_id}/unread"]) == {"patch"}


# ============================================================
# 4-9. List + unread count
# ============================================================


def test_list_returns_shaped_rows_and_unread_count():
    def fake_list(_client, faculty_id, **kwargs):
        assert faculty_id == "faculty-9"
        return [_shaped(), _shaped(id=_NID2, read_at="2026-09-02T00:00:00Z", is_read=True)]

    with (
        authenticated_as("FACULTY", user_id="faculty-9"),
        patch.object(svc, "list_notifications", side_effect=fake_list),
        patch.object(svc, "unread_count", return_value=1),
    ):
        resp = client.get(
            "/api/v1/faculty/notifications", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 1
    assert [n["is_read"] for n in body["notifications"]] == [False, True]
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

    def fake_list(_client, faculty_id, **kwargs):
        captured.update({"faculty_id": faculty_id, **kwargs})
        return []

    with (
        authenticated_as("FACULTY", user_id="f-1"),
        patch.object(svc, "list_notifications", side_effect=fake_list),
        patch.object(svc, "unread_count", return_value=0),
    ):
        resp = client.get(
            "/api/v1/faculty/notifications?unread=true&limit=10",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"faculty_id": "f-1", "unread_only": True, "limit": 10}


def test_list_rejects_out_of_range_limit():
    with authenticated_as("FACULTY"):
        assert (
            client.get(
                "/api/v1/faculty/notifications?limit=0",
                headers={"Authorization": "Bearer token"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/faculty/notifications?limit=100000",
                headers={"Authorization": "Bearer token"},
            ).status_code
            == 422
        )


def test_unread_count_endpoint_is_cheap_and_scoped():
    with (
        authenticated_as("FACULTY", user_id="f-1"),
        patch.object(svc, "unread_count", return_value=3) as mock_count,
    ):
        resp = client.get(
            "/api/v1/faculty/notifications/unread-count", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json() == {"unread_count": 3}
    assert mock_count.call_args.args[1] == "f-1"


def test_service_list_filters_by_faculty_and_orders_newest_first():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_notifications(supabase, "faculty-1", unread_only=True, limit=5)
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("faculty_id", "faculty-1") in eq_calls
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
    assert svc.unread_count(supabase, "faculty-1") == 4
    q.is_.assert_any_call("read_at", "null")


# ============================================================
# 10-13. Detail + IDOR
# ============================================================


def test_get_detail_returns_row():
    with (
        authenticated_as("FACULTY", user_id="f-1"),
        patch.object(svc, "get_notification", return_value=_shaped()),
    ):
        resp = client.get(
            f"/api/v1/faculty/notifications/{_NID}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["title"] == "You have been assigned an evaluation"


def test_get_detail_404_when_not_the_callers():
    """None from the service -- another Faculty member's notification is
    indistinguishable from one that doesn't exist, even to a caller who
    knows the UUID (IDOR)."""
    with (
        authenticated_as("FACULTY", user_id="attacker"),
        patch.object(svc, "get_notification", return_value=None) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/faculty/notifications/{uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "attacker"


def test_get_detail_rejects_non_uuid():
    with authenticated_as("FACULTY"):
        resp = client.get(
            "/api/v1/faculty/notifications/not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_get_filters_id_and_faculty():
    supabase = MagicMock()
    q = _fluent(None)
    supabase.table.return_value = q
    assert svc.get_notification(supabase, "faculty-1", _NID) is None
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("id", _NID) in eq_calls
    assert ("faculty_id", "faculty-1") in eq_calls


# ============================================================
# 14-19. Mark read / unread / read-all
# ============================================================


def test_mark_read_uses_caller_id_not_a_client_value():
    captured = {}

    def fake_set(_client, faculty_id, notification_id, *, read):
        captured.update(
            {"faculty_id": faculty_id, "notification_id": notification_id, "read": read}
        )
        return _shaped(read_at="2026-09-02T00:00:00Z", is_read=True)

    with (
        authenticated_as("FACULTY", user_id="f-42"),
        patch.object(svc, "set_read", side_effect=fake_set),
    ):
        resp = client.patch(
            f"/api/v1/faculty/notifications/{_NID}/read",
            json={"faculty_id": "victim", "is_read": False, "title": "hacked"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"faculty_id": "f-42", "notification_id": _NID, "read": True}
    assert resp.json()["is_read"] is True


def test_mark_unread_sets_read_false():
    captured = {}

    def fake_set(_client, faculty_id, notification_id, *, read):
        captured["read"] = read
        return _shaped()

    with (
        authenticated_as("FACULTY", user_id="f-1"),
        patch.object(svc, "set_read", side_effect=fake_set),
    ):
        resp = client.patch(
            f"/api/v1/faculty/notifications/{_NID}/unread",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["read"] is False


def test_mark_read_404_for_another_facultys_notification():
    with (
        authenticated_as("FACULTY", user_id="attacker"),
        patch.object(svc, "set_read", return_value=None),
    ):
        resp = client.patch(
            f"/api/v1/faculty/notifications/{uuid4()}/read",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_service_set_read_only_writes_read_at():
    supabase = MagicMock()
    with patch.object(svc, "get_notification", side_effect=[_shaped(), _shaped(is_read=True)]):
        upd = _fluent([_row(read_at="x")])
        supabase.table.return_value = upd
        svc.set_read(supabase, "f-1", _NID, read=True)
    payload = supabase.table.return_value.update.call_args.args[0]
    assert set(payload) == {"read_at"}


def test_service_set_read_is_noop_when_already_in_target_state():
    supabase = MagicMock()
    with patch.object(svc, "get_notification", return_value=_shaped(is_read=True, read_at="t")):
        result = svc.set_read(supabase, "f-1", _NID, read=True)
    supabase.table.return_value.update.assert_not_called()
    assert result["is_read"] is True


def test_service_mark_all_read_filters_faculty_and_unread():
    supabase = MagicMock()
    q = _fluent([_row(), _row(id=_NID2)])
    supabase.table.return_value = q
    assert svc.mark_all_read(supabase, "f-1") == 2
    payload = q.update.call_args.args[0]
    assert set(payload) == {"read_at"}
    q.eq.assert_any_call("faculty_id", "f-1")
    q.is_.assert_any_call("read_at", "null")


# ============================================================
# 20-24. Service / architecture security
# ============================================================


def test_routes_never_declare_an_owner_id_parameter():
    from app.api import faculty_notifications as routes

    for name in dir(routes):
        fn = getattr(routes, name)
        if callable(fn) and getattr(fn, "__module__", "") == routes.__name__:
            params = set(inspect.signature(fn).parameters) if hasattr(fn, "__code__") else set()
            for banned in ("faculty_id", "recipient_id", "user_id", "owner_id"):
                assert banned not in params, f"{name} must not take a {banned} parameter"


def test_routes_take_no_request_body_model():
    from app.api import faculty_notifications as routes

    for fn in (
        routes.mark_notification_read,
        routes.mark_notification_unread,
        routes.mark_all_notifications_read,
    ):
        params = inspect.signature(fn).parameters
        assert "body" not in params and "payload" not in params, fn.__name__


def test_modules_do_not_use_service_role():
    from app.api import faculty_notifications as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_service_only_touches_faculty_notifications_table():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    tables = set(re.findall(r'\.table\("([a-z_]+)"\)', compact))
    assert tables == {"faculty_notifications"}, tables


def test_service_never_inserts_or_deletes():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    for m in re.finditer(r'\.table\("faculty_notifications"\)(\.[a-z_]+\()', compact):
        assert m.group(1) not in (".insert(", ".delete(", ".upsert("), m.group(1)


def test_routes_pass_only_current_user_id_to_the_service():
    from app.api import faculty_notifications as routes

    code = re.sub(r'""".*?"""', "", inspect.getsource(routes), flags=re.DOTALL)
    for call in re.findall(
        r"faculty_notification_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")
    ):
        assert "current_user.id" in call, call
        for banned in ("faculty_id=", "recipient_id=", "user_id="):
            assert banned not in call, call


# ============================================================
# 25-33. Migration 066 schema guard (read from SQL, no live DB)
# ============================================================

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
_M066 = (_MIGRATIONS_DIR / "066_faculty_notifications.sql").read_text(encoding="utf-8")
_M066_CODE = "\n".join(
    ln for ln in _M066.splitlines() if not ln.strip().startswith("--")
).lower()


def test_migration_066_exists_and_numbering_is_contiguous():
    names = sorted(p.name for p in _MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    numbers = sorted(int(n[:3]) for n in names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap: {numbers}"
    assert "066_faculty_notifications.sql" in names
    # 065 (Phase 3E) must not have been touched by this phase
    assert "065_assessment_source_metadata.sql" in names


def test_migration_066_creates_one_table_with_pk_and_fk():
    assert "create table if not exists faculty_notifications" in _M066_CODE
    assert "id uuid primary key default gen_random_uuid()" in _M066_CODE
    assert "faculty_id uuid not null references profiles (id) on delete cascade" in _M066_CODE


def test_migration_066_type_and_related_entity_constraints():
    assert "check (type in (" in _M066_CODE
    for t in ("evaluation_assigned", "evaluation_revoked", "review_decision", "mentorship"):
        assert f"'{t}'" in _M066_CODE
    assert "check (related_entity_type in (" in _M066_CODE
    assert "faculty_notifications_related_entity_paired" in _M066_CODE


def test_migration_066_read_state_column():
    assert "read_at timestamptz" in _M066_CODE
    assert "updated_at" not in _M066_CODE
    assert "set_updated_at" not in _M066_CODE


def test_migration_066_indexes():
    assert "faculty_notifications_faculty_created_idx" in _M066_CODE
    assert "on faculty_notifications (faculty_id, created_at desc)" in _M066_CODE
    assert "faculty_notifications_unread_idx" in _M066_CODE
    assert "where read_at is null" in _M066_CODE


def test_migration_066_dedupe_key_and_unique_index():
    """Idempotency Layer 2 (belt-and-suspenders): a partial unique index
    on (faculty_id, dedupe_key)."""
    assert "dedupe_key text" in _M066_CODE
    assert "faculty_notifications_dedupe_idx" in _M066_CODE
    assert "unique index" in _M066_CODE
    assert "on faculty_notifications (faculty_id, dedupe_key)" in _M066_CODE
    assert "where dedupe_key is not null" in _M066_CODE


def test_migration_066_rls_enabled_select_and_update_only():
    assert "alter table faculty_notifications enable row level security" in _M066_CODE
    assert "for select" in _M066_CODE
    assert "for update" in _M066_CODE
    assert "for insert" not in _M066_CODE
    assert "for delete" not in _M066_CODE


def test_migration_066_ownership_predicate_uses_is_faculty():
    assert _M066_CODE.count("auth.uid() = faculty_id and public.is_faculty(auth.uid())") >= 2


def test_migration_066_freeze_trigger_pins_every_content_column():
    assert "before update on faculty_notifications" in _M066_CODE
    assert "enforce_faculty_notification_immutability" in _M066_CODE
    assert "current_setting('role', true) = 'service_role'" in _M066_CODE
    for col in (
        "faculty_id",
        "type",
        "title",
        "body",
        "related_entity_type",
        "related_entity_id",
        "dedupe_key",
        "created_at",
    ):
        assert f"new.{col} is distinct from old.{col}" in _M066_CODE
    assert "new.read_at is distinct from old.read_at" not in _M066_CODE


def test_migration_066_is_additive_and_non_destructive():
    assert "drop table" not in _M066_CODE
    for existing in ("profiles", "assessments", "student_notifications", "assessment_attempts"):
        assert f"alter table {existing} " not in _M066_CODE
    assert "create or replace function public.set_updated_at" not in _M066_CODE


# ============================================================
# 34-44. Producer: recipient correctness + best-effort + dedupe keys
# ============================================================


def test_emit_evaluation_assigned_resolves_evaluation_and_writes_dedupe_key():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "id": "eval-1"
    }
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_evaluation_assigned(evaluator_id="evaluator-1", assignment_id="assign-1")

    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert insert_call["faculty_id"] == "evaluator-1"
    assert insert_call["type"] == "EVALUATION_ASSIGNED"
    assert insert_call["related_entity_type"] == "EVALUATION"
    assert insert_call["related_entity_id"] == "eval-1"
    assert insert_call["dedupe_key"] == "eval_assigned:assign-1"


def test_emit_evaluation_assigned_omits_related_entity_when_evaluation_not_found():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_evaluation_assigned(evaluator_id="evaluator-1", assignment_id="assign-1")

    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert "related_entity_type" not in insert_call


def test_emit_evaluation_revoked_has_no_related_entity():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_evaluation_revoked(evaluator_id="evaluator-1", assignment_id="assign-1")

    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert insert_call["faculty_id"] == "evaluator-1"
    assert insert_call["type"] == "EVALUATION_REVOKED"
    assert "related_entity_type" not in insert_call
    assert insert_call["dedupe_key"] == "eval_revoked:assign-1"


def test_emit_review_decision_notifies_the_author_not_the_reviewer():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_review_decision(
            author_id="author-1", question_id="q-1", decision="APPROVED", updated_at="2026-01-01T00:00:00Z"
        )

    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert insert_call["faculty_id"] == "author-1"
    assert insert_call["type"] == "REVIEW_DECISION"
    assert insert_call["related_entity_type"] == "QUESTION"
    assert insert_call["related_entity_id"] == "q-1"
    assert insert_call["dedupe_key"] == "review_decision:q-1:2026-01-01T00:00:00Z"


def test_emit_review_decision_two_distinct_decisions_get_distinct_dedupe_keys():
    """A question rejected then later approved must notify twice, not be
    deduped against its own earlier rejection."""
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_review_decision(
            author_id="author-1", question_id="q-1", decision="REJECTED", updated_at="t1"
        )
        producer.emit_review_decision(
            author_id="author-1", question_id="q-1", decision="APPROVED", updated_at="t2"
        )

    keys = [c.args[0]["dedupe_key"] for c in fake_client.table.return_value.insert.call_args_list]
    assert keys == ["review_decision:q-1:t1", "review_decision:q-1:t2"]
    assert len(set(keys)) == 2


def test_emit_review_decision_noop_for_unrecognized_decision():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_review_decision(
            author_id="author-1", question_id="q-1", decision="PENDING", updated_at="t"
        )
    fake_client.table.return_value.insert.assert_not_called()


def test_emit_mentorship_request_notifies_faculty_with_student_name():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "full_name": "Jane Doe",
        "username": "janedoe",
    }
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_mentorship_request(faculty_id="f-1", student_id="s-1", mentorship_id="m-1")

    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert insert_call["faculty_id"] == "f-1"
    assert insert_call["type"] == "MENTORSHIP"
    assert "Jane Doe" in insert_call["body"]
    assert insert_call["related_entity_type"] == "MENTORSHIP"
    assert insert_call["related_entity_id"] == "m-1"
    assert insert_call["dedupe_key"] == "mentorship_requested:m-1"


def test_emit_mentorship_status_change_noop_for_unrecognized_status():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_mentorship_status_change(
            faculty_id="f-1", student_id="s-1", mentorship_id="m-1", new_status="REQUESTED"
        )
    fake_client.table.return_value.insert.assert_not_called()


def test_emit_mentorship_status_change_dedupe_key_includes_status():
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "full_name": None,
        "username": "s1",
    }
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_mentorship_status_change(
            faculty_id="f-1", student_id="s-1", mentorship_id="m-1", new_status="ACCEPTED"
        )
    insert_call = fake_client.table.return_value.insert.call_args.args[0]
    assert insert_call["dedupe_key"] == "mentorship_status:m-1:ACCEPTED"
    assert insert_call["faculty_id"] == "f-1"


def test_producers_are_best_effort_and_never_raise():
    """A failed notification write must never propagate -- the caller
    does not (and must not need to) wrap these calls in try/except."""
    from app.services import faculty_notification_producer as producer

    fake_client = MagicMock()
    fake_client.table.side_effect = RuntimeError("db unavailable")
    with patch.object(producer, "get_supabase", return_value=fake_client):
        producer.emit_evaluation_assigned(evaluator_id="e-1", assignment_id="a-1")
        producer.emit_evaluation_revoked(evaluator_id="e-1", assignment_id="a-1")
        producer.emit_review_decision(author_id="a-1", question_id="q-1", decision="APPROVED", updated_at="t")
        producer.emit_mentorship_request(faculty_id="f-1", student_id="s-1", mentorship_id="m-1")
        producer.emit_mentorship_status_change(
            faculty_id="f-1", student_id="s-1", mentorship_id="m-1", new_status="ACCEPTED"
        )
    # reaching here at all is the assertion: none of the above raised


def test_producer_never_reads_from_the_faculty_notifications_table():
    """Producers must only ever write -- never a select against the
    notifications table itself (that would be a read of other faculty's
    private data using service_role, which the read-side API must never
    need)."""
    import inspect as _inspect

    from app.services import faculty_notification_producer as producer

    compact = _inspect.getsource(producer).replace("\n", "").replace(" ", "")
    for m in re.finditer(r'\.table\("faculty_notifications"\)(\.[a-z_]+\()', compact):
        assert m.group(1) == ".insert(", m.group(1)


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
