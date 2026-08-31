"""API routes for the student's own digital portfolio (Phase 1N).

RLS (025_portfolio_projects_and_certifications.sql) is the real
enforcement for ownership; this router's own checks are defense in
depth, matching every other router in this codebase. Every route reads/
writes through build_user_client(access_token) -- never get_supabase();
no service-role access exists anywhere in this domain (see
app.services.portfolio_service's own docstring for why RLS alone is
sufficient here, unlike the industry applicant match-score path).

The industry-facing read (GET /applications/{id}/portfolio) lives in
app/api/applications.py instead, alongside that domain's other
industry-facing routes -- not here, since it isn't the student's own
CRUD surface.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.portfolio import (
    CertificationCreateRequest,
    CertificationListResponse,
    CertificationResponse,
    CertificationUpdateRequest,
    PortfolioResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _project_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


def _certification_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found.")


@router.get("", response_model=PortfolioResponse)
def get_my_portfolio(current_user: CurrentUser = Depends(require_student)) -> PortfolioResponse:
    """The authenticated student's own full portfolio -- identity always
    from the token, never a client-supplied student_id."""
    client = build_user_client(current_user.access_token)
    try:
        portfolio = portfolio_service.get_student_portfolio(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load your portfolio."
        ) from exc
    return PortfolioResponse(**portfolio)


# ------------------------------------------------------------
# Projects
# ------------------------------------------------------------


@router.get("/projects", response_model=ProjectListResponse)
def list_my_projects(current_user: CurrentUser = Depends(require_student)) -> ProjectListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = portfolio_service.list_projects(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load your projects."
        ) from exc
    return ProjectListResponse(projects=rows)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest, current_user: CurrentUser = Depends(require_student)
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = portfolio_service.create_project(
            client, current_user.id, payload.model_dump(mode="json")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create this project."
        ) from exc
    return ProjectResponse(**row)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = portfolio_service.get_project(client, project_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load this project."
        ) from exc
    if row is None:
        raise _project_not_found()
    return ProjectResponse(**row)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    current_user: CurrentUser = Depends(require_student),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    update_data = payload.model_dump(mode="json", exclude_unset=True)
    try:
        row = portfolio_service.update_project(client, project_id, update_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update this project."
        ) from exc
    if row is None:
        raise _project_not_found()
    return ProjectResponse(**row)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, current_user: CurrentUser = Depends(require_student)) -> None:
    client = build_user_client(current_user.access_token)
    try:
        deleted = portfolio_service.delete_project(client, project_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete this project."
        ) from exc
    if not deleted:
        raise _project_not_found()


# ------------------------------------------------------------
# Certifications
# ------------------------------------------------------------


@router.get("/certifications", response_model=CertificationListResponse)
def list_my_certifications(
    current_user: CurrentUser = Depends(require_student),
) -> CertificationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = portfolio_service.list_certifications(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load your certifications."
        ) from exc
    return CertificationListResponse(certifications=rows)


@router.post(
    "/certifications", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED
)
def create_certification(
    payload: CertificationCreateRequest, current_user: CurrentUser = Depends(require_student)
) -> CertificationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = portfolio_service.create_certification(
            client, current_user.id, payload.model_dump(mode="json")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create this certification."
        ) from exc
    return CertificationResponse(**row)


@router.get("/certifications/{certification_id}", response_model=CertificationResponse)
def get_certification(
    certification_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> CertificationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = portfolio_service.get_certification(client, certification_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not load this certification."
        ) from exc
    if row is None:
        raise _certification_not_found()
    return CertificationResponse(**row)


@router.patch("/certifications/{certification_id}", response_model=CertificationResponse)
def update_certification(
    certification_id: UUID,
    payload: CertificationUpdateRequest,
    current_user: CurrentUser = Depends(require_student),
) -> CertificationResponse:
    client = build_user_client(current_user.access_token)
    update_data = payload.model_dump(mode="json", exclude_unset=True)
    try:
        row = portfolio_service.update_certification(client, certification_id, update_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update this certification."
        ) from exc
    if row is None:
        raise _certification_not_found()
    return CertificationResponse(**row)


@router.delete("/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certification(
    certification_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> None:
    client = build_user_client(current_user.access_token)
    try:
        deleted = portfolio_service.delete_certification(client, certification_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete this certification."
        ) from exc
    if not deleted:
        raise _certification_not_found()
