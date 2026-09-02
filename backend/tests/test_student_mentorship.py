"""Tests for the Student Mentorship API: /api/v1/student/mentorship.

Route tests mock app.services.student_mentorship_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_events.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token. Nothing here claims real DB behaviour: RLS on
`industry_mentorship` ("Authenticated users can view published mentorship
opportunities") is the real visibility boundary and is not re-verified
against a live database here.

S5 adds NO migration -- a student-facing "mentorship opportunity" is one
PUBLISHED row of the existing `industry_mentorship` table
(025_industry_mentorship.sql). There is no request/pairing table, so
there is no request endpoint to test.
"""

import inspect
import re
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services import student_mentorship_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_MID = "11111111-1111-1111-1111-111111111111"
_MID2 = "22222222-2222-2222-2222-222222222222"


def _summary(**overrides):
    row = {
        "id": _MID,
        "title": "Cloud-Native Engineering Mentorship",
        "description": "A six-month mentoring engagement.",
        "location": "Bengaluru",
        "work_mode": "HYBRID",
        "duration_months": 6,
        "capacity": 5,
        "start_date": "2026-10-01",
        "application_deadline": "2026-09-20T00:00:00Z",
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
            "eligibility_criteria": "Open to final-year students.",
            "requests_available": False,
        }
    )
    row.update(overrides)
    return row


# ============================================================
# 1-2. Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/student/mentorship"),
    ("get", f"/api/v1/student/mentorship/{_MID}"),
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
# 3-9. Mentorship list
# ============================================================


def test_list_mentorship_returns_normalized_rows():
    def fake_list(_client, **kwargs):
        return [
            _summary(),
            _summary(id=_MID2, title="Data Platform Mentorship", work_mode="REMOTE"),
        ]

    with (
        authenticated_as("STUDENT", user_id="student-9"),
        patch.object(svc, "list_mentorships", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/mentorship", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()["mentorship_opportunities"]
    assert [m["title"] for m in body] == [
        "Cloud-Native Engineering Mentorship",
        "Data Platform Mentorship",
    ]
    assert body[0]["organizer"]["company_name"] == "Acme"
    # internal columns are not exposed
    assert "industry_id" not in body[0]
    assert "status" not in body[0]


def test_list_mentorship_passes_filters_to_service():
    captured = {}

    def fake_list(_client, **kwargs):
        captured.update(kwargs)
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_mentorships", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/mentorship?work_mode=REMOTE&search=cloud",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"work_mode": "REMOTE", "search": "cloud"}


def test_list_mentorship_no_filters_passes_none():
    captured = {}

    def fake_list(_client, **kwargs):
        captured.update(kwargs)
        return []

    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_mentorships", side_effect=fake_list),
    ):
        client.get("/api/v1/student/mentorship", headers={"Authorization": "Bearer token"})
    assert captured == {"work_mode": None, "search": None}


def test_list_mentorship_rejects_overlong_search():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/mentorship?search=" + "x" * 201,
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_list_filters_published_and_applies_filters():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_mentorships(supabase, work_mode="REMOTE", search="cloud")
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("status", "PUBLISHED") in eq_calls
    assert ("work_mode", "REMOTE") in eq_calls
    ilike_calls = [c.args for c in q.ilike.call_args_list]
    assert ("title", "%cloud%") in ilike_calls


def test_service_list_ignores_unknown_work_mode():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_mentorships(supabase, work_mode="ASTRAL")
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("status", "PUBLISHED") in eq_calls
    assert not any(call[0] == "work_mode" for call in eq_calls)


def test_service_list_sorts_undated_last_then_by_start_date():
    supabase = MagicMock()
    rows = [
        {**_raw(id="a"), "start_date": None},
        {**_raw(id="b"), "start_date": "2026-12-01"},
        {**_raw(id="c"), "start_date": "2026-06-01"},
    ]
    q = _fluent(rows)
    supabase.table.return_value = q
    with patch.object(svc, "_fetch_organizers", return_value={}):
        result = svc.list_mentorships(supabase)
    assert [m["id"] for m in result] == ["c", "b", "a"]


# ============================================================
# 10-14. Mentorship detail
# ============================================================


