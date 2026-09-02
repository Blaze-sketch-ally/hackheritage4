"""Tests for the Student Portfolio API: /api/v1/student/{portfolio,projects,
certifications,achievements}.

Route tests mock app.services.student_portfolio_service and use
tests.conftest.authenticated_as, exactly like tests/test_student_learning.py.
Service tests drive the functions with a MagicMock Supabase client -- no
live project or real token. RLS is the real ownership boundary and is not
re-verified against a live database here (same note as
tests/test_student_learning.py).
"""

import inspect
import re
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.main import app
from app.services import student_portfolio_service as svc
from tests.conftest import authenticated_as

client = TestClient(app)

_PID = "11111111-1111-1111-1111-111111111111"
_CID = "22222222-2222-2222-2222-222222222222"
_AID = "33333333-3333-3333-3333-333333333333"
_SKILL = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

_H = {"Authorization": "Bearer token"}


def _project(**o):
    row = {
        "id": _PID,
        "title": "Skill Portal",
        "description": "A portfolio app.",
        "project_url": "https://example.com/app",
        "repo_url": "https://github.com/me/app",
        "start_date": "2026-01-01",
        "end_date": "2026-03-01",
        "is_ongoing": False,
        "skills": [{"skill_id": _SKILL, "skill_name": "Python", "category_name": "Programming"}],
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
    }
    row.update(o)
    return row


def _cert(**o):
    row = {
        "id": _CID,
        "name": "AWS Certified Cloud Practitioner",
        "issuing_organization": "Amazon Web Services",
        "issue_date": "2026-02-01",
        "expiry_date": "2029-02-01",
        "credential_id": "ABC-123",
        "credential_url": "https://verify.example.com/abc-123",
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
    }
    row.update(o)
    return row


def _achievement(**o):
    row = {
        "id": _AID,
        "title": "Hackathon Winner",
        "description": "1st place, HackHeritage 4.",
        "achievement_date": "2026-08-30",
        "issuing_organization": "AIC",
        "url": "https://example.com/win",
        "created_at": "2026-09-02T00:00:00Z",
        "updated_at": "2026-09-02T00:00:00Z",
    }
    row.update(o)
    return row


# ============================================================
# 1. Auth / role guards -- every endpoint
# ============================================================

_ENDPOINTS = [
    ("get", "/api/v1/student/portfolio", None),
    ("get", "/api/v1/student/projects", None),
    ("post", "/api/v1/student/projects", {"title": "x"}),
    ("get", f"/api/v1/student/projects/{_PID}", None),
    ("put", f"/api/v1/student/projects/{_PID}", {"title": "x"}),
    ("delete", f"/api/v1/student/projects/{_PID}", None),
    ("get", "/api/v1/student/certifications", None),
    ("post", "/api/v1/student/certifications", {"name": "x"}),
    ("get", f"/api/v1/student/certifications/{_CID}", None),
    ("put", f"/api/v1/student/certifications/{_CID}", {"name": "x"}),
    ("delete", f"/api/v1/student/certifications/{_CID}", None),
    ("get", "/api/v1/student/achievements", None),
    ("post", "/api/v1/student/achievements", {"title": "x"}),
    ("get", f"/api/v1/student/achievements/{_AID}", None),
    ("put", f"/api/v1/student/achievements/{_AID}", {"title": "x"}),
    ("delete", f"/api/v1/student/achievements/{_AID}", None),
]


def _call(method, url, body, *, headers=None):
    kw = {"headers": headers} if headers else {}
    if body is not None:
        return getattr(client, method)(url, json=body, **kw)
    return getattr(client, method)(url, **kw)


def test_all_endpoints_reject_unauthenticated():
    for method, url, body in _ENDPOINTS:
        assert _call(method, url, body).status_code == 401, (method, url)


def test_all_endpoints_forbid_non_student_roles():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", None):
        for method, url, body in _ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, body, headers=_H)
            assert resp.status_code == 403, (role, method, url)


# ============================================================
# 2. Projects -- CRUD happy path (identity always from the token)
# ============================================================


