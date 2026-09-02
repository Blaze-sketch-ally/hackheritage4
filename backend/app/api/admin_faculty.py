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
from app.schemas.faculty_permissions import (
    AdminFacultyListResponse,
    AdminGrantCapabilityRequest,
    AdminSetPermissionStatusRequest,
    FacultyPermissionAdminResponse,
    FacultyWithPermissionsResponse,
)
from app.services import faculty_permission_service

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
