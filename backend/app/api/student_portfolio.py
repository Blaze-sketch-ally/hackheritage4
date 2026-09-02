"""API routes for the STUDENT Portfolio module
(database/migrations/034_student_portfolio.sql): the student's own
projects, certifications, achievements, and a read-only portfolio
aggregate.

Every route is guarded by require_student() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. `student_id` is always current_user.id, never
read from a request body, query parameter, or path parameter. Every
request model is `extra="forbid"` (see app.schemas.student_portfolio), so
an `owner_id` / `student_id` / `id` / `is_verified` / … field in the body
is a 422 before the handler runs.

Portfolio records are EVIDENCE ONLY. Nothing here writes `student_skills`,
touches proficiency/verification, or couples to assessments / learning /
skill-gap.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_portfolio import (
    AchievementCreate,
    AchievementListResponse,
    AchievementResponse,
    AchievementUpdate,
    CertificationCreate,
    CertificationListResponse,
    CertificationResponse,
    CertificationUpdate,
    PortfolioResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services import student_portfolio_service

router = APIRouter(prefix="/student", tags=["student-portfolio"])


def _not_found(kind: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"This {kind} is not available."
    )


def _invalid_skills(missing: list[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unknown skill id(s): {', '.join(missing)}",
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


# ============================================================
# Portfolio aggregate
# ============================================================


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(current_user: CurrentUser = Depends(require_student)) -> PortfolioResponse:
    client = build_user_client(current_user.access_token)
    try:
        data = student_portfolio_service.get_portfolio(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your portfolio") from exc
    return PortfolioResponse(**data)


# ============================================================
# Projects
# ============================================================


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(current_user: CurrentUser = Depends(require_student)) -> ProjectListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_portfolio_service.list_projects(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your projects") from exc
    return ProjectListResponse(projects=[ProjectResponse(**r) for r in rows])


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate, current_user: CurrentUser = Depends(require_student)
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.create_project(
            client, current_user.id, body.model_dump()
        )
    except student_portfolio_service.InvalidSkillError as exc:
        raise _invalid_skills(list(exc.args[0])) from exc
    except Exception as exc:
        raise _server_error("save your project") from exc
    return ProjectResponse(**row)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.get_project(client, current_user.id, str(project_id))
    except Exception as exc:
        raise _server_error("load this project") from exc
    if row is None:
        raise _not_found("project")
    return ProjectResponse(**row)


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    current_user: CurrentUser = Depends(require_student),
) -> ProjectResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.update_project(
            client, current_user.id, str(project_id), body.model_dump()
        )
    except student_portfolio_service.InvalidSkillError as exc:
        raise _invalid_skills(list(exc.args[0])) from exc
    except Exception as exc:
        raise _server_error("update this project") from exc
    if row is None:
        raise _not_found("project")
    return ProjectResponse(**row)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> None:
    client = build_user_client(current_user.access_token)
    try:
        ok = student_portfolio_service.delete_project(client, current_user.id, str(project_id))
    except Exception as exc:
        raise _server_error("delete this project") from exc
    if not ok:
        raise _not_found("project")


# ============================================================
# Certifications
# ============================================================


@router.get("/certifications", response_model=CertificationListResponse)
def list_certifications(
    current_user: CurrentUser = Depends(require_student),
) -> CertificationListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_portfolio_service.list_certifications(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your certifications") from exc
    return CertificationListResponse(
        certifications=[CertificationResponse(**r) for r in rows]
    )


@router.post(
    "/certifications",
    response_model=CertificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_certification(
    body: CertificationCreate, current_user: CurrentUser = Depends(require_student)
) -> CertificationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.create_certification(
            client, current_user.id, body.model_dump()
        )
    except Exception as exc:
        raise _server_error("save your certification") from exc
    return CertificationResponse(**row)


@router.get("/certifications/{certification_id}", response_model=CertificationResponse)
def get_certification(
    certification_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> CertificationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.get_certification(
            client, current_user.id, str(certification_id)
        )
    except Exception as exc:
        raise _server_error("load this certification") from exc
    if row is None:
        raise _not_found("certification")
    return CertificationResponse(**row)


@router.put("/certifications/{certification_id}", response_model=CertificationResponse)
def update_certification(
    certification_id: UUID,
    body: CertificationUpdate,
    current_user: CurrentUser = Depends(require_student),
) -> CertificationResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.update_certification(
            client, current_user.id, str(certification_id), body.model_dump()
        )
    except Exception as exc:
        raise _server_error("update this certification") from exc
    if row is None:
        raise _not_found("certification")
    return CertificationResponse(**row)


@router.delete(
    "/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_certification(
    certification_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> None:
    client = build_user_client(current_user.access_token)
    try:
        ok = student_portfolio_service.delete_certification(
            client, current_user.id, str(certification_id)
        )
    except Exception as exc:
        raise _server_error("delete this certification") from exc
    if not ok:
        raise _not_found("certification")


# ============================================================
# Achievements
# ============================================================


@router.get("/achievements", response_model=AchievementListResponse)
def list_achievements(
    current_user: CurrentUser = Depends(require_student),
) -> AchievementListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_portfolio_service.list_achievements(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your achievements") from exc
    return AchievementListResponse(
        achievements=[AchievementResponse(**r) for r in rows]
    )


@router.post(
    "/achievements", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED
)
def create_achievement(
    body: AchievementCreate, current_user: CurrentUser = Depends(require_student)
) -> AchievementResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.create_achievement(
            client, current_user.id, body.model_dump()
        )
    except Exception as exc:
        raise _server_error("save your achievement") from exc
    return AchievementResponse(**row)


@router.get("/achievements/{achievement_id}", response_model=AchievementResponse)
def get_achievement(
    achievement_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> AchievementResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.get_achievement(
            client, current_user.id, str(achievement_id)
        )
    except Exception as exc:
        raise _server_error("load this achievement") from exc
    if row is None:
        raise _not_found("achievement")
    return AchievementResponse(**row)


@router.put("/achievements/{achievement_id}", response_model=AchievementResponse)
def update_achievement(
    achievement_id: UUID,
    body: AchievementUpdate,
    current_user: CurrentUser = Depends(require_student),
) -> AchievementResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = student_portfolio_service.update_achievement(
            client, current_user.id, str(achievement_id), body.model_dump()
        )
    except Exception as exc:
        raise _server_error("update this achievement") from exc
    if row is None:
        raise _not_found("achievement")
    return AchievementResponse(**row)


@router.delete("/achievements/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_achievement(
    achievement_id: UUID, current_user: CurrentUser = Depends(require_student)
) -> None:
    client = build_user_client(current_user.access_token)
    try:
        ok = student_portfolio_service.delete_achievement(
            client, current_user.id, str(achievement_id)
        )
    except Exception as exc:
        raise _server_error("delete this achievement") from exc
    if not ok:
        raise _not_found("achievement")
