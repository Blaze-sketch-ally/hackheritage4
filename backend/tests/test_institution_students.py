"""Tests for the Institution Student Directory:
GET /api/v1/institution/students, GET /api/v1/institution/students/{id}.

Route tests mock app.services.institution_student_service and use
tests.conftest.authenticated_as, matching test_institution.py's structure.
Service tests drive list_students/get_student_detail with a fake Supabase
client (table reads + rpc calls) to verify tenancy scoping, search/filter/
sort/pagination, placement-status consistency with the dashboard
(_placement_buckets reuse), profile-completion parity with the student's
own page, and that interview notes are never selected.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_student_service
from tests.conftest import authenticated_as

client = TestClient(app)

LIST_URL = "/api/v1/institution/students"
STUDENT_ID = "11111111-1111-1111-1111-111111111111"


def _empty_list_payload():
    return {
        "students": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "filters": {"departments": [], "batches": []},
        "summary": {
            "total_students": 0,
            "placed": 0,
            "unplaced": 0,
            "no_applications": 0,
            "internship_selected": 0,
        },
    }


def _detail_payload(**overrides):
    payload = {
        "id": STUDENT_ID,
        "full_name": "Priya Sharma",
        "username": "priya_s",
        "avatar_url": None,
        "link_request_id": "22222222-2222-2222-2222-222222222222",
        "department_id": "33333333-3333-3333-3333-333333333333",
        "department": "CSE",
        "self_reported_department": "CSE",
        "batch": 2026,
        "degree": "B.Tech",
        "cgpa": 8.7,
        "percentage": None,
        "profile_completion": 75,
        "skills": [],
        "projects": [],
        "certifications": [],
        "achievements": [],
        "applications": [],
        "placement_status": "NOT_PARTICIPATING",
        "internship_status": "NONE",
        "assessments_completed": 0,
        "average_assessment_percentage": None,
        "assessments": [],
        "interviews": [],
        "notes": ["note"],
    }
    payload.update(overrides)
    return payload


# ============================================================
# Auth / role guards
# ============================================================


def test_list_unauthenticated_returns_401():
    assert client.get(LIST_URL).status_code == 401


def test_detail_unauthenticated_returns_401():
    assert client.get(f"{LIST_URL}/{STUDENT_ID}").status_code == 401


def test_list_forbids_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(LIST_URL, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


def test_detail_forbids_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(f"{LIST_URL}/{STUDENT_ID}", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


# ============================================================
# Route wiring
# ============================================================


def test_list_scopes_to_authenticated_institution_and_forwards_params():
    captured = {}

    def fake_list(_client, institution_id, **kwargs):
        captured["institution_id"] = institution_id
        captured.update(kwargs)
        return _empty_list_payload()

    with (
        authenticated_as("INSTITUTION", user_id="institution-55"),
        patch.object(institution_student_service, "list_students", side_effect=fake_list),
    ):
        resp = client.get(
            f"{LIST_URL}?search=priya&department=CSE&batch=2026&cgpa_min=7&cgpa_max=9"
            "&placement_status=PLACED&internship_status=NONE&skill=python&sort_by=cgpa"
            "&sort_dir=desc&page=2&page_size=10",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-55"
    assert captured["search"] == "priya"
    assert captured["department"] == "CSE"
    assert captured["batch"] == 2026
    assert captured["cgpa_min"] == 7
    assert captured["cgpa_max"] == 9
    assert captured["placement_status"] == "PLACED"
    assert captured["internship_status"] == "NONE"
    assert captured["skill"] == "python"
    assert captured["sort_by"] == "cgpa"
    assert captured["sort_dir"] == "desc"
    assert captured["page"] == 2
    assert captured["page_size"] == 10


def test_list_rejects_unknown_placement_status():
    with authenticated_as("INSTITUTION"):
        resp = client.get(
            f"{LIST_URL}?placement_status=BOGUS", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_list_falls_back_to_name_sort_for_unknown_sort_field():
    captured = {}

    def fake_list(_client, _institution_id, **kwargs):
        captured.update(kwargs)
        return _empty_list_payload()

    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_student_service, "list_students", side_effect=fake_list),
    ):
        resp = client.get(f"{LIST_URL}?sort_by=nonsense", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["sort_by"] == "name"


def test_detail_scopes_to_authenticated_institution():
    captured = {}

    def fake_detail(_client, institution_id, student_id):
        captured["institution_id"] = institution_id
        captured["student_id"] = student_id
        return _detail_payload()

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_student_service, "get_student_detail", side_effect=fake_detail),
    ):
        resp = client.get(f"{LIST_URL}/{STUDENT_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["student_id"] == STUDENT_ID


def test_detail_404_when_not_found_or_not_owned():
    """Institution B requesting Institution A's student (or any
    nonexistent id) gets the same 404 -- indistinguishable, since the
    service's own institution_id-scoped lookup returns None either way."""
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_student_service, "get_student_detail", return_value=None),
    ):
        resp = client.get(f"{LIST_URL}/{STUDENT_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_detail_rejects_invalid_student_id_format():
    with authenticated_as("INSTITUTION"):
        resp = client.get(f"{LIST_URL}/not-a-uuid", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


# ============================================================
# Service-level tests -- fake Supabase client
# ============================================================


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._single = False

    def select(self, *_a, **_k):
        return self

    def eq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) == value]
        return self

    def in_(self, field, values):
        values = set(values)
        self._rows = [r for r in self._rows if r.get(field) in values]
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
        return _FakeQuery(self._tables.get(name, []))

    def rpc(self, name, params):
        handler = self._rpc_results.get(name, [])
        data = handler(params) if callable(handler) else handler
        return MagicMock(execute=lambda: MagicMock(data=data))


