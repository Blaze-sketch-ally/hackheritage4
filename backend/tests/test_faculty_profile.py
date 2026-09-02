"""Unit coverage for the Faculty academic profile (Phase F3 subphase 1,
database/migrations/036_faculty_profiles.sql)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import authenticated_as

client = TestClient(app)

_FULL_ROW = {
    "id": "faculty-1",
    "designation": "Professor",
    "department": "Computer Science",
    "institution_name": "AIC Institute",
    "phone": "+91 9876543210",
    "bio": "Teaches distributed systems.",
    "expertise_areas": ["Distributed Systems", "Databases"],
    "years_of_experience": 12,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_read_faculty_profile(role):
    with authenticated_as(role):
        response = client.get("/api/v1/faculty/profile", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_update_faculty_profile(role):
    with authenticated_as(role):
        response = client.put(
            "/api/v1/faculty/profile",
            json={"designation": "Professor"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_faculty_profile_with_no_row_yet_returns_empty_state_not_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.api.faculty.faculty_profile_service.get_profile", return_value=None),
    ):
        response = client.get("/api/v1/faculty/profile", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": "faculty-1",
        "designation": None,
        "department": None,
        "institution_name": None,
        "phone": None,
        "bio": None,
        "expertise_areas": [],
        "years_of_experience": None,
        "created_at": None,
        "updated_at": None,
        "completeness": 0.0,
    }


def test_faculty_profile_returns_existing_row_with_completeness():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.api.faculty.faculty_profile_service.get_profile", return_value=_FULL_ROW),
    ):
        response = client.get("/api/v1/faculty/profile", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    body = response.json()
    assert body["designation"] == "Professor"
    assert body["expertise_areas"] == ["Distributed Systems", "Databases"]
    assert body["completeness"] == 1.0  # every counted field filled in


def test_faculty_profile_completeness_reflects_partially_filled_fields():
    partial = {**_FULL_ROW, "department": None, "phone": None, "expertise_areas": []}
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch("app.api.faculty.faculty_profile_service.get_profile", return_value=partial),
    ):
        response = client.get("/api/v1/faculty/profile", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    # 4 of 7 counted fields filled: designation, institution_name, bio, years_of_experience
    assert response.json()["completeness"] == round(4 / 7, 2)


def test_faculty_can_update_own_profile_and_ownership_is_always_the_caller():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty.faculty_profile_service.upsert_profile", return_value=_FULL_ROW
        ) as upsert,
    ):
        response = client.put(
            "/api/v1/faculty/profile",
            json={"designation": "Professor", "expertise_areas": ["Databases"]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["designation"] == "Professor"
    # There is no faculty_id/id field on the request body at all
    # (extra="forbid" below proves the client cannot supply one) -- the
    # service is always called with the authenticated caller's own id,
    # which is what makes cross-Faculty-member modification structurally
    # impossible through this endpoint.
    upsert.assert_called_once()
    assert upsert.call_args.args[1] == "faculty-1"


def test_faculty_profile_update_rejects_a_client_supplied_id():
    with authenticated_as("FACULTY", user_id="faculty-1"):
        response = client.put(
            "/api/v1/faculty/profile",
            json={"designation": "Professor", "id": "someone-elses-id"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


@pytest.mark.parametrize("phone", ["not-a-phone!!", "123", "x" * 25])
def test_faculty_profile_rejects_invalid_phone(phone):
    with authenticated_as("FACULTY", user_id="faculty-1"):
        response = client.put(
            "/api/v1/faculty/profile",
            json={"phone": phone},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_faculty_profile_rejects_too_many_expertise_areas():
    with authenticated_as("FACULTY", user_id="faculty-1"):
        response = client.put(
            "/api/v1/faculty/profile",
            json={"expertise_areas": [f"area-{i}" for i in range(26)]},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_faculty_profile_blanks_out_whitespace_only_fields():
    with (
        authenticated_as("FACULTY", user_id="faculty-1"),
        patch(
            "app.api.faculty.faculty_profile_service.upsert_profile", return_value=_FULL_ROW
        ) as upsert,
    ):
        response = client.put(
            "/api/v1/faculty/profile",
            json={"designation": "   ", "department": "CSE"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    sent_fields = upsert.call_args.args[2]
    assert sent_fields["designation"] is None
    assert sent_fields["department"] == "CSE"