def test_create_project_derives_student_id_from_token():
    captured = {}

    def fake_create(_client, student_id, data):
        captured["student_id"] = student_id
        captured["data"] = data
        return _project(title=data["title"])

    with (
        authenticated_as("STUDENT", user_id="student-9"),
        patch.object(svc, "create_project", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/student/projects",
            json={"title": "  Skill Portal  ", "skill_ids": [_SKILL, _SKILL]},
            headers=_H,
        )
    assert resp.status_code == 201
    assert captured["student_id"] == "student-9"
    assert captured["data"]["title"] == "Skill Portal"  # trimmed
    assert captured["data"]["skill_ids"] == [_SKILL]  # deduped
    assert "student_id" not in captured["data"]
    assert resp.json()["title"] == "Skill Portal"


def test_list_projects_scoped_to_caller():
    captured = {}

    def fake_list(_client, student_id):
        captured["student_id"] = student_id
        return [_project(), _project(id=str(uuid4()), title="Second")]

    with (
        authenticated_as("STUDENT", user_id="student-77"),
        patch.object(svc, "list_projects", side_effect=fake_list),
    ):
        resp = client.get("/api/v1/student/projects", headers=_H)
    assert resp.status_code == 200
    assert captured["student_id"] == "student-77"
    body = resp.json()["projects"]
    assert [p["title"] for p in body] == ["Skill Portal", "Second"]
    assert body[0]["skills"][0]["skill_name"] == "Python"


def test_get_project_404_when_not_owned():
    """The service returns None for another student's project (its query
    filters `.eq('student_id', caller)`) -- the route turns that into 404,
    never revealing the row exists."""
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_project", return_value=None),
    ):
        resp = client.get(f"/api/v1/student/projects/{uuid4()}", headers=_H)
    assert resp.status_code == 404


def test_update_project_404_when_not_owned():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "update_project", return_value=None) as mock_update,
    ):
        resp = client.put(
            f"/api/v1/student/projects/{_PID}", json={"title": "hijack"}, headers=_H
        )
    assert resp.status_code == 404
    assert mock_update.call_args.args[1] == "student-1"  # caller id, not a body value


def test_delete_project_404_when_not_owned():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "delete_project", return_value=False),
    ):
        resp = client.delete(f"/api/v1/student/projects/{_PID}", headers=_H)
    assert resp.status_code == 404


def test_delete_project_204_when_owned():
    with (
        authenticated_as("STUDENT", user_id="student-5"),
        patch.object(svc, "delete_project", return_value=True) as mock_del,
    ):
        resp = client.delete(f"/api/v1/student/projects/{_PID}", headers=_H)
    assert resp.status_code == 204
    assert mock_del.call_args.args[1:] == ("student-5", _PID)


def test_create_project_rejects_unknown_skill_ids():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            svc, "create_project", side_effect=svc.InvalidSkillError(["deadbeef"])
        ),
    ):
        resp = client.post(
            "/api/v1/student/projects",
            json={"title": "P", "skill_ids": ["deadbeef"]},
            headers=_H,
        )
    assert resp.status_code == 422
    assert "deadbeef" in resp.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "P", "student_id": "victim"},
        {"title": "P", "owner_id": "victim"},
        {"title": "P", "id": "forced-id"},
        {"title": "P", "created_at": "2020-01-01T00:00:00Z"},
        {"title": "P", "is_verified": True},
        {"title": "P", "verified_at": "2020-01-01"},
    ],
)
def test_create_project_rejects_extra_ownership_fields(payload):
    with authenticated_as("STUDENT"):
        resp = client.post("/api/v1/student/projects", json=payload, headers=_H)
    assert resp.status_code == 422, payload


def test_create_project_rejects_missing_title():
    with authenticated_as("STUDENT"):
        assert client.post("/api/v1/student/projects", json={}, headers=_H).status_code == 422
        assert (
            client.post(
                "/api/v1/student/projects", json={"title": "   "}, headers=_H
            ).status_code
            == 422
        )


def test_create_project_rejects_bad_dates_and_urls():
    with authenticated_as("STUDENT"):
        assert (
            client.post(
                "/api/v1/student/projects",
                json={"title": "P", "start_date": "2026-06-01", "end_date": "2026-01-01"},
                headers=_H,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/student/projects",
                json={"title": "P", "is_ongoing": True, "end_date": "2026-01-01"},
                headers=_H,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/student/projects",
                json={"title": "P", "project_url": "ftp://x"},
                headers=_H,
            ).status_code
            == 422
        )


def test_project_id_path_must_be_uuid():
    with authenticated_as("STUDENT"):
        assert client.get("/api/v1/student/projects/not-a-uuid", headers=_H).status_code == 422


