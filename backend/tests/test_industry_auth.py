"""Tests for the Industry role-security foundation (Phase 2):
require_industry() and the GET /api/v1/industry/me probe endpoint.

Mirrors tests/test_auth.py and the API-route tests in
tests/test_skill_gap.py -- verify_access_token() and build_user_client()
are mocked via tests.conftest.authenticated_as, so these run offline with
no live Supabase project or real token.
"""

from fastapi.testclient import TestClient

from app.api import industry as industry_routes
from app.main import app
from tests.conftest import authenticated_as

client = TestClient(app)


def test_industry_me_missing_token_returns_401():
    response = client.get("/api/v1/industry/me")
    assert response.status_code == 401


def test_industry_me_invalid_token_returns_401():
    from unittest.mock import patch

    from app.core.security import InvalidTokenError

    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad token"),
    ):
        response = client.get(
            "/api/v1/industry/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
    assert response.status_code == 401


def test_industry_me_student_role_forbidden():
    with authenticated_as("STUDENT"):
        response = client.get("/api/v1/industry/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_industry_me_faculty_role_forbidden():
    with authenticated_as("FACULTY"):
        response = client.get("/api/v1/industry/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_industry_me_null_role_forbidden():
    """A user who hasn't finished onboarding (role IS NULL) is not INDUSTRY."""
    with authenticated_as(None):
        response = client.get("/api/v1/industry/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_industry_me_industry_role_allowed():
    with authenticated_as("INDUSTRY", user_id="industry-1"):
        response = client.get("/api/v1/industry/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_industry_me_response_identifies_authenticated_role_and_id():
    with authenticated_as("INDUSTRY", user_id="industry-42"):
        response = client.get("/api/v1/industry/me", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "industry-42"
    assert body["role"] == "INDUSTRY"
    # The access token must never be echoed back.
    assert "access_token" not in body
    assert "token" not in body


def test_industry_routes_module_does_not_use_service_role():
    """The Phase 2 probe must not reach for get_supabase() (service_role)
    -- same guard style as test_skill_gap.test_skill_gap_routes_module_uses_build_user_client.
    """
    assert not hasattr(industry_routes, "get_supabase")
