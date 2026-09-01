"""Tests for the Industry company-profile API (Phase 4):
GET / PUT /api/v1/industry/profile.

Same architecture as tests/test_skill_gap.py's API section --
verify_access_token() and build_user_client() are mocked via
tests.conftest.authenticated_as, and the service layer
(app.services.industry_service) is patched so no live Supabase project or
real token is needed.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import industry as industry_routes
from app.main import app
from app.services import industry_service
from tests.conftest import authenticated_as

client = TestClient(app)

_FULL_ROW = {
    "id": "industry-1",
    "company_name": "Acme Robotics",
    "industry_sector": "Manufacturing",
    "company_size": "51-200",
    "website_url": "https://acme.example",
    "company_description": "We build robots.",
    "headquarters_location": "Pune, India",
    "founded_year": 2015,
    "contact_phone": "+91 20 1234 5678",
    "linkedin_url": "https://linkedin.com/company/acme",
    "logo_url": "https://acme.example/logo.png",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-02-01T00:00:00Z",
}


# ---- GET ----


def test_get_profile_as_industry_returns_saved_row():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_service, "get_profile", return_value=dict(_FULL_ROW)),
    ):
        response = client.get(
            "/api/v1/industry/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "industry-1"
    assert body["company_name"] == "Acme Robotics"
    assert body["company_size"] == "51-200"
    assert body["founded_year"] == 2015


def test_get_profile_with_no_row_returns_empty_state_not_404():
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_service, "get_profile", return_value=None),
    ):
        response = client.get(
            "/api/v1/industry/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "industry-1"
    assert body["company_name"] is None
    assert body["company_size"] is None
    assert body["created_at"] is None
    assert body["updated_at"] is None


def test_get_profile_derives_owner_from_token_not_query():
    """The id in the response is always the authenticated caller's own --
    there is no request input that can point it elsewhere."""
    captured = {}

    def fake_get_profile(_client, industry_id):
        # No row saved yet -> the route should still 200 with the caller's id.
        captured["industry_id"] = industry_id

    with (
        authenticated_as("INDUSTRY", user_id="industry-42"),
        patch.object(industry_service, "get_profile", side_effect=fake_get_profile),
    ):
        response = client.get(
            "/api/v1/industry/profile?id=someone-else",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert captured["industry_id"] == "industry-42"
    assert response.json()["id"] == "industry-42"


# ---- PUT ----


def test_put_profile_as_industry_saves_and_returns_row():
    saved = dict(_FULL_ROW)
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_service, "upsert_profile", return_value=saved) as mock_upsert,
    ):
        response = client.put(
            "/api/v1/industry/profile",
            json={"company_name": "Acme Robotics", "company_size": "51-200", "founded_year": 2015},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["company_name"] == "Acme Robotics"
    # ownership arg is the authenticated caller, positionally the 2nd arg
    assert mock_upsert.call_args.args[1] == "industry-1"


def test_put_profile_first_save_with_empty_body_is_allowed():
    """A brand-new INDUSTRY account may save a still-mostly-empty profile
    -- every field is optional."""
    row = {**{k: None for k in _FULL_ROW}, "id": "industry-1"}
    row["created_at"] = "2026-03-01T00:00:00Z"
    row["updated_at"] = "2026-03-01T00:00:00Z"
    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_service, "upsert_profile", return_value=row),
    ):
        response = client.put(
            "/api/v1/industry/profile", json={}, headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200


def test_put_profile_rejects_client_supplied_id():
    """extra='forbid' on IndustryProfileUpdate is what structurally stops
    a client smuggling an id (or a student_id, etc.) into the body."""
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.put(
            "/api/v1/industry/profile",
            json={"company_name": "Acme", "id": "attacker-owned-row"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_put_profile_blank_strings_are_normalised_to_null():
    captured = {}

    def fake_upsert(_client, _industry_id, fields):
        captured.update(fields)
        return {**{k: None for k in _FULL_ROW}, "id": "industry-1"}

    with (
        authenticated_as("INDUSTRY", user_id="industry-1"),
        patch.object(industry_service, "upsert_profile", side_effect=fake_upsert),
    ):
        response = client.put(
            "/api/v1/industry/profile",
            json={"company_name": "  Acme  ", "industry_sector": "", "contact_phone": "   "},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert captured["company_name"] == "Acme"
    assert captured["industry_sector"] is None
    assert captured["contact_phone"] is None


def test_put_profile_rejects_bad_phone():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.put(
            "/api/v1/industry/profile",
            json={"contact_phone": "not a phone number!!"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_put_profile_rejects_out_of_range_founded_year():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.put(
            "/api/v1/industry/profile",
            json={"founded_year": 1500},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_put_profile_rejects_unknown_company_size():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.put(
            "/api/v1/industry/profile",
            json={"company_size": "HUGE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


# ---- role / auth guards ----


def test_get_profile_unauthenticated_returns_401():
    assert client.get("/api/v1/industry/profile").status_code == 401


def test_put_profile_unauthenticated_returns_401():
    assert client.put("/api/v1/industry/profile", json={}).status_code == 401


def test_get_profile_student_forbidden():
    with authenticated_as("STUDENT"):
        response = client.get(
            "/api/v1/industry/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_get_profile_faculty_forbidden():
    with authenticated_as("FACULTY"):
        response = client.get(
            "/api/v1/industry/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_get_profile_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.get(
            "/api/v1/industry/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_get_profile_null_role_forbidden():
    with authenticated_as(None):
        response = client.get(
            "/api/v1/industry/profile", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_put_profile_student_forbidden():
    with authenticated_as("STUDENT"):
        response = client.put(
            "/api/v1/industry/profile",
            json={"company_name": "X"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_put_profile_institution_forbidden():
    with authenticated_as("INSTITUTION"):
        response = client.put(
            "/api/v1/industry/profile",
            json={"company_name": "X"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


# ---- RLS boundary: no service-role anywhere on this path ----


def test_industry_service_module_has_no_service_role_access():
    assert not hasattr(industry_service, "get_supabase")


def test_industry_routes_use_user_scoped_client_not_service_role():
    assert hasattr(industry_routes, "build_user_client")
    assert not hasattr(industry_routes, "get_supabase")
