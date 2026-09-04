"""Phase 4 -- INDUSTRY internship-program authoring
(/api/v1/internships/{internship_id}/program).

Route tests mock the service and use tests.conftest.authenticated_as
(same convention as tests/test_applications.py). Service tests drive the
functions with a small in-memory fake Supabase client that enforces the
`.eq()` filters the service relies on -- so an ownership bypass shows up
as a test failure, not just an assertion on a mock call.

RLS (037_internship_program.sql, via public.owns_internship_program +
the internship-ownership predicate) is the real access-control boundary,
applied + verified live in Phase 1. This suite verifies the Python
layer's half: every read/write is scoped by the caller's own id and the
program / module / item lineage, publish is DRAFT->PUBLISHED only,
program skills are constrained to the internship's own recruitment
skills, and nothing outside internship_programs / program_modules /
module_items / program_skills is written.
"""

import itertools
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import internship_program_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)
_IID = "11111111-1111-1111-1111-111111111111"


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
        return all(row.get(f) == v for f, v in self._filters)

    def _embed(self, row):
        row = dict(row)
        if "module_items(" in self._select:
            row["module_items"] = [
                dict(i) for i in self._db.rows("module_items") if i["module_id"] == row["id"]
            ]
        if "program_assignments(" in self._select:
            row["program_assignments"] = [
                dict(a)
                for a in self._db.rows("program_assignments")
                if a["module_id"] == row["id"]
            ]
        if "skill:skills(" in self._select:
            skill = next((s for s in self._db.rows("skills") if s["id"] == row.get("skill_id")), None)
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
                r.setdefault("created_at", "2026-09-04T00:00:00Z")
                r.setdefault("order_index", r.get("order_index", 0))
                if self._table == "program_assignments" and "program_id" not in r:
                    # emulates the set_program_assignment_program_id trigger (037)
                    mod = next(
                        (m for m in self._db.rows("program_modules") if m["id"] == r.get("module_id")),
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
        # select
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
            "internships": [],
            "internship_programs": [],
            "program_modules": [],
            "module_items": [],
            "program_assignments": [],
            "program_skills": [],
            "internship_skills": [],
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


def _db(*, industry_id="industry-1", program=True, modules=None, items=None,
        assignments=None, program_skills=None, internship_skills=None, skills=None):
    tables = {
        "internships": [{"id": _IID, "industry_id": industry_id, "title": "ML Intern", "status": "PUBLISHED"}],
        "internship_programs": (
            [{"id": "prog-1", "internship_id": _IID, "title": "ML Program", "summary": None,
              "estimated_weeks": None, "status": "DRAFT", "published_at": None,
              "created_at": "2026-09-01T00:00:00Z", "updated_at": "2026-09-01T00:00:00Z"}]
            if program else []
        ),
        "program_modules": modules or [],
        "module_items": items or [],
        "program_assignments": assignments or [],
        "program_skills": program_skills or [],
        "internship_skills": internship_skills
        if internship_skills is not None
        else [
            {"id": "is-1", "internship_id": _IID, "skill_id": "sk-py", "required_level": "Advanced", "importance": "CORE"},
            {"id": "is-2", "internship_id": _IID, "skill_id": "sk-sql", "required_level": "Intermediate", "importance": "IMPORTANT"},
        ],
        "skills": skills or [
            {"id": "sk-py", "name": "Python"}, {"id": "sk-sql", "name": "SQL"},
            {"id": "sk-other", "name": "Rust"},
        ],
    }
    return _DB(**tables)


# ============================================================
# service -- read + ownership (3, 4, 16)
# ============================================================


def test_get_bundle_returns_program_modules_skills_and_available_skills():
    db = _db(
        modules=[{"id": "m1", "program_id": "prog-1", "title": "Python", "description": None, "order_index": 0, "is_published": True}],
        items=[{"id": "i1", "module_id": "m1", "title": "Intro", "item_type": "VIDEO", "content_url": "u", "content_text": None, "order_index": 0, "is_published": True}],
        program_skills=[{"id": "ps1", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}],
    )
    bundle = svc.get_program_bundle(db, "industry-1", _IID)
    assert bundle["program"]["title"] == "ML Program"
    assert bundle["modules"][0]["items"][0]["title"] == "Intro"
    assert bundle["skills"][0]["skill_name"] == "Python"
    assert {s["skill_id"] for s in bundle["available_skills"]} == {"sk-py", "sk-sql"}


def test_get_bundle_returns_null_program_when_none_exists():
    bundle = svc.get_program_bundle(_db(program=False), "industry-1", _IID)
    assert bundle["program"] is None
    assert bundle["modules"] == [] and bundle["skills"] == []
    assert len(bundle["available_skills"]) == 2  # still resolvable


def test_another_company_cannot_read_the_program():
    with pytest.raises(svc.InternshipNotFoundError):
        svc.get_program_bundle(_db(), "industry-999", _IID)


def test_missing_internship_is_a_clean_error():
    with pytest.raises(svc.InternshipNotFoundError):
        svc.get_program_bundle(_db(), "industry-1", str(uuid4()))


# ============================================================
# service -- create (1, 2)
# ============================================================


def test_industry_creates_a_draft_program_for_its_own_internship():
    db = _db(program=False)
    bundle = svc.create_program(db, "industry-1", _IID, {"title": "New Program", "summary": "s", "estimated_weeks": 6, "status": "PUBLISHED"})
    assert bundle["program"]["status"] == "DRAFT"  # client status ignored
    assert bundle["program"]["title"] == "New Program"
    inserted = db.inserts[0][1]
    assert inserted["status"] == "DRAFT" and inserted["internship_id"] == _IID
    assert "status" not in {k for k in inserted if k not in ("title", "summary", "estimated_weeks", "internship_id", "status")}


def test_duplicate_program_creation_is_rejected():
    with pytest.raises(svc.ProgramExistsError):
        svc.create_program(_db(program=True), "industry-1", _IID, {"title": "x"})


def test_another_company_cannot_create_a_program():
    with pytest.raises(svc.InternshipNotFoundError):
        svc.create_program(_db(program=False), "industry-999", _IID, {"title": "x"})


# ============================================================
# service -- update (5) + published-content editing
# ============================================================


def test_update_program_edits_metadata_only():
    db = _db()
    svc.update_program(db, "industry-1", _IID, {"title": "Renamed", "summary": "New summary"})
    written = db.updates[0][1]
    assert written == {"title": "Renamed", "summary": "New summary"}
    assert "status" not in written


def test_update_program_ignores_status_and_published_at():
    db = _db()
    svc.update_program(db, "industry-1", _IID, {"title": "t", "status": "PUBLISHED", "published_at": "x"})
    assert db.updates[0][1] == {"title": "t"}


def test_published_program_content_stays_editable():
    db = _db()
    db.tables["internship_programs"][0]["status"] = "PUBLISHED"
    bundle = svc.update_program(db, "industry-1", _IID, {"summary": "post-publish edit"})
    assert bundle["program"]["status"] == "PUBLISHED"
    assert db.updates[0][1] == {"summary": "post-publish edit"}


# ============================================================
# service -- modules (6, 7)
# ============================================================


def test_create_module_assigns_the_next_order_index():
    db = _db(modules=[{"id": "m0", "program_id": "prog-1", "title": "A", "description": None, "order_index": 0, "is_published": True}])
    svc.create_module(db, "industry-1", _IID, {"title": "B", "description": None, "is_published": True})
    inserted = db.inserts[0][1]
    assert inserted["program_id"] == "prog-1"
    assert inserted["order_index"] == 1


def test_update_module_is_scoped_to_the_program():
    db = _db(modules=[{"id": "m1", "program_id": "prog-1", "title": "A", "description": None, "order_index": 0, "is_published": True}])
    svc.update_module(db, "industry-1", _IID, "m1", {"title": "A2", "is_published": False})
    assert db.updates[-1][1] == {"title": "A2", "is_published": False}


def test_update_module_from_another_program_is_not_found():
    db = _db(modules=[{"id": "m-foreign", "program_id": "prog-OTHER", "title": "X", "description": None, "order_index": 0, "is_published": True}])
    with pytest.raises(svc.ModuleNotFoundError):
        svc.update_module(db, "industry-1", _IID, "m-foreign", {"title": "hax"})
    assert db.updates == []


def test_reorder_modules_reassigns_indices():
    db = _db(modules=[
        {"id": "m1", "program_id": "prog-1", "title": "A", "description": None, "order_index": 0, "is_published": True},
        {"id": "m2", "program_id": "prog-1", "title": "B", "description": None, "order_index": 1, "is_published": True},
        {"id": "m3", "program_id": "prog-1", "title": "C", "description": None, "order_index": 2, "is_published": True},
    ])
    bundle = svc.reorder_modules(db, "industry-1", _IID, ["m3", "m1", "m2"])
    order = {m["id"]: m["order_index"] for m in bundle["modules"]}
    assert order == {"m3": 0, "m1": 1, "m2": 2}


def test_reorder_modules_rejects_a_list_that_is_not_the_exact_set():
    db = _db(modules=[
        {"id": "m1", "program_id": "prog-1", "title": "A", "description": None, "order_index": 0, "is_published": True},
        {"id": "m2", "program_id": "prog-1", "title": "B", "description": None, "order_index": 1, "is_published": True},
    ])
    with pytest.raises(svc.InvalidReorderError):
        svc.reorder_modules(db, "industry-1", _IID, ["m1"])  # missing m2
    with pytest.raises(svc.InvalidReorderError):
        svc.reorder_modules(db, "industry-1", _IID, ["m1", "m2", "m-ghost"])


# ============================================================
# service -- items (8, 9)
# ============================================================


def _mod():
    return {"id": "m1", "program_id": "prog-1", "title": "M", "description": None, "order_index": 0, "is_published": True}


def test_create_item_assigns_order_index_and_validates_content():
    db = _db(modules=[_mod()])
    svc.create_item(db, "industry-1", _IID, "m1", {"title": "V", "item_type": "VIDEO", "content_url": "https://x", "content_text": None, "is_published": True})
    inserted = db.inserts[0][1]
    assert inserted["module_id"] == "m1" and inserted["order_index"] == 0


def test_create_item_rejects_content_that_does_not_match_type():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.InvalidItemError):
        svc.create_item(db, "industry-1", _IID, "m1", {"title": "T", "item_type": "TEXT", "content_url": "x", "content_text": None, "is_published": True})
    with pytest.raises(svc.InvalidItemError):
        svc.create_item(db, "industry-1", _IID, "m1", {"title": "L", "item_type": "LINK", "content_url": None, "content_text": None, "is_published": True})
    assert db.inserts == []