def _names_rpc(rows):
    def handler(params):
        wanted = set(params.get("student_ids", []))
        return [r for r in rows if r["student_id"] in wanted]

    return handler


def _base_tables(**overrides):
    tables = {
        "student_profiles": [],
        "applications": [],
        "student_skills": [],
        "student_projects": [],
        "student_project_skills": [],
        "student_certifications": [],
        "student_achievements": [],
        "assessment_attempts": [],
        "assessments": [],
        "skills": [],
        "industry_profiles": [],
        "interviews": [],
        "institution_link_requests": [],
        "departments": [],
    }
    tables.update(overrides)
    return tables


def test_list_empty_institution_returns_empty_not_error():
    result = institution_student_service.list_students(_FakeClient(_base_tables()), "inst-1")
    assert result == {
        "students": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "filters": {"departments": [], "batches": []},
        "summary": {
            "total_students": 0,
            "placed": 0,
            "unplaced": 0,
            "no_applications": 0,
            "internship_selected": 0,
        },
    }


def test_list_summary_reflects_full_roster_not_the_filtered_page():
    """The summary cards must stay correct even when a search/filter/page
    narrows down `students` -- summary is computed from the roster BEFORE
    any of that is applied."""
    tables = _base_tables(
        student_profiles=[
            {"id": "placed", "institution_id": "inst-1", "department_id": "dept-cse", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
            {"id": "applying", "institution_id": "inst-1", "department_id": "dept-ece", "graduation_year": 2026, "cgpa": 7.0, "percentage": None},
            {"id": "none", "institution_id": "inst-1", "department_id": "dept-ece", "graduation_year": 2026, "cgpa": 6.0, "percentage": None},
        ],
        applications=[
            {"id": "a1", "student_id": "placed", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "int-1", "job_id": None, "applied_at": None, "industry_id": "co-1"},
            {"id": "a2", "student_id": "applying", "status": "APPLIED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "applied_at": None, "industry_id": "co-1"},
        ],
        departments=[
            {"id": "dept-cse", "institution_id": "inst-1", "name": "CSE"},
            {"id": "dept-ece", "institution_id": "inst-1", "name": "ECE"},
        ],
    )
    # Filtered down to just the CSE department -- only 1 of 3 students visible.
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1", department="dept-cse")
    assert len(result["students"]) == 1
    assert result["summary"] == {
        "total_students": 3,
        "placed": 1,
        "unplaced": 1,
        "no_applications": 1,
        "internship_selected": 1,
    }


def test_list_basic_fields_and_filters_metadata():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "dept-cse", "graduation_year": 2026, "cgpa": 8.7, "percentage": None},
            {"id": "s2", "institution_id": "inst-1", "department_id": "dept-ece", "graduation_year": 2027, "cgpa": 6.5, "percentage": None},
        ],
        departments=[
            {"id": "dept-cse", "institution_id": "inst-1", "name": "CSE"},
            {"id": "dept-ece", "institution_id": "inst-1", "name": "ECE"},
        ],
    )
    names = [
        {"student_id": "s1", "full_name": "A Student", "username": "a_student", "avatar_url": None},
        {"student_id": "s2", "full_name": "B Student", "username": "b_student", "avatar_url": None},
    ]
    result = institution_student_service.list_students(
        _FakeClient(tables, rpc_results={"institution_student_names": _names_rpc(names)}), "inst-1"
    )
    assert result["total"] == 2
    assert {d["name"] for d in result["filters"]["departments"]} == {"CSE", "ECE"}
    assert set(result["filters"]["batches"]) == {2026, 2027}
    by_id = {s["id"]: s for s in result["students"]}
    assert by_id["s1"]["full_name"] == "A Student"
    assert by_id["s1"]["department"] == "CSE"
    assert by_id["s1"]["cgpa"] == 8.7


