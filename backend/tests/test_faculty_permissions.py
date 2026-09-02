"""Unit coverage for Phase F2's capability dependencies and self-only API."""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import (
    CurrentUser,
    require_assessment_author,
    require_assessment_evaluator,
    require_assessment_lead,
    require_assessment_moderator,
    require_assessment_reviewer,
)
from app.main import app
from app.schemas.faculty_permissions import AssessmentCapability
from app.services import faculty_permission_service
from tests.conftest import authenticated_as

client = TestClient(app)
_dependency_app = FastAPI()


@_dependency_app.get("/author")
def author_only(current_user: CurrentUser = Depends(require_assessment_author)):
    return {"id": current_user.id}


@_dependency_app.get("/reviewer")
def reviewer_only(current_user: CurrentUser = Depends(require_assessment_reviewer)):
    return {"id": current_user.id}


@_dependency_app.get("/evaluator")
def evaluator_only(current_user: CurrentUser = Depends(require_assessment_evaluator)):
    return {"id": current_user.id}


@_dependency_app.get("/moderator")
def moderator_only(current_user: CurrentUser = Depends(require_assessment_moderator)):
    return {"id": current_user.id}


@_dependency_app.get("/lead")
def lead_only(current_user: CurrentUser = Depends(require_assessment_lead)):
    return {"id": current_user.id}


dependency_client = TestClient(_dependency_app)


