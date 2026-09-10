"""Phase J3 -- STUDENT Job Training consumption API
(/api/v1/student/job-training).

Route tests mock the service + use tests.conftest.authenticated_as
(same convention as the other student API suites). Service tests drive
list_student_enrollments / get_student_program with a small in-memory
fake Supabase client that ENFORCES the J1 RLS predicates in its read
path:

  * job_training_enrollments  -> only auth.uid() == student_id
  * jobs                      -> only status == 'PUBLISHED'
  * job_programs              -> only status == 'PUBLISHED' AND a
                                non-revoked enrollment exists for
                                (student, job)  == student_can_access_job_program
  * job_program_modules       -> only is_published AND program visible
  * job_program_items / _assignments -> only is_published AND module visible
  * job_program_skills        -> only program visible

So a data-leak / unpublished-content bug is a test failure, not a
missed mock assertion. Note the program-visibility predicate DELIBERATELY
never checks jobs.status -- a CLOSED / ARCHIVED job keeps a selected
candidate's access.
"""

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import job_training_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_SID = "student-1"
_EID = "enr-1"


# ============================================================
# in-memory fake Supabase with RLS baked into the read path
# ============================================================


class _Q:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.eqs: list[tuple] = []
        self.neqs: list[tuple] = []
        self.ins: list[tuple] = []
        self.single = False
        self.select_str = "*"
        self.order_field = None

    def select(self, s="*", *a, **k):
        self.select_str = s
        return self

    def eq(self, f, v):
        self.eqs.append((f, v))
        return self

    def neq(self, f, v):
        self.neqs.append((f, v))
        return self

    def in_(self, f, vs):
        self.ins.append((f, list(vs)))
        return self

    def order(self, f, desc=False):
        self.order_field = (f, desc)
        return self

    def limit(self, n):
        return self

    def maybe_single(self):
        self.single = True
        return self

    def _match(self, r):
        if not all(r.get(f) == v for f, v in self.eqs):
            return False
        if any(r.get(f) == v for f, v in self.neqs):
            return False
        return all(r.get(f) in set(vs) for f, vs in self.ins)

    def execute(self):
        rows = [
            self.db.embed(self.table_name, dict(r), self.select_str)
            for r in self.db.visible(self.table_name)
            if self._match(r)
        ]
        if self.order_field:
            f, desc = self.order_field
            rows.sort(key=lambda r: (r.get(f) is None, r.get(f)), reverse=desc)
        if self.single:
            return SimpleNamespace(data=rows[0] if rows else None)
        return SimpleNamespace(data=rows)


class _StudentDB:
    def __init__(self, *, student_id=_SID, **tables):
        self.student_id = student_id
        self.tables: dict[str, list] = {
            "job_training_enrollments": [],
            "job_programs": [],
            "job_program_modules": [],
            "job_program_items": [],
            "job_program_assignments": [],
            "job_program_skills": [],
            "jobs": [],
            "skills": [],
        }
        for name, rows in tables.items():
            self.tables[name] = rows

    def t(self, name):
        return self.tables.setdefault(name, [])

    def table(self, name):
        return _Q(self, name)

    # ---- RLS ----

    def _has_enrollment(self, job_id):
        return any(
            e["student_id"] == self.student_id
            and e["job_id"] == job_id
            and e["enrollment_status"] != "REVOKED"
            for e in self.t("job_training_enrollments")
        )

    def _program_visible(self, program_id):
        return any(p["id"] == program_id for p in self.visible("job_programs"))

    def _module_visible(self, module_id):
        return any(m["id"] == module_id for m in self.visible("job_program_modules"))

    def visible(self, table):
        if table == "job_training_enrollments":
            return [r for r in self.t(table) if r["student_id"] == self.student_id]
        if table == "jobs":
            return [r for r in self.t(table) if r.get("status") == "PUBLISHED"]
        if table == "job_programs":
            return [
                r
                for r in self.t(table)
                if r.get("status") == "PUBLISHED" and self._has_enrollment(r["job_id"])
            ]
        if table == "job_program_modules":
            return [
                r
                for r in self.t(table)
                if r.get("is_published") and self._program_visible(r["program_id"])
            ]
        if table in ("job_program_items", "job_program_assignments"):
            return [
                r
                for r in self.t(table)
                if r.get("is_published") and self._module_visible(r["module_id"])
            ]
        if table == "job_program_skills":
            return [r for r in self.t(table) if self._program_visible(r["program_id"])]
        return self.t(table)

    def embed(self, table, row, select_str):
        if table == "job_program_modules":
            if "job_program_items(" in select_str:
                row["job_program_items"] = [
                    dict(i)
                    for i in self.visible("job_program_items")
                    if i["module_id"] == row["id"]
                ]
            if "job_program_assignments(" in select_str:
                row["job_program_assignments"] = [
                    dict(a)
                    for a in self.visible("job_program_assignments")
                    if a["module_id"] == row["id"]
                ]
        if table == "job_program_skills" and "skill:skills(" in select_str:
            skill = next(
                (s for s in self.t("skills") if s["id"] == row.get("skill_id")), None
            )
            row["skill"] = {"name": skill["name"]} if skill else None
        return row


