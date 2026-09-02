"""API routes for Industry-owned Faculty opportunities
(`industry_faculty_opportunities`) and reviewing the expressions of
interest submitted against them.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role. The owner is always current_user.id;
`industry_id` is never read from the request. Lifecycle changes go
through the dedicated publish/close endpoints, not PUT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.faculty_engagement import (
    FacultyEngagementListResponse,
    FacultyEngagementResponse,
    UpdateEngagementStatusRequest,
)
from app.schemas.faculty_opportunity_expression import (
    FacultyOpportunityExpressionListResponse,
    FacultyOpportunityExpressionResponse,
    ReviewExpressionRequest,
)
from app.schemas.faculty_opportunity_posting import (
    FacultyOpportunityPostingCreate,
    FacultyOpportunityPostingListResponse,
    FacultyOpportunityPostingResponse,
    FacultyOpportunityPostingUpdate,
)
from app.services import industry_faculty_opportunity_service as service

router = APIRouter(prefix="/industry/faculty-opportunities", tags=["industry-faculty-opportunities"])


def _to_response(row: dict) -> FacultyOpportunityPostingResponse:
    return FacultyOpportunityPostingResponse(**{**row, "owner_id": row["industry_id"]})


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty opportunity not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=FacultyOpportunityPostingListResponse)
def list_own_opportunities(current_user: CurrentUser = Depends(require_industry)) -> FacultyOpportunityPostingListResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_opportunities(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your Faculty opportunities") from exc
    return FacultyOpportunityPostingListResponse(opportunities=[_to_response(r) for r in rows])


@router.post("", response_model=FacultyOpportunityPostingResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    body: FacultyOpportunityPostingCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> FacultyOpportunityPostingResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.create_opportunity(client, current_user.id, body.model_dump())
    except Exception as exc:
        raise _server_error("create the Faculty opportunity") from exc
    return _to_response(row)


@router.put("/{opportunity_id}", response_model=FacultyOpportunityPostingResponse)
def update_opportunity(
    opportunity_id: str,
    body: FacultyOpportunityPostingUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> FacultyOpportunityPostingResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.update_opportunity(
            client, current_user.id, opportunity_id, body.model_dump(exclude_unset=True)
        )
    except Exception as exc:
        raise _server_error("update the Faculty opportunity") from exc
    if row is None:
        raise _not_found()
    return _to_response(row)


@router.post("/{opportunity_id}/publish", response_model=FacultyOpportunityPostingResponse)
def publish_opportunity(
    opportunity_id: str,
    current_user: CurrentUser = Depends(require_industry),
) -> FacultyOpportunityPostingResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.publish_opportunity(client, current_user.id, opportunity_id)
    except service.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("publish the Faculty opportunity") from exc
    if row is None:
        raise _not_found()
    return _to_response(row)


@router.post("/{opportunity_id}/close", response_model=FacultyOpportunityPostingResponse)
def close_opportunity(
    opportunity_id: str,
    current_user: CurrentUser = Depends(require_industry),
) -> FacultyOpportunityPostingResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.close_opportunity(client, current_user.id, opportunity_id)
    except service.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("close the Faculty opportunity") from exc
    if row is None:
        raise _not_found()
    return _to_response(row)


# ---- Expression-of-interest review (owner side) ----


@router.get("/eoi", response_model=FacultyOpportunityExpressionListResponse)
def list_eois(current_user: CurrentUser = Depends(require_industry)) -> FacultyOpportunityExpressionListResponse:
    """Every expression of interest submitted against one of the caller's
    own Faculty opportunities."""
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_eois_for_own_opportunities(client, current_user.id)
    except Exception as exc:
        raise _server_error("load expressions of interest") from exc
    return FacultyOpportunityExpressionListResponse(
        expressions=[FacultyOpportunityExpressionResponse(**{**r, "source": "INDUSTRY"}) for r in rows]
    )


@router.patch("/eoi/{eoi_id}/review", response_model=FacultyOpportunityExpressionResponse)
def review_eoi(
    eoi_id: str,
    body: ReviewExpressionRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> FacultyOpportunityExpressionResponse:
    """Transition one expression of interest submitted against one of the
    caller's own opportunities. Only SUBMITTED->UNDER_REVIEW and
    UNDER_REVIEW->ACCEPTED/REJECTED are legal -- the database trigger
    (guard_faculty_industry_eoi_update) is the real enforcement; the
    service-layer check here exists so an invalid transition comes back
    as a clean 409 rather than a raw database error."""
    try:
        client = build_user_client(current_user.access_token)
        row = service.review_eoi(client, current_user.id, eoi_id, body.status, body.reviewer_note)
    except service.EoiInvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except APIError as exc:
        # From accept_faculty_industry_expression() (Phase F4.1) when
        # status == "ACCEPTED": P0002 (no such EOI) -> 404, 55000 (not
        # UNDER_REVIEW) / 23505 (an Engagement already exists -- the
        # UNIQUE-constraint backstop, not expected in normal operation)
        # -> 409, everything else (42501: not INDUSTRY / not the owner)
        # -> 403.
        if exc.code == "P0002":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if exc.code in ("55000", "23505"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("update the expression of interest") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expression of interest not found.")
    return FacultyOpportunityExpressionResponse(**{**row, "source": "INDUSTRY"})


# ---- Engagements (Phase F4.1) ----
# Created exclusively by accept_faculty_industry_expression() (see
# review_eoi above) -- there is no create endpoint here, only viewing
# and the explicit lifecycle-transition operation below.


@router.get("/engagements", response_model=FacultyEngagementListResponse)
def list_engagements(current_user: CurrentUser = Depends(require_industry)) -> FacultyEngagementListResponse:
    """Every Engagement belonging to one of the caller's own accepted EOIs."""
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_own_engagements(client, current_user.id)
    except Exception as exc:
        raise _server_error("load engagements") from exc
    return FacultyEngagementListResponse(engagements=[FacultyEngagementResponse(**r) for r in rows])


@router.patch("/engagements/{engagement_id}/status", response_model=FacultyEngagementResponse)
def update_engagement_status(
    engagement_id: str,
    body: UpdateEngagementStatusRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> FacultyEngagementResponse:
    """Transition one of the caller's own Engagements. Only
    PLANNED->ACTIVE/CANCELLED and ACTIVE->COMPLETED/CANCELLED are legal --
    the database trigger (guard_faculty_engagement_update) is the real
    enforcement."""
    try:
        client = build_user_client(current_user.access_token)
        row = service.update_engagement_status(
            client,
            current_user.id,
            engagement_id,
            body.status,
            body.model_dump(exclude={"status"}, exclude_unset=True),
        )
    except service.EngagementInvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("update the engagement") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found.")
    return FacultyEngagementResponse(**row)
