"""API routes for Industry project management.

Every route is guarded by require_industry() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The project owner is always current_user.id;
`industry_id` is never read from the request. Lifecycle changes go
through the dedicated publish/close/archive endpoints, not PUT.

Student-facing project discovery/application is NOT part of this module
(Phase 10A scope -- see database/migrations/022_industry_projects.sql).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.industry_project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectStatus,
    ProjectUpdate,
)
from app.services import industry_project_service

router = APIRouter(prefix="/projects", tags=["industry-projects"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = industry_project_service.list_projects(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your projects") from exc
    return ProjectListResponse(projects=rows)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    try:
        row = industry_project_service.create_project(client, current_user.id, payload)
    except Exception as exc:
        raise _server_error("create the project") from exc
    return ProjectResponse(**row)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_project_service.get_project(client, current_user.id, str(project_id))
    except Exception as exc:
        raise _server_error("load the project") from exc
    if row is None:
        raise _not_found()
    return ProjectResponse(**row)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    try:
        row = industry_project_service.update_project(
            client, current_user.id, str(project_id), payload
        )
    except Exception as exc:
        raise _server_error("save the project") from exc
    if row is None:
        raise _not_found()
    return ProjectResponse(**row)


@router.post("/{project_id}/publish", response_model=ProjectResponse)
def publish_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_project_service.publish_project(client, current_user.id, str(project_id))
    except industry_project_service.PublishValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This project isn't ready to publish. Add: " + ", ".join(exc.missing) + ".",
        ) from exc
    except industry_project_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft or closed project can be published.",
        ) from exc
    except Exception as exc:
        raise _server_error("publish the project") from exc
    if row is None:
        raise _not_found()
    return ProjectResponse(**row)


@router.post("/{project_id}/close", response_model=ProjectResponse)
def close_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_project_service.close_project(client, current_user.id, str(project_id))
    except industry_project_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published project can be closed.",
        ) from exc
    except Exception as exc:
        raise _server_error("close the project") from exc
    if row is None:
        raise _not_found()
    return ProjectResponse(**row)


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = industry_project_service.archive_project(client, current_user.id, str(project_id))
    except industry_project_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project is already archived.",
        ) from exc
    except Exception as exc:
        raise _server_error("archive the project") from exc
    if row is None:
        raise _not_found()
    return ProjectResponse(**row)
