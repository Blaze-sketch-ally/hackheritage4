"""Phase J2 -- INDUSTRY Job Training program authoring
(/api/v1/jobs/{job_id}/training-program).

Route tests mock the service and use tests.conftest.authenticated_as
(same convention as tests/test_internship_program.py). Service tests
drive the functions with a small in-memory fake Supabase client that
enforces the `.eq()` / `.in_()` filters the service relies on -- so an
ownership bypass shows up as a test failure, not just an assertion on a
mock call.

RLS (040_job_training.sql, via public.owns_job_program + the
job-ownership predicate) is the real access-control boundary. This suite
verifies the Python layer's half: every read/write is scoped by the
caller's own id and the program / module / item / assignment lineage;
publish is DRAFT->PUBLISHED (with a structural readiness check) and
unpublish is PUBLISHED->DRAFT only; program skills are constrained to the
canonical skills catalog; and nothing outside job_programs /
job_program_modules / job_program_items / job_program_skills /
job_program_assignments is ever written -- in particular
job_training_enrollments is never touched.
"""

import itertools
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import job_training_program_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)
_JID = "11111111-1111-1111-1111-111111111111"


# ============================================================
# in-memory fake Supabase client
# ============================================================


class _Query:
    _ids = itertools.count(1)

    def __init__(self, db, table):
        self._db = db
        self._table = table
        self._select = "*"
        self._filters: list[tuple] = []
        self._in_filters: list[tuple] = []
        self._single = False
        self._order = None
        self._desc = False
        self._limit = None
        self._op = "select"
        self._payload = None

    def select(self, s="*", *a, **k):
        self._select = s
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        self._db.filters.append((self._table, field, value))
        return self

    def in_(self, field, values):
        self._in_filters.append((field, list(values)))
        return self

    def order(self, field, desc=False):
        self._order, self._desc = field, desc
        return self

    def limit(self, n):
        self._limit = n
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

    def _match(self, row):
        if not all(row.get(f) == v for f, v in self._filters):
            return False
        return all(row.get(f) in set(vs) for f, vs in self._in_filters)

    def _embed(self, row):
        row = dict(row)
        if "job_program_items(" in self._select:
            row["job_program_items"] = [
                dict(i)
                for i in self._db.rows("job_program_items")
                if i["module_id"] == row["id"]
            ]
        if "job_program_assignments(" in self._select:
            row["job_program_assignments"] = [
                dict(a)
                for a in self._db.rows("job_program_assignments")
                if a["module_id"] == row["id"]
            ]
        if "skill:skills(" in self._select:
            skill = next(
                (s for s in self._db.rows("skills") if s["id"] == row.get("skill_id")), None
            )
            row["skill"] = {"name": skill["name"]} if skill else None
        return row

    def execute(self):
        rows = self._db.rows(self._table)
        if self._op == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            created = []
            for p in payloads:
                r = dict(p)
                r.setdefault("id", f"{self._table[:3]}-{next(self._ids)}")
                r.setdefault("created_at", "2026-09-08T00:00:00Z")
                r.setdefault("updated_at", "2026-09-08T00:00:00Z")
                r.setdefault("order_index", r.get("order_index", 0))
                if self._table == "job_program_assignments" and "program_id" not in r:
                    # emulates set_job_program_assignment_program_id (040)
                    mod = next(
                        (
                            m
                            for m in self._db.rows("job_program_modules")
                            if m["id"] == r.get("module_id")
                        ),
                        None,
                    )
                    if mod is not None:
                        r["program_id"] = mod.get("program_id")
                self._db.rows(self._table).append(r)
                self._db.inserts.append((self._table, dict(p)))
                created.append(r)
            return SimpleNamespace(data=created)
        if self._op == "update":
            hit = [r for r in rows if self._match(r)]
            for r in hit:
                r.update(self._payload)
            self._db.updates.append((self._table, dict(self._payload)))
            return SimpleNamespace(data=[dict(r) for r in hit])
        if self._op == "delete":
            keep = [r for r in rows if not self._match(r)]
            self._db.deletes.append((self._table, list(self._filters)))
            self._db.tables[self._table] = keep
            return SimpleNamespace(data=[])
        matched = [r for r in rows if self._match(r)]
        if self._order:
            matched.sort(key=lambda r: r.get(self._order) or 0, reverse=self._desc)
        if self._limit is not None:
            matched = matched[: self._limit]
        matched = [self._embed(r) for r in matched]
        if self._single:
            return SimpleNamespace(data=matched[0] if matched else None)
        return SimpleNamespace(data=matched)


