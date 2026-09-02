"""ADMIN-only management of Faculty assessment capabilities (Phase F2's
admin control surface, 035_admin_faculty_permission_management.sql).

Every route here is guarded by require_admin() and every call goes
through build_user_client(current_user.access_token) -- never
get_supabase()/service_role. The three admin_* RPCs this module calls are
SECURITY DEFINER and each independently re-checks is_admin(auth.uid())
internally, so a user-scoped client is sufficient and correct: RLS/RPC
internals remain the real access-control boundary, this router's
require_admin() dependency is the app-layer complement to it, not a
replacement (same relationship require_faculty already has to
is_faculty() elsewhere in this project).

This does NOT expose granted_by/status_changed_by/expires_at to Faculty
anywhere -- that stays exclusive to GET /faculty/me/assessment-capabilities
(backend/app/api/faculty.py), which returns capability names only.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_admin
from app.core.security import build_user_client
from app.schemas.faculty_mentor_permission import (
    AdminFacultyMentorPermissionListResponse,
    AdminSetMentorPermissionStatusRequest,
    FacultyMentorPermissionAdminResponse,
    FacultyWithMentorPermissionResponse,
)
from app.schemas.faculty_permissions import (
    AdminFacultyListResponse,
    AdminGrantCapabilityRequest,
    AdminSetPermissionStatusRequest,
    FacultyPermissionAdminResponse,
    FacultyWithPermissionsResponse,
)
from app.services import faculty_mentor_permission_service, faculty_permission_service

router = APIRouter(prefix="/admin/faculty", tags=["admin-faculty"])


def _forbidden(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/assessment-permissions", response_model=AdminFacultyListResponse)
def list_faculty_assessment_permissions(
    current_user: CurrentUser = Depends(require_admin),
) -> AdminFacultyListResponse:
    """Every Faculty member and their current capability grants."""
    try:
        client = build_user_client(current_user.access_token)
        faculty = faculty_permission_service.admin_list_faculty_with_permissions(client)
    except faculty_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("load Faculty assessment permissions") from exc
    return AdminFacultyListResponse(faculty=faculty)


@router.get(
    "/{faculty_id}/assessment-permissions",
    response_model=FacultyWithPermissionsResponse,
)
def get_faculty_assessment_permissions(
    faculty_id: str,
    current_user: CurrentUser = Depends(require_admin),
) -> FacultyWithPermissionsResponse:
    """One Faculty member's current capability grants."""
    try:
        client = build_user_client(current_user.access_token)
        faculty = faculty_permission_service.admin_list_faculty_with_permissions(client)
    except faculty_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("load Faculty assessment permissions") from exc

    match = next((entry for entry in faculty if entry["faculty_id"] == faculty_id), None)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FACULTY account found with that id.",
        )
    return FacultyWithPermissionsResponse(**match)


@router.post(
    "/{faculty_id}/assessment-permissions",
    response_model=FacultyPermissionAdminResponse,
)
def grant_faculty_assessment_capability(
    faculty_id: str,
    body: AdminGrantCapabilityRequest,
    current_user: CurrentUser = Depends(require_admin),
) -> FacultyPermissionAdminResponse:
    """Grant (or re-grant) one capability to one Faculty member."""
    try:
        client = build_user_client(current_user.access_token)
        expires_at = body.expires_at.isoformat() if body.expires_at else None
        row = faculty_permission_service.admin_grant_capability(
            client, faculty_id, body.capability, expires_at
        )
    except faculty_permission_service.PermissionNotFoundError as exc:
        raise _not_found(exc) from exc
    except faculty_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("grant the assessment capability") from exc
    return FacultyPermissionAdminResponse(**row)


