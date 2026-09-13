"""API route for the cross-module Industry Participant view.

Guarded by require_industry(); every read goes through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role. Composes the four existing, already ownership-scoped
Applicants list functions (Job/Internship via `applications`, Project,
Workshop, Training) into one normalized feed -- see
app.services.industry_participant_service. No new table, no new RLS
boundary: ownership is exactly what those four functions already enforce.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry_participant import ParticipantListResponse, ParticipantOpportunityType
from app.services import industry_participant_service

router = APIRouter(prefix="/industry", tags=["industry-participants"])


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/participants", response_model=ParticipantListResponse)
def list_participants(
    opportunity_type: ParticipantOpportunityType | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_industry),
) -> ParticipantListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_participant_service.list_participants(
            client, current_user.id, opportunity_type=opportunity_type, search=search
        )
    except Exception as exc:
        raise _server_error("load your participants") from exc
    return ParticipantListResponse(records=rows)