class _DB:
    def __init__(self, **tables):
        self.tables: dict[str, list] = {
            "jobs": [],
            "job_programs": [],
            "job_program_modules": [],
            "job_program_items": [],
            "job_program_assignments": [],
            "job_program_skills": [],
            "job_skills": [],
            "job_training_enrollments": [],
            "skills": [],
        }
        for name, rows in tables.items():
            self.tables[name] = rows
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []
        self.deletes: list[tuple] = []
        self.filters: list[tuple] = []

    def rows(self, table):
        return self.tables.setdefault(table, [])

    def table(self, name):
        return _Query(self, name)

    def touched_tables(self) -> set[str]:
        return (
            {t for t, _ in self.inserts}
            | {t for t, _ in self.updates}
            | {t for t, _ in self.deletes}
        )


def _db(
    *,
    industry_id="industry-1",
    program=True,
    program_status="DRAFT",
    modules=None,
    items=None,
    assignments=None,
    program_skills=None,
    job_skills=None,
    skills=None,
):
    tables = {
        "jobs": [
            {"id": _JID, "industry_id": industry_id, "title": "Platform Engineer", "status": "PUBLISHED"}
        ],
        "job_programs": (
            [
                {
                    "id": "prog-1",
                    "job_id": _JID,
                    "title": "Platform Onboarding",
                    "summary": None,
                    "estimated_weeks": None,
                    "status": program_status,
                    "published_at": None,
                    "created_at": "2026-09-01T00:00:00Z",
                    "updated_at": "2026-09-01T00:00:00Z",
                }
            ]
            if program
            else []
        ),
        "job_program_modules": modules or [],
        "job_program_items": items or [],
        "job_program_assignments": assignments or [],
        "job_program_skills": program_skills or [],
        "job_skills": job_skills
        if job_skills is not None
        else [
            {"id": "js-1", "job_id": _JID, "skill_id": "sk-py", "required_level": "Advanced", "importance": "CORE"},
            {"id": "js-2", "job_id": _JID, "skill_id": "sk-sql", "required_level": "Intermediate", "importance": "IMPORTANT"},
        ],
        "skills": skills
        if skills is not None
        else [
            {"id": "sk-py", "name": "Python"},
            {"id": "sk-sql", "name": "SQL"},
            {"id": "sk-k8s", "name": "Kubernetes"},
        ],
    }
    return _DB(**tables)


def _mod(**over):
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
        "title": "Welcome video",
        "item_type": "VIDEO",
        "content_url": "https://example.com/v",
        "content_text": None,
        "order_index": 0,
        "is_published": True,
    }
    row.update(over)
    return row


