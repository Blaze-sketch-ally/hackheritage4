"""Tests for the Institution Departments module:
/api/v1/institution/departments..., /api/v1/institution/students/{id}/department.

Route tests mock app.services.institution_department_service and use
tests.conftest.authenticated_as, matching the rest of the institution test
suite. Service tests drive institution_department_service against a fake
Supabase client to verify tenancy isolation, duplicate-name/code handling,
cross-institution assignment rejection, and that placement statistics
reuse the exact same _placement_buckets definition as the Dashboard.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_department_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/departments"
DEPT_ID = "11111111-1111-1111-1111-111111111111"
STUDENT_ID = "22222222-2222-2222-2222-222222222222"


def _department_row(**overrides):
    row = {
        "id": DEPT_ID,
        "name": "CSE",
        "code": "CSE",
        "description": None,
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "student_count": 0,
        "placed_count": 0,
        "unplaced_count": 0,
        "no_applications_count": 0,
        "placement_rate": None,
        "internship_selected_count": 0,
    }
    row.update(overrides)
    return row


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/{DEPT_ID}").status_code == 401
    assert client.post(BASE, json={"name": "CSE"}).status_code == 401
    assert client.put(f"{BASE}/{DEPT_ID}", json={"name": "CSE"}).status_code == 401
    assert (
        client.patch(
            f"/api/v1/institution/students/{STUDENT_ID}/department", json={"department_id": None}
        ).status_code
        == 401
    )


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.post(BASE, json={"name": "CSE"}, headers={"Authorization": "Bearer token"}).status_code
                == 403
            )


# ============================================================
# Route wiring
# ============================================================


def test_list_scopes_to_authenticated_institution():
    captured = {}

    def fake_list(_client, institution_id):
        captured["institution_id"] = institution_id
        return []

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_department_service, "list_departments", side_effect=fake_list),
    ):
        resp = client.get(BASE, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert resp.json() == {"departments": []}
    assert captured["institution_id"] == "institution-1"


def test_get_404_when_not_found_or_not_owned():
    """Institution B requesting Institution A's department gets the same
    404 as a nonexistent id -- indistinguishable, since the service's own
    institution_id-scoped lookup returns None either way."""
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_department_service, "get_department", return_value=None),
    ):
        resp = client.get(f"{BASE}/{DEPT_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_create_derives_institution_from_token_not_body():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["institution_id"] = institution_id
        captured["fields"] = fields
        return _department_row()

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_department_service, "create_department", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={"name": "CSE", "code": "CSE"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["institution_id"] == "institution-1"
    assert captured["fields"]["name"] == "CSE"


def test_create_rejects_client_supplied_institution_id():
    with authenticated_as("INSTITUTION"):
        resp = client.post(
            BASE,
            json={"name": "CSE", "institution_id": "someone-else"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_blank_name():
    with authenticated_as("INSTITUTION"):
        resp = client.post(BASE, json={"name": "   "}, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 422


def test_create_maps_duplicate_to_409():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_department_service,
            "create_department",
            side_effect=institution_department_service.DuplicateDepartmentError("name"),
        ),
    ):
        resp = client.post(BASE, json={"name": "CSE"}, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 409


def test_update_404_when_not_owned():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_department_service, "update_department", return_value=None),
    ):
        resp = client.put(
            f"{BASE}/{DEPT_ID}", json={"name": "New Name"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_update_maps_duplicate_to_409():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_department_service,
            "update_department",
            side_effect=institution_department_service.DuplicateDepartmentError("code"),
        ),
    ):
        resp = client.put(f"{BASE}/{DEPT_ID}", json={"code": "CSE"}, headers={"Authorization": "Bearer token"})
    assert resp.status_code == 409


def test_update_only_sends_explicitly_set_fields():
    captured = {}

    def fake_update(_client, _institution_id, _department_id, fields):
        captured["fields"] = fields
        return _department_row(is_active=False)

    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_department_service, "update_department", side_effect=fake_update),
    ):
        resp = client.put(
            f"{BASE}/{DEPT_ID}", json={"is_active": False}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["fields"] == {"is_active": False}
    assert resp.json()["is_active"] is False


def test_no_delete_endpoint_exists():
    """There is no DELETE endpoint at all -- deactivation (PUT
    is_active=false) is the only lifecycle action. A DELETE to the same
    path FastAPI already routes GET/PUT for comes back 405 Method Not
    Allowed, not 404 -- proof the path exists but DELETE was never
    registered on it, rather than the path simply not existing."""
    with authenticated_as("INSTITUTION"):
        resp = client.delete(f"{BASE}/{DEPT_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 405


def test_assign_department_scopes_to_authenticated_institution():
    captured = {}

    def fake_assign(_client, institution_id, student_id, department_id):
        captured["institution_id"] = institution_id
        captured["student_id"] = student_id
        captured["department_id"] = department_id
        return {}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_department_service, "assign_student_department", side_effect=fake_assign),
        patch(
            "app.api.institution.institution_student_service.get_student_detail",
            return_value={
                "id": STUDENT_ID,
                "full_name": None,
                "username": None,
                "avatar_url": None,
                "link_request_id": None,
                "department_id": DEPT_ID,
                "department": "CSE",
                "self_reported_department": None,
                "batch": None,
                "degree": None,
                "cgpa": None,
                "percentage": None,
                "profile_completion": 0,
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
                "notes": [],
            },
        ),
    ):
        resp = client.patch(
            f"/api/v1/institution/students/{STUDENT_ID}/department",
            json={"department_id": DEPT_ID},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"institution_id": "institution-1", "student_id": STUDENT_ID, "department_id": DEPT_ID}


def test_assign_department_maps_cross_institution_error_to_422():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_department_service,
            "assign_student_department",
            side_effect=institution_department_service.CrossInstitutionAssignmentError("nope"),
        ),
    ):
        resp = client.patch(
            f"/api/v1/institution/students/{STUDENT_ID}/department",
            json={"department_id": DEPT_ID},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_assign_department_allows_null_to_unassign():
    captured = {}

    def fake_assign(_client, _institution_id, _student_id, department_id):
        captured["department_id"] = department_id
        return {}

    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_department_service, "assign_student_department", side_effect=fake_assign),
        patch(
            "app.api.institution.institution_student_service.get_student_detail",
            return_value=None,
        ),
    ):
        resp = client.patch(
            f"/api/v1/institution/students/{STUDENT_ID}/department",
            json={"department_id": None},
            headers={"Authorization": "Bearer token"},
        )
    # `department_id: null` passes schema validation cleanly and is
    # forwarded through as None (unassign), not rejected as a 422.
    assert "department_id" in captured
    assert captured["department_id"] is None
    assert resp.status_code == 404  # get_student_detail returned None above


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

    def insert(self, payload):
        row = {"id": "new-dept", **payload}
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
        return MagicMock(data=data)


class _FakeQueryWithStore(_FakeQuery):
    def __init__(self, store, name):
        self._store = store
        self._name = name
        super().__init__(store.get(name, []))


class _FakeClient:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQueryWithStore(self._tables, name)


def _base_tables(**overrides):
    tables = {
        "departments": [],
        "student_profiles": [],
        "applications": [],
    }
    tables.update(overrides)
    return tables


def test_list_departments_only_counts_own_institution_students():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        student_profiles=[
            {"id": "s1", "institution_id": "inst-A", "department_id": "d1"},
            # Belongs to a DIFFERENT institution -- must never be counted.
            {"id": "s2", "institution_id": "inst-B", "department_id": "d1"},
        ],
        applications=[
            {"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB"},
            {"id": "a2", "student_id": "s2", "status": "SELECTED", "opportunity_type": "JOB"},
        ],
    )
    result = institution_department_service.list_departments(_FakeClient(tables), "inst-A")
    assert len(result) == 1
    assert result[0]["student_count"] == 1
    assert result[0]["placed_count"] == 1


def test_list_departments_isolated_between_institutions():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
            {"id": "d2", "institution_id": "inst-B", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
    )
    result_a = institution_department_service.list_departments(_FakeClient(tables), "inst-A")
    result_b = institution_department_service.list_departments(_FakeClient(tables), "inst-B")
    assert [d["id"] for d in result_a] == ["d1"]
    assert [d["id"] for d in result_b] == ["d2"]


def test_get_department_returns_none_for_another_institutions_department():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-B", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
    )
    assert institution_department_service.get_department(_FakeClient(tables), "inst-A", "d1") is None


def test_create_department_success():
    tables = _base_tables()
    row = institution_department_service.create_department(
        _FakeClient(tables), "inst-A", {"name": "CSE", "code": "CSE", "description": None}
    )
    assert row["name"] == "CSE"
    assert row["student_count"] == 0
    assert row["placement_rate"] is None


def test_create_department_duplicate_name_case_insensitive():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ]
    )
    try:
        institution_department_service.create_department(
            _FakeClient(tables), "inst-A", {"name": "cse", "code": None, "description": None}
        )
        raised = False
    except institution_department_service.DuplicateDepartmentError as exc:
        raised = True
        assert exc.field == "name"
    assert raised


def test_create_department_same_name_allowed_across_institutions():
    """Institution A and Institution B may both have a "CSE" department."""
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ]
    )
    row = institution_department_service.create_department(
        _FakeClient(tables), "inst-B", {"name": "CSE", "code": None, "description": None}
    )
    assert row["name"] == "CSE"


def test_create_department_duplicate_code_case_insensitive():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "Computer Science", "code": "CSE",
             "description": None, "is_active": True, "created_at": None, "updated_at": None},
        ]
    )
    try:
        institution_department_service.create_department(
            _FakeClient(tables), "inst-A", {"name": "Something Else", "code": "cse", "description": None}
        )
        raised = False
    except institution_department_service.DuplicateDepartmentError as exc:
        raised = True
        assert exc.field == "code"
    assert raised


def test_update_department_excludes_self_from_duplicate_check():
    """Saving a department without changing its own name must not trip
    the duplicate check against itself."""
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ]
    )
    row = institution_department_service.update_department(
        _FakeClient(tables), "inst-A", "d1", {"name": "CSE", "description": "Updated description"}
    )
    assert row is not None
    assert row["description"] == "Updated description"


def test_update_department_returns_none_for_another_institution():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-B", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ]
    )
    assert institution_department_service.update_department(_FakeClient(tables), "inst-A", "d1", {"name": "X"}) is None


def test_deactivating_department_keeps_student_and_stats_intact():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        student_profiles=[{"id": "s1", "institution_id": "inst-A", "department_id": "d1"}],
        applications=[{"id": "a1", "student_id": "s1", "status": "SELECTED", "opportunity_type": "JOB"}],
    )
    row = institution_department_service.update_department(_FakeClient(tables), "inst-A", "d1", {"is_active": False})
    assert row["is_active"] is False
    assert row["student_count"] == 1
    assert row["placed_count"] == 1


def test_placement_rate_matches_dashboard_definition():
    """placed = has >=1 SELECTED application -- the exact same
    _placement_buckets used by institution_service (the Dashboard)."""
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        student_profiles=[
            {"id": "placed", "institution_id": "inst-A", "department_id": "d1"},
            {"id": "applying", "institution_id": "inst-A", "department_id": "d1"},
            {"id": "none", "institution_id": "inst-A", "department_id": "d1"},
        ],
        applications=[
            {"id": "a1", "student_id": "placed", "status": "SELECTED", "opportunity_type": "JOB"},
            {"id": "a2", "student_id": "applying", "status": "APPLIED", "opportunity_type": "JOB"},
        ],
    )
    result = institution_department_service.list_departments(_FakeClient(tables), "inst-A")
    dept = result[0]
    assert dept["student_count"] == 3
    assert dept["placed_count"] == 1
    assert dept["unplaced_count"] == 1
    assert dept["no_applications_count"] == 1
    assert dept["placement_rate"] == round(1 / 3 * 100, 1)


# ---- student <-> department assignment ----


def test_assign_student_to_own_institutions_department_succeeds():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        student_profiles=[{"id": "s1", "institution_id": "inst-A", "department_id": None}],
    )
    result = institution_department_service.assign_student_department(_FakeClient(tables), "inst-A", "s1", "d1")
    assert result["department_id"] == "d1"


def test_assign_student_to_another_institutions_department_is_rejected():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-B", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        student_profiles=[{"id": "s1", "institution_id": "inst-A", "department_id": None}],
    )
    try:
        institution_department_service.assign_student_department(_FakeClient(tables), "inst-A", "s1", "d1")
        raised = False
    except institution_department_service.CrossInstitutionAssignmentError:
        raised = True
    assert raised


def test_assign_another_institutions_student_is_rejected():
    tables = _base_tables(
        departments=[
            {"id": "d1", "institution_id": "inst-A", "name": "CSE", "code": None, "description": None,
             "is_active": True, "created_at": None, "updated_at": None},
        ],
        student_profiles=[{"id": "s1", "institution_id": "inst-B", "department_id": None}],
    )
    try:
        institution_department_service.assign_student_department(_FakeClient(tables), "inst-A", "s1", "d1")
        raised = False
    except institution_department_service.CrossInstitutionAssignmentError:
        raised = True
    assert raised


def test_assign_none_unassigns_without_department_lookup():
    tables = _base_tables(student_profiles=[{"id": "s1", "institution_id": "inst-A", "department_id": "d1"}])
    result = institution_department_service.assign_student_department(_FakeClient(tables), "inst-A", "s1", None)
    assert result["department_id"] is None


# ============================================================
# RLS boundary: no service-role anywhere on this path
# ============================================================


def test_institution_department_service_has_no_service_role_access():
    assert not hasattr(institution_department_service, "get_supabase")
