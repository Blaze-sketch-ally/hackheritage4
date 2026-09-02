"""Tests for the Student Events API: /api/v1/student/events.

Route tests mock app.services.student_event_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_learning.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token. Nothing here claims real DB behaviour: RLS on
`industry_workshops` ("Authenticated users can view published workshops")
is the real visibility boundary and is not re-verified against a live
database here.

S4 adds NO migration -- a student-facing "event" is one PUBLISHED row of
the existing `industry_workshops` table (024_industry_workshops.sql).
"""

import inspect
import re
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import student_event_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_EID = "11111111-1111-1111-1111-111111111111"
_EID2 = "22222222-2222-2222-2222-222222222222"


def _summary(**overrides):
    row = {
        "id": _EID,
        "title": "Intro to Kubernetes",
        "description": "A hands-on afternoon workshop.",
        "location": "Bengaluru",
        "work_mode": "ONSITE",
        "start_date": "2026-10-01",
        "application_deadline": "2026-09-20",
        "duration_days": 1,
        "organizer": {
            "id": "industry-1",
            "company_name": "Acme",
            "industry_sector": "Software",
            "logo_url": None,
        },
        "created_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _detail(**overrides):
    row = _summary()
    row.update(
        {
            "capacity": 30,
            "eligibility_criteria": "Open to all students.",
            "registration_available": False,
        }
    )
    row.update(overrides)
    return row


# ============================================================
# 1-2. Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/student/events"),
    ("get", f"/api/v1/student/events/{_EID}"),
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
# 3-8. Event list
# ============================================================


def test_list_events_returns_normalized_rows():
    def fake_list(_client, **kwargs):
        return [_summary(), _summary(id=_EID2, title="GraphQL Deep Dive", work_mode="REMOTE")]

    with (
        authenticated_as("STUDENT", user_id="student-9"),
        patch.object(svc, "list_events", side_effect=fake_list),
    ):
        resp = client.get("/api/v1/student/events", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    body = resp.json()["events"]
    assert [e["title"] for e in body] == ["Intro to Kubernetes", "GraphQL Deep Dive"]
    assert body[0]["organizer"]["company_name"] == "Acme"
    # internal columns are not exposed
    assert "industry_id" not in body[0]
    assert "status" not in body[0]


def test_list_events_passes_filters_to_service():
    captured = {}

    def fake_list(_client, **kwargs):
        captured.update(kwargs)
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_events", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/events?work_mode=REMOTE&search=kafka",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"work_mode": "REMOTE", "search": "kafka"}


def test_list_events_no_filters_passes_none():
    captured = {}

    def fake_list(_client, **kwargs):
        captured.update(kwargs)
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_events", side_effect=fake_list),
    ):
        client.get("/api/v1/student/events", headers={"Authorization": "Bearer token"})
    assert captured == {"work_mode": None, "search": None}


def test_list_events_rejects_overlong_search():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/events?search=" + "x" * 201,
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_list_events_filters_published_and_applies_filters():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_events(supabase, work_mode="REMOTE", search="k8s")
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("status", "PUBLISHED") in eq_calls
    assert ("work_mode", "REMOTE") in eq_calls
    ilike_calls = [c.args for c in q.ilike.call_args_list]
    assert ("title", "%k8s%") in ilike_calls


def test_service_list_events_ignores_unknown_work_mode():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_events(supabase, work_mode="TELEPATHIC")
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("status", "PUBLISHED") in eq_calls
    assert not any(call[0] == "work_mode" for call in eq_calls)


def test_service_list_events_sorts_undated_last_then_by_start_date():
    supabase = MagicMock()
    rows = [
        {**_raw(id="a"), "start_date": None},
        {**_raw(id="b"), "start_date": "2026-12-01"},
        {**_raw(id="c"), "start_date": "2026-06-01"},
    ]
    q = _fluent(rows)
    supabase.table.return_value = q
    with patch.object(svc, "_fetch_organizers", return_value={}):
        result = svc.list_events(supabase)
    assert [e["id"] for e in result] == ["c", "b", "a"]


# ============================================================
# 9-12. Event detail
# ============================================================