# ============================================================
# 3. Certifications -- CRUD + IDOR
# ============================================================


def test_certification_crud_and_scoping():
    captured = {}
    with (
        authenticated_as("STUDENT", user_id="student-3"),
        patch.object(svc, "create_certification", side_effect=lambda _c, sid, d: captured.update(sid=sid, d=d) or _cert(name=d["name"])),
        patch.object(svc, "list_certifications", return_value=[_cert()]),
        patch.object(svc, "get_certification", return_value=_cert()),
        patch.object(svc, "update_certification", return_value=_cert(name="Renamed")),
        patch.object(svc, "delete_certification", return_value=True),
    ):
        r = client.post("/api/v1/student/certifications", json={"name": "AWS CCP"}, headers=_H)
        assert r.status_code == 201 and captured["sid"] == "student-3"
        assert "student_id" not in captured["d"]
        assert client.get("/api/v1/student/certifications", headers=_H).json()["certifications"][0]["name"] == "AWS Certified Cloud Practitioner"
        assert client.get(f"/api/v1/student/certifications/{_CID}", headers=_H).status_code == 200
        assert client.put(f"/api/v1/student/certifications/{_CID}", json={"name": "Renamed"}, headers=_H).json()["name"] == "Renamed"
        assert client.delete(f"/api/v1/student/certifications/{_CID}", headers=_H).status_code == 204


def test_certification_404_when_not_owned():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_certification", return_value=None),
        patch.object(svc, "update_certification", return_value=None),
        patch.object(svc, "delete_certification", return_value=False),
    ):
        assert client.get(f"/api/v1/student/certifications/{uuid4()}", headers=_H).status_code == 404
        assert client.put(f"/api/v1/student/certifications/{_CID}", json={"name": "x"}, headers=_H).status_code == 404
        assert client.delete(f"/api/v1/student/certifications/{_CID}", headers=_H).status_code == 404


def test_certification_rejects_extra_and_bad_fields():
    with authenticated_as("STUDENT"):
        assert client.post("/api/v1/student/certifications", json={"name": "C", "student_id": "v"}, headers=_H).status_code == 422
        assert client.post("/api/v1/student/certifications", json={"name": "C", "issue_date": "2026-06-01", "expiry_date": "2026-01-01"}, headers=_H).status_code == 422
        assert client.post("/api/v1/student/certifications", json={}, headers=_H).status_code == 422


# ============================================================
# 4. Achievements -- CRUD + IDOR
# ============================================================


def test_achievement_crud_and_scoping():
    captured = {}
    with (
        authenticated_as("STUDENT", user_id="student-4"),
        patch.object(svc, "create_achievement", side_effect=lambda _c, sid, d: captured.update(sid=sid, d=d) or _achievement(title=d["title"])),
        patch.object(svc, "list_achievements", return_value=[_achievement()]),
        patch.object(svc, "get_achievement", return_value=_achievement()),
        patch.object(svc, "update_achievement", return_value=_achievement(title="Edited")),
        patch.object(svc, "delete_achievement", return_value=True),
    ):
        r = client.post("/api/v1/student/achievements", json={"title": "Winner"}, headers=_H)
        assert r.status_code == 201 and captured["sid"] == "student-4" and "student_id" not in captured["d"]
        assert client.get("/api/v1/student/achievements", headers=_H).json()["achievements"][0]["title"] == "Hackathon Winner"
        assert client.get(f"/api/v1/student/achievements/{_AID}", headers=_H).status_code == 200
        assert client.put(f"/api/v1/student/achievements/{_AID}", json={"title": "Edited"}, headers=_H).json()["title"] == "Edited"
        assert client.delete(f"/api/v1/student/achievements/{_AID}", headers=_H).status_code == 204


def test_achievement_404_when_not_owned():
    with (
        authenticated_as("STUDENT"),
        patch.object(svc, "get_achievement", return_value=None),
        patch.object(svc, "update_achievement", return_value=None),
        patch.object(svc, "delete_achievement", return_value=False),
    ):
        assert client.get(f"/api/v1/student/achievements/{uuid4()}", headers=_H).status_code == 404
        assert client.put(f"/api/v1/student/achievements/{_AID}", json={"title": "x"}, headers=_H).status_code == 404
        assert client.delete(f"/api/v1/student/achievements/{_AID}", headers=_H).status_code == 404


