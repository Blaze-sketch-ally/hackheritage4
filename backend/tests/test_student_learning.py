"""Tests for the Student Learning API: /api/v1/student/learning/*.

Route tests mock app.services.student_learning_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_opportunities.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token. Nothing here claims real DB behaviour: RLS is
the real ownership boundary and is not re-verified against a live database
here (same note as tests/test_student_opportunities.py).
"""

import inspect
import re
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import student_learning_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_RID = "11111111-1111-1111-1111-111111111111"
_RID2 = "22222222-2222-2222-2222-222222222222"


def _resource(**overrides):
    row = {
        "id": _RID,
        "title": "Python for Everybody",
        "description": "A gentle intro to Python.",
        "url": "https://www.py4e.com/",
        "provider": "py4e",
        "resource_type": "COURSE",
        "difficulty": "Beginner",
        "estimated_minutes": 1200,
        "skills": [
            {"skill_id": "s1", "skill_name": "Python", "target_level": "Beginner"},
        ],
        "progress": None,
    }
    row.update(overrides)
    return row


def _progress_item(**overrides):
    row = {
        "resource_id": _RID,
        "status": "IN_PROGRESS",
        "started_at": "2026-09-02T00:00:00Z",
        "completed_at": None,
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
        "resource": {
            "id": _RID,
            "title": "Python for Everybody",
            "url": "https://www.py4e.com/",
            "provider": "py4e",
            "resource_type": "COURSE",
            "difficulty": "Beginner",
        },
    }
    row.update(overrides)
    return row


def _progress_write(**overrides):
    row = {
        "resource_id": _RID,
        "status": "SAVED",
        "started_at": None,
        "completed_at": None,
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
    }
    row.update(overrides)
    return row


# ============================================================
# 1-2. Auth / role guards
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/student/learning/resources"),
    ("get", f"/api/v1/student/learning/resources/{_RID}"),
    ("get", "/api/v1/student/learning/progress"),
    ("post", f"/api/v1/student/learning/resources/{_RID}/progress"),
]


def _call(method, url, *, headers=None):
    if method == "post":
        return client.post(url, json={"status": "SAVED"}, headers=headers)
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        for method, url in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# 3-8. Resource list
# ============================================================


def test_list_resources_returns_normalized_rows_with_skills():
    captured = {}

    def fake_list(_client, student_id, **kwargs):
        captured.update({"student_id": student_id, **kwargs})
        return [_resource(), _resource(id=_RID2, title="SQLBolt", resource_type="COURSE")]

    with (
        authenticated_as("STUDENT", user_id="student-9"),
        patch.object(svc, "list_resources", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/learning/resources", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["student_id"] == "student-9"
    assert captured == {
        "student_id": "student-9",
        "skill_id": None,
        "difficulty": None,
        "resource_type": None,
    }
    body = resp.json()["resources"]
    assert body[0]["title"] == "Python for Everybody"
    assert body[0]["skills"][0]["skill_name"] == "Python"
    assert body[0]["progress"] is None
    # internal columns are not exposed
    assert "is_active" not in body[0]
    assert "created_at" not in body[0]


def test_list_resources_passes_all_filters_to_service():
    captured = {}

    def fake_list(_client, _student_id, **kwargs):
        captured.update(kwargs)
        return []

    skill_id = str(uuid4())
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "list_resources", side_effect=fake_list),
    ):
        resp = client.get(
            f"/api/v1/student/learning/resources?skill_id={skill_id}"
            "&difficulty=Advanced&resource_type=VIDEO",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"skill_id": skill_id, "difficulty": "Advanced", "resource_type": "VIDEO"}


def test_list_resources_rejects_unknown_difficulty():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/learning/resources?difficulty=Wizard",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_list_resources_rejects_unknown_resource_type():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/learning/resources?resource_type=PODCAST",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_list_resources_rejects_non_uuid_skill_id():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/learning/resources?skill_id=not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_list_resources_filters_active_and_applies_filters():
    supabase = MagicMock()
    q = _fluent([])
    supabase.table.return_value = q
    svc.list_resources(supabase, "student-1", difficulty="Beginner", resource_type="COURSE")
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("is_active", True) in eq_calls
    assert ("difficulty", "Beginner") in eq_calls
    assert ("resource_type", "COURSE") in eq_calls


def test_service_list_resources_skill_filter_resolves_resource_ids_first():
    supabase = MagicMock()
    # _resource_ids_for_skill query
    supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"resource_id": _RID}
    ]
    with patch.object(svc, "_resource_ids_for_skill", return_value=[_RID]) as mock_ids:
        supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.execute.return_value.data = []
        svc.list_resources(supabase, "student-1", skill_id="skill-1")
    mock_ids.assert_called_once_with(supabase, "skill-1")