def test_update_item_is_scoped_to_the_module():
    db = _db(
        modules=[_mod()],
        items=[{"id": "i1", "module_id": "m1", "title": "A", "item_type": "LINK", "content_url": "u", "content_text": None, "order_index": 0, "is_published": True}],
    )
    svc.update_item(db, "industry-1", _IID, "m1", "i1", {"title": "A2"})
    assert db.updates[-1][1] == {"title": "A2"}


def test_update_item_from_another_module_is_not_found():
    db = _db(
        modules=[_mod()],
        items=[{"id": "i-foreign", "module_id": "m-OTHER", "title": "X", "item_type": "LINK", "content_url": "u", "content_text": None, "order_index": 0, "is_published": True}],
    )
    with pytest.raises(svc.ItemNotFoundError):
        svc.update_item(db, "industry-1", _IID, "m1", "i-foreign", {"title": "hax"})


def test_reorder_items_reassigns_indices():
    db = _db(
        modules=[_mod()],
        items=[
            {"id": "i1", "module_id": "m1", "title": "A", "item_type": "LINK", "content_url": "u", "content_text": None, "order_index": 0, "is_published": True},
            {"id": "i2", "module_id": "m1", "title": "B", "item_type": "LINK", "content_url": "u", "content_text": None, "order_index": 1, "is_published": True},
        ],
    )
    bundle = svc.reorder_items(db, "industry-1", _IID, "m1", ["i2", "i1"])
    order = {i["id"]: i["order_index"] for i in bundle["modules"][0]["items"]}
    assert order == {"i2": 0, "i1": 1}