def test_achievement_rejects_extra_fields():
    with authenticated_as("STUDENT"):
        assert client.post("/api/v1/student/achievements", json={"title": "A", "owner_id": "v"}, headers=_H).status_code == 422
        assert client.post("/api/v1/student/achievements", json={"title": "A", "url": "notaurl"}, headers=_H).status_code == 422


# ============================================================
# 5. Portfolio aggregate -- only the caller's own data
# ============================================================


def test_portfolio_aggregates_only_own_data():
    captured = {}

    def fake_portfolio(_client, student_id):
        captured["student_id"] = student_id
        return {
            "projects": [_project()],
            "certifications": [_cert()],
            "achievements": [_achievement()],
            "skills": [
                {
                    "skill_id": _SKILL,
                    "skill_name": "Python",
                    "category_name": "Programming",
                    "proficiency_level": "Advanced",
                    "is_verified": True,
                }
            ],
        }

    with (
        authenticated_as("STUDENT", user_id="student-88"),
        patch.object(svc, "get_portfolio", side_effect=fake_portfolio),
    ):
        resp = client.get("/api/v1/student/portfolio", headers=_H)
    assert resp.status_code == 200
    assert captured["student_id"] == "student-88"
    body = resp.json()
    assert len(body["projects"]) == 1
    assert len(body["certifications"]) == 1
    assert len(body["achievements"]) == 1
    assert body["skills"][0]["proficiency_level"] == "Advanced"
    assert body["skills"][0]["is_verified"] is True


# ============================================================
# 6. Service layer -- ownership filter + skill validation + no student_skills writes
# ============================================================


def _fluent(final_data):
    q = MagicMock()
    for m in ("select", "eq", "in_", "order", "maybe_single", "insert", "update", "delete"):
        getattr(q, m).return_value = q
    q.execute.return_value.data = final_data
    return q


def test_service_own_lookups_filter_by_student_id():
    for fn, table in (
        (svc._own_project, "student_projects"),
        (svc._own_certification, "student_certifications"),
        (svc._own_achievement, "student_achievements"),
    ):
        supabase = MagicMock()
        q = _fluent(None)
        supabase.table.return_value = q
        fn(supabase, "student-1", "row-1")
        eq_calls = [c.args for c in q.eq.call_args_list]
        assert ("id", "row-1") in eq_calls
        assert ("student_id", "student-1") in eq_calls


def test_service_create_project_sets_student_id_from_argument_only():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": _PID}]
    with (
        patch.object(svc, "_validate_skill_ids"),
        patch.object(svc, "_set_project_skills"),
        patch.object(svc, "_own_project", return_value=_project()),
    ):
        svc.create_project(supabase, "student-1", {"title": "P", "skill_ids": []})
    payload = supabase.table.return_value.insert.call_args.args[0]
    assert payload["student_id"] == "student-1"
    assert payload["title"] == "P"


def test_service_validate_skill_ids_raises_on_unknown():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {"id": _SKILL}
    ]
    svc._validate_skill_ids(supabase, [_SKILL])  # ok
    with pytest.raises(svc.InvalidSkillError):
        svc._validate_skill_ids(supabase, [_SKILL, "missing"])


def test_service_create_project_maps_fk_violation_to_invalid_skill():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": _PID}]
    with (
        patch.object(svc, "_validate_skill_ids"),
        patch.object(
            svc,
            "_set_project_skills",
            side_effect=APIError({"code": "23503", "message": "fk"}),
        ),
        pytest.raises(svc.InvalidSkillError),
    ):
        svc.create_project(supabase, "student-1", {"title": "P", "skill_ids": [_SKILL]})


def test_service_never_writes_student_skills_or_verification():
    """The service may READ student_skills (portfolio aggregate) but must
    never WRITE it, and must never touch the assessment scoring path."""
    src = inspect.getsource(svc).replace("\n", "")
    for banned in (
        'table("student_skills").insert(',
        'table("student_skills").update(',
        'table("student_skills").upsert(',
        'table("student_skills").delete(',
        "score_assessment_attempt",
        'table("assessment_attempts")',
        'table("assessments")',
    ):
        assert banned not in src, f"service must not touch {banned}"
    # a WRITE payload never carries a verification / proficiency field
    for m in re.finditer(r'payload\s*=\s*\{(.*?)\}', inspect.getsource(svc), re.DOTALL):
        block = m.group(1)
        assert "is_verified" not in block and "verified_at" not in block and "proficiency" not in block


