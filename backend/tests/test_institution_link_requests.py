"""Tests for the student <-> institution linking workflow:
/api/v1/institution-links/*.

Same architecture as tests/test_industry_collaborations.py --
verify_access_token() and build_user_client() are mocked via
tests.conftest.authenticated_as, and the service layer
(app.services.institution_link_service) is patched at the route level so
no live Supabase project or real token is needed. Route tests verify
auth/role guards and request/response wiring; service tests drive the
functions directly against a fake Supabase client to verify the
duplicate-request guard, status-transition rules, and RPC-based name
enrichment.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import institution_link_service
from tests.conftest import authenticated_as

client = TestClient(app)

_REQUEST_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "student_id": "student-1",
    "institution_id": "institution-1",
    "status": "PENDING",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


# ============================================================
# Auth / role guards
# ============================================================


def test_all_endpoints_reject_unauthenticated():
    assert client.get("/api/v1/institution-links/resolve?identifier=x").status_code == 401
    assert client.get("/api/v1/institution-links/mine").status_code == 401
    assert client.post("/api/v1/institution-links", json={"institution_id": "x"}).status_code == 401
    assert client.post("/api/v1/institution-links/11111111-1111-1111-1111-111111111111/cancel").status_code == 401
    assert client.get("/api/v1/institution-links/incoming").status_code == 401
    assert client.post("/api/v1/institution-links/11111111-1111-1111-1111-111111111111/approve").status_code == 401
    assert client.post("/api/v1/institution-links/11111111-1111-1111-1111-111111111111/reject").status_code == 401
    assert client.post("/api/v1/institution-links/11111111-1111-1111-1111-111111111111/unlink").status_code == 401


def test_student_only_endpoints_forbid_non_students():
    for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
        with authenticated_as(role):
            assert (
                client.get(
                    "/api/v1/institution-links/mine", headers={"Authorization": "Bearer token"}
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/institution-links",
                    json={"institution_id": "x"},
                    headers={"Authorization": "Bearer token"},
                ).status_code
                == 403
            )


def test_institution_only_endpoints_forbid_non_institutions():
    for role in ("STUDENT", "INDUSTRY", "FACULTY", "ADMIN", None):
        with authenticated_as(role):
            assert (
                client.get(
                    "/api/v1/institution-links/incoming", headers={"Authorization": "Bearer token"}
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/approve",
                    headers={"Authorization": "Bearer token"},
                ).status_code
                == 403
            )


# ============================================================
# Resolution
# ============================================================


def test_resolve_returns_minimal_fields():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            institution_link_service,
            "resolve_institution",
            return_value={"id": "institution-1", "full_name": "State College"},
        ),
    ):
        response = client.get(
            "/api/v1/institution-links/resolve?identifier=state_college",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() == {"id": "institution-1", "full_name": "State College"}


def test_resolve_404_when_not_found():
    with (
        authenticated_as("STUDENT"),
        patch.object(institution_link_service, "resolve_institution", return_value=None),
    ):
        response = client.get(
            "/api/v1/institution-links/resolve?identifier=nope",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


# ============================================================
# Student side
# ============================================================


def test_create_derives_student_from_token_not_body():
    captured = {}

    def fake_create(_client, student_id, institution_id):
        captured["student_id"] = student_id
        captured["institution_id"] = institution_id
        return dict(_REQUEST_ROW)

    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(institution_link_service, "create_request", side_effect=fake_create),
    ):
        response = client.post(
            "/api/v1/institution-links",
            json={"institution_id": "institution-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 201
    assert captured["student_id"] == "student-1"
    assert captured["institution_id"] == "institution-1"


def test_create_rejects_client_supplied_status():
    with authenticated_as("STUDENT"):
        response = client.post(
            "/api/v1/institution-links",
            json={"institution_id": "institution-1", "status": "APPROVED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_maps_already_linked_to_409():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            institution_link_service,
            "create_request",
            side_effect=institution_link_service.AlreadyLinkedError("PENDING"),
        ),
    ):
        response = client.post(
            "/api/v1/institution-links",
            json={"institution_id": "institution-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 409


def test_create_maps_invalid_institution_to_422():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            institution_link_service,
            "create_request",
            side_effect=institution_link_service.InvalidInstitutionError("bad"),
        ),
    ):
        response = client.post(
            "/api/v1/institution-links",
            json={"institution_id": "not-a-real-institution"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_list_mine_scoped_to_caller():
    captured = {}

    def fake_list(_client, student_id):
        captured["student_id"] = student_id
        return [dict(_REQUEST_ROW)]

    with (
        authenticated_as("STUDENT", user_id="student-1"),
        patch.object(institution_link_service, "list_my_requests", side_effect=fake_list),
    ):
        response = client.get(
            "/api/v1/institution-links/mine", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert captured["student_id"] == "student-1"
    assert len(response.json()["requests"]) == 1


def test_cancel_404_when_not_owned():
    with (
        authenticated_as("STUDENT"),
        patch.object(institution_link_service, "cancel_own_request", return_value=None),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/cancel", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_cancel_bad_transition_maps_to_409():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            institution_link_service,
            "cancel_own_request",
            side_effect=institution_link_service.InvalidStatusTransitionError("APPROVED", "CANCELLED"),
        ),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/cancel", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


# ============================================================
# Institution side
# ============================================================


def test_incoming_list_scoped_to_caller():
    captured = {}

    def fake_incoming(_client, institution_id, *, status=None):
        captured["institution_id"] = institution_id
        captured["status"] = status
        return [dict(_REQUEST_ROW)]

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_link_service, "list_incoming", side_effect=fake_incoming),
    ):
        response = client.get(
            "/api/v1/institution-links/incoming?status=PENDING",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert captured["institution_id"] == "institution-1"
    assert captured["status"] == "PENDING"


def test_approve_404_when_not_addressed_to_caller():
    """Institution B trying to approve a request addressed to Institution
    A gets 404, indistinguishable from a nonexistent request -- the
    service's own institution_id-scoped lookup is what enforces this."""
    with (
        authenticated_as("INSTITUTION", user_id="institution-B"),
        patch.object(institution_link_service, "approve_request", return_value=None),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_approve_only_from_pending():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_link_service,
            "approve_request",
            side_effect=institution_link_service.InvalidStatusTransitionError("REJECTED", "APPROVED"),
        ),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


