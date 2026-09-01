"""API routes for the Industry portal.

Phase 2: GET /industry/me -- a role-security probe.
Phase 4: GET / PUT /industry/profile -- the company profile.

Every route is guarded by require_industry() -> get_current_user() (the
verified Supabase token). Ownership is always current_user.id, never a
value from the request body or query string. Reads and writes go through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so Supabase RLS stays the real access-control boundary.
The queries themselves live in app.services.industry_service.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry import (
    IndustryIdentityResponse,
    IndustryProfileResponse,
    IndustryProfileUpdate,
)
from app.services import industry_service

router = APIRouter(prefix="/industry", tags=["industry"])


@router.get("/me", response_model=IndustryIdentityResponse)
def get_industry_me(
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryIdentityResponse:
    """The authenticated INDUSTRY caller's own identity.

    Straight from the token verification + profiles.role lookup that
    require_industry() already performed -- no extra database work, and
    the access token is never echoed back.
    """
    return IndustryIdentityResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
    )


@router.get("/profile", response_model=IndustryProfileResponse)
def get_industry_profile(
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryProfileResponse:
    """The caller's own company profile.

    `industry_profiles` is a lazy 1:1 row -- a brand-new INDUSTRY account
    has none yet. That is not a 404: this returns 200 with `id` set and
    every other field null, so the frontend can render a clean
    "start your company profile" state.
    """
    client = build_user_client(current_user.access_token)
    try:
        row = industry_service.get_profile(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your company profile.",
        ) from exc

    if row is None:
        return IndustryProfileResponse(id=current_user.id)
    return IndustryProfileResponse(**row)


@router.put("/profile", response_model=IndustryProfileResponse)
def update_industry_profile(
    body: IndustryProfileUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryProfileResponse:
    """Create (first save) or replace the caller's own company profile.

    The row id is forced to current_user.id inside the service; nothing
    from `body` can change which row is written. RLS re-checks ownership
    and the INDUSTRY role on both the INSERT and UPDATE paths.
    """
    client = build_user_client(current_user.access_token)
    try:
        row = industry_service.upsert_profile(
            client, current_user.id, body.model_dump()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save your company profile.",
        ) from exc

    return IndustryProfileResponse(**row)