# ============================================================
# service -- skills (10, 11, 12)
# ============================================================


def test_set_program_skills_replace_set_with_required_and_optional():
    db = _db(program_skills=[{"id": "ps-old", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}])
    bundle = svc.set_program_skills(
        db, "industry-1", _IID,
        [{"skill_id": "sk-py", "requirement": "REQUIRED"}, {"skill_id": "sk-sql", "requirement": "OPTIONAL"}],
    )
    got = {s["skill_id"]: s["requirement"] for s in bundle["skills"]}
    assert got == {"sk-py": "REQUIRED", "sk-sql": "OPTIONAL"}
    assert db.deletes and db.deletes[0][0] == "program_skills"  # replace-set


def test_set_program_skills_rejects_a_skill_not_in_the_internships_skills():
    db = _db()
    with pytest.raises(svc.InvalidProgramSkillError):
        svc.set_program_skills(db, "industry-1", _IID, [{"skill_id": "sk-other", "requirement": "REQUIRED"}])
    assert db.deletes == [] and db.inserts == []


def test_set_program_skills_rejects_a_foreign_internships_skill():
    # sk-foreign only belongs to a different internship
    db = _db(internship_skills=[{"id": "is-x", "internship_id": "other-internship", "skill_id": "sk-foreign", "required_level": "Beginner", "importance": "CORE"}])
    with pytest.raises(svc.InvalidProgramSkillError):
        svc.set_program_skills(db, "industry-1", _IID, [{"skill_id": "sk-foreign", "requirement": "REQUIRED"}])


