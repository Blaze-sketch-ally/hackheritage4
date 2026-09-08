"""Tests for Institution Analytics: GET /api/v1/institution/analytics
(backend/app/services/institution_analytics_service.py).

Route tests mock the service and use tests.conftest.authenticated_as,
matching the rest of the institution test suite. Service tests drive
compute_institution_analytics against a fake Supabase client (table
reads + rpc calls, same shape as test_institution_placements.py's own
fake client, since this service calls into institution_placement_service
and institution_department_service directly) -- verifying tenancy
isolation, the placed/unplaced/placement-rate definition stays identical
to the Dashboard's, department/batch filter scoping, the
selected-offers-vs-unique-placed-students distinction, skill coverage
percentages, skill-gap thresholds and the "unavailable" fallback, and
that nothing here fabricates a metric the schema cannot support (no
pass_rate, no eligible_students).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_analytics_service
from tests.conftest import authenticated_as

client = TestClient(app)

URL = "/api/v1/institution/analytics"


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


def test_scopes_to_authenticated_institution_and_forwards_filters():
    captured = {}

    def fake_compute(_client, institution_id, **kwargs):
        captured["institution_id"] = institution_id
        captured.update(kwargs)
        return _empty_payload()

    with (
        authenticated_as("INSTITUTION", user_id="institution-55"),
        patch.object(institution_analytics_service, "compute_institution_analytics", side_effect=fake_compute),
    ):
        resp = client.get(
            f"{URL}?department_id=dept-1&batch=2026&date_from=2026-01-01&date_to=2026-06-30",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-55"
    assert captured["department_id"] == "dept-1"
    assert captured["batch"] == 2026
    assert captured["date_from"] == "2026-01-01"
    assert captured["date_to"] == "2026-06-30"


def _empty_payload():
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "institution_name": None,
        "filters_applied": {"department_id": None, "batch": None, "date_from": None, "date_to": None},
        "filter_options": {"departments": [], "batches": []},
        "overview": {
            "total_students": 0,
            "placed_students": 0,
            "unplaced_students": 0,
            "placement_rate": None,
            "students_with_applications": 0,
            "students_without_applications": 0,
            "internship_participants": 0,
            "active_placement_drives": 0,
            "completed_placement_drives": 0,
        },
        "departments": [],
        "placements": {
            "total_drives": 0,
            "active_drives": 0,
            "completed_drives": 0,
            "cancelled_drives": 0,
            "draft_drives": 0,
            "participating_students": 0,
            "placed_students": 0,
            "total_selected_offers": 0,
            "placement_rate": None,
            "average_applicants_per_drive": None,
            "department_breakdown": [],
            "drives": [],
        },
        "companies": [],
        "applications": {
            "total_applications": 0,
            "students_with_applications": 0,
            "students_without_applications": 0,
            "applications_per_applying_student": None,
            "status_distribution": [],
        },
        "skills": {"total_students_considered": 0, "top_skills": []},
        "skill_gaps": {"available": False, "note": "note", "items": []},
        "internships": {
            "available": True,
            "note": "note",
            "participants": 0,
            "applications_total": 0,
            "participation_rate": None,
            "status_distribution": [],
        },
        "assessments": {"students_assessed": 0, "total_attempts": 0, "average_score": None},
        "interviews": {
            "total": 0,
            "students_interviewed": 0,
            "scheduled": 0,
            "completed": 0,
            "cancelled": 0,
            "upcoming": 0,
        },
        "trends": {"has_sufficient_data": False, "months": [], "historical_note": "note"},
        "tenancy_note": "note",
        "eligibility_note": "note",
        "filter_scope_note": "note",
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

    def ilike(self, field, value):
        self._rows = [r for r in self._rows if str(r.get(field, "")).lower() == str(value).lower()]
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
        "job_skills": [],
        "skills": [],
        "student_skills": [],
        "assessment_attempts": [],
        "interviews": [],
        "industry_profiles": [],
        "institution_profiles": [],
    }
    tables.update(overrides)
    return tables


def _rpc(job_rows=None, name_rows=None):
    def job_details(params):
        wanted = set(params.get("job_ids", []))
        return [r for r in (job_rows or []) if r["id"] in wanted]

    def student_names(params):
        wanted = set(params.get("student_ids", []))
        return [r for r in (name_rows or []) if r["student_id"] in wanted]

    return {
        "institution_visible_job_details": job_details,
        "institution_student_names": student_names,
    }


def _compute(tables, institution_id="inst-1", rpc_results=None, **filters):
    return institution_analytics_service.compute_institution_analytics(
        _FakeClient(tables, rpc_results=rpc_results or _rpc()), institution_id, **filters
    )


# ---- empty state ----


def test_empty_institution_is_all_zeros_not_error():
    result = _compute(_base_tables())
    assert result["overview"] == {
        "total_students": 0,
        "placed_students": 0,
        "unplaced_students": 0,
        "placement_rate": None,
        "students_with_applications": 0,
        "students_without_applications": 0,
        "internship_participants": 0,
        "active_placement_drives": 0,
        "completed_placement_drives": 0,
    }
    assert result["departments"] == []
    assert result["companies"] == []
    assert result["skill_gaps"]["available"] is False
    assert result["trends"]["has_sufficient_data"] is False


# ---- overview / placement definition consistency ----


def test_overview_reuses_placed_definition_and_percentage():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 7.0},
            {"id": "s3", "institution_id": "inst-1", "department_id": None, "graduation_year": 2027, "cgpa": 9.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
            {"id": "a2", "student_id": "s2", "status": "APPLIED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
    )
    result = _compute(tables)
    ov = result["overview"]
    assert ov["total_students"] == 3
    assert ov["placed_students"] == 1
    assert ov["unplaced_students"] == 1
    assert ov["students_without_applications"] == 1
    assert ov["placement_rate"] == round(1 / 3 * 100, 1)


def test_cross_institution_students_never_counted():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-B", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
    )
    result = _compute(tables, institution_id="inst-A")
    assert result["overview"]["total_students"] == 1


# ---- department / batch filters ----


def test_department_filter_narrows_overview_but_not_department_table():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-1", "department_id": "d2", "graduation_year": 2026, "cgpa": 8.0},
        ],
        departments=[
            {"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
            {"id": "d2", "institution_id": "inst-1", "name": "ECE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
    )
    result = _compute(tables, department_id="d1")
    assert result["overview"]["total_students"] == 1
    # The departments breakdown itself is never filtered -- both still appear.
    assert {d["name"] for d in result["departments"]} == {"CSE", "ECE"}


def test_unassigned_department_filter_value():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-1", "department_id": "d1", "graduation_year": 2026, "cgpa": 8.0},
        ],
    )
    result = _compute(tables, department_id="unassigned")
    assert result["overview"]["total_students"] == 1


def test_batch_filter():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-1", "department_id": None, "graduation_year": 2027, "cgpa": 8.0},
        ],
    )
    result = _compute(tables, batch=2026)
    assert result["overview"]["total_students"] == 1
    assert result["filter_options"]["batches"] == [2026, 2027]


# ---- applications / status distribution ----


def test_application_status_distribution_uses_real_statuses():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SHORTLISTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
            {"id": "a2", "student_id": "s1", "status": "REJECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j2", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
    )
    result = _compute(tables)
    dist = {row["status"]: row["count"] for row in result["applications"]["status_distribution"]}
    assert dist["SHORTLISTED"] == 1
    assert dist["REJECTED"] == 1
    assert dist["APPLIED"] == 0
    assert result["applications"]["applications_per_applying_student"] == 2.0


def test_date_range_filters_applications_section_only():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "APPLIED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": "2026-01-15T00:00:00Z"},
            {"id": "a2", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j2", "industry_id": "co-1", "applied_at": "2026-05-15T00:00:00Z"},
        ],
    )
    result = _compute(tables, date_from="2026-05-01", date_to="2026-05-31")
    assert result["applications"]["total_applications"] == 1
    # Overview's placement bucket classification is NOT date-filtered --
    # both applications still count toward "placed" (application a2 is SELECTED).
    assert result["overview"]["placed_students"] == 1


# ---- companies: selected offers vs unique placed students ----


def test_company_breakdown_distinguishes_offers_from_unique_students():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
            {"id": "a2", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j2", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute(tables)
    acme = result["companies"][0]
    assert acme["company_name"] == "Acme Corp"
    assert acme["selected_offers"] == 2
    assert acme["unique_students_placed"] == 1


# ---- drives: selection rate N/A on zero applicants ----


def test_drive_selection_rate_is_none_when_no_applicants():
    tables = _base_tables(
        placement_drives=[
            {"id": "drive-1", "institution_id": "inst-1", "job_id": "job-1", "title": "Drive", "status": "OPEN",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        jobs=[{"id": "job-1", "status": "PUBLISHED"}],
    )
    result = _compute(
        tables,
        rpc_results=_rpc(job_rows=[{"id": "job-1", "title": "SWE", "industry_id": "co-1", "status": "PUBLISHED"}]),
    )
    drive = result["placements"]["drives"][0]
    assert drive["applied_count"] == 0
    assert drive["selection_rate"] is None


# ---- skills / skill gaps ----


def test_skill_coverage_percentage_and_dedup():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        student_skills=[
            {"student_id": "s1", "skill_id": "sk1", "skills": {"name": "Python"}},
            {"student_id": "s2", "skill_id": "sk1", "skills": {"name": "Python"}},
        ],
    )
    result = _compute(tables)
    top = result["skills"]["top_skills"]
    assert top[0] == {"skill_name": "Python", "student_count": 2, "coverage_percentage": 100.0}


def test_skill_gaps_unavailable_when_no_job_requires_any_skill():
    tables = _base_tables(jobs=[{"id": "job-1", "status": "PUBLISHED"}])
    result = _compute(tables)
    assert result["skill_gaps"]["available"] is False
    assert result["skill_gaps"]["items"] == []


def test_skill_gaps_flags_high_demand_low_coverage_from_documented_thresholds():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        jobs=[
            {"id": f"job-{i}", "status": "PUBLISHED"} for i in range(3)
        ],
        job_skills=[
            {"job_id": f"job-{i}", "skill_id": "sk1", "skills": {"name": "Kubernetes"}} for i in range(3)
        ],
        # No student on record has Kubernetes -- coverage is 0%.
    )
    result = _compute(tables)
    gaps = result["skill_gaps"]
    assert gaps["available"] is True
    item = gaps["items"][0]
    assert item["skill_name"] == "Kubernetes"
    assert item["job_demand_count"] == 3
    assert item["high_demand"] is True
    assert item["low_coverage"] is True
    assert item["student_coverage_percentage"] == 0.0


def test_no_eligible_students_metric_is_ever_fabricated():
    result = _compute(_base_tables())
    assert "eligibility_note" in result
    assert "eligible" not in result["overview"]
    for dept in result["departments"]:
        assert "eligible" not in dept


# ---- internships ----


def test_internship_participation():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "i1", "job_id": None, "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
    )
    result = _compute(tables)
    iv = result["internships"]
    assert iv["participants"] == 1
    assert iv["applications_total"] == 1
    assert iv["participation_rate"] == round(1 / 2 * 100, 1)


# ---- assessments: no fabricated pass_rate ----


def test_assessments_average_score_no_pass_rate_field():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        assessment_attempts=[
            {"student_id": "s1", "status": "COMPLETED", "percentage": 80.0},
            {"student_id": "s1", "status": "COMPLETED", "percentage": 60.0},
        ],
    )
    result = _compute(tables)
    assert result["assessments"] == {"students_assessed": 1, "total_attempts": 2, "average_score": 70.0}
    assert "pass_rate" not in result["assessments"]


# ---- interviews: excludes private notes, computes upcoming ----


def test_interviews_upcoming_and_status_breakdown():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        interviews=[
            {"id": "iv1", "student_id": "s1", "status": "SCHEDULED", "scheduled_at": "2099-01-01T00:00:00+00:00"},
            {"id": "iv2", "student_id": "s1", "status": "COMPLETED", "scheduled_at": "2020-01-01T00:00:00+00:00"},
        ],
    )
    result = _compute(tables)
    iv = result["interviews"]
    assert iv["total"] == 2
    assert iv["students_interviewed"] == 1
    assert iv["scheduled"] == 1
    assert iv["completed"] == 1
    assert iv["upcoming"] == 1


# ---- trends ----


def test_trends_insufficient_data():
    result = _compute(_base_tables())
    assert result["trends"]["has_sufficient_data"] is False
    assert result["trends"]["months"] == []


def test_trends_reports_real_months_when_data_exists():
    from datetime import UTC, datetime

    this_month = datetime.now(UTC).strftime("%Y-%m")
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "j1", "industry_id": "co-1", "applied_at": f"{this_month}-15T00:00:00Z"},
        ],
    )
    result = _compute(tables)
    assert result["trends"]["has_sufficient_data"] is True
    assert len(result["trends"]["months"]) == 6
    assert sum(m["applications"] for m in result["trends"]["months"]) == 1