def _assignment_row(**over):
    row = {
        "id": "as1",
        "module_id": "m1",
        "program_id": "prog-1",
        "title": "Ship a service",
        "description": None,
        "instructions": None,
        "assignment_type": "PROJECT",
        "is_required": True,
        "is_published": True,
        "order_index": 0,
        "due_offset_days": None,
        "submission_kind": "REPO",
        "repo_required": True,
        "live_url_expected": False,
        "max_score": None,
        "linked_skill_id": None,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(over)
    return row


def _new_assignment(**over):
    data = {
        "title": "Ship a service",
        "assignment_type": "PROJECT",
        "is_required": True,
        "is_published": True,
        "submission_kind": "LINK",
        "repo_required": False,
        "live_url_expected": False,
    }
    data.update(over)
    return data


# ============================================================
# service -- read + ownership (A4, A5, B5, D13, D14)
# ============================================================


def test_get_bundle_returns_program_modules_skills_and_available_skills():
    db = _db(
        modules=[_mod()],
        items=[_item()],
        program_skills=[{"id": "ps1", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}],
    )
    bundle = svc.get_program_bundle(db, "industry-1", _JID)
    assert bundle["program"]["title"] == "Platform Onboarding"
    assert bundle["job"]["id"] == _JID
    assert bundle["modules"][0]["items"][0]["title"] == "Welcome video"
    assert bundle["skills"][0]["skill_name"] == "Python"
    assert {s["skill_id"] for s in bundle["available_skills"]} == {"sk-py", "sk-sql"}


def test_get_bundle_returns_null_program_when_none_exists():
    bundle = svc.get_program_bundle(_db(program=False), "industry-1", _JID)
    assert bundle["program"] is None
    assert bundle["modules"] == [] and bundle["skills"] == []
    assert len(bundle["available_skills"]) == 2


def test_another_company_cannot_read_the_program():
    with pytest.raises(svc.JobNotFoundError):
        svc.get_program_bundle(_db(), "industry-999", _JID)


def test_missing_job_is_a_clean_error():
    with pytest.raises(svc.JobNotFoundError):
        svc.get_program_bundle(_db(), "industry-1", str(uuid4()))


# ============================================================
# service -- create + cardinality (C11, C12, D13)
# ============================================================


def test_industry_creates_a_draft_program_for_its_own_job():
    db = _db(program=False)
    bundle = svc.create_program(
        db, "industry-1", _JID, {"title": "Onboarding", "summary": "s", "estimated_weeks": 6}
    )
    assert bundle["program"]["status"] == "DRAFT"
    assert bundle["program"]["title"] == "Onboarding"
    inserted = db.inserts[0][1]
    assert inserted["status"] == "DRAFT" and inserted["job_id"] == _JID
    assert "internship_id" not in inserted


def test_duplicate_program_creation_is_rejected():
    with pytest.raises(svc.ProgramExistsError):
        svc.create_program(_db(program=True), "industry-1", _JID, {"title": "x"})


def test_another_company_cannot_create_a_program_for_a_foreign_job():
    db = _db(program=False)
    with pytest.raises(svc.JobNotFoundError):
        svc.create_program(db, "industry-999", _JID, {"title": "x"})
    assert db.inserts == []


def test_create_program_for_a_nonexistent_job_is_rejected():
    with pytest.raises(svc.JobNotFoundError):
        svc.create_program(_db(program=False), "industry-1", str(uuid4()), {"title": "x"})


# ============================================================
# service -- update (job association is immutable)
# ============================================================


def test_update_program_edits_metadata_only():
    db = _db()
    svc.update_program(db, "industry-1", _JID, {"title": "Renamed", "summary": "New"})
    assert db.updates[0][1] == {"title": "Renamed", "summary": "New"}
    assert "status" not in db.updates[0][1]


def test_update_program_ignores_status_published_at_and_job_id():
    db = _db()
    svc.update_program(
        db, "industry-1", _JID, {"title": "t", "status": "PUBLISHED", "published_at": "x", "job_id": "other"}
    )
    assert db.updates[0][1] == {"title": "t"}


def test_published_program_content_stays_editable():
    db = _db(program_status="PUBLISHED")
    bundle = svc.update_program(db, "industry-1", _JID, {"summary": "post-publish edit"})
    assert bundle["program"]["status"] == "PUBLISHED"
    assert db.updates[0][1] == {"summary": "post-publish edit"}


def test_another_company_cannot_update_the_program():
    db = _db()
    with pytest.raises(svc.JobNotFoundError):
        svc.update_program(db, "industry-999", _JID, {"title": "hax"})
    assert db.updates == []


# ============================================================
# service -- modules (E15, B7)
# ============================================================


def test_create_module_assigns_the_next_order_index():
    db = _db(modules=[_mod(id="m0", order_index=0)])
    svc.create_module(db, "industry-1", _JID, {"title": "Week 2", "description": None, "is_published": True})
    inserted = db.inserts[0][1]
    assert inserted["program_id"] == "prog-1" and inserted["order_index"] == 1


def test_update_module_is_scoped_to_the_program():
    db = _db(modules=[_mod()])
    svc.update_module(db, "industry-1", _JID, "m1", {"title": "Renamed", "is_published": False})
    assert db.updates[-1][1] == {"title": "Renamed", "is_published": False}


def test_update_module_from_another_program_is_not_found():
    db = _db(modules=[_mod(id="m-foreign", program_id="prog-OTHER")])
    with pytest.raises(svc.ModuleNotFoundError):
        svc.update_module(db, "industry-1", _JID, "m-foreign", {"title": "hax"})
    assert db.updates == []


def test_another_company_cannot_touch_a_module():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.JobNotFoundError):
        svc.update_module(db, "industry-999", _JID, "m1", {"title": "hax"})
    assert db.updates == []


def test_reorder_modules_reassigns_indices():
    db = _db(modules=[_mod(id="m1", order_index=0), _mod(id="m2", order_index=1), _mod(id="m3", order_index=2)])
    bundle = svc.reorder_modules(db, "industry-1", _JID, ["m3", "m1", "m2"])
    assert {m["id"]: m["order_index"] for m in bundle["modules"]} == {"m3": 0, "m1": 1, "m2": 2}


def test_reorder_modules_rejects_a_list_that_is_not_the_exact_set():
    db = _db(modules=[_mod(id="m1"), _mod(id="m2", order_index=1)])
    with pytest.raises(svc.InvalidReorderError):
        svc.reorder_modules(db, "industry-1", _JID, ["m1"])
    with pytest.raises(svc.InvalidReorderError):
        svc.reorder_modules(db, "industry-1", _JID, ["m1", "m2", "m-ghost"])


