"""Faculty-side opportunity discovery and expressions of interest
(Phase F3.2, corrected + extended in Phase F3.4).

Every route is guarded by require_faculty(). Reads/writes go through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so RLS (and, for EOI mutations, the
guard_faculty_*_eoi_update() triggers) stay the real access-control
boundary. This module never writes to industry_faculty_opportunities/
institution_faculty_opportunities themselves -- posting management is
exclusively the owner-side routers (industry_faculty_opportunities.py,
institution_faculty_opportunities.py).

Kept as its own focused router (not folded into faculty.py) -- same
reasoning industry_projects.py is separate from industry.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from postgrest.exceptions import APIError

from app.core.dependencies import CurrentUser, require_faculty
from app.core.security import build_user_client
from app.schemas.faculty_opportunity import (
    OPPORTUNITY_SOURCES,
    FacultyOpportunityListResponse,
)
from app.schemas.faculty_opportunity_expression import (
    ExpressInterestRequest,
    FacultyOpportunityExpressionListResponse,
    FacultyOpportunityExpressionResponse,
)
from app.services import faculty_opportunity_expression_service, faculty_opportunity_service

router = APIRouter(prefix="/faculty/opportunities", tags=["faculty-opportunities"])


def _validate_source(source: str) -> None:
    if source not in OPPORTUNITY_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"source must be one of: {', '.join(OPPORTUNITY_SOURCES)}.",
        )


@router.get("", response_model=FacultyOpportunityListResponse)
def list_faculty_opportunities(
    source: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyOpportunityListResponse:
    """Every currently published Faculty opportunity, optionally filtered
    to one source (INDUSTRY/INSTITUTION). There is no way to request
    DRAFT/CLOSED postings through this endpoint at all, by construction
    (status is never a request parameter here)."""
    sources = None
    if source is not None:
        _validate_source(source)
        sources = [source]

    try:
        client = build_user_client(current_user.access_token)
        opportunities = faculty_opportunity_service.list_published_opportunities(client, sources)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load opportunities.",
        ) from exc

    return FacultyOpportunityListResponse(opportunities=opportunities)


# ---- Expressions of interest (Faculty side) ----
# Registered before the "{source}/{opportunity_id}/..." routes below so
# the literal "eoi" path segment is never shadowed by a path parameter.


@router.get("/eoi/mine", response_model=FacultyOpportunityExpressionListResponse)
def list_my_expressions(
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyOpportunityExpressionListResponse:
    """The caller's own expressions of interest, across both sources."""
    try:
        client = build_user_client(current_user.access_token)
        expressions = faculty_opportunity_expression_service.list_own_expressions(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your expressions of interest.",
        ) from exc
    return FacultyOpportunityExpressionListResponse(
        expressions=[FacultyOpportunityExpressionResponse(**e) for e in expressions]
    )


@router.post("/eoi/{source}/{eoi_id}/withdraw", response_model=FacultyOpportunityExpressionResponse)
def withdraw_expression(
    source: str,
    eoi_id: str,
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyOpportunityExpressionResponse:
    _validate_source(source)
    try:
        client = build_user_client(current_user.access_token)
        row = faculty_opportunity_expression_service.withdraw_expression(
            client, source, current_user.id, eoi_id
        )
    except APIError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not withdraw the expression of interest.",
        ) from exc

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expression of interest not found.")
    return FacultyOpportunityExpressionResponse(**row)


@router.post("/{source}/{opportunity_id}/express-interest", response_model=FacultyOpportunityExpressionResponse)
def express_interest(
    source: str,
    opportunity_id: str,
    body: ExpressInterestRequest,
    current_user: CurrentUser = Depends(require_faculty),
) -> FacultyOpportunityExpressionResponse:
    """Submit an expression of interest against one published Faculty
    opportunity. `opportunity_id` must be a currently PUBLISHED
    opportunity from the given source -- verified explicitly before any
    write, so a stale/closed/draft id gets a clean 404 rather than an
    RLS/constraint error."""
    _validate_source(source)
    try:
        client = build_user_client(current_user.access_token)
        target = faculty_opportunity_service.get_published_opportunity(client, source, opportunity_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No published opportunity found with that id.",
            )
        row = faculty_opportunity_expression_service.express_interest(
            client, source, current_user.id, opportunity_id, body.message
        )
    except HTTPException:
        raise
    except APIError as exc:
        if exc.code == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already expressed interest in this opportunity.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit your expression of interest.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not submit your expression of interest.",
        ) from exc

    return FacultyOpportunityExpressionResponse(**row)
