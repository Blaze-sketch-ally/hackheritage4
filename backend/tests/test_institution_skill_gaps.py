"""Tests for the Institution Skill Gap Analysis:
/api/v1/institution/skill-gaps..., database/migrations/
080_institution_skill_gap.sql.

An APPLICATION-scoped tool, not an institution-wide dashboard: student ->
application -> job/internship -> required skills -> student skills -> gap.
Route tests mock app.services.institution_skill_gap_service and use
tests.conftest.authenticated_as, matching the rest of the institution test
suite. Service tests drive institution_skill_gap_service against a fake
Supabase client (table reads + rpc calls) to verify tenancy isolation, that
the deterministic match_service.compute_match engine is reused unchanged
(never a second scoring algorithm), and that job/internship applications,
multiple applications by the same student, and missing/empty data are all
handled safely.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_skill_gap_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/skill-gaps"
APP_ID = "11111111-1111-1111-1111-111111111111"


def _summary_row(**overrides):
    row = {
        "application_id": APP_ID,
        "student_id": "student-1",
        "full_name": "Tapan",
        "username": "tapan1",
        "opportunity_type": "INTERNSHIP",
        "opportunity_title": "Software Intern",
        "company_name": "Robotics Inc",
        "status": "APPLIED",
        "applied_at": "2026-01-01T00:00:00Z",
        "score": 67,
        "recommendation": "PARTIAL",
        "skill_coverage": "2 / 3",
        "matched_count": 2,
        "needs_improvement_count": 0,
        "missing_count": 1,
    }
    row.update(overrides)
    return row


def _detail_row(**overrides):
    row = {
        **_summary_row(),
        "required_count": 3,
        "matched_skills": [],
        "needs_improvement_skills": [],
        "missing_skills": [],
        "student_skills": [],
    }
    row.update(overrides)
    return row


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/{APP_ID}").status_code == 401


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.get(f"{BASE}/{APP_ID}", headers={"Authorization": "Bearer token"}).status_code
                == 403
            )


# ============================================================
# Route wiring
# ============================================================


def test_list_scopes_to_authenticated_institution_and_forwards_params():
    captured = {}

    def fake_list(_client, institution_id, **kwargs):
        captured["institution_id"] = institution_id
        captured.update(kwargs)
        return [_summary_row()]

    with (
        authenticated_as("INSTITUTION", user_id="inst-1"),
        patch.object(institution_skill_gap_service, "list_skill_gap_applications", side_effect=fake_list),
    ):
        resp = client.get(
            f"{BASE}?search=tapan&opportunity_type=INTERNSHIP&status=APPLIED",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert resp.json()["applications"][0]["application_id"] == APP_ID
    assert captured["institution_id"] == "inst-1"
    assert captured["search"] == "tapan"
    assert captured["opportunity_type"] == "INTERNSHIP"
    assert captured["status_filter"] == "APPLIED"


def test_list_returns_empty_list_with_no_applications():
    with (
        authenticated_as("INSTITUTION", user_id="inst-1"),
        patch.object(institution_skill_gap_service, "list_skill_gap_applications", return_value=[]),
    ):
        resp = client.get(BASE, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json() == {"applications": []}


def test_list_service_error_becomes_safe_500():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_skill_gap_service,
            "list_skill_gap_applications",
            side_effect=RuntimeError("pg exploded"),
        ),
    ):
        resp = client.get(BASE, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 500
    assert "pg exploded" not in resp.text


def test_detail_scopes_to_authenticated_institution():
    captured = {}

    def fake_get(_client, institution_id, application_id):
        captured["institution_id"] = institution_id
        captured["application_id"] = application_id
        return _detail_row()

    with (
        authenticated_as("INSTITUTION", user_id="inst-1"),
        patch.object(institution_skill_gap_service, "get_skill_gap_detail", side_effect=fake_get),
    ):
        resp = client.get(f"{BASE}/{APP_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json()["application_id"] == APP_ID
    assert captured["institution_id"] == "inst-1"
    assert captured["application_id"] == APP_ID


def test_detail_404_when_not_found_or_not_owned():
    with (
        authenticated_as("INSTITUTION", user_id="inst-1"),
        patch.object(institution_skill_gap_service, "get_skill_gap_detail", return_value=None),
    ):
        resp = client.get(f"{BASE}/{APP_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_detail_service_error_becomes_safe_500():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_skill_gap_service, "get_skill_gap_detail", side_effect=RuntimeError("boom")
        ),
    ):
        resp = client.get(f"{BASE}/{APP_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 500
    assert "boom" not in resp.text


def test_no_write_endpoints_exist():
    with authenticated_as("INSTITUTION"):
        assert client.post(BASE, json={}, headers={"Authorization": "Bearer token"}).status_code == 405
        assert (
            client.delete(f"{BASE}/{APP_ID}", headers={"Authorization": "Bearer token"}).status_code
            == 405
        )


# ============================================================
# Service-level tests -- fake Supabase client
# ============================================================


class _FakeQuery:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._rows = list(store.get(name, []))
        self._single = False

    def select(self, *_a, **_kw):
        return self

    def eq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) == value]
        return self

    def in_(self, field, values):
        values = set(values)
        self._rows = [r for r in self._rows if r.get(field) in values]
        return self

    def order(self, _field, desc=False):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        data = self._rows[0] if self._single and self._rows else (None if self._single else self._rows)
        return MagicMock(data=data)


class _FakeClient:
    def __init__(self, tables: dict, rpc_results: dict | None = None):
        self._tables = tables
        self._rpc_results = rpc_results or {}

    def table(self, name):
        return _FakeQuery(self._tables, name)

    def rpc(self, name, params):
        handler = self._rpc_results.get(name, [])
        data = handler(params) if callable(handler) else handler
        return MagicMock(execute=lambda: MagicMock(data=data))


def _base_tables(**overrides):
    tables = {
        "student_profiles": [],
        "applications": [],
        "industry_profiles": [],
        "student_skills": [],
    }
    tables.update(overrides)
    return tables


def _names_rpc(rows):
    return lambda params: [r for r in rows if r["student_id"] in set(params.get("student_ids", []))]


def _titles_rpc(rows):
    def handler(params):
        wanted = set(params.get("internship_ids", [])) | set(params.get("job_ids", []))
        return [r for r in rows if r["id"] in wanted]

    return handler


def _skill_match_rpc(rows):
    def handler(params):
        wanted = set(params.get("p_application_ids", []))
        return [r for r in rows if r["application_id"] in wanted]

    return handler


_NAMES = [{"student_id": "student-1", "full_name": "Tapan", "username": "tapan1", "avatar_url": None}]
_TITLES = [
    {"id": "intern-1", "opportunity_type": "INTERNSHIP", "title": "Software Intern"},
    {"id": "job-1", "opportunity_type": "JOB", "title": "Backend Developer"},
]
_COMPANIES = [
    {"id": "co-1", "company_name": "Robotics Inc"},
    {"id": "co-2", "company_name": "Beta Technologies"},
]


def _internship_application(**overrides):
    row = {
        "id": "app-1",
        "student_id": "student-1",
        "status": "APPLIED",
        "opportunity_type": "INTERNSHIP",
        "internship_id": "intern-1",
        "job_id": None,
        "applied_at": "2026-01-01T00:00:00Z",
        "industry_id": "co-1",
    }
    row.update(overrides)
    return row


def _job_application(**overrides):
    row = {
        "id": "app-2",
        "student_id": "student-1",
        "status": "SELECTED",
        "opportunity_type": "JOB",
        "internship_id": None,
        "job_id": "job-1",
        "applied_at": "2026-01-02T00:00:00Z",
        "industry_id": "co-2",
    }
    row.update(overrides)
    return row


def _skill_row(application_id, skill_id, name, required_level, importance, *, has, level=None, verified=False):
    return {
        "application_id": application_id,
        "skill_id": skill_id,
        "skill_name": name,
        "required_level": required_level,
        "importance": importance,
        "candidate_has": has,
        "candidate_level": level,
        "candidate_verified": verified,
    }


# ---- (1) Institution can retrieve its students' applications ----


def test_list_returns_own_students_applications():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [_skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True)]
        ),
    }
    rows = institution_skill_gap_service.list_skill_gap_applications(_FakeClient(tables, rpc), "inst-1")
    assert len(rows) == 1
    assert rows[0]["application_id"] == "app-1"
    assert rows[0]["full_name"] == "Tapan"
    assert rows[0]["opportunity_title"] == "Software Intern"
    assert rows[0]["company_name"] == "Robotics Inc"


# ---- (2) Institution cannot retrieve another institution's applications ----


def test_list_isolated_between_institutions():
    tables = _base_tables(
        student_profiles=[
            {"id": "student-1", "institution_id": "inst-1"},
            {"id": "student-2", "institution_id": "inst-2"},
        ],
        applications=[_internship_application(), _internship_application(id="app-other", student_id="student-2")],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc([]),
    }
    rows = institution_skill_gap_service.list_skill_gap_applications(_FakeClient(tables, rpc), "inst-1")
    assert {r["application_id"] for r in rows} == {"app-1"}

    rows_empty = institution_skill_gap_service.list_skill_gap_applications(
        _FakeClient(_base_tables(student_profiles=[{"id": "student-1", "institution_id": "inst-1"}]), rpc),
        "inst-2",
    )
    assert rows_empty == []


def test_list_returns_empty_when_institution_has_no_students():
    tables = _base_tables()
    rows = institution_skill_gap_service.list_skill_gap_applications(_FakeClient(tables), "inst-1")
    assert rows == []


# ---- (3) Institution can retrieve skill-gap detail for its student's application ----


def test_detail_returns_own_students_application():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application()],
        industry_profiles=_COMPANIES,
        student_skills=[
            {"student_id": "student-1", "proficiency_level": "Advanced", "is_verified": True, "skills": {"name": "Python"}}
        ],
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [_skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True)]
        ),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
    assert detail is not None
    assert detail["application_id"] == "app-1"
    assert detail["full_name"] == "Tapan"
    assert detail["student_skills"] == [
        {"skill_name": "Python", "proficiency_level": "Advanced", "is_verified": True}
    ]


# ---- (4) Institution cannot retrieve skill-gap detail for another institution's student's application ----


def test_detail_returns_none_for_another_institutions_application():
    tables = _base_tables(
        student_profiles=[{"id": "student-2", "institution_id": "inst-2"}],
        applications=[_internship_application(id="app-other", student_id="student-2")],
    )
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables), "inst-1", "app-other")
    assert detail is None


def test_detail_returns_none_for_nonexistent_application():
    tables = _base_tables(student_profiles=[{"id": "student-1", "institution_id": "inst-1"}])
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables), "inst-1", "does-not-exist")
    assert detail is None


def test_detail_returns_none_when_institution_has_no_students():
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(_base_tables()), "inst-1", "app-1")
    assert detail is None


# ---- (5) Job application skill gap works ----


def test_job_application_skill_gap():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_job_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [_skill_row("app-2", "s2", "SQL", "Advanced", "CORE", has=True, level="Advanced", verified=True)]
        ),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-2")
    assert detail["opportunity_type"] == "JOB"
    assert detail["opportunity_title"] == "Backend Developer"
    assert detail["company_name"] == "Beta Technologies"
    assert detail["matched_count"] == 1


# ---- (6) Internship application skill gap works ----


def test_internship_application_skill_gap():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [_skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True)]
        ),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
    assert detail["opportunity_type"] == "INTERNSHIP"
    assert detail["opportunity_title"] == "Software Intern"
    assert detail["matched_count"] == 1


# ---- (7)/(8)/(9) matched / missing / partial (needs-improvement) skills ----


def test_matched_missing_and_partial_skills_calculated_correctly():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [
                _skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True),
                _skill_row("app-1", "s2", "React", "Intermediate", "IMPORTANT", has=False),
                _skill_row("app-1", "s3", "SQL", "Advanced", "CORE", has=True, level="Beginner", verified=True),
            ]
        ),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
    assert detail["matched_count"] == 1
    assert detail["missing_count"] == 1
    assert detail["needs_improvement_count"] == 1
    assert detail["matched_skills"][0]["skill_name"] == "Python"
    assert detail["missing_skills"][0]["skill_name"] == "React"
    assert detail["needs_improvement_skills"][0]["skill_name"] == "SQL"


# ---- (10) No required skills is handled safely ----


def test_no_required_skills_is_handled_safely():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc([]),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
    assert detail["required_count"] == 0
    assert detail["score"] == 0
    assert detail["matched_skills"] == []
    assert detail["missing_skills"] == []


# ---- (11) Student with no recorded skills is handled safely ----


def test_student_with_no_recorded_skills_is_handled_safely():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application()],
        industry_profiles=_COMPANIES,
        student_skills=[],
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [_skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=False)]
        ),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
    assert detail["student_skills"] == []
    assert detail["missing_count"] == 1


# ---- (12) Missing/invalid opportunity reference is handled safely ----


def test_unresolvable_opportunity_title_is_handled_safely():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application(internship_id="deleted-internship")],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc([]),  # nothing resolves
        "institution_visible_application_skill_match": _skill_match_rpc([]),
    }
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
    assert detail is not None
    assert detail["opportunity_title"] is None


def test_application_with_no_internship_or_job_id_is_handled_safely():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application(internship_id=None, job_id=None)],
        industry_profiles=_COMPANIES,
    )
    detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables), "inst-1", "app-1")
    assert detail is not None
    assert detail["opportunity_title"] is None


# ---- (13) Multiple applications by the same student are handled independently ----


def test_multiple_applications_by_same_student_handled_independently():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application(), _job_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc(
            [
                _skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True),
                _skill_row("app-2", "s2", "SQL", "Advanced", "CORE", has=False),
            ]
        ),
    }
    rows = institution_skill_gap_service.list_skill_gap_applications(_FakeClient(tables, rpc), "inst-1")
    by_id = {r["application_id"]: r for r in rows}
    assert len(rows) == 2
    assert by_id["app-1"]["score"] == 100
    assert by_id["app-1"]["opportunity_type"] == "INTERNSHIP"
    assert by_id["app-2"]["score"] == 0
    assert by_id["app-2"]["opportunity_type"] == "JOB"


# ---- (14) Application status does not break skill-gap calculation ----


def test_application_status_does_not_affect_skill_gap_calculation():
    for app_status in ("APPLIED", "UNDER_REVIEW", "SHORTLISTED", "SELECTED", "REJECTED", "WITHDRAWN"):
        tables = _base_tables(
            student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
            applications=[_internship_application(status=app_status)],
            industry_profiles=_COMPANIES,
        )
        rpc = {
            "institution_student_names": _names_rpc(_NAMES),
            "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
            "institution_visible_application_skill_match": _skill_match_rpc(
                [_skill_row("app-1", "s1", "Python", "Intermediate", "CORE", has=True, level="Advanced", verified=True)]
            ),
        }
        detail = institution_skill_gap_service.get_skill_gap_detail(_FakeClient(tables, rpc), "inst-1", "app-1")
        assert detail["status"] == app_status
        assert detail["score"] == 100
        assert detail["matched_count"] == 1


# ---- Filters ----


def test_list_filters_by_search_type_and_status():
    tables = _base_tables(
        student_profiles=[{"id": "student-1", "institution_id": "inst-1"}],
        applications=[_internship_application(), _job_application()],
        industry_profiles=_COMPANIES,
    )
    rpc = {
        "institution_student_names": _names_rpc(_NAMES),
        "institution_visible_opportunity_titles": _titles_rpc(_TITLES),
        "institution_visible_application_skill_match": _skill_match_rpc([]),
    }

    only_jobs = institution_skill_gap_service.list_skill_gap_applications(
        _FakeClient(tables, rpc), "inst-1", opportunity_type="JOB"
    )
    assert {r["application_id"] for r in only_jobs} == {"app-2"}

    only_selected = institution_skill_gap_service.list_skill_gap_applications(
        _FakeClient(tables, rpc), "inst-1", status_filter="SELECTED"
    )
    assert {r["application_id"] for r in only_selected} == {"app-2"}

    by_company = institution_skill_gap_service.list_skill_gap_applications(
        _FakeClient(tables, rpc), "inst-1", search="robotics"
    )
    assert {r["application_id"] for r in by_company} == {"app-1"}


# ============================================================
# No service-role
# ============================================================


def test_institution_skill_gap_service_has_no_service_role_access():
    assert not hasattr(institution_skill_gap_service, "get_supabase")