def test_there_is_no_module_delete_helper():
    # 040 grants no DELETE policy on job_program_modules -- hide via is_published.
    assert not hasattr(svc, "delete_module")


# ============================================================
# service -- items (E16, B8)
# ============================================================


def test_create_item_assigns_order_index_and_validates_content():
    db = _db(modules=[_mod()])
    svc.create_item(
        db, "industry-1", _JID, "m1",
        {"title": "V", "item_type": "VIDEO", "content_url": "https://x", "content_text": None, "is_published": True},
    )
    inserted = db.inserts[0][1]
    assert inserted["module_id"] == "m1" and inserted["order_index"] == 0


def test_create_item_rejects_content_that_does_not_match_type():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.InvalidItemError):
        svc.create_item(
            db, "industry-1", _JID, "m1",
            {"title": "T", "item_type": "TEXT", "content_url": "x", "content_text": None, "is_published": True},
        )
    with pytest.raises(svc.InvalidItemError):
        svc.create_item(
            db, "industry-1", _JID, "m1",
            {"title": "L", "item_type": "LINK", "content_url": None, "content_text": None, "is_published": True},
        )
    assert db.inserts == []


def test_update_item_is_scoped_to_the_module():
    db = _db(modules=[_mod()], items=[_item(item_type="LINK", content_url="u")])
    svc.update_item(db, "industry-1", _JID, "m1", "i1", {"title": "Renamed"})
    assert db.updates[-1][1] == {"title": "Renamed"}


def test_update_item_from_another_module_is_not_found():
    db = _db(modules=[_mod()], items=[_item(id="i-foreign", module_id="m-OTHER")])
    with pytest.raises(svc.ItemNotFoundError):
        svc.update_item(db, "industry-1", _JID, "m1", "i-foreign", {"title": "hax"})


def test_another_company_cannot_touch_an_item():
    db = _db(modules=[_mod()], items=[_item()])
    with pytest.raises(svc.JobNotFoundError):
        svc.update_item(db, "industry-999", _JID, "m1", "i1", {"title": "hax"})
    assert db.updates == []


def test_reorder_items_reassigns_indices():
    db = _db(modules=[_mod()], items=[_item(id="i1", order_index=0), _item(id="i2", order_index=1)])
    bundle = svc.reorder_items(db, "industry-1", _JID, "m1", ["i2", "i1"])
    assert {i["id"]: i["order_index"] for i in bundle["modules"][0]["items"]} == {"i2": 0, "i1": 1}


# ============================================================
# service -- skills (E17, E19, B9)
# ============================================================


def test_set_program_skills_replace_set_with_required_and_optional():
    db = _db(program_skills=[{"id": "ps-old", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}])
    bundle = svc.set_program_skills(
        db, "industry-1", _JID,
        [{"skill_id": "sk-py", "requirement": "REQUIRED"}, {"skill_id": "sk-sql", "requirement": "OPTIONAL"}],
    )
    got = {s["skill_id"]: s["requirement"] for s in bundle["skills"]}
    assert got == {"sk-py": "REQUIRED", "sk-sql": "OPTIONAL"}
    assert db.deletes and db.deletes[0][0] == "job_program_skills"


def test_set_program_skills_allows_a_catalog_skill_outside_the_jobs_recruitment_skills():
    # sk-k8s is a real catalog skill but NOT one of the job's job_skills.
    db = _db()
    bundle = svc.set_program_skills(db, "industry-1", _JID, [{"skill_id": "sk-k8s", "requirement": "REQUIRED"}])
    assert [s["skill_id"] for s in bundle["skills"]] == ["sk-k8s"]


def test_set_program_skills_rejects_a_skill_that_is_not_in_the_catalog():
    db = _db()
    with pytest.raises(svc.InvalidProgramSkillError):
        svc.set_program_skills(db, "industry-1", _JID, [{"skill_id": "sk-made-up", "requirement": "REQUIRED"}])
    assert db.deletes == [] and db.inserts == []


def test_set_program_skills_never_writes_job_skills_or_skills():
    db = _db()
    svc.set_program_skills(db, "industry-1", _JID, [{"skill_id": "sk-py", "requirement": "REQUIRED"}])
    assert db.touched_tables() <= {"job_program_skills"}


def test_set_program_skills_empty_list_clears_selections():
    db = _db(program_skills=[{"id": "ps1", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}])
    bundle = svc.set_program_skills(db, "industry-1", _JID, [])
    assert bundle["skills"] == []
    assert db.inserts == []


