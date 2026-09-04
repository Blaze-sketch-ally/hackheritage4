"""Phase 3 -- the student Internship Workspace read + acceptance surface
(/api/v1/student/internship-workspaces).

Route tests mock the service and use tests.conftest.authenticated_as
(same convention as tests/test_applications.py). Service tests drive the
functions with a small purpose-built fake Supabase client -- no live
project.

RLS + the DB triggers enforce_workspace_status_transitions and
enforce_workspace_skill_selectable (038_internship_workspace.sql, applied
+ verified live in Phase 1) are the real access-control boundary: a
student can never read/write another student's workspace, and the only
student transition allowed is PENDING_ACCEPTANCE -> ACCEPTED|DECLINED.
This suite verifies the Python layer's half -- every read/write is scoped
to the caller's own id, the role guards gate every route, the same
transition/skill rules are re-checked so the API returns a clean 4xx, and
the workspace stays readable regardless of the internship posting status.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import internship_workspace_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_WID = "11111111-1111-1111-1111-111111111111"


# ============================================================
# fake Supabase client
# ============================================================


def _ws_row(**overrides):
    row = {
        "id": _WID,
        "application_id": "app-1",
        "internship_id": "int-1",
        "student_id": "student-1",
        "industry_id": "industry-1",
        "work_mode": "REMOTE",
        "workspace_status": "PENDING_ACCEPTANCE",
        "accepted_at": None,
        "started_at": None,
        "completed_at": None,
        "declined_at": None,
        "decline_reason": None,
        "rescinded_at": None,
        "rescind_reason": None,
        "created_at": "2026-09-04T00:00:00Z",
        "updated_at": "2026-09-04T00:00:00Z",
    }
    row.update(overrides)
    return row


class _Q:
    def __init__(self, fake, table):
        self._fake, self._table = fake, table
        self._single = False
        self._insert = None
        self._delete = False
        self._eqs: list[tuple] = []

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def eq(self, field, value):
        self._eqs.append((field, value))
        self._fake.filters.append((self._table, field, value))
        return self

    def in_(self, *a, **k):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        self._insert = payload
        return self

    def delete(self):
        self._delete = True
        return self

    def update(self, payload):
        self._fake.updates.append((self._table, payload))
        self._pending_update = payload
        return self

    def execute(self):
        return self._fake._execute(self)


class _Fake:
    def __init__(
        self,
        *,
        workspace=None,
        workspace_list=None,
        program=None,
        modules=None,
        program_skills=None,
        selections=None,
        update_error=None,
        insert_error=None,
    ):
        self.workspace = workspace
        self.workspace_list = workspace_list or []
        self.program = program
        self.modules = modules or []
        self.program_skills = program_skills or []
        self.selections = selections or []
        self.update_error = update_error
        self.insert_error = insert_error
        self.filters: list[tuple] = []
        self.updates: list[tuple] = []
        self.deletes: list[tuple] = []
        self.inserts: list[tuple] = []

    def table(self, name):
        return _Q(self, name)

    def _execute(self, q: _Q):
        t = q._table
        if getattr(q, "_pending_update", None) is not None:
            if t == "internship_workspaces" and self.update_error is not None:
                raise self.update_error
            return SimpleNamespace(data=[{"id": _WID}])
        if q._delete:
            self.deletes.append((t, dict(q._eqs)))
            return SimpleNamespace(data=[])
        if q._insert is not None:
            self.inserts.append((t, q._insert))
            if t == "workspace_skill_selections" and self.insert_error is not None:
                raise self.insert_error
            return SimpleNamespace(data=q._insert if isinstance(q._insert, list) else [q._insert])

        if t == "internship_workspaces":
            if q._single:
                return SimpleNamespace(data=self.workspace)
            return SimpleNamespace(data=self.workspace_list)
        if t == "internship_programs":
            return SimpleNamespace(data=self.program)
        if t == "program_modules":
            return SimpleNamespace(data=self.modules)
        if t == "program_skills":
            rows = self.program_skills
            if ("requirement", "OPTIONAL") in q._eqs:
                rows = [r for r in rows if r.get("requirement") == "OPTIONAL"]
            return SimpleNamespace(data=rows)
        if t == "workspace_skill_selections":
            return SimpleNamespace(data=self.selections)
        raise AssertionError(f"unexpected table {t!r}")


_INTERNSHIP = {
    "id": "int-1", "title": "ML Intern", "description": "Build models.",
    "work_mode": "REMOTE", "status": "PUBLISHED",
}


@pytest.fixture(autouse=True)
def _stub_internship_resolver():
    """_resolve_internship_summaries is the one service-role call; stub it
    everywhere so no test builds a real client. Individual tests override
    the return value where the internship posting status matters."""
    with patch.object(svc, "_resolve_internship_summaries", return_value={"int-1": _INTERNSHIP}):
        yield


# ============================================================
# service -- detail read (B, C, R, S, T)
# ============================================================


def test_detail_returns_workspace_program_and_selections():
    fake = _Fake(
        workspace=_ws_row(workspace_status="ACCEPTED"),
        program={"id": "prog-1", "title": "ML Program", "summary": "Learn ML.", "status": "PUBLISHED"},
        modules=[{
            "id": "m1", "title": "Python", "description": None, "order_index": 0,
            "module_items": [
                {"id": "i2", "title": "B", "item_type": "PDF", "content_url": "u", "content_text": None, "order_index": 1, "is_published": True},
                {"id": "i1", "title": "A", "item_type": "VIDEO", "content_url": "v", "content_text": None, "order_index": 0, "is_published": True},
            ],
        }],
        program_skills=[
            {"skill_id": "s-req", "requirement": "REQUIRED", "skill": {"id": "s-req", "name": "Python"}},
            {"skill_id": "s-opt", "requirement": "OPTIONAL", "skill": {"id": "s-opt", "name": "SQL"}},
        ],
        selections=[{"skill_id": "s-opt"}],
    )
    detail = svc.get_student_workspace(fake, "student-1", _WID)
    assert detail["internship"]["title"] == "ML Intern"
    assert detail["program"]["title"] == "ML Program"
    assert [m["title"] for m in detail["program"]["modules"]] == ["Python"]
    assert [it["title"] for it in detail["program"]["modules"][0]["items"]] == ["A", "B"]  # ordered
    assert [s["requirement"] for s in detail["program"]["skills"]] == ["REQUIRED", "OPTIONAL"]
    assert detail["selected_skill_ids"] == ["s-opt"]


def test_detail_is_scoped_to_the_caller_and_404s_for_a_foreign_workspace():
    fake = _Fake(workspace=None)  # RLS + .eq("student_id", ...) yielded nothing
    assert svc.get_student_workspace(fake, "student-9", _WID) is None
    assert ("internship_workspaces", "student_id", "student-9") in fake.filters


def test_detail_survives_a_closed_internship_posting():
    fake = _Fake(workspace=_ws_row(workspace_status="ACCEPTED"), program=None)
    with patch.object(
        svc, "_resolve_internship_summaries",
        return_value={"int-1": {**_INTERNSHIP, "status": "ARCHIVED"}},
    ):
        detail = svc.get_student_workspace(fake, "student-1", _WID)
    assert detail["internship"]["status"] == "ARCHIVED"
    assert detail["internship"]["title"] == "ML Intern"
    assert detail["program"] is None


def test_detail_never_queries_internships_through_the_user_client():
    # the ONLY internships read is the patched service-role resolver
    fake = _Fake(workspace=_ws_row())
    svc.get_student_workspace(fake, "student-1", _WID)
    assert not any(f[0] == "internships" for f in fake.filters)


# ============================================================
# service -- accept / decline (F, G, H, I, J, K, L, S)
# ============================================================


def _accept_fake(status_value):
    return _Fake(workspace=_ws_row(workspace_status=status_value), program=None, selections=[])


def test_accept_from_pending_works():
    fake = _accept_fake("PENDING_ACCEPTANCE")
    calls = {"n": 0}

    def read(_c, _s, _w):  # first read: PENDING; second (post-update): ACCEPTED
        calls["n"] += 1
        return _ws_row(workspace_status="PENDING_ACCEPTANCE" if calls["n"] == 1 else "ACCEPTED")

    with patch.object(svc, "_read_own_workspace", side_effect=read):
        detail = svc.accept_workspace(fake, "student-1", _WID)
    assert detail["workspace_status"] == "ACCEPTED"
    written = fake.updates[0][1]
    assert written["workspace_status"] == "ACCEPTED"
    assert "accepted_at" in written
    # only ever writes the workspace table -- never applications / internships
    assert all(t == "internship_workspaces" for t, _ in fake.updates)


def test_decline_from_pending_works():
    fake = _accept_fake("PENDING_ACCEPTANCE")
    calls = {"n": 0}

    def read(c, s, w):
        calls["n"] += 1
        return _ws_row(workspace_status="PENDING_ACCEPTANCE" if calls["n"] == 1 else "DECLINED")

    with patch.object(svc, "_read_own_workspace", side_effect=read):
        detail = svc.decline_workspace(fake, "student-1", _WID, "Timing clash")
    assert detail["workspace_status"] == "DECLINED"
    written = fake.updates[0][1]
    assert written["workspace_status"] == "DECLINED"
    assert written["decline_reason"] == "Timing clash"


@pytest.mark.parametrize("current", ["ACCEPTED", "DECLINED", "RESCINDED", "IN_PROGRESS", "COMPLETED"])
def test_accept_is_rejected_from_any_non_pending_state(current):
    fake = _accept_fake(current)
    with pytest.raises(svc.InvalidWorkspaceTransitionError):
        svc.accept_workspace(fake, "student-1", _WID)
    assert fake.updates == []  # nothing written


@pytest.mark.parametrize("current", ["ACCEPTED", "DECLINED", "RESCINDED", "IN_PROGRESS", "COMPLETED"])
def test_decline_is_rejected_from_any_non_pending_state(current):
    fake = _accept_fake(current)
    with pytest.raises(svc.InvalidWorkspaceTransitionError):
        svc.decline_workspace(fake, "student-1", _WID)
    assert fake.updates == []


def test_transition_translates_a_db_trigger_rejection_to_409():
    fake = _Fake(
        workspace=_ws_row(workspace_status="PENDING_ACCEPTANCE"),
        update_error=APIError({"code": "42501", "message": "trigger"}),
    )
    with pytest.raises(svc.InvalidWorkspaceTransitionError):
        svc.accept_workspace(fake, "student-1", _WID)


def test_transition_404s_for_a_foreign_or_missing_workspace():
    fake = _Fake(workspace=None)
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.accept_workspace(fake, "student-9", _WID)
    assert fake.updates == []


# ============================================================
# service -- skill selection (M, N, O, P, Q)
# ============================================================


def _skill_fake(status_value="ACCEPTED", *, optional_ids=("s-opt", "s-opt2"), **kw):
    program_skills = [
        {"skill_id": "s-req", "requirement": "REQUIRED", "skill": {"id": "s-req", "name": "Python"}},
        *[
            {"skill_id": sid, "requirement": "OPTIONAL", "skill": {"id": sid, "name": sid}}
            for sid in optional_ids
        ],
    ]
    return _Fake(
        workspace=_ws_row(workspace_status=status_value),
        program={"id": "prog-1", "title": "P", "summary": None, "status": "PUBLISHED"},
        program_skills=program_skills,
        **kw,
    )


def test_optional_skills_can_be_selected():
    fake = _skill_fake(selections=[])
    with patch.object(svc, "get_student_workspace", return_value={"selected_skill_ids": ["s-opt"]}):
        svc.set_skill_selections(fake, "student-1", _WID, ["s-opt"])
    assert fake.deletes and fake.deletes[0][0] == "workspace_skill_selections"
    inserted = fake.inserts[0][1]
    assert inserted == [{"workspace_id": _WID, "skill_id": "s-opt"}]


def test_optional_skills_can_be_deselected_replace_set_to_empty():
    fake = _skill_fake(selections=[{"skill_id": "s-opt"}])
    with patch.object(svc, "get_student_workspace", return_value={"selected_skill_ids": []}):
        svc.set_skill_selections(fake, "student-1", _WID, [])
    assert fake.deletes  # cleared
    assert fake.inserts == []  # nothing re-inserted


def test_duplicate_skill_ids_are_normalised():
    fake = _skill_fake(selections=[])
    with patch.object(svc, "get_student_workspace", return_value={}):
        svc.set_skill_selections(fake, "student-1", _WID, ["s-opt", "s-opt", "s-opt2", ""])
    inserted = fake.inserts[0][1]
    assert [r["skill_id"] for r in inserted] == ["s-opt", "s-opt2"]


def test_a_required_skill_cannot_be_selected():
    fake = _skill_fake()
    with pytest.raises(svc.InvalidSkillSelectionError):
        svc.set_skill_selections(fake, "student-1", _WID, ["s-req"])
    assert fake.deletes == [] and fake.inserts == []


def test_a_skill_from_another_program_is_rejected():
    fake = _skill_fake(optional_ids=("s-opt",))
    with pytest.raises(svc.InvalidSkillSelectionError):
        svc.set_skill_selections(fake, "student-1", _WID, ["s-from-elsewhere"])
    assert fake.deletes == [] and fake.inserts == []


def test_skill_selection_requires_an_accepted_workspace():
    for state in ("PENDING_ACCEPTANCE", "DECLINED", "RESCINDED", "COMPLETED"):
        fake = _skill_fake(state)
        with pytest.raises(svc.WorkspaceNotAcceptedError):
            svc.set_skill_selections(fake, "student-1", _WID, ["s-opt"])
        assert fake.deletes == []


def test_skill_selection_404s_for_a_foreign_workspace():
    fake = _skill_fake()
    fake.workspace = None
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.set_skill_selections(fake, "student-9", _WID, ["s-opt"])


def test_skill_selection_translates_a_trigger_rejection_to_invalid_selection():
    fake = _skill_fake(insert_error=APIError({"code": "42501", "message": "trigger"}))
    with pytest.raises(svc.InvalidSkillSelectionError):
        svc.set_skill_selections(fake, "student-1", _WID, ["s-opt"])


def test_skill_selection_never_writes_program_skills_or_internship_skills():
    fake = _skill_fake(selections=[])
    with patch.object(svc, "get_student_workspace", return_value={}):
        svc.set_skill_selections(fake, "student-1", _WID, ["s-opt"])
    written_tables = {t for t, _ in fake.inserts} | {t for t, _ in fake.deletes} | {t for t, _ in fake.updates}
    assert written_tables <= {"workspace_skill_selections"}


# ============================================================
# routes -- auth / role guards (D, E)
# ============================================================

_STUDENT_ENDPOINTS = [
    ("get", "/api/v1/student/internship-workspaces"),
    ("get", f"/api/v1/student/internship-workspaces/{_WID}"),
    ("post", f"/api/v1/student/internship-workspaces/{_WID}/accept"),
    ("post", f"/api/v1/student/internship-workspaces/{_WID}/decline"),
    ("put", f"/api/v1/student/internship-workspaces/{_WID}/skills"),
]


def _call(method, url, **kw):
    body = kw.pop("json", {} if method in {"post", "put"} else None)
    if method == "put":
        body = {"skill_ids": []}
    return getattr(client, method)(url, json=body, **kw) if body is not None else getattr(client, method)(url, **kw)


def test_all_student_endpoints_reject_unauthenticated():
    for method, url in _STUDENT_ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_all_student_endpoints_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _STUDENT_ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# routes -- behaviour (A, F, G, H, T)
# ============================================================


def test_list_endpoint_scopes_to_the_caller():
    captured = {}

    def fake_list(_c, student_id):
        captured["student_id"] = student_id
        return [_ws_row(student_id=student_id, internship={"id": "int-1", "title": "ML Intern", "description": None, "work_mode": "REMOTE", "status": "PUBLISHED"})]

    with (
        authenticated_as("STUDENT", user_id="student-42"),
        patch.object(svc, "list_student_workspaces", side_effect=fake_list),
    ):
        resp = client.get("/api/v1/student/internship-workspaces", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert captured["student_id"] == "student-42"


def test_detail_endpoint_404s_when_service_returns_none():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "get_student_workspace", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/internship-workspaces/{_WID}", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 404


def _detail_payload(**over):
    row = _ws_row(**over)
    row["internship"] = {"id": "int-1", "title": "ML Intern", "description": "d", "work_mode": "REMOTE", "status": "PUBLISHED"}
    row["program"] = None
    row["selected_skill_ids"] = []
    return row


def test_accept_endpoint_returns_the_updated_detail():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "accept_workspace", return_value=_detail_payload(workspace_status="ACCEPTED", accepted_at="2026-09-04T01:00:00Z")),
    ):
        resp = client.post(
            f"/api/v1/student/internship-workspaces/{_WID}/accept", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 200
    assert resp.json()["workspace_status"] == "ACCEPTED"


def test_decline_endpoint_returns_the_updated_detail():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(svc, "decline_workspace", return_value=_detail_payload(workspace_status="DECLINED")),
    ):
        resp = client.post(
            f"/api/v1/student/internship-workspaces/{_WID}/decline",
            json={"reason": "clash"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 200
    assert resp.json()["workspace_status"] == "DECLINED"


def test_accept_endpoint_maps_invalid_transition_to_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            svc, "accept_workspace",
            side_effect=svc.InvalidWorkspaceTransitionError("DECLINED", "ACCEPTED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/student/internship-workspaces/{_WID}/accept", headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 409


def test_skills_endpoint_maps_invalid_selection_to_422_and_not_accepted_to_409():
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            svc, "set_skill_selections", side_effect=svc.InvalidSkillSelectionError("nope")
        ),
    ):
        r1 = client.put(
            f"/api/v1/student/internship-workspaces/{_WID}/skills",
            json={"skill_ids": ["x"]}, headers={"Authorization": "Bearer t"},
        )
    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(
            svc, "set_skill_selections", side_effect=svc.WorkspaceNotAcceptedError("accept first")
        ),
    ):
        r2 = client.put(
            f"/api/v1/student/internship-workspaces/{_WID}/skills",
            json={"skill_ids": ["x"]}, headers={"Authorization": "Bearer t"},
        )
    assert r1.status_code == 422
    assert r2.status_code == 409


def test_skills_endpoint_rejects_extra_fields():
    with authenticated_as("STUDENT", user_id="student-1"):
        resp = client.put(
            f"/api/v1/student/internship-workspaces/{_WID}/skills",
            json={"skill_ids": [], "workspace_status": "ACCEPTED"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422
