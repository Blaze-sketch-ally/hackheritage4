"""Read-only Faculty-side access to Engagements (Phase F4.1,
`faculty_engagements`, 038_faculty_engagements.sql).

Every route is guarded by require_faculty(). Reads go through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so RLS ("Faculty can view their own engagements") stays
the real access-control boundary. This module never writes to
faculty_engagements at all -- Faculty has no lifecycle-mutating action on
an engagement in this phase, per the approved F4.1 scope. Lifecycle
transitions are exclusively the owning Industry/Institution's routers.

Kept as its own focused router (not folded into faculty_opportunities.py)
-- Engagement is a distinct concept from the EOI/opportunity discovery
that router already covers.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_faculty
from app.core.security import build_user_client
from app.schemas.faculty_engagement import FacultyEngagementListResponse, FacultyEngagementResponse
from app.services import faculty_engagement_service

router = APIRouter(prefix="/faculty/engagements", tags=["faculty-engagements"])


@router.get("", response_model=FacultyEngagementListResponse)
def list_my_engagements(
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyEngagementListResponse:
    """The caller's own engagements, across both Industry and Institution
    sources."""
    try:
        client = build_user_client(current_user.access_token)
        engagements = faculty_engagement_service.list_own_engagements(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your engagements.",
        ) from exc
    return FacultyEngagementListResponse(
        engagements=[FacultyEngagementResponse(**e) for e in engagements]
    )
