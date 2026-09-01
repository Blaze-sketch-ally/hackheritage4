"""Tests for Industry collaborations (Phase 10E): /api/v1/collaborations.

Unlike test_industry_projects.py/test_industry_training.py/
test_industry_workshops.py/test_industry_mentorship.py, this is a
bilateral relationship, not a posting: an INDUSTRY account (industry_id)
and a FACULTY/INSTITUTION account (recipient_id) each see and act on
their own side of the same row. Route tests mock
app.services.industry_collaboration_service and use
tests.conftest.authenticated_as; service tests drive the functions with a
MagicMock Supabase client and patched helpers -- no live project or real
token.

Cross-role RLS isolation (a FACULTY-authenticated request can never touch
an INSTITUTION-targeted row, and vice versa) is enforced at the database
layer by the `recipient_type` column plus the `is_faculty()`/
`is_institution()` checks in 026_industry_collaborations.sql's RLS
policies -- exactly like every prior module's "RLS is the real
access-control boundary" convention, this is not independently
re-verified against a live database here. What IS verified here: the
Python service layer always scopes its query by the caller's own
identity column (industry_id or recipient_id), the role guards
(require_industry / require_collaboration_recipient) correctly gate which
roles can reach which routes, and identity/content fields can never be
supplied or overridden by the client.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import industry_collaborations as collab_routes
from app.main import app
from app.services import industry_collaboration_service
from tests.conftest import authenticated_as

client = TestClient(app)


def _row(**overrides):
    row = {
        "id": "collab-1",
        "industry_id": "industry-1",
        "recipient_id": "faculty-1",
        "recipient_type": "FACULTY",
        "title": "Joint Research Proposal",
        "description": "A proposed research collaboration on applied ML.",
        "status": "DRAFT",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _create_body(**overrides):
    body = {
        "title": "Joint Research Proposal",
        "description": "A proposed research collaboration on applied ML.",
        "recipient_id": str(uuid4()),
    }
    body.update(overrides)
    return body


# ============================================================
# Auth / role guards
# ============================================================

_INDUSTRY_ENDPOINTS = [
    ("get", "/api/v1/collaborations"),
    ("post", "/api/v1/collaborations"),
    ("put", f"/api/v1/collaborations/{uuid4()}"),
    ("post", f"/api/v1/collaborations/{uuid4()}/send"),
    ("post", f"/api/v1/collaborations/{uuid4()}/activate"),
    ("post", f"/api/v1/collaborations/{uuid4()}/complete"),
    ("post", f"/api/v1/collaborations/{uuid4()}/cancel"),
    ("get", "/api/v1/collaborations/recipients/resolve?identifier=someone"),
]

_RECIPIENT_ENDPOINTS = [
    ("get", "/api/v1/collaborations/incoming"),
    ("post", f"/api/v1/collaborations/{uuid4()}/accept"),
    ("post", f"/api/v1/collaborations/{uuid4()}/reject"),
]

_SHARED_ENDPOINTS = [("get", f"/api/v1/collaborations/{uuid4()}")]


def _call(method: str, url: str, *, headers=None):
    if method in {"post", "put"}:
        return getattr(client, method)(url, json=_create_body(), headers=headers)
    return getattr(client, method)(url, headers=headers)


def test_all_endpoints_reject_unauthenticated():
    for method, url in _INDUSTRY_ENDPOINTS + _RECIPIENT_ENDPOINTS + _SHARED_ENDPOINTS:
        assert _call(method, url).status_code == 401, (method, url)


def test_industry_endpoints_forbid_non_industry_roles():
    for role in ("STUDENT", "FACULTY", "INSTITUTION", None):
        for method, url in _INDUSTRY_ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


def test_recipient_endpoints_allow_faculty_and_institution_but_not_industry_or_student():
    for role in ("FACULTY", "INSTITUTION"):
        for method, url in _RECIPIENT_ENDPOINTS:
            with (
                authenticated_as(role),
                patch.object(industry_collaboration_service, "list_incoming_collaborations", return_value=[]),
                patch.object(industry_collaboration_service, "accept_collaboration", return_value=_row()),
                patch.object(industry_collaboration_service, "reject_collaboration", return_value=_row()),
            ):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code != 403, (role, method, url)

    for role in ("STUDENT", "INDUSTRY"):
        for method, url in _RECIPIENT_ENDPOINTS:
            with authenticated_as(role):
                resp = _call(method, url, headers={"Authorization": "Bearer token"})
            assert resp.status_code == 403, (role, method, url)


def test_shared_detail_endpoint_forbids_student():
    with authenticated_as("STUDENT"):
        resp = client.get(f"/api/v1/collaborations/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 403


# ============================================================
# Recipient resolution
# ============================================================


def test_resolve_recipient_returns_minimal_fields():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "resolve_recipient",
            return_value={"id": "faculty-1", "role": "FACULTY", "full_name": "Dr. Rao"},
        ),
    ):
        resp = client.get(
            "/api/v1/collaborations/recipients/resolve?identifier=drrao",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"id", "role", "full_name"}
    assert body["role"] == "FACULTY"


def test_resolve_recipient_404_when_not_found():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_collaboration_service, "resolve_recipient", return_value=None),
    ):
        resp = client.get(
            "/api/v1/collaborations/recipients/resolve?identifier=nobody",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


# ============================================================
# Industry: create
# ============================================================


def test_create_derives_owner_from_token_and_starts_draft():
    captured = {}

    def fake_create(_client, industry_id, data):
        captured.update({"industry_id": industry_id, "data": data})
        return _row(industry_id=industry_id, status="DRAFT")

    with (
        authenticated_as("INDUSTRY", user_id="industry-99"),
        patch.object(industry_collaboration_service, "create_collaboration", side_effect=fake_create),
    ):
        resp = client.post(
            "/api/v1/collaborations", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 201
    assert captured["industry_id"] == "industry-99"
    assert "industry_id" not in captured["data"]
    assert "status" not in captured["data"]
    assert "recipient_type" not in captured["data"]
    assert resp.json()["status"] == "DRAFT"


def test_create_rejects_client_supplied_industry_id():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/collaborations",
            json=_create_body(industry_id="attacker-owned"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_status():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/collaborations",
            json=_create_body(status="ACTIVE"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_client_supplied_recipient_type():
    """recipient_type must never be accepted from the client -- it is
    derived server-side (by a database trigger) from recipient_id's real
    role. extra="forbid" rejects any attempt to smuggle it into the
    create payload."""
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/collaborations",
            json=_create_body(recipient_type="INSTITUTION"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_rejects_missing_title():
    body = _create_body()
    del body["title"]
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/collaborations", json=body, headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


def test_create_rejects_invalid_recipient_id_format():
    with authenticated_as("INDUSTRY"):
        resp = client.post(
            "/api/v1/collaborations",
            json=_create_body(recipient_id="not-a-uuid"),
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_create_maps_invalid_recipient_to_422():
    """The database trigger rejects a recipient that doesn't exist or
    isn't FACULTY/INSTITUTION -- surfaced by the service as
    InvalidRecipientError, mapped to a 422 here."""
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "create_collaboration",
            side_effect=industry_collaboration_service.InvalidRecipientError("not eligible"),
        ),
    ):
        resp = client.post(
            "/api/v1/collaborations", json=_create_body(), headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 422


# ============================================================
# Industry: list / detail / update -- ownership
# ============================================================


def test_list_returns_only_callers_collaborations():
    captured = {}

    def fake_list(_client, industry_id, *, status=None, search=None):
        captured.update({"industry_id": industry_id, "status": status, "search": search})
        return [_row()]

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_collaboration_service, "list_collaborations", side_effect=fake_list),
    ):
        resp = client.get(
            "/api/v1/collaborations?status=SENT&search=research",
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200
    assert captured == {"industry_id": "industry-1", "status": "SENT", "search": "research"}
    assert resp.json()["collaborations"][0]["id"] == "collab-1"


def test_industry_isolation_get_detail_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(
            industry_collaboration_service, "get_own_collaboration", return_value=None
        ) as mock_get,
    ):
        resp = client.get(
            f"/api/v1/collaborations/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "industry-A"


def test_update_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY", user_id="industry-A"),
        patch.object(industry_collaboration_service, "update_collaboration", return_value=None),
    ):
        resp = client.put(
            f"/api/v1/collaborations/{uuid4()}",
            json={"title": "New title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 404


def test_update_rejects_status_field():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            f"/api/v1/collaborations/{uuid4()}",
            json={"status": "ACTIVE"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_rejects_recipient_id_field():
    with authenticated_as("INDUSTRY"):
        resp = client.put(
            f"/api/v1/collaborations/{uuid4()}",
            json={"recipient_id": str(uuid4())},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 422


def test_update_rejects_when_not_draft():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "update_collaboration",
            side_effect=industry_collaboration_service.NotDraftError("SENT"),
        ),
    ):
        resp = client.put(
            f"/api/v1/collaborations/{uuid4()}",
            json={"title": "Updated"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 409


def test_update_allowed_while_draft():
    with (
        authenticated_as("INDUSTRY", user_id="industry-7"),
        patch.object(industry_collaboration_service, "update_collaboration", return_value=_row()),
    ):
        resp = client.put(
            f"/api/v1/collaborations/{uuid4()}",
            json={"title": "Updated draft title"},
            headers={"Authorization": "Bearer token"},
        )
    assert resp.status_code == 200


# ============================================================
# Industry: lifecycle endpoints
# ============================================================


def test_send_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_collaboration_service, "send_collaboration", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/send", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_send_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "send_collaboration",
            side_effect=industry_collaboration_service.InvalidStatusTransitionError("SENT", "SENT"),
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/send", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_activate_only_from_accepted():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "activate_collaboration",
            side_effect=industry_collaboration_service.InvalidStatusTransitionError("SENT", "ACTIVE"),
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/activate", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_activate_succeeds_when_accepted():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service, "activate_collaboration", return_value=_row(status="ACTIVE")
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/activate", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


def test_complete_only_from_active():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "complete_collaboration",
            side_effect=industry_collaboration_service.InvalidStatusTransitionError("ACCEPTED", "COMPLETED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/complete", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_cancel_404_when_not_owned():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(industry_collaboration_service, "cancel_collaboration", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/cancel", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_cancel_bad_transition_maps_to_409():
    with (
        authenticated_as("INDUSTRY"),
        patch.object(
            industry_collaboration_service,
            "cancel_collaboration",
            side_effect=industry_collaboration_service.InvalidStatusTransitionError("COMPLETED", "CANCELLED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/cancel", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


# ============================================================
# Recipient: incoming list / accept / reject
# ============================================================


def test_incoming_list_scoped_to_caller():
    captured = {}

    def fake_list(_client, recipient_id, *, status=None):
        captured.update({"recipient_id": recipient_id, "status": status})
        return [_row(status="SENT")]

    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch.object(
            industry_collaboration_service, "list_incoming_collaborations", side_effect=fake_list
        ),
    ):
        resp = client.get(
            "/api/v1/collaborations/incoming?status=SENT", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured == {"recipient_id": "faculty-1", "status": "SENT"}


def test_institution_incoming_list_scoped_to_caller():
    captured = {}

    def fake_list(_client, recipient_id, *, status=None):
        captured.update({"recipient_id": recipient_id})
        return []

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(
            industry_collaboration_service, "list_incoming_collaborations", side_effect=fake_list
        ),
    ):
        resp = client.get("/api/v1/collaborations/incoming", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    assert captured["recipient_id"] == "institution-1"


def test_faculty_recipient_isolation_404_when_not_addressed_to_them():
    with (
        authenticated_as("FACULTY", user_id="faculty-A"),
        patch.object(
            industry_collaboration_service, "get_incoming_collaboration", return_value=None
        ) as mock_get,
    ):
        resp = client.get(f"/api/v1/collaborations/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "faculty-A"


def test_institution_recipient_isolation_404_when_not_addressed_to_them():
    with (
        authenticated_as("INSTITUTION", user_id="institution-A"),
        patch.object(
            industry_collaboration_service, "get_incoming_collaboration", return_value=None
        ) as mock_get,
    ):
        resp = client.get(f"/api/v1/collaborations/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 404
    assert mock_get.call_args.args[1] == "institution-A"


def test_accept_404_when_not_addressed_to_caller():
    with (
        authenticated_as("FACULTY"),
        patch.object(industry_collaboration_service, "accept_collaboration", return_value=None),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/accept", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 404


def test_accept_only_from_sent():
    with (
        authenticated_as("FACULTY"),
        patch.object(
            industry_collaboration_service,
            "accept_collaboration",
            side_effect=industry_collaboration_service.InvalidStatusTransitionError("DRAFT", "ACCEPTED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/accept", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_reject_only_from_sent():
    with (
        authenticated_as("INSTITUTION"),
        patch.object(
            industry_collaboration_service,
            "reject_collaboration",
            side_effect=industry_collaboration_service.InvalidStatusTransitionError("ACCEPTED", "REJECTED"),
        ),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/reject", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 409


def test_accept_succeeds_and_passes_recipient_identity():
    captured = {}

    def fake_accept(_client, recipient_id, collaboration_id):
        captured["recipient_id"] = recipient_id
        return _row(status="ACCEPTED")

    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch.object(industry_collaboration_service, "accept_collaboration", side_effect=fake_accept),
    ):
        resp = client.post(
            f"/api/v1/collaborations/{uuid4()}/accept", headers={"Authorization": "Bearer token"}
        )
    assert resp.status_code == 200
    assert captured["recipient_id"] == "faculty-1"
    assert resp.json()["status"] == "ACCEPTED"


# ============================================================
# Shared detail: routes to the right service function per role
# ============================================================


def test_detail_uses_own_lookup_for_industry():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(
            industry_collaboration_service, "get_own_collaboration", return_value=_row()
        ) as mock_own,
        patch.object(industry_collaboration_service, "get_incoming_collaboration") as mock_incoming,
    ):
        resp = client.get(f"/api/v1/collaborations/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    mock_own.assert_called_once()
    mock_incoming.assert_not_called()


def test_detail_uses_incoming_lookup_for_faculty():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch.object(industry_collaboration_service, "get_own_collaboration") as mock_own,
        patch.object(
            industry_collaboration_service,
            "get_incoming_collaboration",
            return_value=_row(status="SENT"),
        ) as mock_incoming,
    ):
        resp = client.get(f"/api/v1/collaborations/{uuid4()}", headers={"Authorization": "Bearer token"})
    assert resp.status_code == 200
    mock_incoming.assert_called_once()
    mock_own.assert_not_called()


# ============================================================
# Service layer
# ============================================================


def test_create_forces_draft_and_owner_and_drops_junk():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-1"}]

    with patch.object(
        industry_collaboration_service, "get_own_collaboration", return_value=_row(id="new-1")
    ):
        industry_collaboration_service.create_collaboration(
            supabase,
            "industry-1",
            {
                "title": "T",
                "description": "D",
                "recipient_id": "faculty-1",
                "status": "ACTIVE",
                "industry_id": "attacker",
                "recipient_type": "INSTITUTION",
                "id": "x",
            },
        )

    inserted = supabase.table.return_value.insert.call_args_list[0].args[0]
    assert inserted["status"] == "DRAFT"
    assert inserted["industry_id"] == "industry-1"
    assert "id" not in inserted
    assert "recipient_type" not in inserted  # derived by the DB trigger, never sent by this layer


def test_create_maps_insert_failure_to_invalid_recipient_error():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        "Collaboration recipient must be a FACULTY or INSTITUTION account."
    )

    raised = False
    try:
        industry_collaboration_service.create_collaboration(
            supabase, "industry-1", {"title": "T", "description": "D", "recipient_id": "student-1"}
        )
    except industry_collaboration_service.InvalidRecipientError:
        raised = True
    assert raised


def test_update_never_writes_status_or_recipient_fields():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_own_collaboration",
        side_effect=[_row(id="collab-1"), _row(id="collab-1", title="Updated")],
    ):
        industry_collaboration_service.update_collaboration(
            supabase,
            "industry-1",
            "collab-1",
            {"title": "Updated", "status": "ACTIVE", "recipient_id": "someone-else"},
        )
    updated = supabase.table.return_value.update.call_args.args[0]
    assert updated == {"title": "Updated"}


def test_update_blocked_once_sent():
    supabase = MagicMock()
    with patch.object(industry_collaboration_service, "get_own_collaboration", return_value=_row(status="SENT")):
        raised = False
        try:
            industry_collaboration_service.update_collaboration(
                supabase, "industry-1", "collab-1", {"title": "Updated"}
            )
        except industry_collaboration_service.NotDraftError:
            raised = True
    assert raised
    supabase.table.return_value.update.assert_not_called()


def test_update_allowed_while_draft_service_level():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_own_collaboration",
        side_effect=[_row(status="DRAFT"), _row(status="DRAFT", title="Updated")],
    ):
        result = industry_collaboration_service.update_collaboration(
            supabase, "industry-1", "collab-1", {"title": "Updated"}
        )
    assert result["title"] == "Updated"


def test_send_only_from_draft():
    supabase = MagicMock()
    with patch.object(industry_collaboration_service, "get_own_collaboration", return_value=_row(status="SENT")):
        raised = False
        try:
            industry_collaboration_service.send_collaboration(supabase, "industry-1", "collab-1")
        except industry_collaboration_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_send_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_own_collaboration",
        side_effect=[_row(status="DRAFT"), _row(status="SENT")],
    ):
        result = industry_collaboration_service.send_collaboration(supabase, "industry-1", "collab-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "SENT"}
    assert result["status"] == "SENT"


def test_activate_rejects_from_sent():
    supabase = MagicMock()
    with patch.object(industry_collaboration_service, "get_own_collaboration", return_value=_row(status="SENT")):
        raised = False
        try:
            industry_collaboration_service.activate_collaboration(supabase, "industry-1", "collab-1")
        except industry_collaboration_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_activate_allowed_from_accepted():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_own_collaboration",
        side_effect=[_row(status="ACCEPTED"), _row(status="ACTIVE")],
    ):
        result = industry_collaboration_service.activate_collaboration(supabase, "industry-1", "collab-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "ACTIVE"}
    assert result["status"] == "ACTIVE"


def test_complete_allowed_from_active():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_own_collaboration",
        side_effect=[_row(status="ACTIVE"), _row(status="COMPLETED")],
    ):
        result = industry_collaboration_service.complete_collaboration(supabase, "industry-1", "collab-1")
    assert result["status"] == "COMPLETED"


def test_cancel_allowed_from_multiple_states():
    for state in ("DRAFT", "SENT", "ACCEPTED", "ACTIVE"):
        supabase = MagicMock()
        with patch.object(
            industry_collaboration_service,
            "get_own_collaboration",
            side_effect=[_row(status=state), _row(status="CANCELLED")],
        ):
            result = industry_collaboration_service.cancel_collaboration(supabase, "industry-1", "collab-1")
        assert result["status"] == "CANCELLED", state


def test_cancel_rejected_from_terminal_states():
    for state in ("COMPLETED", "CANCELLED", "REJECTED"):
        supabase = MagicMock()
        with patch.object(industry_collaboration_service, "get_own_collaboration", return_value=_row(status=state)):
            raised = False
            try:
                industry_collaboration_service.cancel_collaboration(supabase, "industry-1", "collab-1")
            except industry_collaboration_service.InvalidStatusTransitionError:
                raised = True
        assert raised, state


def test_accept_only_from_sent_service_level():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service, "get_incoming_collaboration", return_value=_row(status="DRAFT")
    ):
        raised = False
        try:
            industry_collaboration_service.accept_collaboration(supabase, "faculty-1", "collab-1")
        except industry_collaboration_service.InvalidStatusTransitionError:
            raised = True
    assert raised


def test_accept_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_incoming_collaboration",
        side_effect=[_row(status="SENT"), _row(status="ACCEPTED")],
    ):
        result = industry_collaboration_service.accept_collaboration(supabase, "faculty-1", "collab-1")
    assert supabase.table.return_value.update.call_args.args[0] == {"status": "ACCEPTED"}
    assert result["status"] == "ACCEPTED"


def test_reject_sets_status_when_valid():
    supabase = MagicMock()
    with patch.object(
        industry_collaboration_service,
        "get_incoming_collaboration",
        side_effect=[_row(status="SENT"), _row(status="REJECTED")],
    ):
        result = industry_collaboration_service.reject_collaboration(supabase, "institution-1", "collab-1")
    assert result["status"] == "REJECTED"


def test_incoming_list_excludes_draft():
    supabase = MagicMock()
    industry_collaboration_service.list_incoming_collaborations(supabase, "faculty-1")
    neq_calls = supabase.table.return_value.select.return_value.eq.return_value.neq.call_args_list
    assert ("status", "DRAFT") in [c.args for c in neq_calls]


def test_resolve_recipient_calls_rpc_with_identifier():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = [
        {"id": "faculty-1", "role": "FACULTY", "full_name": "Dr. Rao"}
    ]
    result = industry_collaboration_service.resolve_recipient(supabase, "drrao")
    supabase.rpc.assert_called_once_with("resolve_collaboration_recipient", {"identifier": "drrao"})
    assert result["role"] == "FACULTY"


def test_resolve_recipient_returns_none_when_empty():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = []
    result = industry_collaboration_service.resolve_recipient(supabase, "nobody")
    assert result is None


# ============================================================
# Counterparty display names (migration 029)
# ============================================================


def test_attach_counterparty_names_merges_from_rpc():
    supabase = MagicMock()
    supabase.rpc.return_value.execute.return_value.data = [
        {
            "collaboration_id": "collab-1",
            "industry_name": "TechNova Solutions (DEMO)",
            "recipient_name": "Dr. Demo Faculty (DEMO)",
        }
    ]
    rows = [_row(id="collab-1"), _row(id="collab-2")]

    industry_collaboration_service._attach_counterparty_names(supabase, rows)

    supabase.rpc.assert_called_once_with(
        "collaboration_counterparty_names", {"collaboration_ids": ["collab-1", "collab-2"]}
    )
    assert rows[0]["industry_name"] == "TechNova Solutions (DEMO)"
    assert rows[0]["recipient_name"] == "Dr. Demo Faculty (DEMO)"
    # a row the function did not resolve (not a party, or no name) -> explicit None
    assert rows[1]["industry_name"] is None
    assert rows[1]["recipient_name"] is None


def test_attach_counterparty_names_tolerates_missing_function():
    """Migration 029 not applied yet: the RPC 404s / raises. The list must
    still come back, just without the names -- the UI falls back to the
    recipient-type label."""
    supabase = MagicMock()
    supabase.rpc.return_value.execute.side_effect = Exception('function does not exist')
    rows = [_row(id="collab-1")]

    result = industry_collaboration_service._attach_counterparty_names(supabase, rows)

    assert result[0]["id"] == "collab-1"
    assert result[0]["industry_name"] is None
    assert result[0]["recipient_name"] is None


def test_attach_counterparty_names_noop_on_empty():
    supabase = MagicMock()
    assert industry_collaboration_service._attach_counterparty_names(supabase, []) == []
    supabase.rpc.assert_not_called()


def test_list_collaborations_enriches_with_counterparty_names():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        _row(id="collab-1")
    ]
    supabase.rpc.return_value.execute.return_value.data = [
        {"collaboration_id": "collab-1", "industry_name": "TechNova Solutions (DEMO)", "recipient_name": "Demo Institution Office (DEMO)"}
    ]

    rows = industry_collaboration_service.list_collaborations(supabase, "industry-1")

    assert rows[0]["recipient_name"] == "Demo Institution Office (DEMO)"
    assert rows[0]["industry_name"] == "TechNova Solutions (DEMO)"


# ============================================================
# No service-role anywhere on this path
# ============================================================


def test_collaboration_modules_do_not_use_service_role():
    assert not hasattr(industry_collaboration_service, "get_supabase")
    assert not hasattr(collab_routes, "get_supabase")
    assert hasattr(collab_routes, "build_user_client")
