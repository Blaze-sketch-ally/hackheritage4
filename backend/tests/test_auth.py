"""Tests for the authentication foundation (Phase 1A):
get_current_user() and require_student().

No live Supabase project is required -- verify_access_token() and
build_user_client() are mocked so these run offline and deterministically.
"""

from unittest.mock import MagicMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import CurrentUser, get_current_user, require_student
from app.core.security import InvalidTokenError

# A throwaway app exists only to exercise get_current_user()/require_student()
# through FastAPI's real dependency-injection pipeline (header parsing,
# Depends resolution, HTTPException handling) rather than calling them as
# plain functions.
_test_app = FastAPI()


@_test_app.get("/whoami")
def _whoami(current_user: CurrentUser = Depends(get_current_user)):
    return {"id": current_user.id, "role": current_user.role}


@_test_app.get("/student-only")
def _student_only(current_user: CurrentUser = Depends(require_student)):
    return {"id": current_user.id}


client = TestClient(_test_app)


def _mock_supabase_user(user_id: str = "user-123", email: str = "student@example.com"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


def _mock_client_with_role(role: str | None):
    mock_table = MagicMock()
    mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        {"role": role} if role is not None else None
    )
    mock_client = MagicMock()
    mock_client.table.return_value = mock_table
    return mock_client


def test_no_token_returns_401():
    response = client.get("/whoami")
    assert response.status_code == 401


def test_invalid_token_returns_401():
    with patch(
        "app.core.dependencies.verify_access_token",
        side_effect=InvalidTokenError("bad token"),
    ):
        response = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_valid_student_is_allowed():
    with (
        patch("app.core.dependencies.verify_access_token", return_value=_mock_supabase_user()),
        patch(
            "app.core.dependencies.build_user_client",
            return_value=_mock_client_with_role("STUDENT"),
        ),
    ):
        response = client.get("/student-only", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json()["id"] == "user-123"


def test_valid_non_student_returns_403():
    with (
        patch("app.core.dependencies.verify_access_token", return_value=_mock_supabase_user()),
        patch(
            "app.core.dependencies.build_user_client",
            return_value=_mock_client_with_role("FACULTY"),
        ),
    ):
        response = client.get("/student-only", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 403


def test_null_role_is_treated_as_non_student():
    """A profile that hasn't completed onboarding yet (role is NULL)
    must not pass require_student()."""
    with (
        patch("app.core.dependencies.verify_access_token", return_value=_mock_supabase_user()),
        patch(
            "app.core.dependencies.build_user_client",
            return_value=_mock_client_with_role(None),
        ),
    ):
        response = client.get("/student-only", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 403