def test_another_company_cannot_set_program_skills():
    db = _db()
    with pytest.raises(svc.JobNotFoundError):
        svc.set_program_skills(db, "industry-999", _JID, [{"skill_id": "sk-py"}])
    assert db.deletes == []


# ============================================================
# service -- assignments (E18, E19, E20, B10)
# ============================================================


def test_industry_creates_an_assignment_in_its_own_module():
    db = _db(modules=[_mod()])
    bundle = svc.create_assignment(db, "industry-1", _JID, "m1", _new_assignment())
    inserted = db.inserts[0]
    assert inserted[0] == "job_program_assignments"
    assert inserted[1]["module_id"] == "m1"
    assert "program_id" not in inserted[1]  # trigger-derived, never client-sent
    got = bundle["modules"][0]["assignments"]
    assert len(got) == 1 and got[0]["program_id"] == "prog-1"


def test_second_assignment_gets_the_next_order_index():
    db = _db(modules=[_mod()], assignments=[_assignment_row(id="as0", order_index=0)])
    svc.create_assignment(db, "industry-1", _JID, "m1", _new_assignment(title="Second"))
    assert db.inserts[0][1]["order_index"] == 1


def test_assignment_cannot_be_created_in_a_foreign_program_module():
    db = _db(modules=[_mod(id="m-foreign", program_id="prog-OTHER")])
    with pytest.raises(svc.ModuleNotFoundError):
        svc.create_assignment(db, "industry-1", _JID, "m-foreign", _new_assignment())
    assert db.inserts == []


def test_another_company_cannot_create_an_assignment():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.JobNotFoundError):
        svc.create_assignment(db, "industry-999", _JID, "m1", _new_assignment())
    assert db.inserts == []


def test_repo_required_with_a_non_repo_kind_is_rejected():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.InvalidAssignmentError):
        svc.create_assignment(
            db, "industry-1", _JID, "m1", _new_assignment(repo_required=True, submission_kind="LINK")
        )
    assert db.inserts == []


def test_repo_required_with_repo_kind_is_accepted():
    db = _db(modules=[_mod()])
    svc.create_assignment(
        db, "industry-1", _JID, "m1", _new_assignment(repo_required=True, submission_kind="REPO")
    )
    assert db.inserts[0][1]["repo_required"] is True


def test_linked_skill_must_be_one_the_program_trains():
    db = _db(
        modules=[_mod()],
        program_skills=[{"id": "ps1", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}],
    )
    with pytest.raises(svc.InvalidAssignmentError):
        svc.create_assignment(
            db, "industry-1", _JID, "m1", _new_assignment(linked_skill_id="sk-sql")
        )
    svc.create_assignment(db, "industry-1", _JID, "m1", _new_assignment(linked_skill_id="sk-py"))
    assert db.inserts[0][1]["linked_skill_id"] == "sk-py"


def test_update_assignment_edits_fields_and_stays_scoped_to_the_module():
    db = _db(modules=[_mod()], assignments=[_assignment_row()])
    svc.update_assignment(db, "industry-1", _JID, "m1", "as1", {"title": "Renamed", "instructions": "Do it"})
    assert db.updates[-1][1] == {"title": "Renamed", "instructions": "Do it"}


def test_update_assignment_can_hide_it_via_is_published():
    db = _db(modules=[_mod()], assignments=[_assignment_row(is_published=True)])
    bundle = svc.update_assignment(db, "industry-1", _JID, "m1", "as1", {"is_published": False})
    assert bundle["modules"][0]["assignments"][0]["is_published"] is False


def test_update_assignment_from_another_module_is_not_found():
    db = _db(modules=[_mod()], assignments=[_assignment_row(id="as-foreign", module_id="m-OTHER")])
    with pytest.raises(svc.AssignmentNotFoundError):
        svc.update_assignment(db, "industry-1", _JID, "m1", "as-foreign", {"title": "hax"})
    assert db.updates == []


def test_update_assignment_rejects_an_inconsistent_repo_config():
    db = _db(modules=[_mod()], assignments=[_assignment_row(submission_kind="REPO", repo_required=True)])
    with pytest.raises(svc.InvalidAssignmentError):
        svc.update_assignment(db, "industry-1", _JID, "m1", "as1", {"submission_kind": "TEXT"})
    assert db.updates == []