def _enr(**over):
    row = {
        "id": _EID,
        "application_id": "app-1",
        "job_id": "job-1",
        "student_id": _SID,
        "industry_id": "industry-1",
        "enrollment_status": "ACTIVE",
        "completed_at": None,
        "revoked_at": None,
        "revoke_reason": None,
        "created_at": "2026-09-08T00:00:00Z",
        "updated_at": "2026-09-08T00:00:00Z",
    }
    row.update(over)
    return row


def _prog(**over):
    row = {
        "id": "prog-1",
        "job_id": "job-1",
        "title": "Platform Onboarding",
        "summary": "Ramp up",
        "estimated_weeks": 6,
        "status": "PUBLISHED",
        "published_at": "2026-09-08T00:00:00Z",
    }
    row.update(over)
    return row


def _module(**over):
    row = {
        "id": "m1",
        "program_id": "prog-1",
        "title": "Week 1",
        "description": None,
        "order_index": 0,
        "is_published": True,
    }
    row.update(over)
    return row


def _item(**over):
    row = {
        "id": "i1",
        "module_id": "m1",
        "title": "Welcome",
        "item_type": "VIDEO",
        "content_url": "https://x",
        "content_text": None,
        "order_index": 0,
        "is_published": True,
    }
    row.update(over)
    return row


def _assignment(**over):
    row = {
        "id": "as1",
        "module_id": "m1",
        "program_id": "prog-1",
        "title": "First task",
        "description": None,
        "instructions": None,
        "assignment_type": "ASSIGNMENT",
        "is_required": True,
        "order_index": 0,
        "due_offset_days": None,
        "submission_kind": "LINK",
        "repo_required": False,
        "live_url_expected": False,
        "max_score": None,
        "linked_skill_id": None,
        "is_published": True,
    }
    row.update(over)
    return row


def _full_db(*, student_id=_SID, job_status="PUBLISHED", **over):
    return _StudentDB(
        student_id=student_id,
        job_training_enrollments=over.get("enrollments", [_enr()]),
        job_programs=over.get("programs", [_prog()]),
        job_program_modules=over.get("modules", [_module()]),
        job_program_items=over.get("items", [_item()]),
        job_program_assignments=over.get("assignments", [_assignment()]),
        job_program_skills=over.get(
            "skills", [{"skill_id": "sk-py", "program_id": "prog-1", "requirement": "REQUIRED"}]
        ),
        jobs=over.get("jobs", [{"id": "job-1", "title": "Platform Engineer", "status": job_status}]),
        skills=[{"id": "sk-py", "name": "Python"}, {"id": "sk-sql", "name": "SQL"}],
    )


# ============================================================
# C. student list (tests 22-27)
# ============================================================


def test_student_sees_own_active_enrollment():
    rows = svc.list_student_enrollments(_full_db(), _SID)
    assert len(rows) == 1
    r = rows[0]
    assert r["enrollment_id"] == _EID
    assert r["job_id"] == "job-1"
    assert r["program_id"] == "prog-1"
    assert r["program_title"] == "Platform Onboarding"
    assert r["program_status"] == "PUBLISHED"
    assert r["enrollment_status"] == "ACTIVE"


def test_student_does_not_see_another_students_enrollment():
    db = _full_db(enrollments=[_enr(student_id="student-OTHER")])
    assert svc.list_student_enrollments(db, _SID) == []


def test_revoked_enrollment_is_excluded_from_the_list():
    db = _full_db(enrollments=[_enr(enrollment_status="REVOKED")])
    assert svc.list_student_enrollments(db, _SID) == []


def test_no_enrollment_means_no_training_entry():
    db = _full_db(enrollments=[])
    assert svc.list_student_enrollments(db, _SID) == []


def test_list_shows_the_enrollment_but_null_program_when_program_still_draft():
    db = _full_db(programs=[_prog(status="DRAFT")])
    rows = svc.list_student_enrollments(db, _SID)
    assert len(rows) == 1
    assert rows[0]["program_id"] is None
    assert rows[0]["program_title"] is None
    assert rows[0]["program_status"] is None
    assert rows[0]["enrollment_status"] == "ACTIVE"


def test_list_job_title_is_best_effort_null_for_a_closed_job():
    db = _full_db(jobs=[{"id": "job-1", "title": "Platform Engineer", "status": "CLOSED"}])
    rows = svc.list_student_enrollments(db, _SID)
    # access still works (program visible), job title just not readable
    assert rows[0]["job_title"] is None
    assert rows[0]["program_id"] == "prog-1"