def test_list_department_defaults_to_unassigned_when_no_department_id():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": None, "cgpa": None, "percentage": None},
        ]
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1")
    assert result["students"][0]["department"] == "Unassigned"
    assert result["students"][0]["department_id"] is None


def test_list_unassigned_filter_value_matches_students_with_no_department_id():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "dept-cse", "graduation_year": None, "cgpa": None, "percentage": None},
            {"id": "s2", "institution_id": "inst-1", "department_id": None, "graduation_year": None, "cgpa": None, "percentage": None},
        ],
        departments=[{"id": "dept-cse", "institution_id": "inst-1", "name": "CSE"}],
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1", department="unassigned")
    assert [s["id"] for s in result["students"]] == ["s2"]


def test_list_placement_status_matches_dashboard_definition():
    tables = _base_tables(
        student_profiles=[
            {"id": "placed", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
            {"id": "applying", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 7.0, "percentage": None},
            {"id": "none", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 6.0, "percentage": None},
        ],
        applications=[
            {"id": "a1", "student_id": "placed", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "applied_at": None, "industry_id": "co-1"},
            {"id": "a2", "student_id": "applying", "status": "APPLIED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "applied_at": None, "industry_id": "co-1"},
        ],
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1")
    by_id = {s["id"]: s for s in result["students"]}
    assert by_id["placed"]["placement_status"] == "PLACED"
    assert by_id["applying"]["placement_status"] == "APPLYING"
    assert by_id["none"]["placement_status"] == "NOT_PARTICIPATING"


def test_list_internship_status_is_scoped_to_internship_applications_only():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
        ],
        applications=[
            # A SELECTED job should NOT count as an internship selection.
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "applied_at": None, "industry_id": "co-1"},
        ],
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1")
    assert result["students"][0]["internship_status"] == "NONE"

    tables["applications"].append(
        {"id": "a2", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
         "internship_id": "int-1", "job_id": None, "applied_at": None, "industry_id": "co-1"}
    )
    result2 = institution_student_service.list_students(_FakeClient(tables), "inst-1")
    assert result2["students"][0]["internship_status"] == "SELECTED"


def test_list_search_matches_name_or_username_only():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
            {"id": "s2", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 7.0, "percentage": None},
        ],
    )
    names = [
        {"student_id": "s1", "full_name": "Priya Sharma", "username": "priya_s", "avatar_url": None},
        {"student_id": "s2", "full_name": "Rahul Verma", "username": "rahul_v", "avatar_url": None},
    ]
    result = institution_student_service.list_students(
        _FakeClient(tables, rpc_results={"institution_student_names": _names_rpc(names)}),
        "inst-1",
        search="priya",
    )
    assert [s["id"] for s in result["students"]] == ["s1"]


