"""API routes for Industry Analytics.

One endpoint, one aggregation call. Guarded by require_industry() and run
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so every underlying read is RLS-scoped to
the caller's own rows. `industry_id` is always current_user.id; it is
never read from the request.

Every metric returned is derived live from existing records (applications,
interviews, the six opportunity modules, collaborations). There is no
analytics table. Historical metrics are limited to record-creation dates
-- see analytics_service and the `historical_note` field in the response.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.analytics import IndustryAnalyticsResponse
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/industry", response_model=IndustryAnalyticsResponse)
def get_industry_analytics(
    current_user: CurrentUser = Depends(require_industry),
) -> IndustryAnalyticsResponse:
    """Every dashboard metric for the authenticated Industry account in a
    single response. Empty accounts get an all-zeros payload, not an
    error."""
    client = build_user_client(current_user.access_token)
    try:
        data = analytics_service.compute_industry_analytics(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load analytics. Please try again.",
        ) from exc
    return IndustryAnalyticsResponse(**data)
