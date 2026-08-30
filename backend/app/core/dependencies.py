"""Shared FastAPI dependencies (current-user, role guards)."""

from fastapi import Header, HTTPException, status
from supabase import Client

from app.core.security import get_authenticated_user_id
from app.database.supabase import get_supabase


def _resolve_supabase() -> Client:
    """Constructs (or returns the already-cached) service_role Supabase
    client, converting a construction failure into a clean 503.

    Deliberately NOT wired in as a sibling `Depends(get_supabase)` on
    get_current_student_id below — FastAPI resolves every parameter-level
    dependency before a function's body ever runs, so a sibling
    dependency here would make the "is there even an Authorization
    header" check unreachable whenever Supabase can't be constructed
    (e.g. empty SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY) — every request,
    authenticated or not, would crash with an unhandled 500 before the
    header was ever inspected. This was a real bug, found via live
    testing: an unauthenticated request returned 500 instead of 401.

    Calling this explicitly, only after the header/token shape has
    already been validated, fixes that: a missing/malformed
    Authorization header now always returns 401 with zero Supabase
    involvement, regardless of backend configuration. A genuine
    Supabase-client construction failure (server misconfiguration, not
    the caller's fault) is reported as 503, never masqueraded as a 401 —
    conflating "we can't verify you" with "your credentials are invalid"
    would be exactly the kind of overly-broad error handling that turns
    a real server problem into a misleading response.
    """
    try:
        return get_supabase()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        ) from exc


async def get_current_student_id(authorization: str | None = Header(default=None)) -> str:
    """Resolves the caller's user id from the `Authorization: Bearer <token>`
    header and verifies their `profiles.role` is STUDENT — the same
    condition the database's own `public.is_student(auth.uid())` checks,
    reimplemented here because this backend's queries run as
    `service_role` (see app/database/supabase.py), which bypasses RLS
    entirely. Never trusts a client-supplied student/user id anywhere.
    """
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    supabase = _resolve_supabase()
    user_id = get_authenticated_user_id(supabase, token)

    profile = supabase.table("profiles").select("role").eq("id", user_id).maybe_single().execute()
    role = profile.data.get("role") if profile.data else None

    if role != "STUDENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students may perform this action.")

    return user_id