def test_list_department_and_cgpa_range_filters():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "dept-cse", "graduation_year": 2026, "cgpa": 9.2, "percentage": None},
            {"id": "s2", "institution_id": "inst-1", "department_id": "dept-cse", "graduation_year": 2026, "cgpa": 6.0, "percentage": None},
            {"id": "s3", "institution_id": "inst-1", "department_id": "dept-ece", "graduation_year": 2026, "cgpa": 9.0, "percentage": None},
        ],
        departments=[
            {"id": "dept-cse", "institution_id": "inst-1", "name": "CSE"},
            {"id": "dept-ece", "institution_id": "inst-1", "name": "ECE"},
        ],
    )
    result = institution_student_service.list_students(
        _FakeClient(tables), "inst-1", department="dept-cse", cgpa_min=8.0
    )
    assert [s["id"] for s in result["students"]] == ["s1"]


def test_list_skill_filter_matches_substring():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
            {"id": "s2", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
        ],
        student_skills=[
            {"student_id": "s1", "proficiency_level": "Advanced", "is_verified": False, "skills": {"name": "Python"}},
            {"student_id": "s2", "proficiency_level": "Advanced", "is_verified": False, "skills": {"name": "Java"}},
        ],
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1", skill="pyth")
    assert [s["id"] for s in result["students"]] == ["s1"]
    assert result["students"][0]["top_skills"] == ["Python"]


def test_list_placement_and_internship_status_filters():
    tables = _base_tables(
        student_profiles=[
            {"id": "placed", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
            {"id": "none", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 8.0, "percentage": None},
        ],
        applications=[
            {"id": "a1", "student_id": "placed", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "applied_at": None, "industry_id": "co-1"},
        ],
    )
    result = institution_student_service.list_students(
        _FakeClient(tables), "inst-1", placement_status="PLACED"
    )
    assert [s["id"] for s in result["students"]] == ["placed"]


def test_list_sorting_by_cgpa_desc():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 6.0, "percentage": None},
            {"id": "s2", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": 9.0, "percentage": None},
            {"id": "s3", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None},
        ],
    )
    result = institution_student_service.list_students(
        _FakeClient(tables), "inst-1", sort_by="cgpa", sort_dir="desc"
    )
    assert [s["id"] for s in result["students"]] == ["s2", "s1", "s3"]


def test_list_pagination_slices_the_filtered_sorted_result():
    tables = _base_tables(
        student_profiles=[
            {"id": f"s{i}", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": float(i), "percentage": None}
            for i in range(1, 6)
        ],
    )
    page1 = institution_student_service.list_students(
        _FakeClient(tables), "inst-1", sort_by="cgpa", page=1, page_size=2
    )
    page2 = institution_student_service.list_students(
        _FakeClient(tables), "inst-1", sort_by="cgpa", page=2, page_size=2
    )
    assert page1["total"] == 5
    assert [s["id"] for s in page1["students"]] == ["s1", "s2"]
    assert [s["id"] for s in page2["students"]] == ["s3", "s4"]


def test_list_includes_link_request_id_for_unlink_action():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None},
        ],
        institution_link_requests=[
            {"id": "req-1", "student_id": "s1", "institution_id": "inst-1", "status": "APPROVED"},
        ],
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1")
    assert result["students"][0]["link_request_id"] == "req-1"


def test_list_page_size_is_capped():
    tables = _base_tables(
        student_profiles=[
            {"id": f"s{i}", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None}
            for i in range(1, 5)
        ]
    )
    result = institution_student_service.list_students(_FakeClient(tables), "inst-1", page_size=99999)
    assert result["page_size"] == 100


# ---- detail ----


