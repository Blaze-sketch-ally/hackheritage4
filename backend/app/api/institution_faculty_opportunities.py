"""API routes for Institution-owned Faculty opportunities
(`institution_faculty_opportunities`) and reviewing the expressions of
interest submitted against them.

Structural twin of api/industry_faculty_opportunities.py -- every route
guarded by require_institution(), build_user_client only, owner always
current_user.id.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.core.dependencies import CurrentUser, require_institution
from app.core.security import build_user_client
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
from app.services import institution_faculty_opportunity_service as service

router = APIRouter(prefix="/institution/faculty-opportunities", tags=["institution-faculty-opportunities"])


def _to_response(row: dict) -> FacultyOpportunityPostingResponse:
    return FacultyOpportunityPostingResponse(**{**row, "owner_id": row["institution_id"]})


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty opportunity not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=FacultyOpportunityPostingListResponse)
def list_own_opportunities(
    current_user: CurrentUser = Depends(require_institution),
) -> FacultyOpportunityPostingListResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_opportunities(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your Faculty opportunities") from exc
    return FacultyOpportunityPostingListResponse(opportunities=[_to_response(r) for r in rows])


@router.post("", response_model=FacultyOpportunityPostingResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    body: FacultyOpportunityPostingCreate,
    current_user: CurrentUser = Depends(require_institution),
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
    current_user: CurrentUser = Depends(require_institution),
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
    current_user: CurrentUser = Depends(require_institution),
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
    current_user: CurrentUser = Depends(require_institution),
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
def list_eois(
    current_user: CurrentUser = Depends(require_institution),
) -> FacultyOpportunityExpressionListResponse:
    try:
        client = build_user_client(current_user.access_token)
        rows = service.list_eois_for_own_opportunities(client, current_user.id)
    except Exception as exc:
        raise _server_error("load expressions of interest") from exc
    return FacultyOpportunityExpressionListResponse(
        expressions=[FacultyOpportunityExpressionResponse(**{**r, "source": "INSTITUTION"}) for r in rows]
    )


@router.patch("/eoi/{eoi_id}/review", response_model=FacultyOpportunityExpressionResponse)
def review_eoi(
    eoi_id: str,
    body: ReviewExpressionRequest,
    current_user: CurrentUser = Depends(require_institution),
) -> FacultyOpportunityExpressionResponse:
    try:
        client = build_user_client(current_user.access_token)
        row = service.review_eoi(client, current_user.id, eoi_id, body.status, body.reviewer_note)
    except service.EoiInvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("update the expression of interest") from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expression of interest not found.")
    return FacultyOpportunityExpressionResponse(**{**row, "source": "INSTITUTION"})
