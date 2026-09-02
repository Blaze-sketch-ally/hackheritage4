"""User-scoped reads/writes for the Faculty mentor capability: the
self-only read path and the ADMIN management path
(039_faculty_mentor_permissions.sql).

Every function here takes a user-scoped Supabase client
(app.core.security.build_user_client) -- including the admin_*
functions, which are SECURITY DEFINER and independently re-check
is_admin(auth.uid()) internally. No service_role usage anywhere in this
module, matching app.services.faculty_permission_service.
"""

from postgrest.exceptions import APIError
from supabase import Client


def get_my_mentor_capability(client: Client) -> bool:
    """Whether the caller currently holds the faculty_mentor capability.
    The database RPC is self-only and independently checks the FACULTY
    role."""
    response = client.rpc("get_my_mentor_capability").execute()
    data = response.data
    if isinstance(data, list):
        data = data[0] if data else False
    return bool(data)


# ---- Admin management (039_faculty_mentor_permissions.sql) ----


class AdminAuthorizationError(Exception):
    """Raised when an admin_* RPC rejects the caller or the request
    target -- SQLSTATE 42501. Route layer: 403."""


class PermissionNotFoundError(Exception):
    """Raised when an admin_* RPC cannot find the referenced row --
    SQLSTATE P0002. Route layer: 404."""


def admin_list_faculty_with_mentor_permission(client: Client) -> list[dict]:
    """Every FACULTY profile and their current mentor-capability grant
    (if any), via admin_list_faculty_mentor_permissions()."""
    try:
        response = client.rpc("admin_list_faculty_mentor_permissions").execute()
    except APIError as exc:
        if exc.code == "42501":
            raise AdminAuthorizationError(str(exc)) from exc
        raise

    faculty: list[dict] = []
    for row in response.data or []:
        entry: dict = {
            "faculty_id": row["faculty_id"],
            "email": row["faculty_email"],
            "username": row["faculty_username"],
            "full_name": row["faculty_full_name"],
            "permission": None,
        }
        if row["permission_id"] is not None:
            entry["permission"] = {
                "permission_id": row["permission_id"],
                "status": row["status"],
                "granted_by": row["granted_by"],
                "status_changed_by": row["status_changed_by"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        faculty.append(entry)
    return faculty


def admin_grant_mentor_capability(client: Client, faculty_id: str) -> dict:
    """Grant (or re-grant) the mentor capability to one Faculty member."""
    try:
        response = client.rpc(
            "admin_grant_mentor_capability", {"target_faculty_id": faculty_id}
        ).execute()
    except APIError as exc:
        if exc.code == "P0002":
            raise PermissionNotFoundError(str(exc)) from exc
        if exc.code == "42501":
            raise AdminAuthorizationError(str(exc)) from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def admin_set_mentor_permission_status(client: Client, permission_id: str, new_status: str) -> dict:
    """Change one Faculty member's mentor-capability status."""
    try:
        response = client.rpc(
            "admin_set_mentor_permission_status",
            {"target_permission_id": permission_id, "new_status": new_status},
        ).execute()
    except APIError as exc:
        if exc.code == "P0002":
            raise PermissionNotFoundError(str(exc)) from exc
        if exc.code == "42501":
            raise AdminAuthorizationError(str(exc)) from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data