def test_reorder_assignments_reassigns_indices():
    db = _db(
        modules=[_mod()],
        assignments=[_assignment_row(id="a1", order_index=0), _assignment_row(id="a2", order_index=1), _assignment_row(id="a3", order_index=2)],
    )
    bundle = svc.reorder_assignments(db, "industry-1", _JID, "m1", ["a3", "a1", "a2"])
    assert {a["id"]: a["order_index"] for a in bundle["modules"][0]["assignments"]} == {"a3": 0, "a1": 1, "a2": 2}


def test_no_assignment_delete_helper_exists():
    assert not hasattr(svc, "delete_assignment")


# ============================================================
# service -- publish / unpublish (F21-F25)
# ============================================================


def _publishable_db(**over):
    return _db(
        modules=[_mod(is_published=True)],
        items=[_item(is_published=True)],
        **over,
    )


def test_publish_moves_a_ready_draft_to_published_and_stamps_published_at():
    db = _publishable_db()
    bundle = svc.publish_program(db, "industry-1", _JID)
    assert bundle["program"]["status"] == "PUBLISHED"
    written = db.updates[-1][1]
    assert written["status"] == "PUBLISHED" and written["published_at"]


def test_publish_rejects_a_program_with_no_modules():
    db = _db()
    with pytest.raises(svc.PublishValidationError) as ei:
        svc.publish_program(db, "industry-1", _JID)
    assert "at least one module" in ei.value.missing


def test_publish_rejects_a_program_whose_only_module_is_unpublished():
    db = _db(modules=[_mod(is_published=False)], items=[_item(is_published=True)])
    with pytest.raises(svc.PublishValidationError) as ei:
        svc.publish_program(db, "industry-1", _JID)
    assert "at least one published module" in ei.value.missing


def test_publish_rejects_a_published_module_with_no_published_content():
    db = _db(modules=[_mod(is_published=True)], items=[_item(is_published=False)])
    with pytest.raises(svc.PublishValidationError):
        svc.publish_program(db, "industry-1", _JID)


def test_publish_accepts_a_published_module_carrying_only_a_published_assignment():
    db = _db(
        modules=[_mod(is_published=True)],
        assignments=[_assignment_row(is_published=True)],
    )
    bundle = svc.publish_program(db, "industry-1", _JID)
    assert bundle["program"]["status"] == "PUBLISHED"


def test_publish_rejects_a_blank_title():
    db = _publishable_db()
    db.tables["job_programs"][0]["title"] = "   "
    with pytest.raises(svc.PublishValidationError) as ei:
        svc.publish_program(db, "industry-1", _JID)
    assert "a title" in ei.value.missing


def test_publish_rejects_a_non_draft_program():
    db = _publishable_db(program_status="PUBLISHED")
    with pytest.raises(svc.InvalidStatusTransitionError):
        svc.publish_program(db, "industry-1", _JID)


def test_only_the_owner_can_publish():
    with pytest.raises(svc.JobNotFoundError):
        svc.publish_program(_publishable_db(industry_id="industry-1"), "industry-999", _JID)


def test_publish_without_a_program_is_a_clean_error():
    with pytest.raises(svc.ProgramNotFoundError):
        svc.publish_program(_db(program=False), "industry-1", _JID)


def test_publish_never_creates_a_job_training_enrollment_or_grants_access():
    db = _publishable_db()
    svc.publish_program(db, "industry-1", _JID)
    # J2 authoring must never write the student access record. Access stays
    # gated by public.student_can_access_job_program (enrollment + PUBLISHED).
    assert "job_training_enrollments" not in db.touched_tables()
    assert db.tables["job_training_enrollments"] == []


def test_unpublish_moves_published_back_to_draft():
    db = _publishable_db(program_status="PUBLISHED")
    bundle = svc.unpublish_program(db, "industry-1", _JID)
    assert bundle["program"]["status"] == "DRAFT"
    assert db.updates[-1][1] == {"status": "DRAFT"}


def test_unpublish_rejects_a_program_that_is_not_published():
    db = _db(program_status="DRAFT")
    with pytest.raises(svc.InvalidStatusTransitionError):
        svc.unpublish_program(db, "industry-1", _JID)


def test_unpublish_only_by_the_owner():
    with pytest.raises(svc.JobNotFoundError):
        svc.unpublish_program(_db(program_status="PUBLISHED"), "industry-999", _JID)


def test_no_archive_helper_is_exposed_in_j2():
    assert not hasattr(svc, "archive_program")


# ============================================================
# service -- global invariant: enrollments/other tables untouched
# ============================================================