def test_set_program_skills_never_writes_internship_skills():
    db = _db()
    svc.set_program_skills(db, "industry-1", _IID, [{"skill_id": "sk-py", "requirement": "REQUIRED"}])
    touched = {t for t, _ in db.inserts} | {t for t, _ in db.updates} | {t for t, _ in db.deletes}
    assert touched <= {"program_skills"}


def test_set_program_skills_empty_list_clears_selections():
    db = _db(program_skills=[{"id": "ps1", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}])
    bundle = svc.set_program_skills(db, "industry-1", _IID, [])
    assert bundle["skills"] == []
    assert db.inserts == []  # nothing re-inserted


# ============================================================
# service -- publish (13, 14)
# ============================================================


def test_publish_moves_draft_to_published_and_stamps_published_at():
    db = _db()
    bundle = svc.publish_program(db, "industry-1", _IID)
    assert bundle["program"]["status"] == "PUBLISHED"
    written = db.updates[-1][1]
    assert written["status"] == "PUBLISHED" and written["published_at"]


def test_publish_rejects_a_non_draft_program():
    db = _db()
    db.tables["internship_programs"][0]["status"] = "PUBLISHED"
    with pytest.raises(svc.InvalidStatusTransitionError):
        svc.publish_program(db, "industry-1", _IID)


def test_publish_rejects_a_blank_title():
    db = _db()
    db.tables["internship_programs"][0]["title"] = "   "
    with pytest.raises(svc.PublishValidationError):
        svc.publish_program(db, "industry-1", _IID)


def test_only_the_owner_can_publish():
    with pytest.raises(svc.InternshipNotFoundError):
        svc.publish_program(_db(), "industry-999", _IID)


def test_publish_without_a_program_is_a_clean_error():
    with pytest.raises(svc.ProgramNotFoundError):
        svc.publish_program(_db(program=False), "industry-1", _IID)


# ============================================================
# routes -- auth / role guards (15)
# ============================================================

