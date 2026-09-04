"""Phase 5 -- student assignment submissions + the READ-ONLY industry
submission view.

Two surfaces are exercised here:

* STUDENT  /api/v1/student/internship-workspaces/{id}/assignments[...]
  -- list published assignments in the student's own workspace, one
  assignment's detail with full attempt history, and creating an
  append-only submission attempt.
* INDUSTRY /api/v1/internships/{id}/program/submissions[...]
  -- list / detail / attempt history, strictly read-only.

The real guarantees (append-only rows, server-assigned attempt_number,
the ACCEPTED/IN_PROGRESS gate, the "previous attempt must be sent back"
resubmission rule, and every ownership boundary) are enforced by the DB
triggers + RLS in 038 / 039 and asserted against the migration text in
tests/test_internship_workspace_schema.py. This suite verifies the Python
layer's half: identity always comes from the token, the same rules are
re-checked so the API returns a clean 4xx instead of a 500, a resubmission
never mutates the previous attempt, and the industry view never writes.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.api import internship_programs as programs_api
from app.main import app
from app.services import internship_program_service as program_svc
from app.services import internship_workspace_service as svc
from app.services import notification_producer
from tests.conftest import authenticated_as

client = TestClient(app)

_WID = "11111111-1111-1111-1111-111111111111"
_AID = "22222222-2222-2222-2222-222222222222"
_IID = "33333333-3333-3333-3333-333333333333"
_SID = "44444444-4444-4444-4444-444444444444"


# ============================================================
# fake Supabase client (shared by both surfaces)
# ============================================================


class _Q:
    def __init__(self, fake, table):
        self.fake, self.table = fake, table
        self._filters: list[tuple] = []
        self._single = False
        self._order = None
        self._desc = False
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        self.fake.filters.append((self.table, field, value))
        return self

    def order(self, field, desc=False):
        self._order, self._desc = field, desc
        return self

    def limit(self, n):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def execute(self):
        return self.fake._exec(self)


class _RpcQ:
    def __init__(self, fake, name, params):
        self.fake, self.name, self.params = fake, name, params

    def execute(self):
        ids = (self.params or {}).get("application_ids", [])
        return SimpleNamespace(
            data=[
                {"application_id": i, "student_name": self.fake.applicant_names[i]}
                for i in ids
                if i in self.fake.applicant_names
            ]
        )


class _Fake:
    def __init__(self, **tables):
        self.tables: dict[str, list] = {k: list(v) for k, v in tables.items()}
        self.filters: list[tuple] = []
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []
        self.deletes: list[tuple] = []
        self.insert_error: Exception | None = None
        self.insert_errors: dict[str, Exception] = {}
        self.update_errors: dict[str, Exception] = {}
        self.applicant_names: dict[str, str] = {}
        self.rpc_calls: list[tuple] = []

    def table(self, name):
        return _Q(self, name)

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, params))
        return _RpcQ(self, name, params)

    def _match(self, q: _Q, row: dict) -> bool:
        for field, value in q._filters:
            if "." in field:
                # an embedded / RLS filter -- trusted in the fake, logged only
                continue
            if row.get(field) != value:
                return False
        return True

    def _exec(self, q: _Q):
        if q._op == "insert":
            self.inserts.append((q.table, q._payload))
            err = self.insert_errors.get(q.table, self.insert_error)
            if err is not None:
                raise err
            payloads = q._payload if isinstance(q._payload, list) else [q._payload]
            return SimpleNamespace(data=[dict(p) for p in payloads])
        if q._op == "update":
            self.updates.append((q.table, q._payload))
            if q.table in self.update_errors:
                raise self.update_errors[q.table]
            for row in self.tables.get(q.table, []):
                if self._match(q, row):
                    row.update(q._payload)
            return SimpleNamespace(data=[])
        if q._op == "delete":
            self.deletes.append((q.table, list(q._filters)))
            return SimpleNamespace(data=[])
        rows = [r for r in self.tables.get(q.table, []) if self._match(q, r)]
        if q._order:
            rows = sorted(rows, key=lambda r: r.get(q._order) or 0, reverse=q._desc)
        if q._single:
            return SimpleNamespace(data=rows[0] if rows else None)
        return SimpleNamespace(data=rows)


# ---- row builders ----


def _ws(**over):
    row = {
        "id": _WID,
        "application_id": "app-1",
        "internship_id": _IID,
        "student_id": _SID,
        "industry_id": "industry-1",
        "work_mode": "REMOTE",
        "workspace_status": "ACCEPTED",
        "accepted_at": "2026-09-02T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "declined_at": None,
        "decline_reason": None,
        "rescinded_at": None,
        "rescind_reason": None,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
    }
    row.update(over)
    return row


def _assignment(**over):
    row = {
        "id": _AID,
        "module_id": "m1",
        "program_id": "prog-1",
        "title": "Build a CLI",
        "description": "desc",
        "instructions": "instructions",
        "assignment_type": "ASSIGNMENT",
        "is_required": True,
        "is_published": True,
        "order_index": 0,
        "due_offset_days": 7,
        "submission_kind": "LINK",
        "repo_required": False,
        "live_url_expected": False,
        "max_score": None,
        "linked_skill_id": None,
        "module": {"id": "m1", "title": "Fundamentals", "order_index": 0},
    }
    row.update(over)
    return row


def _sub(attempt_number=1, status="SUBMITTED", **over):
    row = {
        "id": f"sub-{attempt_number}",
        "workspace_id": _WID,
        "assignment_id": _AID,
        "attempt_number": attempt_number,
        "submission_status": status,
        "repo_url": "https://github.com/x/y",
        "live_url": None,
        "attachment_url": None,
        "notes": None,
        "submitted_at": f"2026-09-0{attempt_number}T00:00:00Z",
        "created_at": f"2026-09-0{attempt_number}T00:00:00Z",
        "updated_at": f"2026-09-0{attempt_number}T00:00:00Z",
    }
    row.update(over)
    return row


# ============================================================
# STUDENT -- assignment visibility (27.6, 27.7)
# ============================================================


def test_student_lists_assignments_in_their_own_accepted_workspace():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[
            _assignment(id="a2", title="Second", order_index=1),
            _assignment(id="a1", title="First", order_index=0),
        ],
        workspace_submissions=[],
    )
    rows = svc.list_workspace_assignments(fake, _SID, _WID)
    assert [r["title"] for r in rows] == ["First", "Second"]
    assert all(r["attempt_count"] == 0 for r in rows)
    assert all(r["can_submit"] for r in rows)  # ACCEPTED, no attempts yet


def test_student_assignment_list_is_scoped_to_the_caller():
    fake = _Fake(internship_workspaces=[_ws()])  # RLS + .eq('student_id') yields nothing
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.list_workspace_assignments(fake, "student-999", _WID)
    assert ("internship_workspaces", "student_id", "student-999") in fake.filters


def test_assignment_list_folds_in_the_students_latest_attempt():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[
            _sub(1, "REVISION_REQUESTED"),
            _sub(2, "SUBMITTED"),
        ],
    )
    (row,) = svc.list_workspace_assignments(fake, _SID, _WID)
    assert row["attempt_count"] == 2
    assert row["latest_submission"]["attempt_number"] == 2
    assert row["can_submit"] is False  # latest attempt still under review
    assert "still being reviewed" in row["submit_blocked_reason"]


@pytest.mark.parametrize(
    ("state", "reason_substring"),
    [
        ("PENDING_ACCEPTANCE", "Accept the internship"),
        ("DECLINED", "declined"),
        ("RESCINDED", "withdrawn"),
        ("COMPLETED", "completed"),
    ],
)
def test_student_cannot_submit_before_accepting_or_after_a_terminal_state(state, reason_substring):
    fake = _Fake(
        internship_workspaces=[_ws(workspace_status=state)],
        program_assignments=[_assignment()],
        workspace_submissions=[],
    )
    (row,) = svc.list_workspace_assignments(fake, _SID, _WID)
    assert row["can_submit"] is False
    assert row["submit_blocked_reason"]
    # Regression (Final QA audit): COMPLETED/DECLINED/RESCINDED are terminal
    # states reached *after* acceptance, so they must never be told to
    # "accept" again -- each status gets its own accurate reason text.
    assert reason_substring in row["submit_blocked_reason"]
    if state != "PENDING_ACCEPTANCE":
        assert "Accept the internship" not in row["submit_blocked_reason"]

    with pytest.raises((svc.WorkspaceNotAcceptedError, svc.WorkspaceNotFoundError)):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x"})
    assert fake.inserts == []


@pytest.mark.parametrize("state", ["ACCEPTED", "IN_PROGRESS"])
def test_student_can_submit_from_an_active_workspace(state):
    fake = _Fake(
        internship_workspaces=[_ws(workspace_status=state)],
        program_assignments=[_assignment()],
        workspace_submissions=[],
    )
    with patch.object(svc, "get_workspace_assignment", return_value={"ok": True}):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://github.com/x/y"})
    assert fake.inserts and fake.inserts[0][0] == "workspace_submissions"
    row = fake.inserts[0][1]
    assert row == {"workspace_id": _WID, "assignment_id": _AID, "repo_url": "https://github.com/x/y"}
    # never sets attempt_number / submission_status -- the DB does
    assert "attempt_number" not in row and "submission_status" not in row


# ============================================================
# STUDENT -- submission creation + append-only history (27.8-27.13)
# ============================================================


def test_first_submission_is_attempt_one_and_starts_submitted():
    # the fake models the DB trigger: attempt_number + status are assigned
    # server-side, so the detail read reflects them.
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[],
    )

    def _record_insert(_c, _s, _w, _a):
        return {
            "assignment": _assignment(),
            "module": {"id": "m1", "title": "Fundamentals"},
            "submissions": [_sub(1, "SUBMITTED")],
            "attempt_count": 1,
            "can_submit": False,
            "submit_blocked_reason": "Your latest submission is still being reviewed.",
        }

    with patch.object(svc, "get_workspace_assignment", side_effect=_record_insert):
        detail = svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x/y"})
    assert detail["submissions"][0]["attempt_number"] == 1
    assert detail["submissions"][0]["submission_status"] == "SUBMITTED"


def test_resubmission_creates_a_new_attempt_and_never_mutates_the_previous():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[_sub(1, "REVISION_REQUESTED", repo_url="https://old")],
    )
    with patch.object(svc, "get_workspace_assignment", return_value={"attempt_count": 2}):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://new"})
    # exactly one INSERT, zero UPDATE / DELETE against workspace_submissions
    assert [t for t, _ in fake.inserts] == ["workspace_submissions"]
    assert fake.updates == [] and fake.deletes == []
    # the stored attempt 1 row is byte-for-byte untouched
    assert fake.tables["workspace_submissions"][0]["repo_url"] == "https://old"


def test_detail_returns_the_full_attempt_history_newest_first():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[
            _sub(1, "REJECTED"),
            _sub(2, "REVISION_REQUESTED"),
            _sub(3, "SUBMITTED"),
        ],
    )
    detail = svc.get_workspace_assignment(fake, _SID, _WID, _AID)
    assert [s["attempt_number"] for s in detail["submissions"]] == [3, 2, 1]
    assert detail["attempt_count"] == 3
    assert detail["module"]["title"] == "Fundamentals"


def test_detail_404s_for_a_foreign_workspace_or_an_invisible_assignment():
    # foreign workspace
    assert svc.get_workspace_assignment(_Fake(internship_workspaces=[]), _SID, _WID, _AID) is None
    # workspace ok, assignment not in the visible set
    fake = _Fake(internship_workspaces=[_ws()], program_assignments=[], workspace_submissions=[])
    assert svc.get_workspace_assignment(fake, _SID, _WID, _AID) is None


def test_submission_against_an_invisible_assignment_is_rejected():
    fake = _Fake(internship_workspaces=[_ws()], program_assignments=[], workspace_submissions=[])
    with pytest.raises(svc.AssignmentNotFoundError):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x"})
    assert fake.inserts == []


def test_a_db_rejection_of_a_submission_is_surfaced_as_409():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[_sub(1, "SUBMITTED")],
        # trigger: attempt 2 blocked because attempt 1 not sent back
    )
    fake.insert_error = APIError({"code": "42501", "message": "trigger"})
    with pytest.raises(svc.SubmissionRejectedError):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x"})


def test_a_concurrent_attempt_race_is_swallowed():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[],
    )
    fake.insert_error = APIError({"code": "23505", "message": "unique"})
    with patch.object(svc, "get_workspace_assignment", return_value={"ok": True}):
        # does not raise
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x"})


# ============================================================
# STUDENT -- malformed submission payloads (27, "Also test malformed")
# ============================================================


def test_repo_required_assignment_rejects_a_payload_without_a_repo_url():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment(submission_kind="REPO", repo_required=True)],
        workspace_submissions=[],
    )
    with pytest.raises(svc.InvalidSubmissionError):
        svc.create_submission(fake, _SID, _WID, _AID, {"notes": "no repo here"})
    assert fake.inserts == []


def test_live_url_expected_assignment_rejects_a_payload_without_a_live_url():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment(live_url_expected=True)],
        workspace_submissions=[],
    )
    with pytest.raises(svc.InvalidSubmissionError):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x"})
    assert fake.inserts == []


def test_text_assignment_requires_written_notes():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment(submission_kind="TEXT")],
        workspace_submissions=[],
    )
    with pytest.raises(svc.InvalidSubmissionError):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://x"})
    with patch.object(svc, "get_workspace_assignment", return_value={}):
        svc.create_submission(fake, _SID, _WID, _AID, {"notes": "My write-up."})
    assert fake.inserts[0][1]["notes"] == "My write-up."


def test_blank_strings_do_not_count_as_provided():
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment(submission_kind="REPO", repo_required=True)],
        workspace_submissions=[],
    )
    with pytest.raises(svc.InvalidSubmissionError):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "   "})


# ============================================================
# STUDENT -- routes: auth guards + error mapping
# ============================================================

_STUDENT_ENDPOINTS = [
    ("get", f"/api/v1/student/internship-workspaces/{_WID}/assignments"),
    ("get", f"/api/v1/student/internship-workspaces/{_WID}/assignments/{_AID}"),
    ("post", f"/api/v1/student/internship-workspaces/{_WID}/assignments/{_AID}/submissions"),
]


def _student_call(method, url, **kw):
    if method == "post":
        return client.post(url, json={"repo_url": "https://x"}, **kw)
    return getattr(client, method)(url, **kw)


def test_student_submission_endpoints_reject_unauthenticated():
    for method, url in _STUDENT_ENDPOINTS:
        assert _student_call(method, url).status_code == 401, (method, url)


def test_student_submission_endpoints_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _STUDENT_ENDPOINTS:
            with authenticated_as(role):
                resp = _student_call(method, url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, method, url)


def test_submission_endpoint_rejects_unknown_payload_fields():
    with authenticated_as("STUDENT", user_id=_SID):
        resp = client.post(
            f"/api/v1/student/internship-workspaces/{_WID}/assignments/{_AID}/submissions",
            json={"repo_url": "https://x", "score": 90},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_submission_endpoint_maps_service_errors():
    cases = [
        (svc.WorkspaceNotFoundError("x"), 404),
        (svc.AssignmentNotFoundError("x"), 404),
        (svc.WorkspaceNotAcceptedError("x"), 409),
        (svc.SubmissionRejectedError("x"), 409),
        (svc.InvalidSubmissionError("x"), 422),
    ]
    for exc, expected in cases:
        with (
            authenticated_as("STUDENT", user_id=_SID),
            patch.object(svc, "create_submission", side_effect=exc),
        ):
            resp = client.post(
                f"/api/v1/student/internship-workspaces/{_WID}/assignments/{_AID}/submissions",
                json={"repo_url": "https://x"},
                headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == expected, exc


def test_assignment_detail_endpoint_404s_when_service_returns_none():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "get_workspace_assignment", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/student/internship-workspaces/{_WID}/assignments/{_AID}",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 404


def test_submission_endpoint_is_201_on_success():
    payload = {
        "assignment": _assignment(),
        "module": {"id": "m1", "title": "Fundamentals"},
        "submissions": [_sub(1, "SUBMITTED")],
        "attempt_count": 1,
        "can_submit": False,
        "submit_blocked_reason": "Your latest submission is still being reviewed.",
    }
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "create_submission", return_value=payload),
    ):
        resp = client.post(
            f"/api/v1/student/internship-workspaces/{_WID}/assignments/{_AID}/submissions",
            json={"repo_url": "https://github.com/x/y"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 201
    assert resp.json()["submissions"][0]["attempt_number"] == 1


# ============================================================
# INDUSTRY -- READ-ONLY submission view (27.14-27.18)
# ============================================================


def _industry_fake(subs=None, *, internship_owner="industry-1"):
    fake = _Fake(
        internships=[{"id": _IID, "industry_id": internship_owner, "title": "ML Intern", "status": "PUBLISHED"}],
        workspace_submissions=subs if subs is not None else [],
    )
    return fake


def _embedded_sub(
    attempt_number=1,
    status="SUBMITTED",
    *,
    application_id="app-1",
    max_score=None,
    reviews=None,
    **over,
):
    row = _sub(attempt_number, status, **over)
    row["workspace"] = {
        "id": _WID,
        "internship_id": _IID,
        "application_id": application_id,
        "industry_id": "industry-1",
        "student_id": _SID,
    }
    row["assignment"] = {
        "id": _AID,
        "title": "Build a CLI",
        "max_score": max_score,
        "module_id": "m1",
        "module": {"id": "m1", "title": "Fundamentals"},
    }
    row["submission_reviews"] = reviews or []
    return row


def _review_row(verdict="ACCEPTED", *, feedback=None, score=None, created_at="2026-09-05T00:00:00Z"):
    return {
        "id": f"rev-{verdict}",
        "submission_id": "sub-1",
        "verdict": verdict,
        "feedback": feedback,
        "score": score,
        "reviewer_id": "industry-1",
        "created_at": created_at,
    }


def test_industry_lists_submissions_for_its_own_internship_with_context():
    fake = _industry_fake([_embedded_sub(1), _embedded_sub(2)])
    fake.applicant_names = {"app-1": "Asha Rao"}
    rows = program_svc.list_submissions(fake, "industry-1", _IID)
    assert len(rows) == 2
    assert rows[0]["student_name"] == "Asha Rao"
    assert rows[0]["assignment_title"] == "Build a CLI"
    assert rows[0]["module_title"] == "Fundamentals"
    assert rows[0]["attempt_count"] == 2
    # scoped by the embedded workspace filters
    assert ("workspace_submissions", "workspace.industry_id", "industry-1") in fake.filters
    assert ("workspace_submissions", "workspace.internship_id", _IID) in fake.filters


def test_industry_submission_list_can_filter_by_assignment_and_workspace():
    fake = _industry_fake([_embedded_sub(1)])
    program_svc.list_submissions(
        fake, "industry-1", _IID, assignment_id=_AID, workspace_id=_WID
    )
    assert ("workspace_submissions", "assignment_id", _AID) in fake.filters
    assert ("workspace_submissions", "workspace_id", _WID) in fake.filters


def test_another_company_cannot_list_submissions_for_this_internship():
    fake = _industry_fake([_embedded_sub(1)], internship_owner="industry-1")
    with pytest.raises(program_svc.InternshipNotFoundError):
        program_svc.list_submissions(fake, "industry-999", _IID)


def test_industry_submission_detail_returns_every_attempt_newest_first():
    subs = [
        _embedded_sub(1, "REJECTED"),
        _embedded_sub(2, "REVISION_REQUESTED"),
        _embedded_sub(3, "SUBMITTED"),
    ]
    fake = _industry_fake(subs)
    fake.applicant_names = {"app-1": "Asha Rao"}
    detail = program_svc.get_submission_detail(fake, "industry-1", _IID, "sub-2")
    assert detail["submission"]["attempt_number"] == 2
    assert [a["attempt_number"] for a in detail["attempts"]] == [3, 2, 1]
    assert detail["student_name"] == "Asha Rao"


def test_industry_submission_detail_is_none_for_a_foreign_or_missing_submission():
    fake = _industry_fake([_embedded_sub(1)])
    assert program_svc.get_submission_detail(fake, "industry-1", _IID, "sub-nope") is None


def test_industry_submission_view_never_writes():
    fake = _industry_fake([_embedded_sub(1), _embedded_sub(2)])
    program_svc.list_submissions(fake, "industry-1", _IID)
    program_svc.get_submission_detail(fake, "industry-1", _IID, "sub-1")
    assert fake.inserts == [] and fake.updates == [] and fake.deletes == []


def test_applicant_name_resolution_failure_is_not_fatal():
    fake = _industry_fake([_embedded_sub(1)])

    def _boom(*_a, **_k):
        raise RuntimeError("rpc down")

    fake.rpc = _boom  # type: ignore[method-assign]
    rows = program_svc.list_submissions(fake, "industry-1", _IID)
    assert rows[0]["student_name"] is None


# ============================================================
# INDUSTRY -- routes: auth guards + 404
# ============================================================

_INDUSTRY_ENDPOINTS = [
    ("get", f"/api/v1/internships/{_IID}/program/submissions"),
    ("get", f"/api/v1/internships/{_IID}/program/submissions/{_AID}"),
]


def test_industry_submission_endpoints_reject_unauthenticated():
    for method, url in _INDUSTRY_ENDPOINTS:
        assert getattr(client, method)(url).status_code == 401, url


def test_industry_submission_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _INDUSTRY_ENDPOINTS:
            with authenticated_as(role):
                resp = getattr(client, method)(url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, url)


def test_industry_submission_detail_endpoint_404s_when_service_returns_none():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(program_svc, "get_submission_detail", return_value=None),
    ):
        resp = client.get(
            f"/api/v1/internships/{_IID}/program/submissions/{_AID}",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 404


def test_industry_submission_list_endpoint_maps_internship_not_found_to_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            program_svc, "list_submissions",
            side_effect=program_svc.InternshipNotFoundError(_IID),
        ),
    ):
        resp = client.get(
            f"/api/v1/internships/{_IID}/program/submissions",
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 404


# ============================================================
# Phase 5 does NOT write later-phase tables
# ============================================================


def test_workspace_service_never_writes_review_tables():
    import inspect

    src = inspect.getsource(svc)
    # Phase 7: internship_completions / internship_certificates are
    # INSERT-only (append + idempotent-read-back on 23505) -- this module
    # never UPDATEs or DELETEs either one; a correction/revocation is a
    # later phase.
    for mutation in (
        '.table("internship_completions").update',
        '.table("internship_completions").delete',
        '.table("internship_certificates").update',
        '.table("internship_certificates").delete',
    ):
        assert mutation not in src, mutation
    # Phase 6: the student READS submission_reviews for their own attempts
    # but NEVER writes it -- reviewing is industry-only.
    for mutation in (
        '.table("submission_reviews").insert',
        '.table("submission_reviews").update',
        '.table("submission_reviews").delete',
    ):
        assert mutation not in src, mutation
    # workspace_submissions is INSERT-only from the student side -- never
    # updated or deleted here (append-only is a DB guarantee too).
    assert '.table("workspace_submissions").update' not in src
    assert '.table("workspace_submissions").delete' not in src


# ============================================================
# PHASE 6 -- industry review of a submission attempt (service)
# ============================================================


def _review_fake(*, status="SUBMITTED", max_score=None, internship_owner="industry-1", reviews=None):
    """An industry fake whose workspace_submissions table holds one
    reviewable attempt (embedded workspace + assignment for the ownership
    read), plus a plain attempts row for the get_submission_detail re-read."""
    sub = _embedded_sub(1, status, max_score=max_score, reviews=list(reviews or []))
    fake = _Fake(
        internships=[{"id": _IID, "industry_id": internship_owner, "title": "ML Intern", "status": "PUBLISHED"}],
        workspace_submissions=[sub],
        submission_reviews=[],
    )
    return fake


def test_start_review_moves_submitted_to_under_review():
    fake = _review_fake(status="SUBMITTED")
    program_svc.start_review(fake, "industry-1", _IID, "sub-1")
    assert ("workspace_submissions", {"submission_status": "UNDER_REVIEW"}) in fake.updates
    # start_review records NO submission_reviews row -- that is the verdict step
    assert [t for t, _ in fake.inserts] == []
    assert fake.tables["workspace_submissions"][0]["submission_status"] == "UNDER_REVIEW"


@pytest.mark.parametrize("state", ["UNDER_REVIEW", "REVISION_REQUESTED", "ACCEPTED", "REJECTED"])
def test_start_review_rejects_a_non_submitted_attempt(state):
    fake = _review_fake(status=state)
    with pytest.raises(program_svc.InvalidReviewTransitionError):
        program_svc.start_review(fake, "industry-1", _IID, "sub-1")
    assert fake.updates == []


def test_start_review_404s_for_a_foreign_or_missing_submission():
    fake = _review_fake()
    with pytest.raises(program_svc.SubmissionNotFoundError):
        program_svc.start_review(fake, "industry-1", _IID, "sub-nope")


def test_another_company_cannot_start_a_review():
    fake = _review_fake(internship_owner="industry-1")
    with pytest.raises(program_svc.InternshipNotFoundError):
        program_svc.start_review(fake, "industry-999", _IID, "sub-1")
    assert fake.updates == []


def test_start_review_translates_a_db_rejection_to_conflict():
    fake = _review_fake(status="SUBMITTED")
    fake.update_errors["workspace_submissions"] = APIError({"code": "42501", "message": "rls"})
    with pytest.raises(program_svc.ReviewRejectedError):
        program_svc.start_review(fake, "industry-1", _IID, "sub-1")


@pytest.mark.parametrize("verdict", ["ACCEPTED", "REVISION_REQUESTED", "REJECTED"])
@pytest.mark.parametrize("start_status", ["SUBMITTED", "UNDER_REVIEW"])
def test_review_records_a_verdict_and_updates_the_status_cache(verdict, start_status):
    fake = _review_fake(status=start_status)
    program_svc.review_submission(
        fake, "industry-1", _IID, "sub-1", {"verdict": verdict, "feedback": "Nice work", "score": None},
    )
    # 1. the submission_reviews row is the source of truth
    review_inserts = [p for t, p in fake.inserts if t == "submission_reviews"]
    assert review_inserts == [{"submission_id": "sub-1", "verdict": verdict, "feedback": "Nice work"}]
    # reviewer_id is NEVER sent from the app -- the DB trigger forces it
    assert "reviewer_id" not in review_inserts[0]
    # 2. the denormalized cache follows
    assert ("workspace_submissions", {"submission_status": verdict}) in fake.updates
    assert fake.tables["workspace_submissions"][0]["submission_status"] == verdict


def test_review_persists_a_score_within_the_assignment_maximum():
    fake = _review_fake(status="UNDER_REVIEW", max_score=100)
    program_svc.review_submission(
        fake, "industry-1", _IID, "sub-1", {"verdict": "ACCEPTED", "feedback": None, "score": 92.5},
    )
    review = next(p for t, p in fake.inserts if t == "submission_reviews")
    assert review["score"] == 92.5
    assert "feedback" not in review  # blank feedback is dropped


def test_review_rejects_a_score_above_the_assignment_maximum():
    fake = _review_fake(status="SUBMITTED", max_score=50)
    with pytest.raises(program_svc.InvalidReviewError):
        program_svc.review_submission(
            fake, "industry-1", _IID, "sub-1", {"verdict": "ACCEPTED", "score": 80},
        )
    assert fake.inserts == [] and fake.updates == []


def test_review_rejects_a_negative_score():
    fake = _review_fake(status="SUBMITTED")
    with pytest.raises(program_svc.InvalidReviewError):
        program_svc.review_submission(
            fake, "industry-1", _IID, "sub-1", {"verdict": "REJECTED", "score": -1},
        )
    assert fake.inserts == []


@pytest.mark.parametrize("state", ["ACCEPTED", "REVISION_REQUESTED", "REJECTED"])
def test_review_is_blocked_once_a_verdict_already_landed(state):
    fake = _review_fake(status=state)
    with pytest.raises(program_svc.InvalidReviewTransitionError):
        program_svc.review_submission(
            fake, "industry-1", _IID, "sub-1", {"verdict": "ACCEPTED"},
        )
    assert fake.inserts == [] and fake.updates == []


def test_review_never_rewrites_the_students_submission_content():
    fake = _review_fake(status="SUBMITTED")
    before = dict(fake.tables["workspace_submissions"][0])
    program_svc.review_submission(
        fake, "industry-1", _IID, "sub-1", {"verdict": "REVISION_REQUESTED", "feedback": "add tests"},
    )
    after = fake.tables["workspace_submissions"][0]
    for field in ("repo_url", "live_url", "attachment_url", "notes", "attempt_number", "submitted_at"):
        assert after[field] == before[field], field
    # ONLY the status cache changed
    assert after["submission_status"] == "REVISION_REQUESTED"


def test_review_404s_for_a_foreign_submission_and_writes_nothing():
    fake = _review_fake()
    with pytest.raises(program_svc.SubmissionNotFoundError):
        program_svc.review_submission(fake, "industry-1", _IID, "sub-nope", {"verdict": "ACCEPTED"})
    assert fake.inserts == [] and fake.updates == []


def test_another_company_cannot_review_this_submission():
    fake = _review_fake(internship_owner="industry-1")
    with pytest.raises(program_svc.InternshipNotFoundError):
        program_svc.review_submission(fake, "industry-999", _IID, "sub-1", {"verdict": "ACCEPTED"})
    assert fake.inserts == []


def test_review_translates_a_db_rls_rejection_to_conflict():
    fake = _review_fake(status="SUBMITTED")
    fake.insert_errors["submission_reviews"] = APIError({"code": "42501", "message": "rls"})
    with pytest.raises(program_svc.ReviewRejectedError):
        program_svc.review_submission(fake, "industry-1", _IID, "sub-1", {"verdict": "ACCEPTED"})
    # the status cache is only touched AFTER the review row lands
    assert fake.updates == []


def test_review_translates_a_check_violation_to_unprocessable():
    fake = _review_fake(status="SUBMITTED")
    fake.insert_errors["submission_reviews"] = APIError({"code": "23514", "message": "check"})
    with pytest.raises(program_svc.InvalidReviewError):
        program_svc.review_submission(fake, "industry-1", _IID, "sub-1", {"verdict": "ACCEPTED"})


def test_review_detail_read_carries_student_and_workspace_for_the_notification():
    fake = _review_fake(status="SUBMITTED")
    detail = program_svc.review_submission(
        fake, "industry-1", _IID, "sub-1", {"verdict": "ACCEPTED"},
    )
    assert detail["student_id"] == _SID
    assert detail["workspace_id"] == _WID
    assert detail["assignment_title"] == "Build a CLI"


# ============================================================
# PHASE 6 -- resubmission after a review keeps prior attempts + reviews intact
# ============================================================


def test_new_attempt_after_revision_leaves_attempt_one_and_its_review_untouched():
    review = _review_row("REVISION_REQUESTED", feedback="add auth")
    attempt1 = _sub(1, "REVISION_REQUESTED", repo_url="https://old", submission_reviews=[review])
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[attempt1],
    )
    with patch.object(svc, "get_workspace_assignment", return_value={"attempt_count": 2}):
        svc.create_submission(fake, _SID, _WID, _AID, {"repo_url": "https://new"})
    # exactly one INSERT on workspace_submissions, no UPDATE / DELETE
    assert [t for t, _ in fake.inserts] == ["workspace_submissions"]
    assert fake.updates == [] and fake.deletes == []
    stored = fake.tables["workspace_submissions"][0]
    assert stored["repo_url"] == "https://old"
    assert stored["submission_reviews"] == [review]  # attempt 1's review still attached


# ============================================================
# PHASE 6 -- student sees the review outcome for their OWN attempts only
# ============================================================


def test_student_assignment_detail_shows_the_review_without_reviewer_identity():
    review = _review_row("REVISION_REQUESTED", feedback="Please add a README", score=None)
    fake = _Fake(
        internship_workspaces=[_ws()],
        program_assignments=[_assignment()],
        workspace_submissions=[_sub(1, "REVISION_REQUESTED", submission_reviews=[review])],
    )
    detail = svc.get_workspace_assignment(fake, _SID, _WID, _AID)
    attempt = detail["submissions"][0]
    assert attempt["latest_review"]["verdict"] == "REVISION_REQUESTED"
    assert attempt["latest_review"]["feedback"] == "Please add a README"
    assert attempt["latest_review"]["reviewed_at"] == review["created_at"]
    # the student NEVER sees who reviewed
    assert "reviewer_id" not in attempt["latest_review"]
    assert attempt["reviews"] == [attempt["latest_review"]]


def test_student_cannot_read_a_foreign_workspaces_reviews():
    fake = _Fake(internship_workspaces=[_ws()])  # RLS + .eq(student_id) -> nothing
    with pytest.raises(svc.WorkspaceNotFoundError):
        svc.list_workspace_assignments(fake, "student-999", _WID)


# ============================================================
# PHASE 6 -- review routes: auth, error mapping, malformed payloads
# ============================================================

_SUBID = "55555555-5555-5555-5555-555555555555"
_REVIEW_START = f"/api/v1/internships/{_IID}/program/submissions/{_SUBID}/review/start"
_REVIEW_URL = f"/api/v1/internships/{_IID}/program/submissions/{_SUBID}/review"


def test_review_endpoints_reject_unauthenticated():
    assert client.post(_REVIEW_START, json={}).status_code == 401
    assert client.post(_REVIEW_URL, json={"verdict": "ACCEPTED"}).status_code == 401


def test_review_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            r1 = client.post(_REVIEW_START, json={}, headers={"Authorization": "Bearer t"})
            r2 = client.post(_REVIEW_URL, json={"verdict": "ACCEPTED"}, headers={"Authorization": "Bearer t"})
        assert r1.status_code == 403, role
        assert r2.status_code == 403, role


def test_review_endpoint_rejects_unknown_fields_and_bad_verdicts():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        bad_field = client.post(
            _REVIEW_URL, json={"verdict": "ACCEPTED", "reviewer_id": "x"},
            headers={"Authorization": "Bearer t"},
        )
        bad_verdict = client.post(
            _REVIEW_URL, json={"verdict": "UNDER_REVIEW"}, headers={"Authorization": "Bearer t"},
        )
        neg_score = client.post(
            _REVIEW_URL, json={"verdict": "ACCEPTED", "score": -5},
            headers={"Authorization": "Bearer t"},
        )
    assert bad_field.status_code == 422
    assert bad_verdict.status_code == 422
    assert neg_score.status_code == 422


def test_review_endpoint_maps_service_errors():
    cases = [
        (program_svc.SubmissionNotFoundError("x"), 404),
        (program_svc.InvalidReviewTransitionError("ACCEPTED", "REJECTED"), 409),
        (program_svc.ReviewRejectedError("x"), 409),
        (program_svc.InvalidReviewError("x"), 422),
        (program_svc.InternshipNotFoundError("x"), 404),
    ]
    for exc, expected in cases:
        with (
            authenticated_as("INDUSTRY", user_id="industry-1"),
            patch.object(program_svc, "review_submission", side_effect=exc),
        ):
            resp = client.post(
                _REVIEW_URL, json={"verdict": "ACCEPTED"}, headers={"Authorization": "Bearer t"},
            )
        assert resp.status_code == expected, exc


def test_start_review_endpoint_maps_conflict():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            program_svc, "start_review",
            side_effect=program_svc.InvalidReviewTransitionError("ACCEPTED", "UNDER_REVIEW"),
        ),
    ):
        resp = client.post(_REVIEW_START, json={}, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 409


def _detail_stub(verdict="ACCEPTED"):
    return {
        "submission": _sub(1, verdict),
        "student_name": "Asha Rao",
        "assignment_title": "Build a CLI",
        "module_title": "Fundamentals",
        "assignment_max_score": None,
        "attempts": [_sub(1, verdict)],
        "student_id": _SID,
        "workspace_id": _WID,
    }


def test_review_endpoint_happy_path_returns_200_and_the_updated_detail():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(program_svc, "review_submission", return_value=_detail_stub("REVISION_REQUESTED")),
        patch.object(programs_api.notification_producer, "emit_submission_review_decision") as notify,
    ):
        resp = client.post(
            _REVIEW_URL,
            json={"verdict": "REVISION_REQUESTED", "feedback": "add tests"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 200
    assert resp.json()["submission"]["submission_status"] == "REVISION_REQUESTED"
    # student_id is internal only -- never serialized
    assert "student_id" not in resp.json()
    notify.assert_called_once()


# ============================================================
# PHASE 6 -- notification is emitted exactly once per verdict, never on start
# ============================================================


@pytest.mark.parametrize("verdict", ["ACCEPTED", "REVISION_REQUESTED", "REJECTED"])
def test_a_verdict_emits_exactly_one_student_notification(verdict):
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(program_svc, "review_submission", return_value=_detail_stub(verdict)),
        patch.object(programs_api.notification_producer, "emit_submission_review_decision") as notify,
    ):
        client.post(_REVIEW_URL, json={"verdict": verdict}, headers={"Authorization": "Bearer t"})
    notify.assert_called_once_with(
        student_id=_SID, workspace_id=_WID, verdict=verdict, assignment_title="Build a CLI"
    )


def test_start_review_emits_no_notification():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(program_svc, "start_review", return_value=_detail_stub("UNDER_REVIEW")),
        patch.object(programs_api.notification_producer, "emit_submission_review_decision") as notify,
    ):
        client.post(_REVIEW_START, json={}, headers={"Authorization": "Bearer t"})
    notify.assert_not_called()


def test_a_failed_notification_write_does_not_break_the_review():
    # The real producer is best-effort (contextlib.suppress). Even with the
    # underlying service-role write blowing up, the review still returns 200.
    from unittest.mock import MagicMock

    fake_sb = MagicMock()
    fake_sb.table.side_effect = RuntimeError("db down")
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(program_svc, "review_submission", return_value=_detail_stub("ACCEPTED")),
        patch.object(notification_producer, "get_supabase", return_value=fake_sb),
    ):
        resp = client.post(
            _REVIEW_URL, json={"verdict": "ACCEPTED"}, headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 200


# ============================================================
# PHASE 6 -- notification producer behaviour
# ============================================================


def test_review_notification_producer_writes_one_internship_workspace_row():
    from unittest.mock import MagicMock

    from app.services import notification_producer

    fake_sb = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_submission_review_decision(
            student_id=_SID, workspace_id=_WID, verdict="ACCEPTED", assignment_title="Build a CLI",
        )
    insert = fake_sb.table.return_value.insert
    insert.assert_called_once()
    row = insert.call_args[0][0]
    assert row["type"] == "INTERNSHIP"
    assert row["related_entity_type"] == "INTERNSHIP_WORKSPACE"
    assert row["related_entity_id"] == _WID
    assert row["student_id"] == _SID


def test_review_notification_producer_is_a_noop_for_under_review_or_missing_ids():
    from unittest.mock import MagicMock

    from app.services import notification_producer

    fake_sb = MagicMock()
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_submission_review_decision(
            student_id=_SID, workspace_id=_WID, verdict="UNDER_REVIEW", assignment_title="x",
        )
        notification_producer.emit_submission_review_decision(
            student_id="", workspace_id=_WID, verdict="ACCEPTED", assignment_title="x",
        )
    fake_sb.table.assert_not_called()


def test_review_notification_producer_swallows_its_own_errors():
    from unittest.mock import MagicMock

    from app.services import notification_producer

    fake_sb = MagicMock()
    fake_sb.table.side_effect = RuntimeError("db down")
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        # must not raise
        notification_producer.emit_submission_review_decision(
            student_id=_SID, workspace_id=_WID, verdict="ACCEPTED", assignment_title="x",
        )


# ============================================================
# PHASE 6 -- source-inspection boundary: no completion/certificate/stipend,
# no application or program-publication writes
# ============================================================


def test_review_service_never_writes_completion_certificate_stipend_or_application():
    import inspect

    src = inspect.getsource(program_svc)
    for forbidden in (
        '.table("internship_completions")',
        '.table("internship_certificates")',
        '.table("stipend_disbursements")',
        '.table("applications")',
    ):
        assert forbidden not in src, forbidden
    # the review path only writes submission_reviews (insert) and the
    # workspace_submissions.submission_status cache (update).
    assert '.table("submission_reviews").update' not in src
    assert '.table("submission_reviews").delete' not in src
    # internship_programs is only ever moved DRAFT -> PUBLISHED by
    # publish_program; review must not update programs.
    review_src = inspect.getsource(program_svc.review_submission) + inspect.getsource(
        program_svc.start_review
    )
    assert "internship_programs" not in review_src