def test_no_authoring_operation_writes_outside_the_five_job_program_tables():
    allowed = {
        "job_programs",
        "job_program_modules",
        "job_program_items",
        "job_program_skills",
        "job_program_assignments",
    }
    db = _db(modules=[_mod()])
    svc.create_module(db, "industry-1", _JID, {"title": "M2", "is_published": True})
    svc.create_item(
        db, "industry-1", _JID, "m1",
        {"title": "V", "item_type": "LINK", "content_url": "https://x", "content_text": None, "is_published": True},
    )
    svc.set_program_skills(db, "industry-1", _JID, [{"skill_id": "sk-py", "requirement": "REQUIRED"}])
    svc.create_assignment(db, "industry-1", _JID, "m1", _new_assignment())
    svc.update_program(db, "industry-1", _JID, {"summary": "s"})
    assert db.touched_tables() <= allowed


# ============================================================
# routes -- auth / role guards (A1, A2, A3)
# ============================================================

_ENDPOINTS = [
    ("get", f"/api/v1/jobs/{_JID}/training-program"),
    ("post", f"/api/v1/jobs/{_JID}/training-program"),
    ("put", f"/api/v1/jobs/{_JID}/training-program"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/publish"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/unpublish"),
    ("put", f"/api/v1/jobs/{_JID}/training-program/skills"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/modules"),
    ("put", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/modules/reorder"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/items"),
    ("put", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/items/{_JID}"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/items/reorder"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/assignments"),
    ("put", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/assignments/{_JID}"),
    ("post", f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/assignments/reorder"),
]


def _body(method, url):
    if "reorder" in url:
        return {"ordered_ids": [_JID]}
    if url.endswith("/skills"):
        return {"skills": []}
    if url.endswith("/items") or "/items/" in url:
        return {"title": "x", "item_type": "LINK", "content_url": "https://x"}
    if url.endswith("/assignments") or "/assignments/" in url:
        return {"title": "x"}
    if url.endswith("/modules") or "/modules/" in url:
        return {"title": "x"}
    if method in ("post", "put"):
        return {"title": "x"}
    return None


def test_all_endpoints_reject_unauthenticated():
    for method, url in _ENDPOINTS:
        body = _body(method, url)
        resp = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
        assert resp.status_code == 401, (method, url)


def test_all_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
        for method, url in _ENDPOINTS:
            body = _body(method, url)
            with authenticated_as(role):
                resp = (
                    getattr(client, method)(url, json=body, headers={"Authorization": "Bearer t"})
                    if body is not None
                    else getattr(client, method)(url, headers={"Authorization": "Bearer t"})
                )
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# routes -- behaviour + error mapping
# ============================================================


def _bundle(**over):
    b = {
        "job": {"id": _JID, "title": "Platform Engineer", "status": "PUBLISHED"},
        "program": {
            "id": "prog-1", "job_id": _JID, "title": "P", "summary": None,
            "estimated_weeks": None, "status": "DRAFT", "published_at": None,
            "created_at": None, "updated_at": None,
        },
        "modules": [], "skills": [], "available_skills": [],
    }
    b.update(over)
    return b


def test_get_program_endpoint_returns_the_bundle():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_program_bundle", return_value=_bundle()),
    ):
        resp = client.get(f"/api/v1/jobs/{_JID}/training-program", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert resp.json()["program"]["status"] == "DRAFT"
    assert resp.json()["job"]["id"] == _JID


def test_create_program_endpoint_is_201():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_program", return_value=_bundle()) as create,
    ):
        resp = client.post(
            f"/api/v1/jobs/{_JID}/training-program",
            json={"title": "P"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 201
    create.assert_called_once()


def test_create_program_endpoint_forbids_client_status_and_job_id():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_program", return_value=_bundle()) as create,
    ):
        resp = client.post(
            f"/api/v1/jobs/{_JID}/training-program",
            json={"title": "P", "status": "PUBLISHED"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422  # extra="forbid"
    create.assert_not_called()


def test_create_program_endpoint_maps_exists_to_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_program", side_effect=svc.ProgramExistsError(_JID)),
    ):
        resp = client.post(
            f"/api/v1/jobs/{_JID}/training-program", json={"title": "P"}, headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 409


def test_program_endpoint_maps_job_not_found_to_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_program_bundle", side_effect=svc.JobNotFoundError(_JID)),
    ):
        resp = client.get(f"/api/v1/jobs/{_JID}/training-program", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_program_endpoint_maps_program_not_found_to_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "update_program", side_effect=svc.ProgramNotFoundError(_JID)),
    ):
        resp = client.put(
            f"/api/v1/jobs/{_JID}/training-program", json={"title": "x"}, headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 404


def test_publish_endpoint_maps_validation_and_transition_errors():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "publish_program", side_effect=svc.PublishValidationError(["at least one module"])),
    ):
        r1 = client.post(f"/api/v1/jobs/{_JID}/training-program/publish", headers={"Authorization": "Bearer t"})
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "publish_program", side_effect=svc.InvalidStatusTransitionError("PUBLISHED", "PUBLISHED")),
    ):
        r2 = client.post(f"/api/v1/jobs/{_JID}/training-program/publish", headers={"Authorization": "Bearer t"})
    assert r1.status_code == 422
    assert r2.status_code == 409


def test_unpublish_endpoint_maps_transition_error_to_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "unpublish_program", side_effect=svc.InvalidStatusTransitionError("DRAFT", "DRAFT")),
    ):
        resp = client.post(f"/api/v1/jobs/{_JID}/training-program/unpublish", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 409


def test_skills_endpoint_maps_invalid_skill_to_422():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "set_program_skills", side_effect=svc.InvalidProgramSkillError("nope")),
    ):
        resp = client.put(
            f"/api/v1/jobs/{_JID}/training-program/skills",
            json={"skills": [{"skill_id": _JID, "requirement": "REQUIRED"}]},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_assignment_endpoint_maps_invalid_assignment_to_422():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_assignment", side_effect=svc.InvalidAssignmentError("bad repo config")),
    ):
        resp = client.post(
            f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}/assignments",
            json={"title": "x", "repo_required": True, "submission_kind": "LINK"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_module_endpoint_maps_module_not_found_to_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "update_module", side_effect=svc.ModuleNotFoundError("m")),
    ):
        resp = client.put(
            f"/api/v1/jobs/{_JID}/training-program/modules/{_JID}",
            json={"title": "x"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 404


# ============================================================
# security-negative -- IDOR / cross-tenant (section 18)
# ============================================================


def test_industry_b_cannot_reach_industry_a_program_via_the_service():
    # Industry A owns _JID + prog-1. Industry B calls every mutating op.
    db = _db(industry_id="industry-A", modules=[_mod()], assignments=[_assignment_row()])
    for call in (
        lambda: svc.get_program_bundle(db, "industry-B", _JID),
        lambda: svc.update_program(db, "industry-B", _JID, {"title": "x"}),
        lambda: svc.publish_program(db, "industry-B", _JID),
        lambda: svc.unpublish_program(db, "industry-B", _JID),
        lambda: svc.create_module(db, "industry-B", _JID, {"title": "x"}),
        lambda: svc.update_module(db, "industry-B", _JID, "m1", {"title": "x"}),
        lambda: svc.set_program_skills(db, "industry-B", _JID, [{"skill_id": "sk-py"}]),
        lambda: svc.create_assignment(db, "industry-B", _JID, "m1", _new_assignment()),
        lambda: svc.update_assignment(db, "industry-B", _JID, "m1", "as1", {"title": "x"}),
    ):
        with pytest.raises(svc.JobNotFoundError):
            call()
    assert db.touched_tables() == set()  # not one write leaked through


def test_forged_foreign_module_id_is_rejected_even_on_the_owners_own_job_path():
    # Industry A owns _JID/prog-1 but passes a module id that belongs to a
    # DIFFERENT program -- the lineage check rejects it.
    db = _db(modules=[_mod(id="m-b", program_id="prog-B")])
    with pytest.raises(svc.ModuleNotFoundError):
        svc.create_item(
            db, "industry-1", _JID, "m-b",
            {"title": "x", "item_type": "LINK", "content_url": "https://x", "content_text": None, "is_published": True},
        )
    with pytest.raises(svc.ModuleNotFoundError):
        svc.create_assignment(db, "industry-1", _JID, "m-b", _new_assignment())
    assert db.inserts == []


def test_assignment_payload_cannot_smuggle_program_id():
    db = _db(modules=[_mod()])
    svc.create_assignment(
        db, "industry-1", _JID, "m1", {**_new_assignment(), "program_id": "prog-EVIL"}
    )
    # program_id is not an editable field -> stripped before insert; the DB
    # trigger derives the real one from the module.
    assert "program_id" not in db.inserts[0][1]


def test_students_are_never_given_an_authoring_path():
    # every endpoint 403s for a student (covered broadly above); assert the
    # router is industry-only by construction.
    from app.api import job_training_programs as mod

    src = mod.__file__
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    # drop the module docstring -- only the actual code matters here
    body = text.split('"""', 2)[2]
    assert "require_industry" in body
    assert "require_student" not in body
    assert "get_supabase" not in body  # never a service-role bypass
    assert "build_user_client(current_user.access_token)" in body
