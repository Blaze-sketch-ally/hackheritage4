"""Tests for the Institution Industry Connections module (Phase 9):
/api/v1/institution/industry-connections..., database/migrations/
076_institution_industry_connections.sql.

Route tests mock institution_industry_connection_service and use
tests.conftest.authenticated_as, matching the rest of the institution
test suite. Service tests drive institution_industry_connection_service
against a fake Supabase client (table reads + insert/update, same shape
as test_institution_industry_partners.py) -- verifying that a connection
always resolves company display fields from the canonical
industry_profiles (never duplicating them), that only a real INDUSTRY
account can be targeted, tenancy isolation, search/filtering, and that
"removing" a connection is is_active=false, never a delete.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_industry_connection_service
from tests.conftest import authenticated_as

client = TestClient(app)

BASE = "/api/v1/institution/industry-connections"
CONNECTION_ID = "44444444-4444-4444-4444-444444444444"
COMPANY_ID = "33333333-3333-3333-3333-333333333333"


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get(BASE).status_code == 401
    assert client.get(f"{BASE}/{CONNECTION_ID}").status_code == 401
    assert client.post(BASE, json={"industry_id": COMPANY_ID, "contact_name": "X"}).status_code == 401
    assert client.patch(f"{BASE}/{CONNECTION_ID}", json={}).status_code == 401


def test_all_endpoints_forbid_non_institution_roles():
    for role in ("STUDENT", "FACULTY", "INDUSTRY", "ADMIN", None):
        with authenticated_as(role):
            assert client.get(BASE, headers={"Authorization": "Bearer token"}).status_code == 403
            assert (
                client.post(
                    BASE, json={"industry_id": COMPANY_ID, "contact_name": "X"}, headers={"Authorization": "Bearer token"}
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
        patch.object(institution_industry_connection_service, "list_connections", side_effect=fake_list),
    ):
        resp = client.get(
            f"{BASE}?search=acme&contact_type=RECRUITMENT&is_active=true",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["search"] == "acme"
    assert captured["contact_type"] == "RECRUITMENT"
    assert captured["is_active"] is True


def test_create_derives_institution_from_token_not_body():
    captured = {}

    def fake_create(_client, institution_id, fields):
        captured["institution_id"] = institution_id
        captured["fields"] = fields
        return {
            "id": CONNECTION_ID,
            "industry_id": COMPANY_ID,
            "company_name": "Acme Corp",
            "industry_sector": None,
            "logo_url": None,
            "contact_name": "Priya Sharma",
            "designation": "HR Manager",
            "contact_type": "RECRUITMENT",
            "email": None,
            "phone": None,
            "notes": None,
            "is_active": True,
            "created_at": None,
            "updated_at": None,
        }

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_industry_connection_service, "create_connection", side_effect=fake_create),
    ):
        resp = client.post(
            BASE,
            json={"industry_id": COMPANY_ID, "contact_name": "Priya Sharma", "contact_type": "RECRUITMENT"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 201
    assert captured["institution_id"] == "institution-1"
    assert captured["fields"]["industry_id"] == COMPANY_ID


def test_create_rejects_unknown_company():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_industry_connection_service,
            "create_connection",
            side_effect=institution_industry_connection_service.IndustryProfileNotFoundError("not found"),
        ),
    ):
        resp = client.post(
            BASE, json={"industry_id": COMPANY_ID, "contact_name": "X"}, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_invalid_contact_type():
    with authenticated_as("INSTITUTION"):
        resp = client.post(
            BASE,
            json={"industry_id": COMPANY_ID, "contact_name": "X", "contact_type": "NOT_A_TYPE"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_invalid_email_and_phone():
    with authenticated_as("INSTITUTION"):
        resp = client.post(
            BASE,
            json={"industry_id": COMPANY_ID, "contact_name": "X", "email": "not-an-email"},
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 422

        resp = client.post(
            BASE,
            json={"industry_id": COMPANY_ID, "contact_name": "X", "phone": "abc"},
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 422


def test_detail_404_for_untracked_connection():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_industry_connection_service, "get_connection", return_value=None),
    ):
        resp = client.get(f"{BASE}/{CONNECTION_ID}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404


def test_update_404_for_untracked_connection():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(institution_industry_connection_service, "update_connection", return_value=None),
    ):
        resp = client.patch(
            f"{BASE}/{CONNECTION_ID}", json={"is_active": False}, headers={"Authorization": "Bearer token"}
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

    def select(self, *_a, **_kw):
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

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        row = {"id": "new-connection", **payload}
        self._store.setdefault(self._name, []).append(row)
        self._rows = [row]
        return self

    def update(self, payload):
        for row in self._rows:
            row.update(payload)
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
        "institution_industry_connections": [],
        "industry_profiles": [],
    }
    tables.update(overrides)
    return tables


def _connection_row(**overrides):
    row = {
        "id": CONNECTION_ID,
        "institution_id": "inst-1",
        "industry_id": "co-1",
        "contact_name": "Priya Sharma",
        "designation": "HR Manager",
        "contact_type": "RECRUITMENT",
        "email": "priya@acme.example",
        "phone": "9876543210",
        "notes": "Met at campus fair",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ---- list / search / filters ----


def test_list_resolves_company_name_from_industry_profiles():
    tables = _base_tables(
        institution_industry_connections=[_connection_row()],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": "Software", "logo_url": None}],
    )
    result = institution_industry_connection_service.list_connections(_FakeClient(tables), "inst-1")
    assert len(result) == 1
    assert result[0]["company_name"] == "Acme Corp"
    assert result[0]["contact_name"] == "Priya Sharma"


def test_list_search_matches_company_or_contact_name():
    tables = _base_tables(
        institution_industry_connections=[
            _connection_row(id="c1", industry_id="co-1", contact_name="Priya Sharma"),
            _connection_row(id="c2", industry_id="co-2", contact_name="Rahul Verma"),
        ],
        industry_profiles=[
            {"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None},
            {"id": "co-2", "company_name": "Globex Inc", "industry_sector": None, "logo_url": None},
        ],
    )
    result = institution_industry_connection_service.list_connections(_FakeClient(tables), "inst-1", search="acme")
    assert [r["contact_name"] for r in result] == ["Priya Sharma"]

    result = institution_industry_connection_service.list_connections(_FakeClient(tables), "inst-1", search="rahul")
    assert [r["contact_name"] for r in result] == ["Rahul Verma"]


def test_list_filters_by_contact_type_and_active():
    tables = _base_tables(
        institution_industry_connections=[
            _connection_row(id="c1", contact_type="RECRUITMENT", is_active=True),
            _connection_row(id="c2", contact_type="ACADEMIC", is_active=False),
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}],
    )
    result = institution_industry_connection_service.list_connections(
        _FakeClient(tables), "inst-1", contact_type="ACADEMIC"
    )
    assert [r["id"] for r in result] == ["c2"]

    result = institution_industry_connection_service.list_connections(_FakeClient(tables), "inst-1", is_active=True)
    assert [r["id"] for r in result] == ["c1"]


def test_list_isolated_between_institutions():
    tables = _base_tables(
        institution_industry_connections=[
            _connection_row(id="c1", institution_id="inst-A"),
            _connection_row(id="c2", institution_id="inst-B"),
        ],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}],
    )
    result_a = institution_industry_connection_service.list_connections(_FakeClient(tables), "inst-A")
    result_b = institution_industry_connection_service.list_connections(_FakeClient(tables), "inst-B")
    assert [r["id"] for r in result_a] == ["c1"]
    assert [r["id"] for r in result_b] == ["c2"]


# ---- detail ----


def test_get_connection_404_for_other_institution():
    tables = _base_tables(institution_industry_connections=[_connection_row(institution_id="inst-B")])
    result = institution_industry_connection_service.get_connection(_FakeClient(tables), "inst-A", CONNECTION_ID)
    assert result is None


def test_get_connection_never_exposes_notes_to_wrong_institution():
    tables = _base_tables(
        institution_industry_connections=[_connection_row(institution_id="inst-A", notes="Private note")],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}],
    )
    own = institution_industry_connection_service.get_connection(_FakeClient(tables), "inst-A", CONNECTION_ID)
    other = institution_industry_connection_service.get_connection(_FakeClient(tables), "inst-B", CONNECTION_ID)
    assert own is not None and own["notes"] == "Private note"
    assert other is None


# ---- create / update ----


def test_create_connection_requires_real_company():
    tables = _base_tables()
    raised = False
    try:
        institution_industry_connection_service.create_connection(
            _FakeClient(tables), "inst-1", {"industry_id": "co-missing", "contact_name": "X"}
        )
    except institution_industry_connection_service.IndustryProfileNotFoundError:
        raised = True
    assert raised


def test_create_connection_succeeds_for_real_company():
    tables = _base_tables(industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}])
    row = institution_industry_connection_service.create_connection(
        _FakeClient(tables),
        "inst-1",
        {"industry_id": "co-1", "contact_name": "Priya Sharma", "contact_type": "RECRUITMENT", "designation": "HR Manager"},
    )
    assert row["industry_id"] == "co-1"
    assert row["company_name"] == "Acme Corp"
    assert row["contact_name"] == "Priya Sharma"
    assert row["contact_type"] == "RECRUITMENT"


def test_create_connection_allows_multiple_contacts_per_company():
    tables = _base_tables(
        institution_industry_connections=[_connection_row(id="c1")],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}],
    )
    row = institution_industry_connection_service.create_connection(
        _FakeClient(tables), "inst-1", {"industry_id": "co-1", "contact_name": "Second Contact"}
    )
    assert row["contact_name"] == "Second Contact"


def test_update_connection_only_changes_sent_fields():
    tables = _base_tables(
        institution_industry_connections=[_connection_row(notes="Old note")],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}],
    )
    row = institution_industry_connection_service.update_connection(
        _FakeClient(tables), "inst-1", CONNECTION_ID, {"is_active": False}
    )
    assert row["is_active"] is False
    assert row["notes"] == "Old note"


def test_update_connection_404_for_other_institution():
    tables = _base_tables(institution_industry_connections=[_connection_row(institution_id="inst-B")])
    result = institution_industry_connection_service.update_connection(
        _FakeClient(tables), "inst-A", CONNECTION_ID, {"is_active": False}
    )
    assert result is None


def test_deactivate_never_deletes_the_row():
    tables = _base_tables(
        institution_industry_connections=[_connection_row()],
        industry_profiles=[{"id": "co-1", "company_name": "Acme Corp", "industry_sector": None, "logo_url": None}],
    )
    institution_industry_connection_service.update_connection(
        _FakeClient(tables), "inst-1", CONNECTION_ID, {"is_active": False}
    )
    assert len(tables["institution_industry_connections"]) == 1
    assert tables["institution_industry_connections"][0]["is_active"] is False