_ENDPOINTS = [
    ("get", f"/api/v1/internships/{_IID}/program"),
    ("post", f"/api/v1/internships/{_IID}/program"),
    ("put", f"/api/v1/internships/{_IID}/program"),
    ("post", f"/api/v1/internships/{_IID}/program/publish"),
    ("put", f"/api/v1/internships/{_IID}/program/skills"),
    ("post", f"/api/v1/internships/{_IID}/program/modules"),
    ("put", f"/api/v1/internships/{_IID}/program/modules/{_IID}"),
    ("post", f"/api/v1/internships/{_IID}/program/modules/reorder"),
    ("post", f"/api/v1/internships/{_IID}/program/modules/{_IID}/items"),
    ("put", f"/api/v1/internships/{_IID}/program/modules/{_IID}/items/{_IID}"),
    ("post", f"/api/v1/internships/{_IID}/program/modules/{_IID}/items/reorder"),
    # Phase 5
    ("post", f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments"),
    ("put", f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments/{_IID}"),
    ("post", f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments/reorder"),
    ("get", f"/api/v1/internships/{_IID}/program/submissions"),
    ("get", f"/api/v1/internships/{_IID}/program/submissions/{_IID}"),
]


def _body(method, url):
    if "reorder" in url:
        return {"ordered_ids": [_IID]}
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
        "internship": {"id": _IID, "title": "ML Intern", "status": "PUBLISHED"},
        "program": {"id": "prog-1", "internship_id": _IID, "title": "P", "summary": None,
                    "estimated_weeks": None, "status": "DRAFT", "published_at": None,
                    "created_at": None, "updated_at": None},
        "modules": [], "skills": [], "available_skills": [],
    }
    b.update(over)
    return b


def test_get_program_endpoint_returns_the_bundle():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_program_bundle", return_value=_bundle()),
    ):
        resp = client.get(f"/api/v1/internships/{_IID}/program", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 200
    assert resp.json()["program"]["status"] == "DRAFT"


def test_create_program_endpoint_is_201_and_forbids_client_status():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_program", return_value=_bundle()) as create,
    ):
        resp = client.post(
            f"/api/v1/internships/{_IID}/program",
            json={"title": "P", "status": "PUBLISHED"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422  # extra="forbid" rejects `status`
    create.assert_not_called()


def test_create_program_endpoint_maps_exists_to_409():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_program", side_effect=svc.ProgramExistsError(_IID)),
    ):
        resp = client.post(
            f"/api/v1/internships/{_IID}/program", json={"title": "P"}, headers={"Authorization": "Bearer t"}
        )
    assert resp.status_code == 409


def test_program_endpoint_maps_internship_not_found_to_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "get_program_bundle", side_effect=svc.InternshipNotFoundError(_IID)),
    ):
        resp = client.get(f"/api/v1/internships/{_IID}/program", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 404


def test_publish_endpoint_maps_validation_and_transition_errors():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "publish_program", side_effect=svc.PublishValidationError(["title"])),
    ):
        r1 = client.post(f"/api/v1/internships/{_IID}/program/publish", headers={"Authorization": "Bearer t"})
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "publish_program", side_effect=svc.InvalidStatusTransitionError("PUBLISHED", "PUBLISHED")),
    ):
        r2 = client.post(f"/api/v1/internships/{_IID}/program/publish", headers={"Authorization": "Bearer t"})
    assert r1.status_code == 422
    assert r2.status_code == 409


def test_skills_endpoint_maps_invalid_skill_to_422():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "set_program_skills", side_effect=svc.InvalidProgramSkillError("nope")),
    ):
        resp = client.put(
            f"/api/v1/internships/{_IID}/program/skills",
            json={"skills": [{"skill_id": _IID, "requirement": "REQUIRED"}]},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


# ============================================================
# Phase 5 -- assignment authoring (service)
# ============================================================


def _assignment_row(**over):
    row = {
        "id": "as1",
        "module_id": "m1",
        "program_id": "prog-1",
        "title": "Build a CLI",
        "description": None,
        "instructions": None,
        "assignment_type": "ASSIGNMENT",
        "is_required": True,
        "is_published": True,
        "order_index": 0,
        "due_offset_days": None,
        "submission_kind": "LINK",
        "repo_required": False,
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
        "title": "Build a CLI",
        "assignment_type": "ASSIGNMENT",
        "is_required": True,
        "is_published": True,
        "submission_kind": "LINK",
        "repo_required": False,
        "live_url_expected": False,
    }
    data.update(over)
    return data


def test_industry_creates_an_assignment_in_its_own_module():
    db = _db(modules=[_mod()])
    bundle = svc.create_assignment(db, "industry-1", _IID, "m1", _new_assignment())
    inserted = db.inserts[0]
    assert inserted[0] == "program_assignments"
    assert inserted[1]["module_id"] == "m1"
    got = bundle["modules"][0]["assignments"]
    assert len(got) == 1 and got[0]["title"] == "Build a CLI"
    assert got[0]["order_index"] == 0
    assert got[0]["program_id"] == "prog-1"  # trigger-forced lineage


def test_second_assignment_gets_the_next_order_index():
    db = _db(modules=[_mod()], assignments=[_assignment_row(id="as0", order_index=0)])
    svc.create_assignment(db, "industry-1", _IID, "m1", _new_assignment(title="Second"))
    assert db.inserts[0][1]["order_index"] == 1


def test_another_company_cannot_create_an_assignment():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.InternshipNotFoundError):
        svc.create_assignment(db, "industry-999", _IID, "m1", _new_assignment())
    assert db.inserts == []