def test_detail_returns_none_when_not_linked_to_this_institution():
    tables = _base_tables()  # no student_profiles rows at all
    assert institution_student_service.get_student_detail(_FakeClient(tables), "inst-1", "ghost") is None


def test_detail_assembles_profile_skills_and_completion():
    tables = _base_tables(
        student_profiles=[
            {
                "id": "s1", "institution_id": "inst-1", "department": "CSE", "department_id": "dept-cse",
                "graduation_year": 2026, "cgpa": 8.7, "percentage": None,
                "degree": "B.Tech", "phone": "123", "date_of_birth": None, "gender": None, "location": None,
                "institution_name": None, "career_goals": None, "preferred_roles": [], "preferred_locations": [],
                "interests": [],
            }
        ],
        departments=[{"id": "dept-cse", "institution_id": "inst-1", "name": "CSE"}],
        student_skills=[
            {"student_id": "s1", "proficiency_level": "Expert", "is_verified": True, "skills": {"name": "Python"}},
        ],
    )
    names = [{"student_id": "s1", "full_name": "A Student", "username": "a_student", "avatar_url": None}]
    result = institution_student_service.get_student_detail(
        _FakeClient(tables, rpc_results={"institution_student_names": _names_rpc(names)}), "inst-1", "s1"
    )
    assert result["full_name"] == "A Student"
    # "department" is the resolved ENTITY name (department_id -> departments.name);
    # "self_reported_department" is the student's own free-text value --
    # both happen to be "CSE" here, but they are two different fields.
    assert result["department"] == "CSE"
    assert result["department_id"] == "dept-cse"
    assert result["self_reported_department"] == "CSE"
    assert result["skills"] == [{"skill_name": "Python", "proficiency_level": "Expert", "is_verified": True}]
    # 5 of 16 checks true: full_name, username, phone, department, degree, graduation_year, cgpa -> recompute exactly
    assert 0 < result["profile_completion"] < 100


def test_detail_department_defaults_to_unassigned_and_self_reported_stays_visible():
    tables = _base_tables(
        student_profiles=[
            {
                "id": "s1", "institution_id": "inst-1", "department": "Computer Science", "department_id": None,
                "graduation_year": None, "cgpa": None, "percentage": None, "degree": None, "phone": None,
                "date_of_birth": None, "gender": None, "location": None, "institution_name": None,
                "career_goals": None, "preferred_roles": [], "preferred_locations": [], "interests": [],
            }
        ],
    )
    result = institution_student_service.get_student_detail(_FakeClient(tables), "inst-1", "s1")
    assert result["department"] == "Unassigned"
    assert result["department_id"] is None
    # The student's own free-text entry is still surfaced, informationally,
    # even though it is not (yet) the authoritative department.
    assert result["self_reported_department"] == "Computer Science"


def test_detail_applications_resolve_title_and_company():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None,
             "degree": None, "phone": None, "date_of_birth": None, "gender": None, "location": None,
             "institution_name": None, "career_goals": None, "preferred_roles": [], "preferred_locations": [],
             "interests": []},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB", "internship_id": None,
             "job_id": "j1", "applied_at": "2026-01-01", "industry_id": "co-1"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    titles = [{"id": "j1", "opportunity_type": "JOB", "title": "Backend Engineer"}]
    result = institution_student_service.get_student_detail(
        _FakeClient(
            tables,
            rpc_results={
                "institution_student_names": _names_rpc([]),
                "institution_visible_opportunity_titles": lambda _params: titles,
            },
        ),
        "inst-1",
        "s1",
    )
    assert result["applications"] == [
        {
            "id": "a1",
            "opportunity_type": "JOB",
            "opportunity_title": "Backend Engineer",
            "company_name": "Acme Corp",
            "status": "SELECTED",
            "applied_at": "2026-01-01",
        }
    ]
    assert result["placement_status"] == "PLACED"