@router.patch(
    "/assessment-permissions/{permission_id}/status",
    response_model=FacultyPermissionAdminResponse,
)
def set_faculty_assessment_permission_status(
    permission_id: str,
    body: AdminSetPermissionStatusRequest,
    current_user: CurrentUser = Depends(require_admin),
) -> FacultyPermissionAdminResponse:
    """Change one permission row's status (GRANTED/SUSPENDED/EXPIRED/REVOKED)."""
    try:
        client = build_user_client(current_user.access_token)
        row = faculty_permission_service.admin_set_permission_status(
            client, permission_id, body.status.value
        )
    except faculty_permission_service.PermissionNotFoundError as exc:
        raise _not_found(exc) from exc
    except faculty_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("update the assessment permission status") from exc
    return FacultyPermissionAdminResponse(**row)


# ---- Mentor capability management (Phase F4.2,
# 039_faculty_mentor_permissions.sql) -- separate trust axis from
# assessment capabilities above; same admin-only, RPC-backed shape. ----


@router.get("/mentor-permissions", response_model=AdminFacultyMentorPermissionListResponse)
def list_faculty_mentor_permissions(
    current_user: CurrentUser = Depends(require_admin),
) -> AdminFacultyMentorPermissionListResponse:
    """Every Faculty member and their current mentor-capability grant."""
    try:
        client = build_user_client(current_user.access_token)
        faculty = faculty_mentor_permission_service.admin_list_faculty_with_mentor_permission(client)
    except faculty_mentor_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("load Faculty mentor permissions") from exc
    return AdminFacultyMentorPermissionListResponse(faculty=faculty)


@router.get("/{faculty_id}/mentor-permission", response_model=FacultyWithMentorPermissionResponse)
def get_faculty_mentor_permission(
    faculty_id: str,
    current_user: CurrentUser = Depends(require_admin),
) -> FacultyWithMentorPermissionResponse:
    """One Faculty member's current mentor-capability grant."""
    try:
        client = build_user_client(current_user.access_token)
        faculty = faculty_mentor_permission_service.admin_list_faculty_with_mentor_permission(client)
    except faculty_mentor_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("load Faculty mentor permissions") from exc

    match = next((entry for entry in faculty if entry["faculty_id"] == faculty_id), None)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FACULTY account found with that id.",
        )
    return FacultyWithMentorPermissionResponse(**match)


@router.post("/{faculty_id}/mentor-permission", response_model=FacultyMentorPermissionAdminResponse)
def grant_faculty_mentor_capability(
    faculty_id: str,
    current_user: CurrentUser = Depends(require_admin),
) -> FacultyMentorPermissionAdminResponse:
    """Grant (or re-grant) the faculty_mentor capability to one Faculty
    member. No request body -- there is exactly one capability."""
    try:
        client = build_user_client(current_user.access_token)
        row = faculty_mentor_permission_service.admin_grant_mentor_capability(client, faculty_id)
    except faculty_mentor_permission_service.PermissionNotFoundError as exc:
        raise _not_found(exc) from exc
    except faculty_mentor_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("grant the mentor capability") from exc
    return FacultyMentorPermissionAdminResponse(**row)


@router.patch(
    "/mentor-permissions/{permission_id}/status",
    response_model=FacultyMentorPermissionAdminResponse,
)
def set_faculty_mentor_permission_status(
    permission_id: str,
    body: AdminSetMentorPermissionStatusRequest,
    current_user: CurrentUser = Depends(require_admin),
) -> FacultyMentorPermissionAdminResponse:
    """Change one Faculty member's mentor-capability status (GRANTED/
    SUSPENDED/REVOKED)."""
    try:
        client = build_user_client(current_user.access_token)
        row = faculty_mentor_permission_service.admin_set_mentor_permission_status(
            client, permission_id, body.status.value
        )
    except faculty_mentor_permission_service.PermissionNotFoundError as exc:
        raise _not_found(exc) from exc
    except faculty_mentor_permission_service.AdminAuthorizationError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise _server_error("update the mentor permission status") from exc
    return FacultyMentorPermissionAdminResponse(**row)