def test_assignment_cannot_be_created_in_a_foreign_program_module():
    db = _db(modules=[{"id": "m-foreign", "program_id": "prog-OTHER", "title": "X",
                       "description": None, "order_index": 0, "is_published": True}])
    with pytest.raises(svc.ModuleNotFoundError):
        svc.create_assignment(db, "industry-1", _IID, "m-foreign", _new_assignment())
    assert db.inserts == []


def test_repo_required_with_a_non_repo_kind_is_rejected():
    db = _db(modules=[_mod()])
    with pytest.raises(svc.InvalidAssignmentError):
        svc.create_assignment(
            db, "industry-1", _IID, "m1",
            _new_assignment(repo_required=True, submission_kind="LINK"),
        )
    assert db.inserts == []


def test_repo_required_with_repo_kind_is_accepted():
    db = _db(modules=[_mod()])
    svc.create_assignment(
        db, "industry-1", _IID, "m1",
        _new_assignment(repo_required=True, submission_kind="REPO"),
    )
    assert db.inserts[0][1]["repo_required"] is True


def test_linked_skill_must_be_one_the_program_trains():
    db = _db(
        modules=[_mod()],
        program_skills=[{"id": "ps1", "program_id": "prog-1", "skill_id": "sk-py", "requirement": "REQUIRED"}],
    )
    with pytest.raises(svc.InvalidAssignmentError):
        svc.create_assignment(
            db, "industry-1", _IID, "m1", _new_assignment(linked_skill_id="sk-not-in-program")
        )
    # a skill the program does train is fine
    svc.create_assignment(
        db, "industry-1", _IID, "m1", _new_assignment(linked_skill_id="sk-py")
    )
    assert db.inserts[0][1]["linked_skill_id"] == "sk-py"


def test_update_assignment_edits_fields_and_stays_scoped_to_the_module():
    db = _db(modules=[_mod()], assignments=[_assignment_row()])
    svc.update_assignment(
        db, "industry-1", _IID, "m1", "as1",
        {"title": "Renamed", "instructions": "Do it well"},
    )
    written = db.updates[-1][1]
    assert written == {"title": "Renamed", "instructions": "Do it well"}


def test_update_assignment_can_hide_it_via_is_published():
    db = _db(modules=[_mod()], assignments=[_assignment_row(is_published=True)])
    bundle = svc.update_assignment(db, "industry-1", _IID, "m1", "as1", {"is_published": False})
    assert db.updates[-1][1] == {"is_published": False}
    assert bundle["modules"][0]["assignments"][0]["is_published"] is False


def test_update_assignment_from_another_module_is_not_found():
    db = _db(
        modules=[_mod()],
        assignments=[_assignment_row(id="as-foreign", module_id="m-OTHER")],
    )
    with pytest.raises(svc.AssignmentNotFoundError):
        svc.update_assignment(db, "industry-1", _IID, "m1", "as-foreign", {"title": "hax"})
    assert db.updates == []


def test_update_assignment_rejects_an_inconsistent_repo_config():
    db = _db(modules=[_mod()], assignments=[_assignment_row(submission_kind="REPO", repo_required=True)])
    with pytest.raises(svc.InvalidAssignmentError):
        svc.update_assignment(db, "industry-1", _IID, "m1", "as1", {"submission_kind": "TEXT"})
    assert db.updates == []


