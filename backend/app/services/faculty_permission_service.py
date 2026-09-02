"""User-scoped reads/writes for Faculty assessment capabilities: the
self-only read path (Phase F2 foundation) and the ADMIN management path
(Phase F2 admin control, 035_admin_faculty_permission_management.sql).

Every function here still takes a user-scoped Supabase client
(app.core.security.build_user_client) -- including the admin_* functions.
The admin RPCs are SECURITY DEFINER and independently re-check
is_admin(auth.uid()) internally, so a user-scoped client is the correct,
sufficient caller: there is no need for (and no use of) service_role
anywhere in this module.
"""

from postgrest.exceptions import APIError
from supabase import Client

from app.schemas.faculty_permissions import AssessmentCapability


def get_effective_capabilities(client: Client) -> set[AssessmentCapability]:
    """Returns only the caller's active, unexpired capabilities.

    The database RPC is self-only and independently checks the FACULTY role;
    callers never receive raw permission rows or grant/audit metadata.
    """
    response = client.rpc("get_my_assessment_capabilities").execute()
    capabilities: set[AssessmentCapability] = set()
    for row in response.data or []:
        value = row.get("capability") if isinstance(row, dict) else row
        if value is not None:
            capabilities.add(AssessmentCapability(value))
    return capabilities


# ---- Admin management (035_admin_faculty_permission_management.sql) ----


class AdminAuthorizationError(Exception):
    """Raised when an admin_* RPC rejects the caller or the request target
    -- SQLSTATE 42501, covering: caller is not ADMIN, target profile is
    not FACULTY, or a reactivation target is no longer FACULTY. The route
    layer maps this to 403 either way; the RPC's own exception message
    (str(exc)) already distinguishes the specific reason for logging."""


class PermissionNotFoundError(Exception):
    """Raised when an admin_* RPC cannot find the referenced row -- either
    a nonexistent target Faculty profile (admin_grant_assessment_capability)
    or a nonexistent permission_id (admin_set_assessment_permission_status).
    SQLSTATE P0002. Route layer: 404."""


def admin_list_faculty_with_permissions(client: Client) -> list[dict]:
    """Every FACULTY profile and their current capability grants (if
    any), via admin_list_faculty_assessment_permissions(). Grouped here
    from the RPC's flat (one row per capability, or one row with nulls for
    a Faculty member with none) result into one entry per Faculty member.
    """
    try:
        response = client.rpc("admin_list_faculty_assessment_permissions").execute()
    except APIError as exc:
        if exc.code == "42501":
            raise AdminAuthorizationError(str(exc)) from exc
        raise

    faculty_by_id: dict[str, dict] = {}
    for row in response.data or []:
        faculty_id = row["faculty_id"]
        entry = faculty_by_id.setdefault(
            faculty_id,
            {
                "faculty_id": faculty_id,
                "email": row["faculty_email"],
                "username": row["faculty_username"],
                "full_name": row["faculty_full_name"],
                "permissions": [],
            },
        )
        if row["permission_id"] is not None:
            entry["permissions"].append(
                {
                    "permission_id": row["permission_id"],
                    "capability": row["capability"],
                    "status": row["status"],
                    "granted_by": row["granted_by"],
                    "status_changed_by": row["status_changed_by"],
                    "expires_at": row["expires_at"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
    return list(faculty_by_id.values())


def admin_grant_capability(
    client: Client,
    faculty_id: str,
    capability: AssessmentCapability,
    expires_at: str | None,
) -> dict:
    """Grant (or re-grant) one capability to one Faculty member via
    admin_grant_assessment_capability(). See that function's own header
    for why this is an upsert rather than a plain insert."""
    try:
        response = client.rpc(
            "admin_grant_assessment_capability",
            {
                "target_faculty_id": faculty_id,
                "requested_capability": capability.value,
                "capability_expires_at": expires_at,
            },
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


def admin_set_permission_status(client: Client, permission_id: str, new_status: str) -> dict:
    """Change one permission row's status via
    admin_set_assessment_permission_status()."""
    try:
        response = client.rpc(
            "admin_set_assessment_permission_status",
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