def test_completed_enrollment_is_still_listed():
    db = _full_db(enrollments=[_enr(enrollment_status="COMPLETED", completed_at="2026-10-01T00:00:00Z")])
    rows = svc.list_student_enrollments(db, _SID)
    assert rows[0]["enrollment_status"] == "COMPLETED"
    assert rows[0]["completed_at"] == "2026-10-01T00:00:00Z"


# ============================================================
# D. student program detail (tests 28-36)
# ============================================================


def test_own_valid_enrollment_plus_published_program_is_accessible():
    detail = svc.get_student_program(_full_db(), _SID, _EID)
    assert detail is not None
    assert detail["program"]["id"] == "prog-1"
    assert detail["program"]["status"] == "PUBLISHED"
    assert detail["enrollment"]["enrollment_id"] == _EID
    assert [m["id"] for m in detail["modules"]] == ["m1"]
    assert detail["modules"][0]["items"][0]["id"] == "i1"
    assert detail["modules"][0]["assignments"][0]["id"] == "as1"
    assert detail["skills"][0]["skill_name"] == "Python"


def test_another_students_enrollment_is_inaccessible():
    db = _full_db()
    assert svc.get_student_program(db, "student-OTHER", _EID) is None


def test_unpublished_program_is_inaccessible():
    db = _full_db(programs=[_prog(status="DRAFT")])
    assert svc.get_student_program(db, _SID, _EID) is None


def test_revoked_enrollment_detail_is_inaccessible():
    db = _full_db(enrollments=[_enr(enrollment_status="REVOKED")])
    assert svc.get_student_program(db, _SID, _EID) is None


def test_no_enrollment_detail_is_inaccessible():
    db = _full_db(enrollments=[])
    assert svc.get_student_program(db, _SID, _EID) is None


def test_unknown_enrollment_id_is_inaccessible():
    assert svc.get_student_program(_full_db(), _SID, "enr-does-not-exist") is None


def test_selected_job_without_a_program_is_inaccessible():
    db = _full_db(programs=[])
    assert svc.get_student_program(db, _SID, _EID) is None


def test_closed_job_with_a_valid_enrollment_is_still_accessible():
    db = _full_db(jobs=[{"id": "job-1", "title": "PE", "status": "CLOSED"}])
    detail = svc.get_student_program(db, _SID, _EID)
    assert detail is not None
    assert detail["program"]["id"] == "prog-1"


def test_archived_job_with_a_valid_enrollment_is_still_accessible():
    db = _full_db(jobs=[{"id": "job-1", "title": "PE", "status": "ARCHIVED"}])
    assert svc.get_student_program(db, _SID, _EID) is not None


# ============================================================
# E. content filtering + ordering (tests 37-43)
# ============================================================


def test_unpublished_module_is_not_returned():
    db = _full_db(modules=[_module(id="m1", is_published=True), _module(id="m2", is_published=False)])
    detail = svc.get_student_program(db, _SID, _EID)
    assert [m["id"] for m in detail["modules"]] == ["m1"]


def test_unpublished_item_is_not_returned():
    db = _full_db(items=[_item(id="i1", is_published=True), _item(id="i2", is_published=False)])
    detail = svc.get_student_program(db, _SID, _EID)
    assert [i["id"] for i in detail["modules"][0]["items"]] == ["i1"]


def test_unpublished_assignment_is_not_returned():
    db = _full_db(
        assignments=[_assignment(id="as1", is_published=True), _assignment(id="as2", is_published=False)]
    )
    detail = svc.get_student_program(db, _SID, _EID)
    assert [a["id"] for a in detail["modules"][0]["assignments"]] == ["as1"]


def test_item_response_never_exposes_is_published():
    detail = svc.get_student_program(_full_db(), _SID, _EID)
    assert "is_published" not in detail["modules"][0]["items"][0]
    assert "is_published" not in detail["modules"][0]["assignments"][0]


def test_module_ordering_is_preserved():
    db = _full_db(modules=[
        _module(id="m2", order_index=1, title="B"),
        _module(id="m1", order_index=0, title="A"),
    ])
    detail = svc.get_student_program(db, _SID, _EID)
    assert [m["title"] for m in detail["modules"]] == ["A", "B"]


def test_item_ordering_is_preserved():
    db = _full_db(items=[
        _item(id="i2", order_index=1, title="B"),
        _item(id="i1", order_index=0, title="A"),
    ])
    detail = svc.get_student_program(db, _SID, _EID)
    assert [i["title"] for i in detail["modules"][0]["items"]] == ["A", "B"]


def test_assignment_ordering_is_preserved():
    db = _full_db(assignments=[
        _assignment(id="a2", order_index=1, title="B"),
        _assignment(id="a1", order_index=0, title="A"),
    ])
    detail = svc.get_student_program(db, _SID, _EID)
    assert [a["title"] for a in detail["modules"][0]["assignments"]] == ["A", "B"]