def test_reject_only_from_pending():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_link_service,
            "reject_request",
            side_effect=institution_link_service.InvalidStatusTransitionError("APPROVED", "REJECTED"),
        ),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/reject", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


def test_unlink_only_from_approved():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            institution_link_service,
            "unlink_request",
            side_effect=institution_link_service.InvalidStatusTransitionError("PENDING", "REMOVED"),
        ),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/unlink", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


def test_approve_succeeds_and_passes_institution_identity():
    captured = {}

    def fake_approve(_client, institution_id, request_id):
        captured["institution_id"] = institution_id
        captured["request_id"] = request_id
        return {**_REQUEST_ROW, "status": "APPROVED"}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_link_service, "approve_request", side_effect=fake_approve),
    ):
        response = client.post(
            "/api/v1/institution-links/11111111-1111-1111-1111-111111111111/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert captured == {"institution_id": "institution-1", "request_id": "11111111-1111-1111-1111-111111111111"}


# ============================================================
# Service-level tests -- fake Supabase client
# ============================================================


class _FakeQuery:
    """Reads from -- and insert/update mutate -- the SAME dict objects
    held in the shared `store[name]` list, so a row created or changed by
    one query is visible to the next `client.table(...)` call, matching
    real Postgrest round-trip behaviour closely enough for these tests
    (e.g. create_request's get_own_request re-read after insert)."""

    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name
        self._rows = list(store.get(name, []))
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

    def order(self, *_a, **_k):
        return self

    def insert(self, payload):
        row = {"id": "new-req", **payload}
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


class _FakeClient:
    def __init__(self, tables: dict, rpc_results: dict | None = None):
        self._tables = tables
        self._rpc_results = rpc_results or {}

    def table(self, name):
        return _FakeQuery(self._tables, name)

    def rpc(self, name, _params):
        return MagicMock(execute=lambda: MagicMock(data=self._rpc_results.get(name, [])))


def test_create_request_blocked_when_already_live():
    tables = {"institution_link_requests": [{"student_id": "s1", "status": "PENDING"}]}
    try:
        institution_link_service.create_request(_FakeClient(tables), "s1", "inst-1")
        raised = False
    except institution_link_service.AlreadyLinkedError as exc:
        raised = True
        assert exc.current_status == "PENDING"
    assert raised


def test_create_request_succeeds_when_no_live_request():
    tables = {"institution_link_requests": []}
    row = institution_link_service.create_request(_FakeClient(tables), "s1", "inst-1")
    assert row["student_id"] == "s1"
    assert row["institution_id"] == "inst-1"
    assert row["status"] == "PENDING"


def test_resolve_institution_calls_rpc_with_identifier():
    fake = _FakeClient({}, rpc_results={"resolve_institution_by_username": [{"id": "inst-1", "full_name": "X"}]})
    result = institution_link_service.resolve_institution(fake, "state_college")
    assert result == {"id": "inst-1", "full_name": "X"}


def test_resolve_institution_returns_none_when_empty():
    fake = _FakeClient({}, rpc_results={"resolve_institution_by_username": []})
    assert institution_link_service.resolve_institution(fake, "nope") is None


def test_attach_student_names_tolerates_missing_function():
    class _BoomClient(_FakeClient):
        def rpc(self, name, params):
            raise RuntimeError("function does not exist")

    rows = [dict(_REQUEST_ROW)]
    out = institution_link_service._attach_student_names(_BoomClient({}), rows)
    assert out[0]["student_name"] is None


def test_attach_institution_names_uses_broadly_readable_institution_profiles():
    tables = {"institution_profiles": [{"id": "institution-1", "institution_name": "State College"}]}
    rows = [dict(_REQUEST_ROW)]
    out = institution_link_service._attach_institution_names(_FakeClient(tables), rows)
    assert out[0]["institution_name"] == "State College"


# ============================================================
# RLS boundary: no service-role anywhere on this path
# ============================================================


def test_institution_link_service_has_no_service_role_access():
    assert not hasattr(institution_link_service, "get_supabase")