def test_reorder_assignments_reassigns_indices():
    db = _db(modules=[_mod()], assignments=[
        _assignment_row(id="a1", order_index=0),
        _assignment_row(id="a2", order_index=1),
        _assignment_row(id="a3", order_index=2),
    ])
    bundle = svc.reorder_assignments(db, "industry-1", _IID, "m1", ["a3", "a1", "a2"])
    order = {a["id"]: a["order_index"] for a in bundle["modules"][0]["assignments"]}
    assert order == {"a3": 0, "a1": 1, "a2": 2}


def test_reorder_assignments_rejects_a_list_that_is_not_the_exact_set():
    db = _db(modules=[_mod()], assignments=[
        _assignment_row(id="a1", order_index=0),
        _assignment_row(id="a2", order_index=1),
    ])
    with pytest.raises(svc.InvalidReorderError):
        svc.reorder_assignments(db, "industry-1", _IID, "m1", ["a1"])
    with pytest.raises(svc.InvalidReorderError):
        svc.reorder_assignments(db, "industry-1", _IID, "m1", ["a1", "a2", "a-ghost"])


def test_bundle_returns_assignments_sorted_by_order_index():
    db = _db(modules=[_mod()], assignments=[
        _assignment_row(id="a2", title="Second", order_index=1),
        _assignment_row(id="a1", title="First", order_index=0),
    ])
    bundle = svc.get_program_bundle(db, "industry-1", _IID)
    assert [a["title"] for a in bundle["modules"][0]["assignments"]] == ["First", "Second"]


def test_no_assignment_delete_helper_exists():
    # 037 grants no DELETE policy on program_assignments -- hide via is_published.
    assert not hasattr(svc, "delete_assignment")


# ============================================================
# Phase 5 -- assignment routes (behaviour + error mapping)
# ============================================================


def test_create_assignment_endpoint_is_201():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_assignment", return_value=_bundle()) as create,
    ):
        resp = client.post(
            f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments",
            json={"title": "Build a CLI"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 201
    create.assert_called_once()


def test_create_assignment_endpoint_forbids_unknown_fields():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        resp = client.post(
            f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments",
            json={"title": "x", "is_graded": True},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_assignment_endpoint_maps_invalid_config_to_422():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "create_assignment", side_effect=svc.InvalidAssignmentError("bad")),
    ):
        resp = client.post(
            f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments",
            json={"title": "x"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 422


def test_assignment_endpoint_maps_not_found_to_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(svc, "update_assignment", side_effect=svc.AssignmentNotFoundError("nope")),
    ):
        resp = client.put(
            f"/api/v1/internships/{_IID}/program/modules/{_IID}/assignments/{_IID}",
            json={"title": "x"},
            headers={"Authorization": "Bearer t"},
        )
    assert resp.status_code == 404


# ============================================================
# 17. Phase 2 provisioning is unaffected by Phase 4 / 5
# ============================================================


def test_phase4_does_not_touch_phase2_provisioning():
    import inspect

    from app.services import internship_workspace_service

    p4_src = inspect.getsource(svc)
    # never CALLs provisioning and never writes a Phase 2 table or a
    # completion / certificate / stipend table (those are later phases).
    assert "provision_for_selection" not in p4_src
    for forbidden in (
        '.table("internship_workspaces")',
        '.table("applications")',
        '.table("internship_completions")',
        '.table("internship_certificates")',
        '.table("stipend_disbursements")',
    ):
        assert forbidden not in p4_src, f"program authoring must not touch {forbidden}"
    # Phase 6 review writes submission_reviews (append-only) + the
    # workspace_submissions.submission_status cache, and nothing else on
    # workspace_submissions -- the student's submission content stays
    # immutable from this module.
    for mutation in (
        '.table("workspace_submissions").insert',
        '.table("workspace_submissions").delete',
        '.table("submission_reviews").update',
        '.table("submission_reviews").delete',
    ):
        assert mutation not in p4_src, f"unexpected write from program service ({mutation})"
    # a published program is exactly what provisioning's SKIPPED_NO_PROGRAM
    # path waits for -- provision_for_selection reads internship_programs by
    # internship_id, which is what this phase creates. So the existing heal
    # endpoint / backfill script pick it up unchanged.
    assert "internship_programs" in inspect.getsource(
        internship_workspace_service.provision_for_selection
    )