def test_get_event_returns_detail():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "get_event", return_value=_detail()),
    ):
        resp = client.get(
            f"/api/v1/student/events/{_EID}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Intro to Kubernetes"
    assert body["capacity"] == 30
    # no fabricated registration mechanism
    assert body["registration_available"] is False


def test_get_event_404_when_missing_or_not_published():
    """None from the service -- a nonexistent workshop and a
    DRAFT/CLOSED/ARCHIVED one are indistinguishable, even to a caller who
    knows the UUID."""
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_event", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/events/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_get_event_rejects_non_uuid_id():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/events/not-a-uuid", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_service_get_event_filters_id_and_published():
    supabase = MagicMock()
    q = _fluent(None)
    supabase.table.return_value = q
    result = svc.get_event(supabase, _EID)
    assert result is None
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("id", _EID) in eq_calls
    assert ("status", "PUBLISHED") in eq_calls


def test_service_get_event_shapes_organizer_and_hides_industry_id():
    supabase = MagicMock()
    q = _fluent(_raw())
    supabase.table.return_value = q
    with patch.object(
        svc,
        "_fetch_organizers",
        return_value={"industry-7": {"company_name": "Globex", "industry_sector": None, "logo_url": None}},
    ):
        row = svc.get_event(supabase, _EID)
    assert row is not None
    assert "industry_id" not in row
    assert row["organizer"]["id"] == "industry-7"
    assert row["organizer"]["company_name"] == "Globex"
    assert row["registration_available"] is False


# ============================================================
# 13-18. Security / architecture
# ============================================================


def test_routes_never_read_an_owner_id_from_the_request():
    from app.api import student_events as routes

    for fn in (routes.list_events, routes.get_event):
        params = set(inspect.signature(fn).parameters)
        for banned in ("student_id", "owner_id", "user_id", "industry_id"):
            assert banned not in params, f"{fn.__name__} must not take a {banned} parameter"


def test_event_modules_do_not_use_service_role():
    from app.api import student_events as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_service_never_writes_anything():
    """S4 is strictly read-only: the service issues SELECTs and nothing
    else -- no insert/update/upsert/delete against any table."""
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    for match in re.finditer(r'\.table\("([a-z_]+)"\)(\.[a-z_]+\()', compact):
        verb = match.group(2)
        assert verb not in (".insert(", ".update(", ".upsert(", ".delete("), (
            f"student_event_service must not write ({verb} against {match.group(1)})"
        )


def test_service_only_reads_workshops_and_industry_profiles():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    tables = set(re.findall(r'\.table\("([a-z_]+)"\)', compact))
    assert tables <= {"industry_workshops", "industry_profiles"}, tables


def test_no_route_can_create_update_or_delete_an_event():
    """The router mounts only GET routes -- there is no POST/PUT/PATCH/
    DELETE path a student could use to mutate a workshop row."""
    from app.api import student_events as routes

    methods = set()
    for route in routes.router.routes:
        methods |= set(getattr(route, "methods", set()))
    assert methods <= {"GET"}, methods


def test_routes_pass_only_the_user_client_to_the_service():
    from app.api import student_events as routes

    code = inspect.getsource(routes)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    for call in re.findall(r"student_event_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")):
        for banned in ("student_id", "owner_id", "user_id", "industry_id"):
            assert banned not in call, f"route passes a raw {banned}: {call}"


# ============================================================
# helpers
# ============================================================


def _raw(**overrides):
    """A raw `industry_workshops` row as the DB would return it."""
    row = {
        "id": _EID,
        "industry_id": "industry-7",
        "title": "Intro to Kubernetes",
        "description": "A hands-on afternoon workshop.",
        "location": "Bengaluru",
        "work_mode": "ONSITE",
        "duration_days": 1,
        "capacity": 30,
        "eligibility_criteria": "Open to all students.",
        "application_deadline": "2026-09-20",
        "start_date": "2026-10-01",
        "status": "PUBLISHED",
        "created_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _fluent(final_data):
    """A Supabase query mock whose chainable methods all return itself, so
    call_args_list on any of them captures every call in the chain."""
    q = MagicMock()
    for method in ("select", "eq", "in_", "order", "ilike", "maybe_single"):
        getattr(q, method).return_value = q
    q.execute.return_value.data = final_data
    return q
