"""API routes for the STUDENT side of Project discovery and applying.

Mirrors app.api.student_workshops exactly, over the standalone
`industry_projects` / `industry_project_applications` tables
(022_industry_projects.sql / 057_project_applications.sql). Named
`/student/industry-projects` (not `/student/projects`) to avoid colliding
with the existing Student Portfolio "projects" feature
(app/student/projects, a different, unrelated feature area).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.project_application import (
    ProjectApplicationListResponse,
    ProjectApplicationResponse,
    ProjectApplyRequest,
)
from app.schemas.student_project import StudentProject, StudentProjectListResponse
from app.services import notification_producer, student_project_service

router = APIRouter(prefix="/student", tags=["student-projects"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This project is not available."
    )


def _application_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="We couldn't find that application."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


def _own_name(client: Client, student_id: str) -> str | None:
    try:
        response = (
            client.table("profiles")
            .select("full_name")
            .eq("id", student_id)
            .maybe_single()
            .execute()
        )
        row = response.data if response is not None else None
        return row.get("full_name") if row else None
    except Exception:  # noqa: BLE001 -- notification enrichment only
        return None


@router.get("/industry-projects", response_model=StudentProjectListResponse)
def list_projects(
    search: str | None = Query(default=None, max_length=200),
    current_user: CurrentUser = Depends(require_student),
) -> StudentProjectListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_project_service.list_projects(client, current_user.id, search=search)
    except Exception as exc:
        raise _server_error("load projects") from exc
    return StudentProjectListResponse(projects=[StudentProject(**row) for row in rows])


@router.get("/industry-projects/{project_id}", response_model=StudentProject)
def get_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> StudentProject:
    client = build_user_client(current_user.access_token)
    try:
        row = student_project_service.get_project(client, current_user.id, str(project_id))
    except Exception as exc:
        raise _server_error("load this project") from exc
    if row is None:
        raise _not_found()
    return StudentProject(**row)


@router.post(
    "/industry-projects/{project_id}/applications",
    response_model=ProjectApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_project(
    project_id: UUID,
    _body: ProjectApplyRequest,
    current_user: CurrentUser = Depends(require_student),
) -> ProjectApplicationResponse:
    client = build_user_client(current_user.access_token)

    try:
        project = student_project_service.get_project(client, current_user.id, str(project_id))
    except Exception as exc:
        raise _server_error("load this project") from exc
    if project is None:
        raise _not_found()

    try:
        row = student_project_service.apply_to_project(
            client, current_user.id, str(project_id)
        )
    except student_project_service.DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this project.",
        ) from exc
    except student_project_service.ProjectNotPublishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project is no longer accepting applications.",
        ) from exc
    except Exception as exc:
        raise _server_error("submit your application") from exc

    notification_producer.emit_new_application(
        industry_id=row["industry_id"],
        kind="PROJECT",
        related_entity_id=row["project_id"],
        opportunity_title=project.get("title"),
        student_name=_own_name(client, current_user.id),
    )

    return ProjectApplicationResponse(**row)


@router.get("/project-applications", response_model=ProjectApplicationListResponse)
def list_my_applications(
    current_user: CurrentUser = Depends(require_student),
) -> ProjectApplicationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_project_service.list_my_applications(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your applications") from exc
    return ProjectApplicationListResponse(
        applications=[ProjectApplicationResponse(**row) for row in rows]
    )


@router.post(
    "/project-applications/{application_id}/withdraw",
    response_model=ProjectApplicationResponse,
)
def withdraw_application(
    application_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> ProjectApplicationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_project_service.withdraw_application(
            client, current_user.id, str(application_id)
        )
    except student_project_service.ApplicationNotWithdrawableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise _server_error("withdraw this application") from exc
    if row is None:
        raise _application_not_found()

    notification_producer.emit_application_withdrawn(
        industry_id=row["industry_id"],
        kind="PROJECT",
        related_entity_id=row["project_id"],
        opportunity_title=(row.get("project") or {}).get("title"),
        student_name=_own_name(client, current_user.id),
    )

    return ProjectApplicationResponse(**row)
