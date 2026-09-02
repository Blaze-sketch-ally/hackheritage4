"""Unit coverage for Phase F4.2's mentor-capability dependency and admin
management API (039_faculty_mentor_permissions.sql). Mirrors
test_faculty_permissions.py's own structure for the (deliberately
simpler -- one capability, no expiry, no EXPIRED status) mentor axis."""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import CurrentUser, require_mentor_capability
from app.main import app
from tests.conftest import authenticated_as

client = TestClient(app)
_dependency_app = FastAPI()


@_dependency_app.get("/mentor-only")
def mentor_only(current_user: CurrentUser = Depends(require_mentor_capability)):
    return {"id": current_user.id}


dependency_client = TestClient(_dependency_app)


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_read_mentor_capability(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/faculty/me/mentor-capability",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_faculty_without_capability_sees_false():
    with (
        authenticated_as("FACULTY"),
        patch("app.api.faculty.faculty_mentor_permission_service.get_my_mentor_capability", return_value=False),
    ):
        response = client.get(
            "/api/v1/faculty/me/mentor-capability",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() == {"role": "FACULTY", "can_mentor": False}


def test_faculty_with_capability_sees_true():
    with (
        authenticated_as("FACULTY"),
        patch("app.api.faculty.faculty_mentor_permission_service.get_my_mentor_capability", return_value=True),
    ):
        response = client.get(
            "/api/v1/faculty/me/mentor-capability",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() == {"role": "FACULTY", "can_mentor": True}


def test_mentor_capability_dependency_denies_without_grant():
    with (
        authenticated_as("FACULTY"),
        patch(
            "app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability",
            return_value=False,
        ),
    ):
        response = dependency_client.get("/mentor-only", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_mentor_capability_dependency_allows_with_grant():
    with (
        authenticated_as("FACULTY"),
        patch(
            "app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability",
            return_value=True,
        ),
    ):
        response = dependency_client.get("/mentor-only", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_mentor_capability_dependency_keeps_faculty_as_a_prerequisite():
    with (
        authenticated_as("STUDENT"),
        patch(
            "app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability",
            return_value=True,
        ) as resolve,
    ):
        response = dependency_client.get("/mentor-only", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403
    resolve.assert_not_called()


def test_mentor_capability_is_independent_of_assessment_capabilities():
    """A Faculty member with every assessment capability but no mentor
    grant is still denied -- the two trust axes never fall through to
    each other."""
    with (
        authenticated_as("FACULTY"),
        patch("app.core.dependencies.faculty_permission_service.get_effective_capabilities", return_value=set()),
        patch(
            "app.core.dependencies.faculty_mentor_permission_service.get_my_mentor_capability",
            return_value=False,
        ),
    ):
        response = dependency_client.get("/mentor-only", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


# ---- ADMIN management API ----

_ADMIN_ROW = {
    "permission_id": "perm-1",
    "status": "GRANTED",
    "granted_by": "admin-1",
    "status_changed_by": "admin-1",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def test_admin_can_grant_mentor_capability_to_faculty():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_mentor_permission_service.admin_grant_mentor_capability",
            return_value=_ADMIN_ROW,
        ) as grant,
    ):
        response = client.post(
            "/api/v1/admin/faculty/faculty-1/mentor-permission",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "GRANTED"
    grant.assert_called_once()
    assert grant.call_args.args[1] == "faculty-1"


@pytest.mark.parametrize("new_status", ["SUSPENDED", "REVOKED", "GRANTED"])
def test_admin_can_change_mentor_permission_status(new_status):
    row = {**_ADMIN_ROW, "status": new_status}
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_mentor_permission_service.admin_set_mentor_permission_status",
            return_value=row,
        ) as set_status,
    ):
        response = client.patch(
            "/api/v1/admin/faculty/mentor-permissions/perm-1/status",
            json={"status": new_status},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == new_status
    set_status.assert_called_once_with(set_status.call_args.args[0], "perm-1", new_status)


def test_admin_can_list_faculty_with_mentor_permissions():
    listing = [
        {
            "faculty_id": "faculty-1",
            "email": "f@example.com",
            "username": None,
            "full_name": None,
            "permission": _ADMIN_ROW,
        }
    ]
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_mentor_permission_service.admin_list_faculty_with_mentor_permission",
            return_value=listing,
        ),
    ):
        response = client.get(
            "/api/v1/admin/faculty/mentor-permissions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["faculty"][0]["faculty_id"] == "faculty-1"
    assert response.json()["faculty"][0]["permission"]["status"] == "GRANTED"


@pytest.mark.parametrize(
    ("role", "target_id"),
    [
        ("FACULTY", "faculty-1"),  # self-grant attempt
        ("FACULTY", "faculty-2"),  # cross-Faculty grant attempt
        ("STUDENT", "faculty-1"),
        ("INDUSTRY", "faculty-1"),
        ("INSTITUTION", "faculty-1"),
    ],
)
def test_non_admin_cannot_grant_mentor_capability(role, target_id):
    with (
        authenticated_as(role, user_id="faculty-1"),
        patch("app.api.admin_faculty.faculty_mentor_permission_service.admin_grant_mentor_capability") as grant,
    ):
        response = client.post(
            f"/api/v1/admin/faculty/{target_id}/mentor-permission",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    grant.assert_not_called()


@pytest.mark.parametrize("role", ["FACULTY", "STUDENT", "INDUSTRY", "INSTITUTION"])
def test_non_admin_cannot_change_mentor_permission_status(role):
    with (
        authenticated_as(role, user_id="someone-1"),
        patch("app.api.admin_faculty.faculty_mentor_permission_service.admin_set_mentor_permission_status") as set_status,
    ):
        response = client.patch(
            "/api/v1/admin/faculty/mentor-permissions/perm-1/status",
            json={"status": "SUSPENDED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    set_status.assert_not_called()


@pytest.mark.parametrize("role", ["FACULTY", "STUDENT", "INDUSTRY", "INSTITUTION"])
def test_non_admin_cannot_list_mentor_permissions(role):
    with (
        authenticated_as(role, user_id="someone-1"),
        patch("app.api.admin_faculty.faculty_mentor_permission_service.admin_list_faculty_with_mentor_permission") as listing,
    ):
        response = client.get(
            "/api/v1/admin/faculty/mentor-permissions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    listing.assert_not_called()


def test_admin_grant_to_nonexistent_faculty_is_404():
    from app.services import faculty_mentor_permission_service

    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_mentor_permission_service.admin_grant_mentor_capability",
            side_effect=faculty_mentor_permission_service.PermissionNotFoundError("Target user does not exist."),
        ),
    ):
        response = client.post(
            "/api/v1/admin/faculty/nonexistent/mentor-permission",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_admin_status_change_on_nonexistent_permission_is_404():
    from app.services import faculty_mentor_permission_service

    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_mentor_permission_service.admin_set_mentor_permission_status",
            side_effect=faculty_mentor_permission_service.PermissionNotFoundError("Permission not found."),
        ),
    ):
        response = client.patch(
            "/api/v1/admin/faculty/mentor-permissions/nonexistent/status",
            json={"status": "REVOKED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404