def test_a_module_from_a_different_program_is_never_leaked():
    db = _full_db(modules=[_module(id="m1", program_id="prog-1"),
                           _module(id="m-other", program_id="prog-OTHER")])
    detail = svc.get_student_program(db, _SID, _EID)
    assert [m["id"] for m in detail["modules"]] == ["m1"]


# ============================================================
# G. authorization on the student routes (tests 50-55)
# ============================================================

_LIST_URL = "/api/v1/student/job-training"
_DETAIL_URL = f"/api/v1/student/job-training/{_EID}"


def test_student_routes_reject_unauthenticated():
    assert client.get(_LIST_URL).status_code == 401
    assert client.get(_DETAIL_URL).status_code == 401


def test_student_routes_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        for url in (_LIST_URL, _DETAIL_URL):
            with authenticated_as(role):
                resp = client.get(url, headers={"Authorization": "Bearer t"})
            assert resp.status_code == 403, (role, url)


def test_list_endpoint_returns_the_students_enrollments():
    payload = [
        {
            "enrollment_id": _EID, "application_id": "app-1", "job_id": "job-1",
            "job_title": "PE", "program_id": "prog-1", "program_title": "Onboarding",
            "program_status": "PUBLISHED", "enrollment_status": "ACTIVE",
            "created_at": "2026-09-08T00:00:00Z", "completed_at": None,
        }
    ]
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "list_student_enrollments", return_value=payload) as list_fn,
    ):
        resp = client.get(_LIST_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert resp.json()["enrollments"][0]["enrollment_id"] == _EID
    # student id comes from the token, never the request
    assert list_fn.call_args.args[1] == _SID


def test_detail_endpoint_404s_for_an_inaccessible_enrollment():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "get_student_program", return_value=None),
    ):
        resp = client.get(_DETAIL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_detail_endpoint_returns_the_program_bundle():
    bundle = {
        "enrollment": {
            "enrollment_id": _EID, "application_id": "app-1", "job_id": "job-1",
            "job_title": "PE", "program_id": "prog-1", "program_title": "Onboarding",
            "program_status": "PUBLISHED", "enrollment_status": "ACTIVE",
            "created_at": None, "completed_at": None,
        },
        "program": {
            "id": "prog-1", "job_id": "job-1", "title": "Onboarding", "summary": None,
            "estimated_weeks": None, "status": "PUBLISHED", "published_at": None,
        },
        "modules": [], "skills": [],
    }
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "get_student_program", return_value=bundle) as get_fn,
    ):
        resp = client.get(_DETAIL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert resp.json()["program"]["id"] == "prog-1"
    assert get_fn.call_args.args[1:] == (_SID, _EID)


# ============================================================
# IDOR -- end to end through the real service + fake RLS DB
# ============================================================


def test_student_a_cannot_read_student_b_enrollment_end_to_end():
    # DB holds student-B's enrollment + a published program. Student A calls.
    db = _StudentDB(
        student_id="student-A",
        job_training_enrollments=[_enr(id="enr-B", student_id="student-B")],
        job_programs=[_prog()],
        job_program_modules=[_module()],
        job_program_items=[_item()],
        job_program_assignments=[_assignment()],
        job_program_skills=[{"skill_id": "sk-py", "program_id": "prog-1", "requirement": "REQUIRED"}],
        jobs=[{"id": "job-1", "title": "PE", "status": "PUBLISHED"}],
        skills=[{"id": "sk-py", "name": "Python"}],
    )
    with (
        authenticated_as("STUDENT", user_id="student-A"),
        patch("app.api.student_job_training.build_user_client", return_value=db),
    ):
        list_resp = client.get(_LIST_URL, headers={"Authorization": "Bearer t"})
        detail_resp = client.get(
            "/api/v1/student/job-training/enr-B", headers={"Authorization": "Bearer t"}
        )
    assert list_resp.status_code == 200
    assert list_resp.json()["enrollments"] == []  # A sees nothing
    assert detail_resp.status_code == 404  # A cannot open B's enrollment


def test_student_with_no_enrollment_cannot_reach_a_published_program_end_to_end():
    db = _StudentDB(
        student_id="student-A",
        job_training_enrollments=[],  # student A has NO enrollment
        job_programs=[_prog()],
        job_program_modules=[_module()],
        jobs=[{"id": "job-1", "title": "PE", "status": "PUBLISHED"}],
        skills=[],
    )
    with (
        authenticated_as("STUDENT", user_id="student-A"),
        patch("app.api.student_job_training.build_user_client", return_value=db),
    ):
        resp = client.get(_DETAIL_URL, headers={"Authorization": "Bearer t"})
    assert resp.status_code == 404
