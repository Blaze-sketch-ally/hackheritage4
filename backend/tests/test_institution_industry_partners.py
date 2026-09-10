"""Tests for the Institution Industry Partners module (Phase 8):
/api/v1/institution/industry-partners..., database/migrations/
075_institution_industry_partners.sql.

Route tests mock institution_industry_service and use
tests.conftest.authenticated_as, matching the rest of the institution
test suite. Service tests drive institution_industry_service against a
fake Supabase client (table reads + rpc calls, same fake-client shape as
test_institution_placements.py / test_institution_internships.py) --
verifying that the canonical company identity stays `industry_profiles`
(never a second entity), that "selected" stays consistent with the rest
of the Institution module, that the directory union covers every
activity source (jobs/internships/drives/collaborations/explicit tags)
without leaking another institution's data, and that the explicit
relationship CRUD only ever targets a real industry account.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_industry_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/industry-partners"
COMPANY_ID = "33333333-3333-3333-3333-333333333333"


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/metrics").status_code == 401
    assert client.get(f"{BASE}/{COMPANY_ID}").status_code == 401
    assert client.post(BASE, json={"industry_id": COMPANY_ID}).status_code == 401
    assert client.patch(f"{BASE}/{COMPANY_ID}/relationship", json={}).status_code == 401


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.post(BASE, json={"industry_id": COMPANY_ID}, headers={"Authorization": "Bearer token"}).status_code
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
        return {"partners": [], "type_options": [], "status_options": []}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_industry_service, "list_partners", side_effect=fake_list),
    ):
        resp = client.get(
            f"{BASE}?search=acme&relationship_type=RECRUITMENT&relationship_status=ACTIVE",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["search"] == "acme"
    assert captured["relationship_type"] == "RECRUITMENT"
    assert captured["relationship_status"] == "ACTIVE"


def test_create_derives_institution_from_token_not_body():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["institution_id"] = institution_id
        captured["fields"] = fields
        return {
            "id": "rel-1",
            "industry_id": COMPANY_ID,
            "relationship_type": "RECRUITMENT",
            "relationship_status": "PROSPECT",
            "notes": None,
            "created_at": None,
            "updated_at": None,
        }

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_industry_service, "create_relationship", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={"industry_id": COMPANY_ID, "relationship_type": "RECRUITMENT"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["institution_id"] == "institution-1"
    assert captured["fields"]["industry_id"] == COMPANY_ID


def test_create_rejects_unknown_company():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_industry_service,
            "create_relationship",
            side_effect=institution_industry_service.IndustryProfileNotFoundError("not found"),
        ),
    ):
        resp = client.post(BASE, json={"industry_id": COMPANY_ID}, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


def test_create_rejects_duplicate_relationship():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_industry_service,
            "create_relationship",
            side_effect=institution_industry_service.DuplicateRelationshipError("dup"),
        ),
    ):
        resp = client.post(BASE, json={"industry_id": COMPANY_ID}, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 409


def test_detail_404_for_company_outside_union():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_industry_service, "get_partner_detail", return_value=None),
    ):
        resp = client.get(f"{BASE}/{COMPANY_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_update_relationship_404_when_not_tracked():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_industry_service, "update_relationship", return_value=None),
    ):
        resp = client.patch(
            f"{BASE}/{COMPANY_ID}/relationship",
            json={"relationship_status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


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

    def in_(self, field, values):
        values = set(values)
        self._rows = [r for r in self._rows if r.get(field) in values]
        return self

    def order(self, field, desc=False):
        self._rows = sorted(self._rows, key=lambda r: r.get(field) or "", reverse=desc)
        return self

    def ilike(self, field, pattern):
        needle = pattern.strip("%").lower()
        self._rows = [r for r in self._rows if needle in str(r.get(field, "")).lower()]
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        row = {"id": f"new-{len(self._store.get(self._name, []))}", **payload}
        self._store.setdefault(self._name, []).append(row)
        self._rows = [row]
        return self

    def update(self, payload):
        for row in self._rows:
            row.update(payload)
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
        "skills": [],
        "industry_profiles": [],
        "industry_collaborations": [],
        "institution_industry_partners": [],
    }
    tables.update(overrides)
    return tables


def _rpc(job_rows=None, internship_rows=None, title_rows=None, name_rows=None):
    def job_details(params):
        wanted = set(params.get("job_ids", []))
        return [r for r in (job_rows or []) if r["id"] in wanted]

    def internship_details(params):
        wanted = set(params.get("internship_ids", []))
        return [r for r in (internship_rows or []) if r["id"] in wanted]

    def opportunity_titles(params):
        job_ids = set(params.get("job_ids", []))
        internship_ids = set(params.get("internship_ids", []))
        return [r for r in (title_rows or []) if r["id"] in job_ids or r["id"] in internship_ids]

    def student_names(params):
        wanted = set(params.get("student_ids", []))
        return [r for r in (name_rows or []) if r["student_id"] in wanted]

    return {
        "institution_visible_job_details": job_details,
        "institution_visible_internship_details": internship_details,
        "institution_visible_opportunity_titles": opportunity_titles,
        "institution_student_names": student_names,
    }


def _compute_list(tables, institution_id="inst-1", rpc_results=None, **kwargs):
    return institution_industry_service.list_partners(
        _FakeClient(tables, rpc_results=rpc_results or _rpc()), institution_id, **kwargs
    )


# ---- empty state ----


def test_empty_institution_has_no_partners_and_zero_metrics():
    result = _compute_list(_base_tables())
    assert result["partners"] == []

    metrics = institution_industry_service.compute_metrics(_FakeClient(_base_tables()), "inst-1")
    assert metrics["metrics"] == {
        "total_partners": 0,
        "active_partners": 0,
        "recruiting_partners": 0,
        "internship_partners": 0,
        "placement_drives_total": 0,
        "students_selected_total": 0,
        "internship_students_total": 0,
    }


# ---- directory union sources ----


def test_company_visible_via_job_application_only():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0}],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(tables)
    assert len(result["partners"]) == 1
    row = result["partners"][0]
    assert row["company_name"] == "Acme Corp"
    assert row["jobs_selected_students"] == 1
    assert row["has_explicit_relationship"] is False
    assert row["relationship_status"] is None


def test_company_visible_via_internship_application_only():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0}],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "i1", "job_id": None, "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(tables)
    assert len(result["partners"]) == 1
    assert result["partners"][0]["internship_selected"] == 1


def test_company_visible_via_placement_drive_only():
    tables = _base_tables(
        placement_drives=[
            {"id": "drive-1", "institution_id": "inst-1", "job_id": "job-1", "title": "Drive", "status": "OPEN",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        jobs=[{"id": "job-1", "status": "PUBLISHED"}],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(
        tables,
        rpc_results=_rpc(job_rows=[{"id": "job-1", "title": "SWE", "industry_id": "co-1", "status": "PUBLISHED"}]),
    )
    assert len(result["partners"]) == 1
    assert result["partners"][0]["placement_drives_count"] == 1


def test_company_visible_via_collaboration_only():
    tables = _base_tables(
        industry_collaborations=[
            {"industry_id": "co-1", "recipient_id": "inst-1", "title": "Research tie-up", "status": "ACTIVE", "updated_at": "2026-01-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(tables)
    assert len(result["partners"]) == 1
    assert result["partners"][0]["last_activity_at"] == "2026-01-01T00:00:00Z"


def test_company_visible_via_explicit_relationship_with_no_activity():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "PROSPECT", "notes": "Met at career fair", "created_at": None, "updated_at": None},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(tables)
    assert len(result["partners"]) == 1
    row = result["partners"][0]
    assert row["has_explicit_relationship"] is True
    assert row["relationship_status"] == "PROSPECT"
    assert row["last_activity_at"] is None
    assert row["jobs_selected_students"] == 0


# ---- cross-institution isolation ----


def test_other_institutions_students_and_drives_never_leak():
    tables = _base_tables(
        student_profiles=[{"id": "sB", "institution_id": "inst-B", "department_id": None, "cgpa": 8.0}],
        applications=[
            {"id": "a1", "student_id": "sB", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        placement_drives=[
            {"id": "drive-1", "institution_id": "inst-B", "job_id": "job-1", "title": "Drive", "status": "OPEN",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(tables, institution_id="inst-A")
    assert result["partners"] == []


def test_other_institutions_explicit_relationship_never_leaks():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-B", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "ACTIVE", "notes": "Private note", "created_at": None, "updated_at": None},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = _compute_list(tables, institution_id="inst-A")
    assert result["partners"] == []


# ---- search / filters ----


def test_search_and_relationship_filters():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "RECRUITMENT",
             "relationship_status": "ACTIVE", "notes": None, "created_at": None, "updated_at": None},
            {"id": "rel-2", "institution_id": "inst-1", "industry_id": "co-2", "relationship_type": "TRAINING",
             "relationship_status": "PROSPECT", "notes": None, "created_at": None, "updated_at": None},
        ],
        industry_profiles=[
            {"id": "co-1", "company_name": "Acme Corp"},
            {"id": "co-2", "company_name": "Globex Inc"},
        ],
    )
    result = _compute_list(tables, search="acme")
    assert [r["company_name"] for r in result["partners"]] == ["Acme Corp"]

    result = _compute_list(tables, relationship_status="PROSPECT")
    assert [r["company_name"] for r in result["partners"]] == ["Globex Inc"]


# ---- detail ----


def test_detail_404_for_company_outside_activity_or_relationship():
    result = institution_industry_service.get_partner_detail(_FakeClient(_base_tables()), "inst-1", "missing")
    assert result is None


def test_detail_distinguishes_jobs_from_internships_and_shows_no_private_fields():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0}],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-1", "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
            {"id": "a2", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "i1", "job_id": None, "industry_id": "co-1", "applied_at": "2026-02-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": "Software"}],
    )
    result = institution_industry_service.get_partner_detail(
        _FakeClient(tables, rpc_results=_rpc(title_rows=[{"id": "job-1", "title": "SWE"}])), "inst-1", "co-1"
    )
    assert result["jobs"]["selected_students"] == 1
    assert result["internships"]["selected"] == 1
    assert result["students_selected"] == 1
    assert "email" not in result
    assert "phone" not in result
    assert "privacy_note" in result


def test_placement_drive_selection_rate_none_when_no_applicants():
    tables = _base_tables(
        placement_drives=[
            {"id": "drive-1", "institution_id": "inst-1", "job_id": "job-1", "title": "Drive", "status": "OPEN",
             "eligible_department_ids": [], "eligible_batches": [], "minimum_cgpa": None, "eligible_skill_ids": []},
        ],
        jobs=[{"id": "job-1", "status": "PUBLISHED"}],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = institution_industry_service.get_partner_detail(
        _FakeClient(
            tables,
            rpc_results=_rpc(job_rows=[{"id": "job-1", "title": "SWE", "industry_id": "co-1", "status": "PUBLISHED"}]),
        ),
        "inst-1",
        "co-1",
    )
    drive = result["placement_drives"]["drives"][0]
    assert drive["applied_count"] == 0
    assert drive["selection_rate"] is None


def test_collaboration_summary_never_duplicates_full_record():
    tables = _base_tables(
        industry_collaborations=[
            {"industry_id": "co-1", "recipient_id": "inst-1", "title": "Research tie-up", "status": "ACTIVE", "updated_at": "2026-01-01T00:00:00Z"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = institution_industry_service.get_partner_detail(_FakeClient(tables), "inst-1", "co-1")
    assert result["collaborations"] == {"count": 1, "latest_status": "ACTIVE", "latest_title": "Research tie-up"}


# ---- metrics ----


def test_metrics_recruiting_and_internship_partners_are_distinct():
    tables = _base_tables(
        student_profiles=[
            {"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB",
             "internship_id": None, "job_id": "job-1", "industry_id": "co-1", "applied_at": "2026-01-01T00:00:00Z"},
            {"id": "a2", "student_id": "s1", "status": "SELECTED", "opportunity_type": "INTERNSHIP",
             "internship_id": "i1", "job_id": None, "industry_id": "co-2", "applied_at": "2026-01-01T00:00:00Z"},
        ],
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "RECRUITMENT",
             "relationship_status": "ACTIVE", "notes": None, "created_at": None, "updated_at": None},
        ],
        industry_profiles=[
            {"id": "co-1", "company_name": "Acme Corp"},
            {"id": "co-2", "company_name": "Globex Inc"},
        ],
    )
    result = institution_industry_service.compute_metrics(_FakeClient(tables), "inst-1")
    m = result["metrics"]
    assert m["total_partners"] == 2
    assert m["active_partners"] == 1
    assert m["recruiting_partners"] == 1
    assert m["internship_partners"] == 1
    assert m["students_selected_total"] == 1
    assert m["internship_students_total"] == 1


# ---- explicit relationship CRUD ----


def test_create_relationship_requires_real_company():
    tables = _base_tables()
    raised = False
    try:
        institution_industry_service.create_relationship(_FakeClient(tables), "inst-1", {"industry_id": "co-missing"})
    except institution_industry_service.IndustryProfileNotFoundError:
        raised = True
    assert raised


def test_create_relationship_succeeds_for_real_company():
    tables = _base_tables(industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}])
    row = institution_industry_service.create_relationship(
        _FakeClient(tables), "inst-1", {"industry_id": "co-1", "relationship_type": "RECRUITMENT", "relationship_status": "ACTIVE"}
    )
    assert row["industry_id"] == "co-1"
    assert row["relationship_type"] == "RECRUITMENT"
    assert row["relationship_status"] == "ACTIVE"


def test_create_relationship_rejects_duplicate():
    tables = _base_tables(
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "PROSPECT", "notes": None, "created_at": None, "updated_at": None},
        ],
    )

    class _DupClient(_FakeClient):
        def table(self, name):
            q = super().table(name)
            if name == "institution_industry_partners":

                def failing_insert(payload):
                    raise RuntimeError("duplicate key value violates unique constraint")

                q.insert = failing_insert
            return q

    raised = False
    try:
        institution_industry_service.create_relationship(_DupClient(tables), "inst-1", {"industry_id": "co-1"})
    except institution_industry_service.DuplicateRelationshipError:
        raised = True
    assert raised


def test_update_relationship_only_changes_sent_fields():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-1", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "PROSPECT", "notes": "Old note", "created_at": None, "updated_at": None},
        ],
    )
    row = institution_industry_service.update_relationship(
        _FakeClient(tables), "inst-1", "co-1", {"relationship_status": "ACTIVE"}
    )
    assert row["relationship_status"] == "ACTIVE"
    assert row["notes"] == "Old note"


def test_update_relationship_404_for_untracked_company():
    result = institution_industry_service.update_relationship(
        _FakeClient(_base_tables()), "inst-1", "co-1", {"relationship_status": "ACTIVE"}
    )
    assert result is None


def test_update_relationship_isolated_between_institutions():
    tables = _base_tables(
        institution_industry_partners=[
            {"id": "rel-1", "institution_id": "inst-B", "industry_id": "co-1", "relationship_type": "OTHER",
             "relationship_status": "PROSPECT", "notes": None, "created_at": None, "updated_at": None},
        ],
    )
    result = institution_industry_service.update_relationship(
        _FakeClient(tables), "inst-A", "co-1", {"relationship_status": "ACTIVE"}
    )
    assert result is None


# ---- company picker ----


def test_search_companies_matches_name_and_returns_real_companies_only():
    tables = _base_tables(
        industry_profiles=[
            {"id": "co-1", "company_name": "Acme Corp", "industry_sector": "Software", "logo_url": None,
             "website_url": None, "headquarters_location": None},
            {"id": "co-2", "company_name": "Globex Inc", "industry_sector": "Manufacturing", "logo_url": None,
             "website_url": None, "headquarters_location": None},
        ],
    )
    result = institution_industry_service.search_companies(_FakeClient(tables), search="acme")
    assert [c["id"] for c in result] == ["co-1"]


def test_search_companies_route_requires_institution_role():
    for role in ("STUDENT", "INDUSTRY", None):
        with authenticated_as(role):
            resp = client.get(f"{BASE}/companies", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 403, role
