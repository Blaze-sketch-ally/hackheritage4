"""Shared FastAPI dependencies: current-user resolution and role guards."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import InvalidTokenError, build_user_client, verify_access_token

# auto_error=False so a missing header falls through to our own check below
# instead of HTTPBearer's default 403 -- "not authenticated" should be 401.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, resolved from their Supabase access token."""

    id: str
    email: str | None
    role: str | None
    access_token: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Resolve the authenticated Supabase user making this request.

    Verifies the bearer token against Supabase Auth, then reads the
    caller's own `profiles` row through a client scoped to their own
    token -- an RLS-protected read (auth.uid() = id), never a
    service-role bypass.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )

    token = credentials.credentials

    try:
        user = verify_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from exc

    try:
        client = build_user_client(token)
        response = client.table("profiles").select("role").eq("id", user.id).single().execute()
        role = response.data.get("role") if response.data else None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not resolve the current user's profile.",
        ) from exc

    return CurrentUser(id=user.id, email=user.email, role=role, access_token=token)


def require_student(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Role guard: only STUDENT accounts may proceed."""
    if current_user.role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the STUDENT role.",
        )
    return current_user


def require_industry(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Role guard: only INDUSTRY accounts may proceed.

    Same shape as require_student -- builds on get_current_user() (which
    already verified the Supabase token and resolved profiles.role via an
    RLS-scoped read), and only adds the role check. A NULL role (user
    hasn't finished onboarding) fails this too, since it isn't "INDUSTRY".
    """
    if current_user.role != "INDUSTRY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the INDUSTRY role.",
        )
    return current_user


def require_faculty(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Role guard: only FACULTY accounts may proceed. Same shape as
    require_student/require_industry."""
    if current_user.role != "FACULTY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the FACULTY role.",
        )
    return current_user


def require_institution(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Role guard: only INSTITUTION accounts may proceed. Same shape as
    require_student/require_industry."""
    if current_user.role != "INSTITUTION":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the INSTITUTION role.",
        )
    return current_user


def require_collaboration_party(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Role guard for the shared collaboration-detail endpoint: any of
    the three roles that can legitimately be a party to a collaboration
    (INDUSTRY as initiator, FACULTY/INSTITUTION as recipient). The route
    itself still decides which side of the relationship applies based on
    current_user.role."""
    if current_user.role not in {"INDUSTRY", "FACULTY", "INSTITUTION"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the INDUSTRY, FACULTY, or INSTITUTION role.",
        )
    return current_user


def require_collaboration_recipient(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Role guard for recipient-only collaboration endpoints (incoming
    list, accept, reject): FACULTY or INSTITUTION only."""
    if current_user.role not in {"FACULTY", "INSTITUTION"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the FACULTY or INSTITUTION role.",
        )
    return current_user