def test_service_list_resources_skill_filter_with_no_matches_returns_empty():
    supabase = MagicMock()
    with patch.object(svc, "_resource_ids_for_skill", return_value=[]):
        result = svc.list_resources(supabase, "student-1", skill_id="skill-x")
    assert result == []


# ============================================================
# 9-11. Resource detail
# ============================================================


def test_get_resource_returns_detail():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "get_resource", return_value=_resource(progress={"status": "SAVED", "started_at": None, "completed_at": None, "updated_at": None})),
    ):
        resp = client.get(
            f"/api/v1/student/learning/resources/{_RID}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Python for Everybody"
    assert body["progress"]["status"] == "SAVED"


def test_get_resource_404_when_missing_or_inactive():
    """None from the service -- a nonexistent resource and an inactive one
    are indistinguishable, even to a caller who knows the UUID."""
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_resource", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/learning/resources/{uuid4()}",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_get_resource_rejects_non_uuid_id():
    with authenticated_as("STUDENT"):
        resp = client.get(
            "/api/v1/student/learning/resources/not-a-uuid",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_service_get_resource_filters_id_and_is_active():
    supabase = MagicMock()
    q = _fluent(None)
    supabase.table.return_value = q
    result = svc.get_resource(supabase, "student-1", _RID)
    assert result is None
    eq_calls = [c.args for c in q.eq.call_args_list]
    assert ("id", _RID) in eq_calls
    assert ("is_active", True) in eq_calls


# ============================================================
# 12-13. My progress -- own data only
# ============================================================


def test_my_progress_scoped_to_caller():
    captured = {}

    def fake_list(_client, student_id):
        captured["student_id"] = student_id
        return [_progress_item(), _progress_item(resource_id=_RID2, status="COMPLETED")]

    with (
        authenticated_as("STUDENT", user_id="student-77"),
        patch.object(svc, "list_my_progress", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/student/learning/progress", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["student_id"] == "student-77"
    body = resp.json()["progress"]
    assert [p["status"] for p in body] == ["IN_PROGRESS", "COMPLETED"]
    assert body[0]["resource"]["title"] == "Python for Everybody"


def test_service_list_my_progress_filters_by_student_and_orders():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    svc.list_my_progress(supabase, "student-55")
    eq_call = supabase.table.return_value.select.return_value.eq.call_args
    assert eq_call.args == ("student_id", "student-55")


def test_service_list_my_progress_nulls_resource_when_embed_missing():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {**_progress_write(status="SAVED"), "resource": None}
    ]
    rows = svc.list_my_progress(supabase, "student-1")
    assert rows[0]["resource"] is None


def test_routes_never_read_a_student_id_from_the_request():
    """Every route derives identity from current_user.id. No route
    *signature* declares a student_id parameter (so nothing can arrive via
    body/query/path), and every student_learning_service call passes
    current_user.id, never a client value."""
    from app.api import student_learning as routes

    route_fns = [
        routes.list_resources,
        routes.get_resource,
        routes.list_my_progress,
        routes.set_progress,
    ]
    for fn in route_fns:
        params = set(inspect.signature(fn).parameters)
        assert "student_id" not in params, f"{fn.__name__} must not take a student_id parameter"

    # code (comments/docstrings stripped) never binds a local student_id,
    # and every service call passes current_user.id, never a raw id.
    code_lines = [
        ln for ln in inspect.getsource(routes).splitlines() if not ln.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    assert "current_user.id" in code
    assert re.search(r"\bstudent_id\s*[:=]", code) is None, "no route may bind a student_id"
    for call in re.findall(r"student_learning_service\.\w+\((?:[^()]|\([^()]*\))*\)", code.replace("\n", " ")):
        assert "student_id" not in call, f"route passes a raw student_id: {call}"


# ============================================================
# 14-20. Progress upsert + timestamp state machine  (service layer)
# ============================================================


def _mock_upsert(supabase, returned_row):
    supabase.table.return_value.upsert.return_value.execute.return_value.data = [returned_row]


def _fluent(final_data):
    """A Supabase query mock whose chainable methods all return itself, so
    call_args_list on any of them captures every call in the chain."""
    q = MagicMock()
    for method in ("select", "eq", "in_", "order", "ilike", "maybe_single"):
        getattr(q, method).return_value = q
    q.execute.return_value.data = final_data
    return q


def test_set_progress_creates_saved_with_no_timestamps():
    supabase = MagicMock()
    with patch.object(svc, "get_own_progress", return_value=None):
        _mock_upsert(supabase, _progress_write(status="SAVED"))
        svc.set_progress(supabase, "student-1", _RID, "SAVED")
    payload = supabase.table.return_value.upsert.call_args.args[0]
    assert payload["status"] == "SAVED"
    assert payload["started_at"] is None
    assert payload["completed_at"] is None
    assert payload["student_id"] == "student-1"
    assert payload["resource_id"] == _RID


def test_set_progress_saved_to_in_progress_sets_started_at():
    supabase = MagicMock()
    with patch.object(svc, "get_own_progress", return_value=_progress_write(status="SAVED", started_at=None)):
        _mock_upsert(supabase, _progress_write(status="IN_PROGRESS", started_at="2026-09-02T10:00:00Z"))
        svc.set_progress(supabase, "student-1", _RID, "IN_PROGRESS")
    payload = supabase.table.return_value.upsert.call_args.args[0]
    assert payload["status"] == "IN_PROGRESS"
    assert payload["started_at"] is not None
    assert payload["completed_at"] is None


def test_set_progress_in_progress_to_completed_sets_completed_at_keeps_started_at():
    supabase = MagicMock()
    existing = _progress_write(status="IN_PROGRESS", started_at="2026-09-01T09:00:00Z")
    with patch.object(svc, "get_own_progress", return_value=existing):
        _mock_upsert(supabase, _progress_write(status="COMPLETED", started_at="2026-09-01T09:00:00Z", completed_at="2026-09-02T10:00:00Z"))
        result = svc.set_progress(supabase, "student-1", _RID, "COMPLETED")
    payload = supabase.table.return_value.upsert.call_args.args[0]
    assert payload["status"] == "COMPLETED"
    assert payload["started_at"] == "2026-09-01T09:00:00Z"  # not rewound
    assert payload["completed_at"] is not None
    assert result["status"] == "COMPLETED"
    assert result["completed_at"] is not None


def test_set_progress_completed_back_to_in_progress_clears_completed_at():
    supabase = MagicMock()
    existing = _progress_write(
        status="COMPLETED", started_at="2026-09-01T09:00:00Z", completed_at="2026-09-02T10:00:00Z"
    )
    with patch.object(svc, "get_own_progress", return_value=existing):
        _mock_upsert(supabase, _progress_write(status="IN_PROGRESS", started_at="2026-09-01T09:00:00Z", completed_at=None))
        svc.set_progress(supabase, "student-1", _RID, "IN_PROGRESS")
    payload = supabase.table.return_value.upsert.call_args.args[0]
    assert payload["status"] == "IN_PROGRESS"
    assert payload["completed_at"] is None
    assert payload["started_at"] == "2026-09-01T09:00:00Z"


def test_set_progress_completed_back_to_saved_clears_completed_at():
    supabase = MagicMock()
    existing = _progress_write(
        status="COMPLETED", started_at="2026-09-01T09:00:00Z", completed_at="2026-09-02T10:00:00Z"
    )
    with patch.object(svc, "get_own_progress", return_value=existing):
        _mock_upsert(supabase, _progress_write(status="SAVED", completed_at=None))
        svc.set_progress(supabase, "student-1", _RID, "SAVED")
    payload = supabase.table.return_value.upsert.call_args.args[0]
    assert payload["status"] == "SAVED"
    assert payload["completed_at"] is None


def test_set_progress_uses_the_natural_key_for_upsert():
    supabase = MagicMock()
    with patch.object(svc, "get_own_progress", return_value=None):
        _mock_upsert(supabase, _progress_write())
        svc.set_progress(supabase, "student-1", _RID, "SAVED")
    kwargs = supabase.table.return_value.upsert.call_args.kwargs
    assert kwargs.get("on_conflict") == "student_id,resource_id"


def test_set_progress_payloads_respect_the_db_check_constraints():
    """For every status, the payload the service builds must satisfy
    033's CHECK constraints: completed_at implies COMPLETED, a non-SAVED
    row has a started_at, completed_at >= started_at."""
    supabase = MagicMock()
    for status_value in ("SAVED", "IN_PROGRESS", "COMPLETED"):
        with patch.object(svc, "get_own_progress", return_value=None):
            _mock_upsert(supabase, _progress_write(status=status_value))
            svc.set_progress(supabase, "student-1", _RID, status_value)
        p = supabase.table.return_value.upsert.call_args.args[0]
        assert p["completed_at"] is None or p["status"] == "COMPLETED"
        assert p["status"] == "SAVED" or p["started_at"] is not None
        if p["completed_at"] and p["started_at"]:
            assert p["completed_at"] >= p["started_at"]


# ============================================================
# route-level progress: resource must exist + be active first
# ============================================================


def test_progress_route_404_when_resource_missing_or_inactive():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_resource", return_value=None),
        patch.object(svc, "set_progress") as mock_set,
    ):
        resp = client.post(
            f"/api/v1/student/learning/resources/{_RID}/progress",
            json={"status": "SAVED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404
    mock_set.assert_not_called()


def test_progress_route_passes_authenticated_id_and_status_only():
    captured = {}

    def fake_set(_client, student_id, resource_id, status_value):
        captured.update({"student_id": student_id, "resource_id": resource_id, "status": status_value})
        return _progress_write(status=status_value)

    with (
        authenticated_as("STUDENT", user_id="student-42"),
        patch.object(svc, "get_resource", return_value=_resource()),
        patch.object(svc, "set_progress", side_effect=fake_set),
    ):
        resp = client.post(
            f"/api/v1/student/learning/resources/{_RID}/progress",
            json={"status": "COMPLETED"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"student_id": "student-42", "resource_id": _RID, "status": "COMPLETED"}


# ============================================================
# 21-25. Validation
# ============================================================


@pytest.mark.parametrize("bad", ["completed", "DONE", "STARTED", "VERIFIED", "PASSED", "", "saved"])
def test_progress_rejects_unsupported_status(bad):
    with authenticated_as("STUDENT"):
        resp = client.post(
            f"/api/v1/student/learning/resources/{_RID}/progress",
            json={"status": bad},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422, bad


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "SAVED", "student_id": "victim"},
        {"status": "SAVED", "created_at": "2020-01-01T00:00:00Z"},
        {"status": "SAVED", "updated_at": "2020-01-01T00:00:00Z"},
        {"status": "SAVED", "started_at": "2020-01-01T00:00:00Z"},
        {"status": "SAVED", "completed_at": "2020-01-01T00:00:00Z"},
        {"status": "COMPLETED", "is_verified": True},
        {"status": "COMPLETED", "verified": True},
        {"status": "COMPLETED", "verified_at": "2020-01-01T00:00:00Z"},
        {"status": "COMPLETED", "score": 100},
        {"status": "COMPLETED", "assessment_id": "a-1"},
        {"status": "COMPLETED", "student_skill_id": "ss-1"},
        {"status": "COMPLETED", "skill_id": "s-1"},
    ],
)
def test_progress_rejects_any_extra_field(payload):
    with authenticated_as("STUDENT"):
        resp = client.post(
            f"/api/v1/student/learning/resources/{_RID}/progress",
            json=payload,
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422, payload


def test_progress_rejects_missing_status():
    with authenticated_as("STUDENT"):
        resp = client.post(
            f"/api/v1/student/learning/resources/{_RID}/progress",
            json={},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


# ============================================================
# 26-30. Security / architecture
# ============================================================


def test_learning_modules_do_not_use_service_role():
    from app.api import student_learning as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_service_never_writes_student_skills_or_verification_state():
    src = inspect.getsource(svc)
    # no write against student_skills / assessment tables
    for banned_write in (
        'table("student_skills").update(',
        'table("student_skills").insert(',
        'table("student_skills").upsert(',
        'table("assessment_attempts")',
        'table("assessment_answers")',
        "score_assessment_attempt",
    ):
        assert banned_write not in src.replace("\n", ""), (
            f"student_learning_service must not touch {banned_write}"
        )
    # no verification / score concept in the payloads it builds
    for banned_key in ('"is_verified"', '"verified_at"', '"score"', '"assessment_id"'):
        assert banned_key not in src, f"student_learning_service must not write {banned_key}"


def test_service_only_writes_student_learning_progress():
    """The only write (.upsert / .insert / .update) anywhere in the
    service is against student_learning_progress -- every other table
    (learning_resources, learning_resource_skills, skills) is read-only."""
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    for match in re.finditer(r'\.table\("([a-z_]+)"\)(\.[a-z_]+\()', compact):
        table, verb = match.group(1), match.group(2)
        if verb in (".upsert(", ".insert(", ".update(", ".delete("):
            assert table == "student_learning_progress", (
                f"unexpected write {verb} against {table} in student_learning_service"
            )


def test_progress_write_always_sets_student_id_from_the_caller_argument():
    """set_progress puts `student_id` in the payload straight from its
    student_id argument (which the route always passes as
    current_user.id) -- never from a resource row or request field."""
    src = inspect.getsource(svc.set_progress)
    assert '"student_id": student_id' in src


def test_route_verifies_resource_before_any_progress_write():
    src = inspect.getsource(__import__("app.api.student_learning", fromlist=["set_progress"]))
    set_progress_src = src.split("def set_progress", 1)[1]
    assert set_progress_src.index("get_resource") < set_progress_src.index("set_progress(")