def test_get_mentorship_returns_detail():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "get_mentorship", return_value=_detail()),
    ):
        resp = client.get(
            f"/api/v1/student/mentorship/{_MID}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Cloud-Native Engineering Mentorship"
    assert body["eligibility_criteria"] == "Open to final-year students."
    # no fabricated request mechanism
    assert body["requests_available"] is False


def test_get_mentorship_404_when_missing_or_not_published():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_mentorship", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/mentorship/{uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_get_mentorship_rejects_non_uuid_id():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/mentorship/not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_get_filters_id_and_published():
    supabase = MagicMock()
    q = _fluent(None)
    supabase.table.return_value = q
    result = svc.get_mentorship(supabase, _MID)
    assert result is None
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("id", _MID) in eq_calls
    assert ("status", "PUBLISHED") in eq_calls


def test_service_get_shapes_organizer_and_hides_industry_id():
    supabase = MagicMock()
    q = _fluent(_raw())
    supabase.table.return_value = q
    with patch.object(
        svc,
        "_fetch_organizers",
        return_value={
            "industry-7": {"company_name": "Globex", "industry_sector": None, "logo_url": None}
        },
    ):
        row = svc.get_mentorship(supabase, _MID)
    assert row is not None
    assert "industry_id" not in row
    assert row["organizer"]["id"] == "industry-7"
    assert row["organizer"]["company_name"] == "Globex"
    assert row["requests_available"] is False


# ============================================================
# 15-21. Security / architecture
# ============================================================


def test_routes_never_read_an_owner_id_from_the_request():
    from app.api import student_mentorship as routes

    for fn in (routes.list_mentorship, routes.get_mentorship):
        params = set(inspect.signature(fn).parameters)
        for banned in ("student_id", "owner_id", "user_id", "industry_id", "requester_id"):
            assert banned not in params, f"{fn.__name__} must not take a {banned} parameter"


def test_mentorship_id_param_is_only_a_resource_identifier():
    """`mentorship_id` identifies the selected resource -- it must never
    reach the service as an ownership argument."""
    from app.api import student_mentorship as routes

    code = inspect.getsource(routes)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    for call in re.findall(
        r"student_mentorship_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")
    ):
        for banned in ("student_id", "owner_id", "user_id", "industry_id"):
            assert banned not in call, f"route passes a raw {banned}: {call}"


def test_mentorship_modules_do_not_use_service_role():
    from app.api import student_mentorship as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_service_never_writes_anything():
    """S5 is strictly read-only: the service issues SELECTs and nothing
    else -- no insert/update/upsert/delete against any table."""
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    for match in re.finditer(r'\.table\("([a-z_]+)"\)(\.[a-z_]+\()', compact):
        verb = match.group(2)
        assert verb not in (".insert(", ".update(", ".upsert(", ".delete("), (
            f"student_mentorship_service must not write ({verb} against {match.group(1)})"
        )


def test_service_only_reads_mentorship_and_industry_profiles():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    tables = set(re.findall(r'\.table\("([a-z_]+)"\)', compact))
    assert tables <= {"industry_mentorship", "industry_profiles"}, tables


def test_no_route_can_create_update_or_delete_a_mentorship():
    from app.api import student_mentorship as routes

    methods = set()
    for route in routes.router.routes:
        methods |= set(getattr(route, "methods", set()))
    assert methods <= {"GET"}, methods


def test_router_is_registered_under_api_v1_student():
    paths = app.openapi()["paths"]
    assert "/api/v1/student/mentorship" in paths
    assert "/api/v1/student/mentorship/{mentorship_id}" in paths
    # read-only: the student mentorship paths expose only GET
    for path in ("/api/v1/student/mentorship", "/api/v1/student/mentorship/{mentorship_id}"):
        assert set(paths[path]) <= {"get"}, (path, list(paths[path]))


# ============================================================
# helpers
# ============================================================


def _raw(**overrides):
    """A raw `industry_mentorship` row as the DB would return it."""
    row = {
        "id": _MID,
        "industry_id": "industry-7",
        "title": "Cloud-Native Engineering Mentorship",
        "description": "A six-month mentoring engagement.",
        "location": "Bengaluru",
        "work_mode": "HYBRID",
        "duration_months": 6,
        "capacity": 5,
        "eligibility_criteria": "Open to final-year students.",
        "application_deadline": "2026-09-20T00:00:00Z",
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
