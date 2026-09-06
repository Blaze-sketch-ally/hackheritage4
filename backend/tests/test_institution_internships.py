"""Tests for the Institution-Curated Internships module:
/api/v1/institution/internships..., database/migrations/
046_institution_internships.sql.

Route tests mock institution_internship_service and use
tests.conftest.authenticated_as, matching the rest of the institution
test suite. Service tests drive institution_internship_service against a
fake Supabase client (table reads/writes + rpc calls, same fake-client
shape as test_institution_placements.py / test_institution_reports.py) --
verifying the curation workflow (browse available -> select -> appears in
curated list -> remove -> disappears but survives as history), tenancy
isolation, duplicate-selection handling, that an unpublished/nonexistent
internship cannot be selected, that the canonical internship and other
institutions' own curation are never affected by a removal, that
"selected" (a student) keeps meaning exactly what it has meant since
037_institution_tenancy.sql, and every other honesty boundary already
established for this module (participation estimate, free-text-only
eligibility, stipend currency grouping).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_internship_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/internships"
INTERNSHIP_ID = "22222222-2222-2222-2222-222222222222"


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/overview").status_code == 401
    assert client.get(f"{BASE}/available").status_code == 401
    assert client.get(f"{BASE}/{INTERNSHIP_ID}").status_code == 401
    assert client.post(f"{BASE}/{INTERNSHIP_ID}/select").status_code == 401
    assert client.patch(f"{BASE}/{INTERNSHIP_ID}/association").status_code == 401


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert client.get(f"{BASE}/available", headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.post(f"{BASE}/{INTERNSHIP_ID}/select", headers={"Authorization": "Bearer token"}).status_code
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
        return {"internships": [], "mode_options": [], "status_options": []}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_internship_service, "list_internships", side_effect=fake_list),
    ):
        resp = client.get(
            f"{BASE}?search=acme&status=PUBLISHED&mode=REMOTE&company_id=co-1",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["search"] == "acme"
    assert captured["status"] == "PUBLISHED"
    assert captured["mode"] == "REMOTE"
    assert captured["company_id"] == "co-1"


def test_available_scopes_to_authenticated_institution_and_forwards_params():
    captured = {}

    def fake_available(_client, institution_id, **kwargs):
        captured["institution_id"] = institution_id
        captured.update(kwargs)
        return {"internships": [], "mode_options": []}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_internship_service, "list_available_internships", side_effect=fake_available),
    ):
        resp = client.get(
            f"{BASE}/available?search=data&mode=HYBRID&company_id=co-2", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["search"] == "data"
    assert captured["mode"] == "HYBRID"
    assert captured["company_id"] == "co-2"


def test_select_returns_201_and_forwards_ids():
    captured = {}

    def fake_select(_client, institution_id, internship_id):
        captured["institution_id"] = institution_id
        captured["internship_id"] = internship_id
        return {"id": "assoc-1", "internship_id": internship_id, "status": "ACTIVE", "created_at": None, "updated_at": None}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_internship_service, "select_internship", side_effect=fake_select),
    ):
        resp = client.post(f"{BASE}/{INTERNSHIP_ID}/select", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 201
    assert captured["institution_id"] == "institution-1"
    assert captured["internship_id"] == INTERNSHIP_ID


def test_select_not_available_returns_404():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            institution_internship_service,
            "select_internship",
            side_effect=institution_internship_service.InternshipNotAvailableError("not available"),
        ),
    ):
        resp = client.post(f"{BASE}/{INTERNSHIP_ID}/select", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_select_duplicate_returns_409():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            institution_internship_service,
            "select_internship",
            side_effect=institution_internship_service.DuplicateAssociationError("already curated"),
        ),
    ):
        resp = client.post(f"{BASE}/{INTERNSHIP_ID}/select", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 409


def test_remove_association_not_found_returns_404():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_internship_service, "remove_internship", return_value=None),
    ):
        resp = client.patch(f"{BASE}/{INTERNSHIP_ID}/association", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_remove_association_success():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            institution_internship_service,
            "remove_internship",
            return_value={"id": "assoc-1", "internship_id": INTERNSHIP_ID, "status": "INACTIVE", "created_at": None, "updated_at": None},
        ),
    ):
        resp = client.patch(f"{BASE}/{INTERNSHIP_ID}/association", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "INACTIVE"


def test_detail_404_for_internship_not_curated_by_this_institution():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_internship_service, "get_internship_detail", return_value=None),
    ):
        resp = client.get(f"{BASE}/{INTERNSHIP_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_overview_scopes_to_authenticated_institution():
    captured = {}

    def fake_overview(_client, institution_id):
        captured["institution_id"] = institution_id
        return _empty_overview()

    with (
        authenticated_as("INSTITUTION", user_id="institution-77"),
        patch.object(institution_internship_service, "compute_internship_overview", side_effect=fake_overview),
    ):
        resp = client.get(f"{BASE}/overview", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-77"


def _empty_overview():
    return {
        "kpis": {
            "curated_internships": 0,
            "active_internships": 0,
            "companies": 0,
            "applicants": 0,
            "selected_students": 0,
            "active_participants": 0,
            "completed_internships": 0,
            "participation_unknown": 0,
        },
        "departments": [],
        "companies": [],
        "mode_distribution": [],
        "status_distribution": [],
        "application_status_distribution": [],
        "stipend": {"available": False, "note": "note", "by_currency": []},
        "tenancy_note": "note",
        "eligibility_note": "note",
        "participation_note": "note",
        "curation_note": "note",
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
        self._pending_update: dict | None = None
        self._pending_insert: dict | None = None

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

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        self._pending_insert = dict(payload)
        return self

    def update(self, payload):
        self._pending_update = dict(payload)
        return self

    def execute(self):
        if self._pending_insert is not None:
            row = dict(self._pending_insert)
            row.setdefault("id", f"generated-{len(self._store.setdefault(self._name, [])) + 1}")
            row.setdefault("created_at", "2026-01-01T00:00:00Z")
            row.setdefault("updated_at", "2026-01-01T00:00:00Z")
            existing = self._store.setdefault(self._name, [])
            pair = (row.get("institution_id"), row.get("internship_id"))
            if any((r.get("institution_id"), r.get("internship_id")) == pair for r in existing):
                raise ValueError("duplicate key value violates unique constraint")
            existing.append(row)
            return MagicMock(data=[row], count=None)
        if self._pending_update is not None:
            table = self._store.setdefault(self._name, [])
            matched_ids = {r["id"] for r in self._rows}
            for r in table:
                if r["id"] in matched_ids:
                    r.update(self._pending_update)
            return MagicMock(data=[r for r in table if r["id"] in matched_ids], count=None)
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
        "internships": [],
        "industry_profiles": [],
        "interviews": [],
        "institution_internships": [],
    }
    tables.update(overrides)
    return tables


def _rpc(internship_rows=None, name_rows=None):
    def curated_details(params):
        wanted = set(params.get("internship_ids", []))
        return [r for r in (internship_rows or []) if r["id"] in wanted]

    def student_names(params):
        wanted = set(params.get("student_ids", []))
        return [r for r in (name_rows or []) if r["student_id"] in wanted]

    return {
        "institution_curated_internship_details": curated_details,
        "institution_student_names": student_names,
    }


_INTERNSHIP = {
    "id": "i1",
    "industry_id": "co-1",
    "title": "Backend Intern",
    "description": "Build things.",
    "location": "Remote",
    "work_mode": "REMOTE",
    "duration_months": 3,
    "stipend_amount": 10000,
    "stipend_currency": "INR",
    "eligibility_criteria": None,
    "application_deadline": "2026-12-01",
    "start_date": "2026-01-01",
    "status": "PUBLISHED",
}


def _curated(institution_id="inst-1", internship_id="i1", assoc_status="ACTIVE"):
    return {
        "id": f"assoc-{institution_id}-{internship_id}",
        "institution_id": institution_id,
        "internship_id": internship_id,
        "status": assoc_status,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


# ---- available internships ----


def test_available_lists_published_internships_not_yet_curated():
    tables = _base_tables(
        internships=[_INTERNSHIP],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1")
    assert [r["id"] for r in result["internships"]] == ["i1"]
    assert result["internships"][0]["company_name"] == "Acme Corp"


def test_available_excludes_already_actively_curated_internship():
    tables = _base_tables(
        internships=[_INTERNSHIP],
        institution_internships=[_curated()],
    )
    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1")
    assert result["internships"] == []


def test_available_includes_previously_removed_internship_again():
    tables = _base_tables(
        internships=[_INTERNSHIP],
        institution_internships=[_curated(assoc_status="INACTIVE")],
    )
    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1")
    assert [r["id"] for r in result["internships"]] == ["i1"]


def test_available_never_shows_unpublished_internship():
    tables = _base_tables(internships=[{**_INTERNSHIP, "id": "i2", "status": "DRAFT"}])
    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1")
    assert result["internships"] == []


def test_available_search_and_mode_and_company_filters():
    tables = _base_tables(
        internships=[
            _INTERNSHIP,
            {**_INTERNSHIP, "id": "i2", "title": "Design Intern", "work_mode": "ONSITE", "industry_id": "co-2"},
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}, {"id": "co-2", "company_name": "Globex"}],
    )
    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1", search="backend")
    assert [r["id"] for r in result["internships"]] == ["i1"]

    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1", mode="ONSITE")
    assert [r["id"] for r in result["internships"]] == ["i2"]

    result = institution_internship_service.list_available_internships(_FakeClient(tables), "inst-1", company_id="co-2")
    assert [r["id"] for r in result["internships"]] == ["i2"]


# ---- select ----


def test_select_adds_a_published_internship_to_curated_list():
    tables = _base_tables(internships=[_INTERNSHIP])
    row = institution_internship_service.select_internship(_FakeClient(tables), "inst-1", "i1")
    assert row["status"] == "ACTIVE"
    assert row["internship_id"] == "i1"
    assert tables["institution_internships"][0]["institution_id"] == "inst-1"


def test_select_unpublished_or_nonexistent_internship_raises():
    tables = _base_tables(internships=[{**_INTERNSHIP, "status": "DRAFT"}])
    try:
        institution_internship_service.select_internship(_FakeClient(tables), "inst-1", "i1")
        raise AssertionError("expected InternshipNotAvailableError")
    except institution_internship_service.InternshipNotAvailableError:
        pass

    tables2 = _base_tables()
    try:
        institution_internship_service.select_internship(_FakeClient(tables2), "inst-1", "missing")
        raise AssertionError("expected InternshipNotAvailableError")
    except institution_internship_service.InternshipNotAvailableError:
        pass


def test_select_duplicate_active_selection_raises():
    tables = _base_tables(internships=[_INTERNSHIP], institution_internships=[_curated()])
    try:
        institution_internship_service.select_internship(_FakeClient(tables), "inst-1", "i1")
        raise AssertionError("expected DuplicateAssociationError")
    except institution_internship_service.DuplicateAssociationError:
        pass


def test_select_reactivates_a_previously_removed_association_idempotently():
    tables = _base_tables(internships=[_INTERNSHIP], institution_internships=[_curated(assoc_status="INACTIVE")])
    row = institution_internship_service.select_internship(_FakeClient(tables), "inst-1", "i1")
    assert row["status"] == "ACTIVE"
    # still exactly one association row -- reactivated, not duplicated
    assert len(tables["institution_internships"]) == 1


def test_select_is_isolated_per_institution():
    tables = _base_tables(internships=[_INTERNSHIP], institution_internships=[_curated(institution_id="inst-A")])
    row = institution_internship_service.select_internship(_FakeClient(tables), "inst-B", "i1")
    assert row["status"] == "ACTIVE"
    assert row["institution_id"] == "inst-B"
    # Institution A's own association is untouched.
    inst_a_row = next(r for r in tables["institution_internships"] if r["institution_id"] == "inst-A")
    assert inst_a_row["status"] == "ACTIVE"


# ---- remove ----


def test_remove_deactivates_without_touching_canonical_internship():
    tables = _base_tables(internships=[_INTERNSHIP], institution_internships=[_curated()])
    row = institution_internship_service.remove_internship(_FakeClient(tables), "inst-1", "i1")
    assert row["status"] == "INACTIVE"
    assert tables["internships"][0]["status"] == "PUBLISHED"


def test_remove_missing_association_returns_none():
    result = institution_internship_service.remove_internship(_FakeClient(_base_tables()), "inst-1", "i1")
    assert result is None


def test_remove_does_not_affect_other_institutions_own_curation():
    tables = _base_tables(
        internships=[_INTERNSHIP],
        institution_internships=[_curated(institution_id="inst-A"), _curated(institution_id="inst-B")],
    )
    institution_internship_service.remove_internship(_FakeClient(tables), "inst-A", "i1")
    inst_b_row = next(r for r in tables["institution_internships"] if r["institution_id"] == "inst-B")
    assert inst_b_row["status"] == "ACTIVE"


# ---- curated directory ----


def test_curated_list_only_shows_actively_selected_internships():
    tables = _base_tables(
        internships=[_INTERNSHIP],
        institution_internships=[_curated()],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-1")
    assert len(result["internships"]) == 1
    row = result["internships"][0]
    assert row["association_status"] == "ACTIVE"
    assert row["company_name"] == "Acme Corp"


def test_curated_list_excludes_removed_internships_by_default():
    tables = _base_tables(internships=[_INTERNSHIP], institution_internships=[_curated(assoc_status="INACTIVE")])
    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-1")
    assert result["internships"] == []


def test_curated_list_never_shows_unselected_published_internships():
    """An internship that is PUBLISHED platform-wide but this institution
    never explicitly curated must NOT appear -- the core behavior change
    this phase makes."""
    tables = _base_tables(internships=[_INTERNSHIP])
    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-1")
    assert result["internships"] == []


def test_curated_list_resolves_non_published_internship_via_curated_rpc():
    closed = {**_INTERNSHIP, "status": "CLOSED"}
    tables = _base_tables(institution_internships=[_curated()])
    result = institution_internship_service.list_internships(
        _FakeClient(tables, rpc_results=_rpc(internship_rows=[closed])), "inst-1"
    )
    assert len(result["internships"]) == 1
    assert result["internships"][0]["status"] == "CLOSED"


def test_cross_institution_curation_never_leaks_into_directory():
    tables = _base_tables(internships=[_INTERNSHIP], institution_internships=[_curated(institution_id="inst-B")])
    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-A")
    assert result["internships"] == []


def test_curated_search_status_mode_company_filters():
    tables = _base_tables(
        internships=[
            _INTERNSHIP,
            {**_INTERNSHIP, "id": "i2", "title": "Design Intern", "work_mode": "ONSITE", "industry_id": "co-2"},
        ],
        institution_internships=[_curated(), _curated(internship_id="i2")],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}, {"id": "co-2", "company_name": "Globex"}],
    )
    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-1", search="backend")
    assert [r["id"] for r in result["internships"]] == ["i1"]

    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-1", mode="ONSITE")
    assert [r["id"] for r in result["internships"]] == ["i2"]

    result = institution_internship_service.list_internships(_FakeClient(tables), "inst-1", company_id="co-2")
    assert [r["id"] for r in result["internships"]] == ["i2"]


# ---- detail / applicants / participation estimate ----


def _selected_setup(start_date, duration_months, today_application_status="SELECTED", assoc_status="ACTIVE"):
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": "d1", "cgpa": 8.5}],
        departments=[{"id": "d1", "institution_id": "inst-1", "name": "CSE", "code": None,
                      "description": None, "is_active": True, "created_at": None, "updated_at": None}],
        applications=[
            {"id": "a1", "student_id": "s1", "internship_id": "i1", "status": today_application_status,
             "opportunity_type": "INTERNSHIP", "applied_at": "2026-01-01T00:00:00Z"},
        ],
        internships=[
            {**_INTERNSHIP, "duration_months": duration_months, "start_date": start_date},
        ],
        institution_internships=[_curated(assoc_status=assoc_status)],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}],
    )
    return tables


def test_detail_404_when_internship_never_curated():
    result = institution_internship_service.get_internship_detail(_FakeClient(_base_tables()), "inst-1", "missing")
    assert result is None


def test_detail_visible_for_removed_association_as_history():
    tables = _selected_setup("2020-01-01", 3, assoc_status="INACTIVE")
    result = institution_internship_service.get_internship_detail(
        _FakeClient(tables, rpc_results=_rpc()), "inst-1", "i1"
    )
    assert result is not None
    assert result["association_status"] == "INACTIVE"


def test_detail_includes_applicant_with_department_and_no_private_fields():
    tables = _selected_setup("2020-01-01", 3)  # started and finished long ago -> COMPLETED
    result = institution_internship_service.get_internship_detail(
        _FakeClient(tables, rpc_results=_rpc(name_rows=[{"student_id": "s1", "full_name": "Ada Lovelace", "username": "ada"}])),
        "inst-1",
        "i1",
    )
    assert result is not None
    assert result["association_status"] == "ACTIVE"
    applicant = result["applicants"][0]
    assert applicant["full_name"] == "Ada Lovelace"
    assert applicant["department"] == "CSE"
    assert applicant["participation_estimate"] == "COMPLETED"
    assert "notes" not in applicant
    assert applicant.get("interview") is None


def test_participation_estimate_active_when_within_window():
    from datetime import UTC, datetime, timedelta

    start = (datetime.now(UTC).date() - timedelta(days=10)).isoformat()
    tables = _selected_setup(start, 6)
    result = institution_internship_service.get_internship_detail(_FakeClient(tables, rpc_results=_rpc()), "inst-1", "i1")
    assert result["participation"]["active"] == 1
    assert result["participation"]["completed"] == 0
    assert result["participation"]["unknown"] == 0


def test_participation_estimate_unknown_when_missing_start_date():
    tables = _selected_setup(None, None)
    result = institution_internship_service.get_internship_detail(_FakeClient(tables, rpc_results=_rpc()), "inst-1", "i1")
    assert result["participation"]["unknown"] == 1
    assert result["participation"]["active"] == 0
    assert result["participation"]["completed"] == 0


def test_non_selected_application_has_no_participation_estimate():
    tables = _selected_setup(None, None, today_application_status="APPLIED")
    result = institution_internship_service.get_internship_detail(_FakeClient(tables, rpc_results=_rpc()), "inst-1", "i1")
    assert result["applicants"][0]["participation_estimate"] is None
    assert sum(result["participation"].values()) == 0


def test_eligibility_criteria_surfaced_as_raw_text_only():
    tables = _selected_setup(None, None)
    tables["internships"][0]["eligibility_criteria"] = "CGPA 7+"
    result = institution_internship_service.get_internship_detail(_FakeClient(tables, rpc_results=_rpc()), "inst-1", "i1")
    assert result["eligibility_criteria"] == "CGPA 7+"
    # No computed per-student eligibility verdict field exists anywhere.
    assert "is_eligible" not in result["applicants"][0]


def test_detail_never_shows_applications_from_unselected_internship():
    """An internship this institution never curated must not leak its
    applicant list through the detail endpoint even if it exists."""
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0}],
        applications=[
            {"id": "a1", "student_id": "s1", "internship_id": "i1", "status": "SELECTED",
             "opportunity_type": "INTERNSHIP", "applied_at": "2026-01-01T00:00:00Z"},
        ],
        internships=[_INTERNSHIP],
    )
    result = institution_internship_service.get_internship_detail(_FakeClient(tables), "inst-1", "i1")
    assert result is None


# ---- overview / KPIs / department / company / stipend ----


def test_overview_empty_institution_is_all_zeros_not_error():
    result = institution_internship_service.compute_internship_overview(_FakeClient(_base_tables()), "inst-1")
    assert result["kpis"] == {
        "curated_internships": 0,
        "active_internships": 0,
        "companies": 0,
        "applicants": 0,
        "selected_students": 0,
        "active_participants": 0,
        "completed_internships": 0,
        "participation_unknown": 0,
    }
    assert result["departments"] == []
    assert result["companies"] == []
    assert result["stipend"]["available"] is False


def test_overview_counts_only_curated_internships_and_companies():
    tables = _base_tables(
        internships=[_INTERNSHIP, {**_INTERNSHIP, "id": "i2", "industry_id": "co-2", "status": "PUBLISHED"}],
        institution_internships=[_curated()],  # only i1 curated
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp"}, {"id": "co-2", "company_name": "Globex"}],
    )
    result = institution_internship_service.compute_internship_overview(_FakeClient(tables), "inst-1")
    assert result["kpis"]["curated_internships"] == 1
    assert result["kpis"]["active_internships"] == 1
    assert result["kpis"]["companies"] == 1


def test_overview_department_breakdown_reuses_selected_count_from_department_service():
    tables = _selected_setup("2020-01-01", 3)
    result = institution_internship_service.compute_internship_overview(
        _FakeClient(tables, rpc_results=_rpc()), "inst-1"
    )
    dept = result["departments"][0]
    assert dept["name"] == "CSE"
    assert dept["participants"] == 1
    assert dept["selected_count"] == 1
    assert dept["completed_count"] == 1
    assert dept["participation_rate"] == 100.0


def test_overview_company_breakdown_distinguishes_selected_from_completed():
    tables = _selected_setup("2020-01-01", 3)
    result = institution_internship_service.compute_internship_overview(
        _FakeClient(tables, rpc_results=_rpc()), "inst-1"
    )
    company = result["companies"][0]
    assert company["company_name"] == "Acme Corp"
    assert company["opportunities"] == 1
    assert company["applicants"] == 1
    assert company["selected"] == 1
    assert company["completed"] == 1


def test_overview_stipend_grouped_by_currency_not_averaged_across_currencies():
    tables = _base_tables(
        internships=[
            {**_INTERNSHIP, "id": "i1", "stipend_amount": 10000, "stipend_currency": "INR"},
            {**_INTERNSHIP, "id": "i2", "stipend_amount": 500, "stipend_currency": "USD"},
            {**_INTERNSHIP, "id": "i3", "stipend_amount": None, "stipend_currency": "INR"},
        ],
        institution_internships=[
            _curated(internship_id="i1"), _curated(internship_id="i2"), _curated(internship_id="i3"),
        ],
    )
    result = institution_internship_service.compute_internship_overview(_FakeClient(tables), "inst-1")
    by_currency = {row["currency"]: row for row in result["stipend"]["by_currency"]}
    assert result["stipend"]["available"] is True
    assert by_currency["INR"]["internship_count"] == 1
    assert by_currency["INR"]["average_stipend"] == 10000
    assert by_currency["USD"]["internship_count"] == 1
    assert by_currency["USD"]["average_stipend"] == 500


def test_overview_excludes_applications_to_uncurated_internships():
    tables = _base_tables(
        student_profiles=[{"id": "s1", "institution_id": "inst-1", "department_id": None, "cgpa": 8.0}],
        applications=[
            {"id": "a1", "student_id": "s1", "internship_id": "i1", "status": "SELECTED",
             "opportunity_type": "INTERNSHIP", "applied_at": "2026-01-01T00:00:00Z"},
        ],
        internships=[_INTERNSHIP],  # never curated
    )
    result = institution_internship_service.compute_internship_overview(_FakeClient(tables), "inst-1")
    assert result["kpis"]["applicants"] == 0
    assert result["kpis"]["selected_students"] == 0


def test_no_fabricated_eligible_students_field_anywhere():
    result = institution_internship_service.compute_internship_overview(_FakeClient(_base_tables()), "inst-1")
    assert "eligibility_note" in result
    assert "curation_note" in result
    assert "eligible" not in result["kpis"]
    for dept in result["departments"]:
        assert "eligible" not in dept
