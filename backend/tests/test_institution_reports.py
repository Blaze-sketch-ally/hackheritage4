"""Tests for the Institution Reports module (Phase 11):
GET /api/v1/institution/reports.

This is NOT a second Analytics module -- institution_reports_service
calls the EXISTING, already-tested service for each domain
(institution_analytics_service, institution_internship_service,
institution_student_service, institution_department_service,
institution_industry_service, institution_industry_connection_service,
institution_event_service, industry_collaboration_service) and reshapes
the result. These tests verify the RESHAPING (correct field mapping, no
fabricated data, no re-derived definitions) and cross-institution
isolation -- not the underlying calculations themselves, which already
have their own dedicated test files.

Route tests mock institution_reports_service and use
tests.conftest.authenticated_as, matching the rest of the institution
test suite. Service tests drive institution_reports_service against a
fake Supabase client (same fake-client shape as
test_institution_industry_partners.py, since the COMPANY report reaches
into institution_placement_service.list_drives internally).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_reports_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/reports"


# ============================================================
# Auth / role guards
# ============================================================


def test_endpoint_rejects_unauthenticated():
    assert client.get(f"{BASE}?report_type=PLACEMENT").status_code == 401


def test_endpoint_forbids_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(f"{BASE}?report_type=PLACEMENT", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


def test_endpoint_requires_report_type():
    with authenticated_as("INSTITUTION"):
        resp = client.get(BASE, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


def test_endpoint_rejects_unknown_report_type():
    with authenticated_as("INSTITUTION"):
        resp = client.get(f"{BASE}?report_type=NOT_A_REPORT", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


# ============================================================
# Route wiring
# ============================================================


def test_route_scopes_to_authenticated_institution_and_forwards_filters():
    captured = {}

    def fake_generate(_client, institution_id, **kwargs):
        captured["institution_id"] = institution_id
        captured.update(kwargs)
        return {
            "report_type": "PLACEMENT",
            "institution_name": None,
            "generated_at": "2026-01-01T00:00:00Z",
            "filters_applied": {},
            "placement": _empty_placement(),
        }

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_reports_service, "generate_report", side_effect=fake_generate),
    ):
        resp = client.get(
            f"{BASE}?report_type=PLACEMENT&department_id=dept-1&batch=2026&date_from=2026-01-01&date_to=2026-06-30",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["report_type"] == "PLACEMENT"
    assert captured["department_id"] == "dept-1"
    assert captured["batch"] == 2026
    assert captured["date_from"] == "2026-01-01"
    assert captured["date_to"] == "2026-06-30"


def _empty_placement():
    return {
        "summary": {
            "total_students": 0,
            "students_with_applications": 0,
            "students_selected": 0,
            "placement_rate": None,
            "companies_involved": 0,
            "active_placement_drives": 0,
        },
        "department_breakdown": [],
        "company_breakdown": [],
        "status_breakdown": [],
        "note": "note",
    }


# ============================================================
# Service-level tests -- fake Supabase client
# ============================================================


class _FakeQuery:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._rows = list(store.get(name, []))
        self._single = False
        self._count_requested = False

    def select(self, *_a, **kwargs):
        self._count_requested = kwargs.get("count") == "exact"
        return self

    def eq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) == value]
        return self

    def neq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) != value]
        return self

    def in_(self, field, values):
        values = set(values)
        self._rows = [r for r in self._rows if r.get(field) in values]
        return self

    def order(self, field, desc=False):
        self._rows = sorted(self._rows, key=lambda r: r.get(field) or "", reverse=desc)
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        data = self._rows[0] if self._single and self._rows else (None if self._single else self._rows)
        count = len(self._rows) if self._count_requested else None
        return MagicMock(data=data, count=count)


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
        "departments": [],
        "applications": [],
        "placement_drives": [],
        "jobs": [],
        "internships": [],
        "industry_profiles": [],
        "industry_collaborations": [],
        "institution_industry_partners": [],
        "institution_industry_connections": [],
        "institution_events": [],
        "industry_workshops": [],
        "institution_profiles": [],
        "institution_internships": [],
        "skills": [],
    }
    tables.update(overrides)
    return tables


def _rpc(**overrides):
    def empty(_params):
        return []

    base = {
        "institution_visible_job_details": empty,
        "institution_visible_internship_details": empty,
        "institution_curated_internship_details": empty,
        "institution_visible_opportunity_titles": empty,
        "institution_student_names": empty,
        "collaboration_counterparty_names": empty,
    }
    base.update(overrides)
    return base


def _generate(tables, institution_id="inst-1", rpc_results=None, **kwargs):
    return institution_reports_service.generate_report(
        _FakeClient(tables, rpc_results=rpc_results or _rpc()), institution_id, **kwargs
    )


# ---- empty dataset handling ----


def test_all_report_types_handle_empty_institution_without_error():
    for report_type in ("PLACEMENT", "INTERNSHIP", "STUDENT", "DEPARTMENT", "INDUSTRY", "EVENTS", "COLLABORATION"):
        result = _generate(_base_tables(), report_type=report_type)
        assert result["report_type"] == report_type
        assert result["generated_at"]


# ---- PLACEMENT ----


def test_placement_report_reuses_analytics_and_placement_definition():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "cgpa": 8.0, "graduation_year": 2026},
        ],
        departments=[{"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None,
                      "description": None, "is_active": True, "created_at": None, "updated_at": None}],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _generate(tables, report_type="PLACEMENT")
    placement = result["placement"]
    assert placement["summary"]["total_students"] == 1
    assert placement["summary"]["students_selected"] == 1
    assert placement["summary"]["placement_rate"] == 100.0
    assert placement["company_breakdown"][0]["company_name"] == "Acme Corp"
    assert placement["company_breakdown"][0]["selection_rate"] == 100.0
    status_labels = {row["label"] for row in placement["status_breakdown"]}
    assert "SELECTED" in status_labels


def test_placement_report_respects_department_filter():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "cgpa": 8.0, "graduation_year": 2026},
            {"id": "s2", "institution_id": "inst-1", "department_id": "d2", "cgpa": 8.0, "graduation_year": 2026},
        ],
        departments=[
            {"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
            {"id": "d2", "institution_id": "inst-1", "name": "ECE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, report_type="PLACEMENT", department_id="d1")
    assert result["placement"]["summary"]["total_students"] == 1


# ---- cross-institution isolation ----


def test_placement_report_isolated_between_institutions():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-B", "department_id": None, "cgpa": 8.0, "graduation_year": 2026}],
    )
    result = _generate(tables, institution_id="inst-A", report_type="PLACEMENT")
    assert result["placement"]["summary"]["total_students"] == 0


def test_student_report_isolated_between_institutions():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-B", "department_id": None, "cgpa": 8.0, "graduation_year": 2026}],
    )
    result = _generate(tables, institution_id="inst-A", report_type="STUDENT", rpc_results=_rpc())
    assert result["student"]["students"] == []
    assert result["student"]["total"] == 0


def test_department_report_isolated_between_institutions():
    tables = _base_tables(departments=[{"id": "d1", "institution_id": "inst-B", "name": "CSE", "code": None,
                                        "description": None, "is_active": True, "created_at": None, "updated_at": None}])
    result = _generate(tables, institution_id="inst-A", report_type="DEPARTMENT")
    assert result["department"]["departments"] == []


def test_company_report_isolated_between_institutions():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-B", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "ACTIVE", "notes": None, "created_at": None, "updated_at": None},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _generate(tables, institution_id="inst-A", report_type="INDUSTRY")
    assert result["industry"]["companies"] == []


def test_events_report_isolated_between_institutions():
    tables = _base_tables(
        institution_events=[
            {"id": "e1", "institution_id": "inst-B", "industry_id": None, "title": "Private Event",
             "description": None, "event_type": "SEMINAR", "status": "PUBLISHED", "mode": None, "venue": None,
             "start_at": None, "end_at": None, "registration_deadline": None, "target_department_ids": [],
             "target_batches": [], "includes_faculty": False, "instructions": None,
             "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, institution_id="inst-A", report_type="EVENTS")
    assert result["events"]["events"] == []


def test_collaboration_report_isolated_between_institutions():
    tables = _base_tables(
        industry_collaborations=[
            {"id": "c1", "industry_id": "co-1", "recipient_id": "inst-B", "recipient_type": "INSTITUTION",
             "title": "X", "description": "d", "status": "SENT", "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, institution_id="inst-A", report_type="COLLABORATION")
    assert result["collaboration"]["collaborations"] == []


# ---- INTERNSHIP ----


def test_internship_report_reuses_internship_overview():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0, "graduation_year": 2026}],
        internships=[
            {"id": "i1", "industry_id": "co-1", "title": "A", "work_mode": "REMOTE", "duration_months": 3,
             "stipend_amount": None, "stipend_currency": "INR", "eligibility_criteria": None,
             "application_deadline": None, "start_date": None, "status": "PUBLISHED", "location": None, "description": None},
        ],
        institution_internships=[
            {"id": "assoc-1", "institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE",
             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "i1", "job_id": None, "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _generate(tables, report_type="INTERNSHIP")
    internship = result["internship"]
    assert internship["kpis"]["selected_students"] == 1
    assert internship["kpis"]["curated_internships"] == 1
    assert internship["note"]


def test_internship_report_reflects_only_curated_internships():
    """An internship this institution's student applied to but the
    institution never explicitly curated must not appear in the report."""
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0, "graduation_year": 2026}],
        internships=[
            {"id": "i1", "industry_id": "co-1", "title": "A", "work_mode": "REMOTE", "duration_months": 3,
             "stipend_amount": None, "stipend_currency": "INR", "eligibility_criteria": None,
             "application_deadline": None, "start_date": None, "status": "PUBLISHED", "location": None, "description": None},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "i1", "job_id": None, "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _generate(tables, report_type="INTERNSHIP")
    internship = result["internship"]
    assert internship["kpis"]["curated_internships"] == 0
    assert internship["kpis"]["selected_students"] == 0


def test_internship_report_stipend_never_averaged_across_currencies():
    tables = _base_tables(
        internships=[
            {"id": "i1", "industry_id": "co-1", "title": "A", "work_mode": "REMOTE", "duration_months": 3,
             "stipend_amount": 10000, "stipend_currency": "INR", "eligibility_criteria": None,
             "application_deadline": None, "start_date": None, "status": "PUBLISHED", "location": None, "description": None},
            {"id": "i2", "industry_id": "co-1", "title": "B", "work_mode": "REMOTE", "duration_months": 3,
             "stipend_amount": 500, "stipend_currency": "USD", "eligibility_criteria": None,
             "application_deadline": None, "start_date": None, "status": "PUBLISHED", "location": None, "description": None},
        ],
        institution_internships=[
            {"id": "assoc-1", "institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE",
             "created_at": None, "updated_at": None},
            {"id": "assoc-2", "institution_id": "inst-1", "internship_id": "i2", "status": "ACTIVE",
             "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, report_type="INTERNSHIP")
    currencies = {row["currency"] for row in result["internship"]["stipend_by_currency"]}
    assert currencies == {"INR", "USD"}


# ---- STUDENT ----


def test_student_report_never_exposes_email_or_phone():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.5, "graduation_year": 2026,
             "percentage": None, "degree": None, "phone": "9999999999", "date_of_birth": None, "gender": None,
             "location": None, "institution_name": None, "career_goals": None, "preferred_roles": [],
             "preferred_locations": [], "interests": [], "department": None},
        ],
    )
    result = _generate(tables, report_type="STUDENT", rpc_results=_rpc())
    student_json = result["student"]["students"]
    assert len(student_json) == 1
    row = student_json[0]
    assert "email" not in row
    assert "phone" not in row
    assert set(row.keys()) == {
        "full_name", "username", "department", "batch", "cgpa", "placement_status", "internship_status", "top_skills",
    }


def test_student_report_department_filter_uses_real_department_id():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "cgpa": 8.0, "graduation_year": 2026,
             "percentage": None, "degree": None, "phone": None, "date_of_birth": None, "gender": None,
             "location": None, "institution_name": None, "career_goals": None, "preferred_roles": [],
             "preferred_locations": [], "interests": [], "department": None},
            {"id": "s2", "institution_id": "inst-1", "department_id": "d2", "cgpa": 8.0, "graduation_year": 2026,
             "percentage": None, "degree": None, "phone": None, "date_of_birth": None, "gender": None,
             "location": None, "institution_name": None, "career_goals": None, "preferred_roles": [],
             "preferred_locations": [], "interests": [], "department": None},
        ],
        departments=[
            {"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
            {"id": "d2", "institution_id": "inst-1", "name": "ECE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, report_type="STUDENT", department_id="d1", rpc_results=_rpc())
    assert result["student"]["total"] == 1
    assert result["student"]["students"][0]["department"] == "CSE"


# ---- DEPARTMENT ----


def test_department_report_average_cgpa_none_when_no_students_have_cgpa():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "cgpa": None, "graduation_year": 2026},
        ],
        departments=[{"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None, "description": None,
                      "is_active": True, "created_at": None, "updated_at": None}],
    )
    result = _generate(tables, report_type="DEPARTMENT")
    dept = result["department"]["departments"][0]
    assert dept["average_cgpa"] is None
    assert dept["student_count"] == 1


def test_department_report_average_cgpa_computed_from_real_students():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "cgpa": 8.0, "graduation_year": 2026},
            {"id": "s2", "institution_id": "inst-1", "department_id": "d1", "cgpa": 9.0, "graduation_year": 2026},
        ],
        departments=[{"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None, "description": None,
                      "is_active": True, "created_at": None, "updated_at": None}],
    )
    result = _generate(tables, report_type="DEPARTMENT")
    dept = result["department"]["departments"][0]
    assert dept["average_cgpa"] == 8.5


# ---- INDUSTRY / COMPANY ----


def test_company_report_groups_connections_events_collaborations_without_n_plus_1():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "RECRUITMENT",
             "relationship_status": "ACTIVE", "notes": None, "created_at": None, "updated_at": None},
        ],
        institution_industry_connections=[
            {"id": "conn-1", "institution_id": "inst-1", "industry_id": "co-1", "contact_name": "Priya",
             "designation": None, "contact_type": "RECRUITMENT", "email": None, "phone": None, "notes": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        institution_events=[
            {"id": "e1", "institution_id": "inst-1", "industry_id": "co-1", "title": "Industry Talk",
             "description": None, "event_type": "INDUSTRY_TALK", "status": "PUBLISHED", "mode": None, "venue": None,
             "start_at": None, "end_at": None, "registration_deadline": None, "target_department_ids": [],
             "target_batches": [], "includes_faculty": False, "instructions": None,
             "created_at": None, "updated_at": None},
        ],
        industry_collaborations=[
            {"id": "c1", "industry_id": "co-1", "recipient_id": "inst-1", "recipient_type": "INSTITUTION",
             "title": "Research tie-up", "description": "d", "status": "ACTIVE", "created_at": None, "updated_at": None},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _generate(tables, report_type="INDUSTRY")
    row = result["industry"]["companies"][0]
    assert row["company_name"] == "Acme Corp"
    assert row["connections_count"] == 1
    assert row["events_count"] == 1
    assert row["collaborations_count"] == 1
    assert row["relationship_status"] == "ACTIVE"


def test_company_report_filters_by_company_id():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "PROSPECT", "notes": None, "created_at": None, "updated_at": None},
            {"id": "rel-2", "institution_id": "inst-1", "industry_id": "co-2", "relationship_type": "OTHER",
             "relationship_status": "PROSPECT", "notes": None, "created_at": None, "updated_at": None},
        ],
        industry_profiles=[
            {"id": "co-1", "company_name": "Acme Corp"},
            {"id": "co-2", "company_name": "Globex Inc"},
        ],
    )
    result = _generate(tables, report_type="INDUSTRY", company_id="co-1")
    assert [c["company_name"] for c in result["industry"]["companies"]] == ["Acme Corp"]


# ---- EVENTS ----


def test_events_report_never_shows_registration_or_attendance_counts():
    tables = _base_tables(
        institution_events=[
            {"id": "e1", "institution_id": "inst-1", "industry_id": None, "title": "Career Session",
             "description": None, "event_type": "CAREER_SESSION", "status": "PUBLISHED", "mode": "ONSITE", "venue": None,
             "start_at": None, "end_at": None, "registration_deadline": None, "target_department_ids": [],
             "target_batches": [], "includes_faculty": False, "instructions": None,
             "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, report_type="EVENTS")
    events = result["events"]
    assert events["total_events"] == 1
    assert "registration_note" in events
    assert events["registration_note"] == "Registration and attendance tracking are not available in the current system."
    for e in events["events"]:
        assert "registered_count" not in e
        assert "attendance" not in e


# ---- COLLABORATION ----


def test_collaboration_report_reuses_existing_lifecycle_and_status_breakdown():
    tables = _base_tables(
        industry_collaborations=[
            {"id": "c1", "industry_id": "co-1", "recipient_id": "inst-1", "recipient_type": "INSTITUTION",
             "title": "AI Research", "description": "d", "status": "SENT", "created_at": None, "updated_at": None},
            {"id": "c2", "industry_id": "co-1", "recipient_id": "inst-1", "recipient_type": "INSTITUTION",
             "title": "Workshop Series", "description": "d", "status": "ACTIVE", "created_at": None, "updated_at": None},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _generate(tables, report_type="COLLABORATION")
    collab = result["collaboration"]
    assert len(collab["collaborations"]) == 2
    labels = {row["label"]: row["count"] for row in collab["status_breakdown"]}
    assert labels == {"SENT": 1, "ACTIVE": 1}


def test_collaboration_report_filters_by_status():
    tables = _base_tables(
        industry_collaborations=[
            {"id": "c1", "industry_id": "co-1", "recipient_id": "inst-1", "recipient_type": "INSTITUTION",
             "title": "AI Research", "description": "d", "status": "SENT", "created_at": None, "updated_at": None},
            {"id": "c2", "industry_id": "co-1", "recipient_id": "inst-1", "recipient_type": "INSTITUTION",
             "title": "Workshop Series", "description": "d", "status": "ACTIVE", "created_at": None, "updated_at": None},
        ],
    )
    result = _generate(tables, report_type="COLLABORATION", collaboration_status="ACTIVE")
    assert [c["title"] for c in result["collaboration"]["collaborations"]] == ["Workshop Series"]
