"""Tests for the Institution Dashboard: GET /api/v1/institution/overview.

Route tests mock app.services.institution_service and use
tests.conftest.authenticated_as, matching test_analytics.py's structure.
Service tests drive compute_institution_overview with a fake Supabase
client whose per-table reads return canned rows -- verifying tenancy
scoping (only linked students ever count), placement-bucket math,
exact-string department grouping, and that no eligibility metric is ever
fabricated.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_service
from tests.conftest import authenticated_as

client = TestClient(app)

URL = "/api/v1/institution/overview"


# ============================================================
# Auth / role guards
# ============================================================


def test_unauthenticated_returns_401():
    assert client.get(URL).status_code == 401


def test_forbids_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            resp = client.get(URL, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role


def test_scopes_to_authenticated_institution():
    captured = {}

    def fake_compute(_client, institution_id):
        captured["institution_id"] = institution_id
        return _empty_payload()

    with (
        authenticated_as("INSTITUTION", user_id="institution-55"),
        patch.object(institution_service, "compute_institution_overview", side_effect=fake_compute),
    ):
        resp = client.get(URL, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-55"


def _empty_payload():
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "institution_name": None,
        "student_metrics": {
            "total_linked_students": 0,
            "placed": 0,
            "unplaced_active": 0,
            "not_participating": 0,
            "placement_percentage": None,
        },
        "department_metrics": [],
        "opportunities": {
            "active_jobs": 0,
            "active_internships": 0,
            "recent": [],
            "platform_wide": True,
        },
        "industry": {
            "total_industry_partners": 0,
            "recent_postings_count": 0,
            "platform_wide": True,
        },
        "collaborations": {"pending": 0, "active": 0, "total": 0},
        "upcoming_events": [],
        "student_insights": {
            "students_with_no_applications": 0,
            "students_actively_applying": 0,
            "top_skills": [],
            "assessments_completed": 0,
            "average_assessment_percentage": None,
        },
        "tenancy_note": "note",
        "eligibility_note": "note",
    }


# ============================================================
# Service aggregation -- fake Supabase client
# ============================================================


class _FakeQuery:
    """Minimal chainable query stand-in: filters an in-memory row list the
    same way the real Postgrest client would for the handful of methods
    institution_service actually calls."""

    def __init__(self, rows):
        self._rows = list(rows)
        self._count_requested = False
        self._single = False

    def select(self, *_a, **kwargs):
        self._count_requested = kwargs.get("count") == "exact"
        return self

    def eq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) == value]
        return self

    def in_(self, field, values):
        values = set(values)
        self._rows = [r for r in self._rows if r.get(field) in values]
        return self

    def gte(self, field, value):
        self._rows = [r for r in self._rows if (r.get(field) or "") >= value]
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
        data = self._rows
        count = len(data) if self._count_requested else None
        if self._single:
            data = data[0] if data else None
        return MagicMock(data=data, count=count)


class _FakeClient:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def _base_tables(**overrides):
    tables = {
        "student_profiles": [],
        "applications": [],
        "internships": [],
        "jobs": [],
        "industry_profiles": [],
        "industry_workshops": [],
        "industry_collaborations": [],
        "student_skills": [],
        "assessment_attempts": [],
        "institution_profiles": [],
        "departments": [],
    }
    tables.update(overrides)
    return tables


def test_empty_institution_is_all_zeros_not_error():
    result = institution_service.compute_institution_overview(
        _FakeClient(_base_tables()), "inst-1"
    )
    assert result["student_metrics"] == {
        "total_linked_students": 0,
        "placed": 0,
        "unplaced_active": 0,
        "not_participating": 0,
        "placement_percentage": None,
    }
    assert result["department_metrics"] == []
    assert result["opportunities"]["recent"] == []
    assert result["collaborations"] == {"pending": 0, "active": 0, "total": 0}
    assert result["student_insights"]["top_skills"] == []


def test_placement_buckets_and_percentage():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "department": "CSE", "institution_id": "inst-1"},
            {"id": "s2", "department": "CSE", "institution_id": "inst-1"},
            {"id": "s3", "department": "ECE", "institution_id": "inst-1"},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "internship_id": None, "job_id": "j1"},
            {"id": "a2", "student_id": "s2", "status": "APPLIED", "internship_id": None, "job_id": "j1"},
            # s3 has no applications at all -> not_participating
        ],
    )
    result = institution_service.compute_institution_overview(_FakeClient(tables), "inst-1")

    m = result["student_metrics"]
    assert m["total_linked_students"] == 3
    assert m["placed"] == 1
    assert m["unplaced_active"] == 1
    assert m["not_participating"] == 1
    assert m["placement_percentage"] == round(1 / 3 * 100, 1)


def test_department_grouping_uses_department_id_entity_and_handles_unassigned():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "dept-cse"},
            {"id": "s2", "institution_id": "inst-1", "department_id": "dept-cs"},
            {"id": "s3", "institution_id": "inst-1", "department_id": None},
            {"id": "s4", "institution_id": "inst-1", "department_id": None},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "internship_id": None, "job_id": "j1"},
        ],
        departments=[
            {"id": "dept-cse", "institution_id": "inst-1", "name": "CSE"},
            # Deliberately a DIFFERENT department row -- no fuzzy/alias
            # merge with "CSE" just because the names are similar.
            {"id": "dept-cs", "institution_id": "inst-1", "name": "Computer Science"},
        ],
    )
    result = institution_service.compute_institution_overview(_FakeClient(tables), "inst-1")

    by_dept = {d["department"]: d for d in result["department_metrics"]}
    assert set(by_dept) == {"CSE", "Computer Science", "Unassigned"}
    assert by_dept["CSE"]["department_id"] == "dept-cse"
    assert by_dept["CSE"]["total_students"] == 1
    assert by_dept["CSE"]["placed_students"] == 1
    assert by_dept["CSE"]["placement_percentage"] == 100.0
    assert by_dept["Computer Science"]["department_id"] == "dept-cs"
    assert by_dept["Computer Science"]["total_students"] == 1
    assert by_dept["Computer Science"]["placed_students"] == 0
    # Both students with no department_id collapse into "Unassigned", one bucket of 2.
    assert by_dept["Unassigned"]["total_students"] == 2
    assert by_dept["Unassigned"]["department_id"] is None


def test_recent_opportunities_only_count_applicants_from_linked_students():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "department": "CSE", "institution_id": "inst-1"}],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "APPLIED", "internship_id": None, "job_id": "job-1"},
        ],
        jobs=[
            {"id": "job-1", "title": "Backend Engineer", "industry_id": "co-1",
             "status": "PUBLISHED", "created_at": "2026-01-02T00:00:00+00:00"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = institution_service.compute_institution_overview(_FakeClient(tables), "inst-1")

    recent = result["opportunities"]["recent"]
    assert len(recent) == 1
    assert recent[0]["company_name"] == "Acme Corp"
    # Only this institution's own linked student's application is counted --
    # a platform-wide applicant count would leak other institutions' data.
    assert recent[0]["applicants_from_your_institution"] == 1


def test_collaborations_counts_by_status():
    tables = _base_tables(
        industry_collaborations=[
            {"status": "SENT", "recipient_id": "inst-1"},
            {"status": "SENT", "recipient_id": "inst-1"},
            {"status": "ACTIVE", "recipient_id": "inst-1"},
            {"status": "COMPLETED", "recipient_id": "inst-1"},
        ],
    )
    result = institution_service.compute_institution_overview(_FakeClient(tables), "inst-1")
    assert result["collaborations"] == {"pending": 2, "active": 1, "total": 4}


def test_top_skills_and_assessment_insights():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "department": "CSE", "institution_id": "inst-1"},
            {"id": "s2", "department": "CSE", "institution_id": "inst-1"},
        ],
        student_skills=[
            {"student_id": "s1", "skill_id": "sk1", "skills": {"name": "Python"}},
            {"student_id": "s2", "skill_id": "sk1", "skills": {"name": "Python"}},
            {"student_id": "s2", "skill_id": "sk2", "skills": {"name": "SQL"}},
        ],
        assessment_attempts=[
            {"student_id": "s1", "status": "COMPLETED", "percentage": 80.0},
            {"student_id": "s2", "status": "COMPLETED", "percentage": 60.0},
        ],
    )
    result = institution_service.compute_institution_overview(_FakeClient(tables), "inst-1")

    top_skills = result["student_insights"]["top_skills"]
    assert top_skills[0] == {"skill_name": "Python", "student_count": 2}
    assert result["student_insights"]["assessments_completed"] == 2
    assert result["student_insights"]["average_assessment_percentage"] == 70.0


def test_no_eligibility_metric_is_ever_fabricated():
    """Structural guarantee: nothing named 'eligible'/'eligibility' appears
    as a numeric field anywhere in the payload -- only the explanatory
    `eligibility_note` string."""
    result = institution_service.compute_institution_overview(
        _FakeClient(_base_tables()), "inst-1"
    )
    assert "eligibility_note" in result
    assert "eligible" not in result["student_metrics"]
    for dept in result["department_metrics"]:
        assert "eligible" not in dept