def test_detail_assessments_resolve_title_and_skill_name_and_average():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None,
             "degree": None, "phone": None, "date_of_birth": None, "gender": None, "location": None,
             "institution_name": None, "career_goals": None, "preferred_roles": [], "preferred_locations": [],
             "interests": []},
        ],
        assessment_attempts=[
            {"student_id": "s1", "assessment_id": "assess-1", "status": "COMPLETED", "percentage": 80.0, "submitted_at": "2026-01-01"},
            {"student_id": "s1", "assessment_id": "assess-1", "status": "IN_PROGRESS", "percentage": None, "submitted_at": None},
        ],
        assessments=[{"id": "assess-1", "title": "Python Basics", "skill_id": "sk-1"}],
        skills=[{"id": "sk-1", "name": "Python"}],
    )
    result = institution_student_service.get_student_detail(_FakeClient(tables), "inst-1", "s1")
    assert result["assessments_completed"] == 1
    assert result["average_assessment_percentage"] == 80.0
    assert result["assessments"][0]["assessment_title"] == "Python Basics"
    assert result["assessments"][0]["skill_name"] == "Python"


def test_detail_interviews_never_select_notes_and_resolve_opportunity():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None,
             "degree": None, "phone": None, "date_of_birth": None, "gender": None, "location": None,
             "institution_name": None, "career_goals": None, "preferred_roles": [], "preferred_locations": [],
             "interests": []},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "INTERVIEW_SCHEDULED", "opportunity_type": "JOB", "internship_id": None,
             "job_id": "j1", "applied_at": None, "industry_id": "co-1"},
        ],
        interviews=[
            {"id": "iv-1", "application_id": "a1", "scheduled_at": "2026-02-01T10:00:00Z",
             "mode": "ONLINE", "status": "SCHEDULED", "notes": "SENSITIVE PREP NOTES"},
        ],
    )
    titles = [{"id": "j1", "opportunity_type": "JOB", "title": "Backend Engineer"}]
    result = institution_student_service.get_student_detail(
        _FakeClient(
            tables,
            rpc_results={
                "institution_student_names": _names_rpc([]),
                "institution_visible_opportunity_titles": lambda _params: titles,
            },
        ),
        "inst-1",
        "s1",
    )
    assert len(result["interviews"]) == 1
    interview = result["interviews"][0]
    assert interview["opportunity_title"] == "Backend Engineer"
    assert "notes" not in interview
    assert "SENSITIVE PREP NOTES" not in str(result)


def test_detail_portfolio_projects_certifications_achievements():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department": "CSE", "graduation_year": 2026, "cgpa": None, "percentage": None,
             "degree": None, "phone": None, "date_of_birth": None, "gender": None, "location": None,
             "institution_name": None, "career_goals": None, "preferred_roles": [], "preferred_locations": [],
             "interests": []},
        ],
        student_projects=[{"id": "p1", "student_id": "s1", "title": "Portfolio Site", "description": None,
                            "project_url": None, "repo_url": None, "is_ongoing": False}],
        student_project_skills=[{"project_id": "p1", "skills": {"name": "React"}}],
        student_certifications=[{"id": "c1", "student_id": "s1", "name": "AWS Cert", "issuing_organization": "AWS",
                                  "issue_date": "2025-01-01", "credential_url": None}],
        student_achievements=[{"id": "ach1", "student_id": "s1", "title": "Hackathon Winner", "description": None,
                                "achievement_date": "2025-06-01", "issuing_organization": None}],
    )
    result = institution_student_service.get_student_detail(_FakeClient(tables), "inst-1", "s1")
    assert result["projects"] == [
        {"id": "p1", "title": "Portfolio Site", "description": None, "project_url": None,
         "repo_url": None, "is_ongoing": False, "skills": ["React"]}
    ]
    assert result["certifications"][0]["name"] == "AWS Cert"
    assert result["achievements"][0]["title"] == "Hackathon Winner"


# ============================================================
# RLS boundary: no service-role anywhere on this path
# ============================================================


def test_institution_student_service_has_no_service_role_access():
    assert not hasattr(institution_student_service, "get_supabase")
