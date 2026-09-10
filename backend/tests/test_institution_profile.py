"""Tests for the Institution profile API: GET / PUT
/api/v1/institution/profile.

Same architecture as tests/test_industry_profile.py -- verify_access_token()
and build_user_client() are mocked via tests.conftest.authenticated_as,
and the service layer (app.services.institution_service) is patched so no
live Supabase project or real token is needed.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import institution as institution_routes
from app.main import app
from app.services import institution_service
from tests.conftest import authenticated_as

client = TestClient(app)

_FULL_ROW = {
    "id": "institution-1",
    "institution_name": "State College of Engineering",
    "institution_type": "Government",
    "location": "Pune, India",
    "website_url": "https://sce.example",
    "contact_phone": "+91 20 1234 5678",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-02-01T00:00:00Z",
}


# ---- GET ----


def test_get_profile_as_institution_returns_saved_row():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_service, "get_profile", return_value=dict(_FULL_ROW)),
    ):
        response = client.get(
            "/api/v1/institution/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "institution-1"
    assert body["institution_name"] == "State College of Engineering"
    assert body["institution_type"] == "Government"


def test_get_profile_with_no_row_returns_empty_state_not_404():
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_service, "get_profile", return_value=None),
    ):
        response = client.get(
            "/api/v1/institution/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "institution-1"
    assert body["institution_name"] is None
    assert body["created_at"] is None


def test_get_profile_derives_owner_from_token_not_query():
    captured = {}

    def fake_get_profile(_client, institution_id):
        captured["institution_id"] = institution_id

    with (
        authenticated_as("INSTITUTION", user_id="institution-42"),
        patch.object(institution_service, "get_profile", side_effect=fake_get_profile),
    ):
        response = client.get(
            "/api/v1/institution/profile?id=someone-else",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert captured["institution_id"] == "institution-42"
    assert response.json()["id"] == "institution-42"


# ---- PUT ----


def test_put_profile_as_institution_saves_and_returns_row():
    saved = dict(_FULL_ROW)
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_service, "upsert_profile", return_value=saved) as mock_upsert,
    ):
        response = client.put(
            "/api/v1/institution/profile",
            json={"institution_name": "State College of Engineering", "institution_type": "Government"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["institution_name"] == "State College of Engineering"
    assert mock_upsert.call_args.args[1] == "institution-1"


def test_put_profile_first_save_with_empty_body_is_allowed():
    row = {**{k: None for k in _FULL_ROW}, "id": "institution-1"}
    row["created_at"] = "2026-03-01T00:00:00Z"
    row["updated_at"] = "2026-03-01T00:00:00Z"
    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_service, "upsert_profile", return_value=row),
    ):
        response = client.put(
            "/api/v1/institution/profile", json={}, headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200


def test_put_profile_rejects_client_supplied_id():
    with authenticated_as("INSTITUTION", user_id="institution-1"):
        response = client.put(
            "/api/v1/institution/profile",
            json={"institution_name": "X", "id": "attacker-owned-row"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_put_profile_blank_strings_are_normalised_to_null():
    captured = {}

    def fake_upsert(_client, _institution_id, fields):
        captured.update(fields)
        return {**{k: None for k in _FULL_ROW}, "id": "institution-1"}

    with (
        authenticated_as("INSTITUTION", user_id="institution-1"),
        patch.object(institution_service, "upsert_profile", side_effect=fake_upsert),
    ):
        response = client.put(
            "/api/v1/institution/profile",
            json={"institution_name": "  State College  ", "location": "", "contact_phone": "   "},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert captured["institution_name"] == "State College"
    assert captured["location"] is None
    assert captured["contact_phone"] is None


def test_put_profile_rejects_bad_phone():
    with authenticated_as("INSTITUTION", user_id="institution-1"):
        response = client.put(
            "/api/v1/institution/profile",
            json={"contact_phone": "not a phone number!!"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ---- role / auth guards ----


def test_get_profile_unauthenticated_returns_401():
    assert client.get("/api/v1/institution/profile").status_code == 401


def test_put_profile_unauthenticated_returns_401():
    assert client.put("/api/v1/institution/profile", json={}).status_code == 401


def test_get_profile_student_forbidden():
    with authenticated_as("STUDENT"):
        response = client.get(
            "/api/v1/institution/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_get_profile_industry_forbidden():
    with authenticated_as("INDUSTRY"):
        response = client.get(
            "/api/v1/institution/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_put_profile_student_forbidden():
    with authenticated_as("STUDENT"):
        response = client.put(
            "/api/v1/institution/profile",
            json={"institution_name": "X"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ---- RLS boundary: no service-role anywhere on this path ----


def test_institution_service_module_has_no_service_role_access():
    assert not hasattr(institution_service, "get_supabase")


def test_institution_routes_use_user_scoped_client_not_service_role():
    assert hasattr(institution_routes, "build_user_client")
    assert not hasattr(institution_routes, "get_supabase")