def test_service_only_writes_portfolio_tables():
    compact = inspect.getsource(svc).replace("\n", "").replace(" ", "")
    allowed = {"student_projects", "student_project_skills", "student_certifications", "student_achievements"}
    for m in re.finditer(r'\.table\("([a-z_]+)"\)(\.[a-z_]+\()', compact):
        table, verb = m.group(1), m.group(2)
        if verb in (".insert(", ".update(", ".upsert(", ".delete("):
            assert table in allowed, f"unexpected write {verb} against {table}"


def test_portfolio_modules_do_not_use_service_role():
    from app.api import student_portfolio as routes

    assert not hasattr(svc, "get_supabase")
    assert not hasattr(routes, "get_supabase")
    assert hasattr(routes, "build_user_client")


def test_routes_never_declare_a_student_id_parameter():
    from app.api import student_portfolio as routes

    for name in dir(routes):
        fn = getattr(routes, name)
        if callable(fn) and getattr(fn, "__module__", "") == routes.__name__:
            params = set(inspect.signature(fn).parameters) if hasattr(fn, "__code__") else set()
            assert "student_id" not in params and "owner_id" not in params, name


# ============================================================
# 7. Migration 034 -- additive, owner-only RLS, orphan tables untouched
# ============================================================

from pathlib import Path

_MIGRATION = (
    Path(__file__).resolve().parents[2] / "database" / "migrations" / "034_student_portfolio.sql"
).read_text(encoding="utf-8").lower()


def test_migration_034_exists_and_is_numbered_after_033():
    mdir = _MIGRATION and (Path(__file__).resolve().parents[2] / "database" / "migrations")
    names = {p.name for p in mdir.glob("[0-9][0-9][0-9]_*.sql")}
    assert "034_student_portfolio.sql" in names
    assert "033_learning_resources.sql" in names
    # placeholder left exactly as-is, not superseded in place
    assert "008_portfolio.sql" in names
    assert "not implemented yet" in _sql(mdir / "008_portfolio.sql").lower()


def _sql(path):
    return path.read_text(encoding="utf-8")


# migration SQL with `-- ...` comment lines stripped, so assertions about
# what the DDL *does* aren't tripped by the prose that explains it.
_MIGRATION_CODE = "\n".join(
    ln for ln in _MIGRATION.splitlines() if not ln.strip().startswith("--")
)


def test_migration_034_creates_the_four_tables_and_no_others():
    for table in (
        "student_projects",
        "student_project_skills",
        "student_certifications",
        "student_achievements",
    ):
        assert f"create table if not exists {table}" in _MIGRATION


def test_migration_034_is_additive_and_touches_no_orphan_or_historical_table():
    code = _MIGRATION_CODE
    assert "drop table" not in code
    # the DDL never names the divergent-lineage orphan tables at all
    # (the header comment discusses them, but no statement references them)
    assert "portfolio_projects" not in code
    assert "portfolio_certifications" not in code
    for existing in ("profiles", "skills", "student_skills", "skill_categories"):
        assert f"alter table {existing} " not in code
    # reuses, never redefines, the shared trigger helper
    assert "create or replace function public.set_updated_at" not in code
    assert "execute procedure public.set_updated_at()" in code


def test_migration_034_rls_is_owner_only_on_all_four_directions():
    # every student-owned table gets select/insert/update/delete, all scoped
    for table in ("student_projects", "student_certifications", "student_achievements"):
        block = _MIGRATION.split(f"create table if not exists {table}", 1)[1]
        for direction in ("for select", "for insert", "for update", "for delete"):
            assert direction in block, f"{table} missing a {direction} policy"
    # the ownership predicate appears for every policy
    assert _MIGRATION.count("auth.uid() = student_id and public.is_student(auth.uid())") >= 12
    # project skills inherit ownership via EXISTS on the parent project
    assert "p.student_id = auth.uid()" in _MIGRATION


def test_migration_034_has_no_verification_or_proficiency_columns():
    # checked against the comment-stripped DDL -- the header note legitimately
    # names these fields to explain what the tables deliberately omit.
    for banned in ("is_verified", "verified_at", "proficiency_level", "proficiency_score"):
        assert banned not in _MIGRATION_CODE, f"portfolio tables must not carry {banned}"
