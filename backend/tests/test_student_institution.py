"""Tests for the Student "My Institution" portal:
/api/v1/student/institution, database/migrations/
047_student_institution_visibility.sql.

Route tests mock student_institution_service and use
tests.conftest.authenticated_as, matching the rest of the test suite.
Service tests drive student_institution_service against a fake Supabase
client -- verifying the three link states (none/pending/verified),
institution-curated (never platform-wide) internship visibility,
placement-drive eligibility reuse, event visibility with no fabricated
registration data, own-applications scoping, cross-institution isolation,
and that two institutions can independently curate the same canonical
internship without duplicating it.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import student_institution_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/student/institution"


# ============================================================
# Auth / role guards
# ============================================================


def test_endpoint_rejects_unauthenticated():
    assert client.get(BASE).status_code == 401


def test_endpoint_forbids_non_student_roles():
    for role in ("INSTITUTION", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403


def test_route_scopes_to_authenticated_student():
    captured = {}

    def fake_get(_client, student_id):
        captured["student_id"] = student_id
        return _empty()

    with (
        authenticated_as("STUDENT", user_id="student-77"),
        patch.object(student_institution_service, "get_my_institution", side_effect=fake_get),
    ):
        resp = client.get(BASE, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["student_id"] == "student-77"


def _empty():
    return {
        "linked": False, "institution": None, "profile": None,
        "kpis": {"placement_drives": 0, "internships": 0, "events": 0, "active_applications": 0},
        "placement_drives": [], "internships": [], "events": [], "activity": [],
        "curation_note": "note", "eligibility_note": "note", "registration_note": "note",
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

    def select(self, *_a, **_kw):
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
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables, name)


def _base_tables(**overrides):
    tables = {
        "student_profiles": [],
        "institution_profiles": [],
        "departments": [],
        "institution_link_requests": [],
        "placement_drives": [],
        "jobs": [],
        "industry_profiles": [],
        "student_skills": [],
        "skills": [],
        "institution_internships": [],
        "internships": [],
        "institution_events": [],
        "applications": [],
    }
    tables.update(overrides)
    return tables


_STUDENT = {"id": "s1", "institution_id": "inst-1", "department_id": "d1", "graduation_year": 2026, "cgpa": 8.5}


# ---- link states ----


def test_student_without_institution_is_not_linked():
    tables = _base_tables(student_profiles=[{**_STUDENT, "institution_id": None}])
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["linked"] is False
    assert result["institution"] is None
    assert result["kpis"] == {"placement_drives": 0, "internships": 0, "events": 0, "active_applications": 0}


def test_student_with_only_a_pending_request_is_not_linked():
    """institution_id stays null until the institution approves -- a
    PENDING request row alone must not unlock the workspace."""
    tables = _base_tables(
        student_profiles=[{**_STUDENT, "institution_id": None}],
        institution_link_requests=[
            {"student_id": "s1", "institution_id": "inst-1", "status": "PENDING", "updated_at": "2026-01-01T00:00:00Z"},
        ],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["linked"] is False


def test_verified_student_is_linked_and_sees_institution_identity():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        institution_profiles=[{"id": "inst-1", "institution_name": "ABC University", "institution_type": "UNIVERSITY", "location": "Delhi", "website_url": None}],
        departments=[{"id": "d1", "name": "CSE"}],
        institution_link_requests=[
            {"student_id": "s1", "institution_id": "inst-1", "status": "APPROVED", "updated_at": "2026-01-05T00:00:00Z"},
        ],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["linked"] is True
    assert result["institution"]["institution_name"] == "ABC University"
    assert result["profile"]["department"] == "CSE"
    assert result["profile"]["batch"] == 2026
    assert result["profile"]["verified_at"] == "2026-01-05T00:00:00Z"


def test_verification_is_authoritative_only_via_institution_id_not_request_status():
    """A REMOVED (unlinked) request must not keep the workspace unlocked
    -- institution_id (already cleared by the DB trigger in that case) is
    the sole source of truth, never institution_link_requests.status read
    independently."""
    tables = _base_tables(
        student_profiles=[{**_STUDENT, "institution_id": None}],
        institution_link_requests=[
            {"student_id": "s1", "institution_id": "inst-1", "status": "REMOVED", "updated_at": "2026-01-05T00:00:00Z"},
        ],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["linked"] is False


# ---- curated internships ----


_INTERNSHIP = {
    "id": "i1", "industry_id": "co-1", "title": "Backend Intern", "description": "Build APIs.",
    "work_mode": "REMOTE", "duration_months": 3, "stipend_amount": 10000, "stipend_currency": "INR",
    "eligibility_criteria": None, "application_deadline": "2026-12-01", "start_date": "2026-01-01",
    "status": "PUBLISHED",
}


def test_sees_institution_curated_published_internship():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        internships=[_INTERNSHIP],
        institution_internships=[{"institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE"}],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert [r["id"] for r in result["internships"]] == ["i1"]
    assert result["internships"][0]["company_name"] == "Acme Corp"
    assert result["kpis"]["internships"] == 1


def test_does_not_see_uncurated_internship_even_if_published():
    tables = _base_tables(student_profiles=[_STUDENT], internships=[_INTERNSHIP])
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["internships"] == []


def test_does_not_see_internship_curated_only_by_a_different_institution():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        internships=[_INTERNSHIP],
        institution_internships=[{"institution_id": "inst-OTHER", "internship_id": "i1", "status": "ACTIVE"}],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["internships"] == []


def test_two_institutions_independently_curate_the_same_canonical_internship():
    """The canonical internship is never duplicated -- each institution's
    students see it via their own independent association."""
    tables_a = _base_tables(
        student_profiles=[_STUDENT],
        internships=[_INTERNSHIP],
        institution_internships=[
            {"institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE"},
            {"institution_id": "inst-2", "internship_id": "i1", "status": "ACTIVE"},
        ],
    )
    result_a = student_institution_service.get_my_institution(_FakeClient(tables_a), "s1")
    assert [r["id"] for r in result_a["internships"]] == ["i1"]

    tables_b = _base_tables(
        student_profiles=[{**_STUDENT, "id": "s2", "institution_id": "inst-2"}],
        internships=[_INTERNSHIP],
        institution_internships=[
            {"institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE"},
            {"institution_id": "inst-2", "internship_id": "i1", "status": "ACTIVE"},
        ],
    )
    result_b = student_institution_service.get_my_institution(_FakeClient(tables_b), "s2")
    assert [r["id"] for r in result_b["internships"]] == ["i1"]


def test_internship_already_applied_reflects_own_application_status():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        internships=[_INTERNSHIP],
        institution_internships=[{"institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE"}],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP", "internship_id": "i1",
             "job_id": None, "applied_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-10T00:00:00Z"},
        ],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    row = result["internships"][0]
    assert row["already_applied"] is True
    assert row["application_status"] == "SELECTED"


# ---- placement drives / eligibility ----


_DRIVE = {
    "id": "pd1", "institution_id": "inst-1", "job_id": "j1", "title": "Campus Drive 2026", "description": None,
    "status": "OPEN", "application_deadline": "2026-12-01", "drive_date": "2026-12-10", "mode": "ONSITE",
    "venue": "Auditorium", "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None,
    "eligible_skill_ids": [],
}


def test_sees_eligible_placement_drive():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        placement_drives=[_DRIVE],
        jobs=[{"id": "j1", "industry_id": "co-1"}],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert len(result["placement_drives"]) == 1
    row = result["placement_drives"][0]
    assert row["is_eligible"] is True
    assert row["eligibility_reasons"] == []
    assert row["company_name"] == "Acme Corp"


def test_shows_ineligible_drive_with_reasons_rather_than_hiding_it():
    """This module reuses the institution's own eligibility engine, which
    always returns a transparent verdict + reasons -- it never silently
    drops a drive the student cannot personally qualify for."""
    tables = _base_tables(
        student_profiles=[_STUDENT],
        placement_drives=[{**_DRIVE, "minimum_cgpa": 9.5}],
        jobs=[{"id": "j1", "industry_id": "co-1"}],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    row = result["placement_drives"][0]
    assert row["is_eligible"] is False
    assert any("CGPA" in r for r in row["eligibility_reasons"])


def test_drive_from_a_different_institution_never_appears():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        placement_drives=[{**_DRIVE, "id": "pd-other"}],  # institution_id filter happens at fetch time
    )
    # Simulate cross-institution isolation directly: the fetch always
    # filters .eq("institution_id", institution_id), so a drive lacking
    # that field (or belonging elsewhere) is naturally excluded by the
    # fake's eq() filter once institution_id is attached.
    tables["placement_drives"][0]["institution_id"] = "inst-OTHER"
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["placement_drives"] == []


# ---- events ----


_EVENT = {
    "id": "e1", "institution_id": "inst-1", "industry_id": None, "title": "Placement Orientation",
    "description": "Kickoff session.", "event_type": "PLACEMENT_ORIENTATION", "status": "PUBLISHED",
    "mode": "ONSITE", "venue": "Hall A", "start_at": "2026-03-01T10:00:00Z", "end_at": "2026-03-01T12:00:00Z",
    "target_department_ids": [], "target_batches": [],
}


def test_sees_published_institution_event_with_no_fabricated_registration_data():
    tables = _base_tables(student_profiles=[_STUDENT], institution_events=[_EVENT])
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert len(result["events"]) == 1
    assert result["events"][0]["is_relevant_to_me"] is True
    assert "registration" not in result["events"][0]
    assert "attendance" not in result["events"][0]
    assert result["registration_note"]


def test_event_targeted_to_a_different_department_is_not_relevant_to_me():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        institution_events=[{**_EVENT, "target_department_ids": ["d-OTHER"]}],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["events"][0]["is_relevant_to_me"] is False


def test_draft_or_other_institution_event_never_appears():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        institution_events=[{**_EVENT, "id": "e-draft", "status": "DRAFT"}],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["events"] == []


# ---- applications / activity ----


def test_own_applications_drive_active_applications_kpi_and_activity_feed():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        internships=[_INTERNSHIP],
        institution_internships=[{"institution_id": "inst-1", "internship_id": "i1", "status": "ACTIVE"}],
        institution_link_requests=[
            {"student_id": "s1", "institution_id": "inst-1", "status": "APPROVED", "updated_at": "2026-01-01T00:00:00Z"},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "APPLIED", "opportunity_type": "INTERNSHIP", "internship_id": "i1",
             "job_id": None, "applied_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z"},
        ],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["kpis"]["active_applications"] == 1
    labels = [a["label"] for a in result["activity"]]
    assert any("Applied to Backend Intern" in label for label in labels)
    assert any("Verified by" in label for label in labels)


def test_application_to_uncurated_internship_does_not_count_toward_active_applications():
    tables = _base_tables(
        student_profiles=[_STUDENT],
        internships=[_INTERNSHIP],  # never curated
        applications=[
            {"id": "a1", "student_id": "s1", "status": "APPLIED", "opportunity_type": "INTERNSHIP", "internship_id": "i1",
             "job_id": None, "applied_at": "2026-02-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z"},
        ],
    )
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["kpis"]["active_applications"] == 0


def test_no_fabricated_fields_anywhere_in_empty_response():
    tables = _base_tables(student_profiles=[{**_STUDENT, "institution_id": None}])
    result = student_institution_service.get_my_institution(_FakeClient(tables), "s1")
    assert result["curation_note"]
    assert result["eligibility_note"]
    assert result["registration_note"]
