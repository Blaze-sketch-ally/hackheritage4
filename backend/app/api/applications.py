"""API routes for applications (Phase 1M) -- the student's own
applications list and industry status updates. Opportunity-scoped
application actions (apply, view applicants) live under
app.api.opportunities instead (POST /opportunities/{id}/applications,
GET /opportunities/{id}/applicants) -- same split as Phase 1K's
assessments.py (owns /assessments/{id}/attempts) vs attempts.py (owns
/attempts/{id}/answers, /submit, /score, /result).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_industry, require_student
from app.core.security import build_user_client
from app.schemas.application import (
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatusUpdateRequest,
)
from app.schemas.portfolio import PortfolioResponse
from app.services import application_service, portfolio_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=ApplicationListResponse)
def list_my_applications(current_user: CurrentUser = Depends(require_student)) -> ApplicationListResponse:
    """The authenticated student's own applications -- identity always
    from the token, never a client-supplied student_id."""
    client = build_user_client(current_user.access_token)
    try:
        rows = application_service.list_student_applications(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load your applications."
        ) from exc
    return ApplicationListResponse(applications=rows)


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
def update_status(
    application_id: UUID,
    payload: ApplicationStatusUpdateRequest,
    current_user: CurrentUser = Depends(require_industry),
) -> ApplicationResponse:
    """Industry-only, scoped to their own opportunities' applicants by
    RLS -- see prevent_unauthorized_application_change
    (024_opportunities_and_applications.sql) for why this can never
    change anything but status, regardless of what a raw REST call
    attempts."""
    client = build_user_client(current_user.access_token)
    try:
        row = application_service.update_application_status(
            client, application_id, payload.status.value
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update this application."
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    return ApplicationResponse(**row)


@router.get("/{application_id}/portfolio", response_model=PortfolioResponse)
def get_application_portfolio(
    application_id: UUID, current_user: CurrentUser = Depends(require_industry)
) -> PortfolioResponse:
    """Phase 1N -- the "Portfolio" step of Industry -> My Opportunities ->
    Applicants -> Applicant -> Portfolio. Security is layered exactly as
    the master prompt requires: (1)-(3) "the application exists, belongs
    to an opportunity, that opportunity belongs to this industry account"
    are all proven together by application_service.get_application()'s
    own RLS-scoped read (its "Industry can view applications for their
    own opportunities" SELECT policy is what makes this return None,
    not another industry's data, for an unrelated caller -- same
    non-leaking 404 as every other Phase 1M ownership check). (4) "the
    portfolio belongs to the student in that application" is then
    independently re-proven by portfolio_projects/
    portfolio_certifications' own RLS policies when
    get_student_portfolio() reads through this SAME caller-scoped
    client -- no service-role client is used anywhere in this route, RLS
    alone is the complete enforcement (see
    app.services.portfolio_service's own docstring)."""
    client = build_user_client(current_user.access_token)
    try:
        application = application_service.get_application(client, application_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load this application."
        ) from exc
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    try:
        portfolio = portfolio_service.get_student_portfolio(client, application["student_id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load this applicant's portfolio."
        ) from exc
    return PortfolioResponse(**portfolio)
