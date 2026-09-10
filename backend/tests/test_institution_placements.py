"""Tests for Institution Placement Drive Management:
/api/v1/institution/placements..., database/migrations/
073_institution_placement_drives.sql.

Route tests mock app.services.institution_placement_service and use
tests.conftest.authenticated_as, matching the rest of the institution
test suite. Service tests drive institution_placement_service against a
fake Supabase client (table reads/writes + rpc calls) to verify tenancy
isolation, job-availability validation, department-ownership validation,
lifecycle-transition rules, the centralized eligibility engine (CGPA,
department, batch, skill), and that placement counts reuse the same
"SELECTED = placed" definition as the rest of the Institution module
without conflating unique students placed with total selected offers.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_placement_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/placements"
DRIVE_ID = "11111111-1111-1111-1111-111111111111"


def _drive_row(**overrides):
    row = {
        "id": DRIVE_ID,
        "job_id": "job-1",
        "job_title": "Software Engineer",
        "company_name": "Acme Corp",
        "location": "Remote",
        "work_mode": "REMOTE",
        "employment_type": "FULL_TIME",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "INR",
        "job_status": "PUBLISHED",
        "job_description": "Build things.",
        "title": "Campus Drive 2026",
        "description": None,
        "status": "DRAFT",
        "application_deadline": None,
        "drive_date": None,
        "mode": "ONSITE",
        "venue": None,
        "instructions": None,
        "eligible_department_ids": [],
        "eligible_department_names": [],
        "eligible_batches": [],
        "minimum_cgpa": None,
        "eligible_skill_ids": [],
        "eligible_skill_names": [],
        "eligible_count": 0,
        "applied_count": 0,
        "selected_count": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/available-jobs").status_code == 401
    assert client.get(f"{BASE}/overview").status_code == 401
    assert client.post(BASE, json={"job_id": "job-1", "title": "X"}).status_code == 401
    assert client.get(f"{BASE}/{DRIVE_ID}").status_code == 401
    assert client.put(f"{BASE}/{DRIVE_ID}", json={"title": "X"}).status_code == 401
    assert client.patch(f"{BASE}/{DRIVE_ID}/status", json={"status": "OPEN"}).status_code == 401
    assert client.get(f"{BASE}/{DRIVE_ID}/students").status_code == 401
    assert client.get(f"{BASE}/{DRIVE_ID}/applications").status_code == 401


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.post(
                    BASE, json={"job_id": "job-1", "title": "X"}, headers={"Authorization": "Bearer token"}
                ).status_code
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
        return []

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_placement_service, "list_drives", side_effect=fake_list),
    ):
        resp = client.get(f"{BASE}?search=acme&status=OPEN", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["search"] == "acme"
    assert captured["status"] == "OPEN"


def test_create_derives_institution_from_token_not_body():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["institution_id"] = institution_id
        captured["fields"] = fields
        return _drive_row()

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_placement_service, "create_drive", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={"job_id": "job-1", "title": "Campus Drive 2026"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["institution_id"] == "institution-1"
    assert captured["fields"]["title"] == "Campus Drive 2026"


def test_create_rejects_client_supplied_status():
    with authenticated_as("INSTITUTION"):
        resp = client.post(
            BASE,
            json={"job_id": "job-1", "title": "X", "status": "OPEN"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_blank_title():
    with authenticated_as("INSTITUTION"):
        resp = client.post(
            BASE, json={"job_id": "job-1", "title": "   "}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_maps_job_not_available_to_422():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_placement_service,
            "create_drive",
            side_effect=institution_placement_service.JobNotAvailableError("not published"),
        ),
    ):
        resp = client.post(
            BASE, json={"job_id": "job-1", "title": "X"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_maps_cross_institution_department_to_422():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_placement_service,
            "create_drive",
            side_effect=institution_placement_service.CrossInstitutionEligibilityError("nope"),
        ),
    ):
        resp = client.post(
            BASE, json={"job_id": "job-1", "title": "X"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_get_404_when_not_found_or_not_owned():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_placement_service, "get_drive", return_value=None),
    ):
        resp = client.get(f"{BASE}/{DRIVE_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_update_does_not_accept_job_id_or_status():
    with authenticated_as("INSTITUTION"):
        resp = client.put(
            f"{BASE}/{DRIVE_ID}",
            json={"job_id": "job-2", "status": "OPEN"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_only_sends_explicitly_set_fields():
    captured = {}

    def fake_update(_client, _institution_id, _drive_id, fields):
        captured["fields"] = fields
        return _drive_row(venue="Auditorium")

    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_placement_service, "update_drive", side_effect=fake_update),
    ):
        resp = client.put(
            f"{BASE}/{DRIVE_ID}", json={"venue": "Auditorium"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["fields"] == {"venue": "Auditorium"}


def test_status_update_maps_invalid_transition_to_409():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_placement_service,
            "update_drive_status",
            side_effect=institution_placement_service.InvalidStatusTransitionError("COMPLETED", "OPEN"),
        ),
    ):
        resp = client.patch(
            f"{BASE}/{DRIVE_ID}/status", json={"status": "OPEN"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_status_update_404_when_not_owned():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_placement_service, "update_drive_status", return_value=None),
    ):
        resp = client.patch(
            f"{BASE}/{DRIVE_ID}/status", json={"status": "OPEN"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_students_endpoint_404_when_not_owned():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_placement_service, "get_drive_students", return_value=None),
    ):
        resp = client.get(f"{BASE}/{DRIVE_ID}/students", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_applications_endpoint_404_when_not_owned():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_placement_service, "get_drive_applicants", return_value=None),
    ):
        resp = client.get(f"{BASE}/{DRIVE_ID}/applications", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_no_delete_endpoint_exists():
    """There is no DELETE endpoint -- CANCELLED is the terminal status
    for a drive that needs to stop; historical drives are never deleted."""
    with authenticated_as("INSTITUTION"):
        resp = client.delete(f"{BASE}/{DRIVE_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 405


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

    def insert(self, payload):
        row = {"id": "new-drive", **payload}
        self._store.setdefault(self._name, []).append(row)
        self._rows = [row]
        return self

    def update(self, payload):
        for row in self._rows:
            row.update(payload)
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


def _job_titles_rpc(rows):
    def handler(params):
        wanted = set(params.get("job_ids", []))
        return [r for r in rows if r["id"] in wanted]

    return handler


def _base_tables(**overrides):
    tables = {
        "placement_drives": [],
        "jobs": [],
        "departments": [],
        "student_profiles": [],
        "student_skills": [],
        "skills": [],
        "applications": [],
        "interviews": [],
        "industry_profiles": [],
    }
    tables.update(overrides)
    return tables


_JOB_TITLES = [
    {
        "id": "job-1",
        "title": "Software Engineer",
        "description": "Build things.",
        "location": "Remote",
        "work_mode": "REMOTE",
        "employment_type": "FULL_TIME",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": "INR",
        "experience_min_years": None,
        "status": "PUBLISHED",
        "industry_id": "co-1",
    }
]


def _rpc(job_rows=None, name_rows=None):
    return {
        "institution_visible_job_details": _job_titles_rpc(job_rows if job_rows is not None else _JOB_TITLES),
        "institution_student_names": (
            lambda params: [r for r in (name_rows or []) if r["student_id"] in set(params.get("student_ids", []))]
        ),
    }


# ---- create_drive ----


def test_create_drive_requires_published_job():
    tables = _base_tables(jobs=[{"id": "job-1", "status": "DRAFT"}])
    try:
        institution_placement_service.create_drive(_FakeClient(tables), "inst-1", {"job_id": "job-1", "title": "X"})
        raised = False
    except institution_placement_service.JobNotAvailableError:
        raised = True
    assert raised


def test_create_drive_succeeds_for_published_job():
    tables = _base_tables(jobs=[{"id": "job-1", "status": "PUBLISHED"}])
    row = institution_placement_service.create_drive(
        _FakeClient(tables, rpc_results=_rpc()), "inst-1", {"job_id": "job-1", "title": "Campus Drive"}
    )
    assert row["title"] == "Campus Drive"
    assert row["status"] == "DRAFT"


def test_create_drive_rejects_another_institutions_department():
    tables = _base_tables(
        jobs=[{"id": "job-1", "status": "PUBLISHED"}],
        departments=[{"id": "dept-1", "institution_id": "inst-B"}],
    )
    try:
        institution_placement_service.create_drive(
            _FakeClient(tables),
            "inst-1",
            {"job_id": "job-1", "title": "X", "eligible_department_ids": ["dept-1"]},
        )
        raised = False
    except institution_placement_service.CrossInstitutionEligibilityError:
        raised = True
    assert raised


def test_create_drive_accepts_own_department():
    tables = _base_tables(
        jobs=[{"id": "job-1", "status": "PUBLISHED"}],
        departments=[{"id": "dept-1", "institution_id": "inst-1", "name": "CSE"}],
    )
    row = institution_placement_service.create_drive(
        _FakeClient(tables, rpc_results=_rpc()),
        "inst-1",
        {"job_id": "job-1", "title": "X", "eligible_department_ids": ["dept-1"]},
    )
    assert row["eligible_department_ids"] == ["dept-1"]


# ---- list / isolation ----


def test_list_drives_isolated_between_institutions():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-A", "job_id": "job-1", "title": "A", "status": "DRAFT",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
            {"id": "d2", "institution_id": "inst-B", "job_id": "job-1", "title": "B", "status": "DRAFT",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    result_a = institution_placement_service.list_drives(_FakeClient(tables, rpc_results=_rpc()), "inst-A")
    result_b = institution_placement_service.list_drives(_FakeClient(tables, rpc_results=_rpc()), "inst-B")
    assert [d["id"] for d in result_a] == ["d1"]
    assert [d["id"] for d in result_b] == ["d2"]


def test_get_drive_returns_none_for_another_institution():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-B", "job_id": "job-1", "title": "B", "status": "DRAFT",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    assert institution_placement_service.get_drive(_FakeClient(tables, rpc_results=_rpc()), "inst-A", "d1") is None


def test_historical_drive_remains_readable_after_job_closes():
    """The job is no longer PUBLISHED, but the institution's own drive
    still resolves its title/company via institution_visible_job_details."""
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-1", "job_id": "job-1", "title": "Old Drive", "status": "COMPLETED",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    closed_job = [{**_JOB_TITLES[0], "status": "CLOSED"}]
    row = institution_placement_service.get_drive(
        _FakeClient(tables, rpc_results=_rpc(job_rows=closed_job)), "inst-1", "d1"
    )
    assert row["job_title"] == "Software Engineer"
    assert row["company_name"] == "Acme Corp"
    assert row["job_status"] == "CLOSED"


# ---- status transitions ----


def test_valid_status_transition_draft_to_open():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-1", "job_id": "job-1", "title": "X", "status": "DRAFT",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    row = institution_placement_service.update_drive_status(
        _FakeClient(tables, rpc_results=_rpc()), "inst-1", "d1", "OPEN"
    )
    assert row["status"] == "OPEN"


def test_invalid_status_transition_rejected():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-1", "job_id": "job-1", "title": "X", "status": "DRAFT",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    try:
        institution_placement_service.update_drive_status(_FakeClient(tables), "inst-1", "d1", "COMPLETED")
        raised = False
    except institution_placement_service.InvalidStatusTransitionError as exc:
        raised = True
        assert exc.current == "DRAFT"
        assert exc.target == "COMPLETED"
    assert raised


def test_terminal_status_has_no_further_transitions():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-1", "job_id": "job-1", "title": "X", "status": "COMPLETED",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    try:
        institution_placement_service.update_drive_status(_FakeClient(tables), "inst-1", "d1", "OPEN")
        raised = False
    except institution_placement_service.InvalidStatusTransitionError:
        raised = True
    assert raised


def test_cancelled_reachable_from_open():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-1", "job_id": "job-1", "title": "X", "status": "OPEN",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    row = institution_placement_service.update_drive_status(
        _FakeClient(tables, rpc_results=_rpc()), "inst-1", "d1", "CANCELLED"
    )
    assert row["status"] == "CANCELLED"


def test_status_update_returns_none_for_another_institutions_drive():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-B", "job_id": "job-1", "title": "X", "status": "DRAFT",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    assert institution_placement_service.update_drive_status(_FakeClient(tables), "inst-A", "d1", "OPEN") is None


# ---- eligibility engine ----


def test_eligibility_no_criteria_means_everyone_eligible():
    drive = {"eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []}
    is_eligible, reasons = institution_placement_service.compute_eligibility({"cgpa": None}, set(), drive, {})
    assert is_eligible is True
    assert reasons == []


def test_eligibility_department_criterion():
    drive = {"eligible_department_ids": ["dept-cse"], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []}
    is_eligible, reasons = institution_placement_service.compute_eligibility(
        {"department_id": "dept-ece"}, set(), drive, {}
    )
    assert is_eligible is False
    assert reasons == ["Department not eligible"]


def test_eligibility_batch_criterion():
    drive = {"eligible_department_ids": [], "eligible_batches": [2027], "minimum_cgpa": None, "eligible_skill_ids": []}
    is_eligible, reasons = institution_placement_service.compute_eligibility(
        {"graduation_year": 2026}, set(), drive, {}
    )
    assert is_eligible is False
    assert reasons == ["Batch not eligible"]


def test_eligibility_minimum_cgpa_criterion():
    drive = {"eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": 7.5, "eligible_skill_ids": []}
    ineligible, reasons = institution_placement_service.compute_eligibility({"cgpa": 6.5}, set(), drive, {})
    eligible, _ = institution_placement_service.compute_eligibility({"cgpa": 8.0}, set(), drive, {})
    assert ineligible is False
    assert reasons == ["CGPA below 7.5"]
    assert eligible is True


def test_eligibility_missing_cgpa_fails_minimum_criterion():
    drive = {"eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": 7.5, "eligible_skill_ids": []}
    is_eligible, reasons = institution_placement_service.compute_eligibility({"cgpa": None}, set(), drive, {})
    assert is_eligible is False
    assert reasons == ["CGPA below 7.5"]


def test_eligibility_skill_criterion_names_the_missing_skill():
    drive = {"eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": ["sk-py"]}
    is_eligible, reasons = institution_placement_service.compute_eligibility(
        {}, set(), drive, {"sk-py": "Python"}
    )
    assert is_eligible is False
    assert reasons == ["Missing required skill(s): Python"]


def test_eligibility_all_criteria_combined():
    drive = {
        "eligible_department_ids": ["dept-cse"],
        "eligible_batches": [2027],
        "minimum_cgpa": 7.5,
        "eligible_skill_ids": ["sk-py"],
    }
    student = {"department_id": "dept-cse", "graduation_year": 2027, "cgpa": 8.2}
    is_eligible, reasons = institution_placement_service.compute_eligibility(
        student, {"sk-py"}, drive, {"sk-py": "Python"}
    )
    assert is_eligible is True
    assert reasons == []


# ---- eligible students / applicants: institution isolation ----


def test_drive_students_only_include_own_institution_students():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-A", "job_id": "job-1",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-B", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
    )
    result = institution_placement_service.get_drive_students(_FakeClient(tables, rpc_results=_rpc()), "inst-A", "d1")
    assert [s["id"] for s in result["students"]] == ["s1"]


def test_drive_students_returns_none_for_another_institutions_drive():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-B", "job_id": "job-1",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
    )
    assert institution_placement_service.get_drive_students(_FakeClient(tables), "inst-A", "d1") is None


def test_drive_students_marks_application_status_when_applied():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-A", "job_id": "job-1",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[{"id": "a1", "student_id": "s1", "job_id": "job-1", "status": "SHORTLISTED", "applied_at": None}],
    )
    result = institution_placement_service.get_drive_students(_FakeClient(tables, rpc_results=_rpc()), "inst-A", "d1")
    assert result["students"][0]["application_status"] == "SHORTLISTED"
    assert result["applied_count"] == 1


def test_drive_applicants_only_from_own_institution():
    tables = _base_tables(
        placement_drives=[{"id": "d1", "institution_id": "inst-A", "job_id": "job-1"}],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "job_id": "job-1", "status": "APPLIED", "applied_at": "2026-01-01"},
        ],
    )
    result = institution_placement_service.get_drive_applicants(
        _FakeClient(tables, rpc_results=_rpc()), "inst-A", "d1"
    )
    assert len(result["applicants"]) == 1
    assert result["applicants"][0]["student_id"] == "s1"


def test_drive_applicants_include_interview_and_exclude_notes():
    tables = _base_tables(
        placement_drives=[{"id": "d1", "institution_id": "inst-A", "job_id": "job-1"}],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "job_id": "job-1", "status": "INTERVIEW_SCHEDULED", "applied_at": None},
        ],
        interviews=[
            {"application_id": "a1", "scheduled_at": "2026-02-01T10:00:00Z", "mode": "ONLINE",
             "status": "SCHEDULED", "notes": "SENSITIVE"},
        ],
    )
    result = institution_placement_service.get_drive_applicants(
        _FakeClient(tables, rpc_results=_rpc()), "inst-A", "d1"
    )
    applicant = result["applicants"][0]
    assert applicant["interview"]["mode"] == "ONLINE"
    assert "notes" not in applicant["interview"]
    assert "SENSITIVE" not in str(result)


# ---- placement overview: unique placed vs total selected offers ----


def test_overview_distinguishes_unique_placed_from_total_selected_offers():
    """A student SELECTED for two different drive-linked jobs counts once
    in placed_students but twice in total_selected_offers (Part 20)."""
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-A", "job_id": "job-1", "status": "OPEN"},
            {"id": "d2", "institution_id": "inst-A", "job_id": "job-2", "status": "OPEN"},
        ],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "job_id": "job-1", "status": "SELECTED", "applied_at": None},
            {"id": "a2", "student_id": "s1", "job_id": "job-2", "status": "SELECTED", "applied_at": None},
        ],
    )
    result = institution_placement_service.get_placement_overview(_FakeClient(tables, rpc_results=_rpc()), "inst-A")
    assert result["placed_students"] == 1
    assert result["total_selected_offers"] == 2
    assert result["participating_students"] == 1
    assert result["placement_rate"] == 100.0


def test_overview_isolated_between_institutions():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-A", "job_id": "job-1", "status": "OPEN"},
            {"id": "d2", "institution_id": "inst-B", "job_id": "job-1", "status": "OPEN"},
        ],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
            {"id": "s2", "institution_id": "inst-B", "department_id": None, "graduation_year": 2026, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "job_id": "job-1", "status": "SELECTED", "applied_at": None},
            {"id": "a2", "student_id": "s2", "job_id": "job-1", "status": "SELECTED", "applied_at": None},
        ],
    )
    result_a = institution_placement_service.get_placement_overview(_FakeClient(tables, rpc_results=_rpc()), "inst-A")
    assert result_a["placed_students"] == 1
    assert result_a["active_drives"] == 1


def test_overview_active_and_completed_drive_counts():
    tables = _base_tables(
        placement_drives=[
            {"id": "d1", "institution_id": "inst-A", "job_id": "job-1", "status": "OPEN"},
            {"id": "d2", "institution_id": "inst-A", "job_id": "job-1", "status": "IN_PROGRESS"},
            {"id": "d3", "institution_id": "inst-A", "job_id": "job-1", "status": "COMPLETED"},
            {"id": "d4", "institution_id": "inst-A", "job_id": "job-1", "status": "CANCELLED"},
            {"id": "d5", "institution_id": "inst-A", "job_id": "job-1", "status": "DRAFT"},
        ],
    )
    result = institution_placement_service.get_placement_overview(_FakeClient(tables, rpc_results=_rpc()), "inst-A")
    assert result["active_drives"] == 2
    assert result["completed_drives"] == 1


# ============================================================
# RLS boundary: no service-role anywhere on this path
# ============================================================


def test_institution_placement_service_has_no_service_role_access():
    assert not hasattr(institution_placement_service, "get_supabase")