@pytest.mark.parametrize("role", ["STUDENT", "INDUSTRY", "INSTITUTION", "ADMIN", None])
def test_non_faculty_cannot_read_faculty_capabilities(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/faculty/me/assessment-capabilities",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_faculty_with_no_capability_receives_empty_effective_list():
    with (
        authenticated_as("FACULTY"),
        patch("app.api.faculty.faculty_permission_service.get_effective_capabilities", return_value=set()),
    ):
        response = client.get(
            "/api/v1/faculty/me/assessment-capabilities",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() == {"role": "FACULTY", "capabilities": []}


def test_faculty_capability_endpoint_returns_only_effective_capabilities():
    granted = {AssessmentCapability.AUTHOR, AssessmentCapability.REVIEWER}
    with (
        authenticated_as("FACULTY"),
        patch("app.api.faculty.faculty_permission_service.get_effective_capabilities", return_value=granted),
    ):
        response = client.get(
            "/api/v1/faculty/me/assessment-capabilities",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "role": "FACULTY",
        "capabilities": ["assessment_author", "assessment_reviewer"],
    }


@pytest.mark.parametrize(
    ("path", "granted", "expected_status"),
    [
        ("/author", {AssessmentCapability.AUTHOR}, 200),
        ("/author", {AssessmentCapability.REVIEWER}, 403),
        ("/reviewer", {AssessmentCapability.REVIEWER}, 200),
        ("/reviewer", {AssessmentCapability.AUTHOR}, 403),
        ("/evaluator", {AssessmentCapability.EVALUATOR}, 200),
        ("/evaluator", {AssessmentCapability.REVIEWER}, 403),
        ("/moderator", {AssessmentCapability.MODERATOR}, 200),
        ("/moderator", {AssessmentCapability.EVALUATOR}, 403),
        ("/lead", {AssessmentCapability.LEAD}, 200),
        ("/lead", {AssessmentCapability.MODERATOR}, 403),
    ],
)
def test_capability_dependencies_do_not_imply_other_capabilities(path, granted, expected_status):
    with (
        authenticated_as("FACULTY"),
        patch("app.core.dependencies.faculty_permission_service.get_effective_capabilities", return_value=granted),
    ):
        response = dependency_client.get(path, headers={"Authorization": "Bearer token"})
    assert response.status_code == expected_status


def test_capability_dependency_keeps_faculty_as_a_prerequisite():
    with (
        authenticated_as("STUDENT"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value={AssessmentCapability.AUTHOR},
        ) as resolve_capabilities,
    ):
        response = dependency_client.get("/author", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403
    resolve_capabilities.assert_not_called()


# ---- ADMIN management API (035_admin_faculty_permission_management.sql) ----

_ADMIN_ROW = {
    "permission_id": "perm-1",
    "capability": "assessment_reviewer",
    "status": "GRANTED",
    "granted_by": "admin-1",
    "status_changed_by": "admin-1",
    "expires_at": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def test_admin_can_grant_capability_to_faculty():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_permission_service.admin_grant_capability",
            return_value=_ADMIN_ROW,
        ) as grant,
    ):
        response = client.post(
            "/api/v1/admin/faculty/faculty-1/assessment-permissions",
            json={"capability": "assessment_reviewer"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "GRANTED"
    grant.assert_called_once()
    assert grant.call_args.args[1] == "faculty-1"


@pytest.mark.parametrize("new_status", ["SUSPENDED", "REVOKED", "GRANTED", "EXPIRED"])
def test_admin_can_change_permission_status(new_status):
    row = {**_ADMIN_ROW, "status": new_status}
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_permission_service.admin_set_permission_status",
            return_value=row,
        ) as set_status,
    ):
        response = client.patch(
            "/api/v1/admin/faculty/assessment-permissions/perm-1/status",
            json={"status": new_status},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == new_status
    set_status.assert_called_once_with(set_status.call_args.args[0], "perm-1", new_status)


def test_admin_can_list_faculty_with_their_capabilities():
    listing = [
        {
            "faculty_id": "faculty-1",
            "email": "f@example.com",
            "username": None,
            "full_name": None,
            "permissions": [_ADMIN_ROW],
        }
    ]
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_permission_service.admin_list_faculty_with_permissions",
            return_value=listing,
        ),
    ):
        response = client.get(
            "/api/v1/admin/faculty/assessment-permissions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert response.json()["faculty"][0]["faculty_id"] == "faculty-1"
    assert response.json()["faculty"][0]["permissions"][0]["status"] == "GRANTED"


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
def test_non_admin_cannot_grant_capability(role, target_id):
    with (
        authenticated_as(role, user_id="faculty-1"),
        patch("app.api.admin_faculty.faculty_permission_service.admin_grant_capability") as grant,
    ):
        response = client.post(
            f"/api/v1/admin/faculty/{target_id}/assessment-permissions",
            json={"capability": "assessment_lead"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    grant.assert_not_called()


@pytest.mark.parametrize("role", ["FACULTY", "STUDENT", "INDUSTRY", "INSTITUTION", None])
def test_non_admin_cannot_change_permission_status(role):
    with (
        authenticated_as(role),
        patch("app.api.admin_faculty.faculty_permission_service.admin_set_permission_status") as set_status,
    ):
        response = client.patch(
            "/api/v1/admin/faculty/assessment-permissions/perm-1/status",
            json={"status": "REVOKED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    set_status.assert_not_called()


@pytest.mark.parametrize("role", ["FACULTY", "STUDENT", "INDUSTRY", "INSTITUTION", None])
def test_non_admin_cannot_list_faculty_permissions(role):
    with authenticated_as(role):
        response = client.get(
            "/api/v1/admin/faculty/assessment-permissions",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_admin_grant_to_non_faculty_target_is_rejected_by_the_database_layer():
    """The RPC's own is_admin/role checks are the real boundary (see
    035_admin_faculty_permission_management.sql); this confirms the
    router correctly surfaces that rejection as 403 rather than 500."""
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_permission_service.admin_grant_capability",
            side_effect=faculty_permission_service.AdminAuthorizationError("target is not FACULTY"),
        ),
    ):
        response = client.post(
            "/api/v1/admin/faculty/student-1/assessment-permissions",
            json={"capability": "assessment_lead"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_admin_grant_to_nonexistent_faculty_is_404():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_permission_service.admin_grant_capability",
            side_effect=faculty_permission_service.PermissionNotFoundError("no such profile"),
        ),
    ):
        response = client.post(
            "/api/v1/admin/faculty/does-not-exist/assessment-permissions",
            json={"capability": "assessment_lead"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_admin_status_change_on_nonexistent_permission_is_404():
    with (
        authenticated_as("ADMIN", user_id="admin-1"),
        patch(
            "app.api.admin_faculty.faculty_permission_service.admin_set_permission_status",
            side_effect=faculty_permission_service.PermissionNotFoundError("no such permission"),
        ),
    ):
        response = client.patch(
            "/api/v1/admin/faculty/assessment-permissions/does-not-exist/status",
            json={"status": "REVOKED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


def test_admin_grant_request_rejects_a_client_supplied_granted_by():
    """Schema-level backstop (belt-and-braces on top of the RPC deriving
    granted_by from auth.uid() server-side): AdminGrantCapabilityRequest
    uses extra='forbid', so a client attempting to smuggle in granted_by
    never even reaches the service layer."""
    with authenticated_as("ADMIN", user_id="admin-1"):
        response = client.post(
            "/api/v1/admin/faculty/faculty-1/assessment-permissions",
            json={"capability": "assessment_lead", "granted_by": "admin-1"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422
