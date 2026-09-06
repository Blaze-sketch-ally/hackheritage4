"""API routes for Industry job management.

Mirrors app.api.internships: every route is guarded by require_industry()
and every read/write goes through build_user_client(current_user.access_token)
-- never get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. The job owner is always current_user.id;
`industry_id` is never read from the request. Lifecycle changes go through
the dedicated publish/close/archive endpoints, not PUT.

Student-facing job discovery is NOT part of this module.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_industry
from app.core.security import build_user_client
from app.schemas.job import (
    JobCreate,
    JobListResponse,
    JobResponse,
    JobStatus,
    JobUpdate,
)
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_industry),
) -> JobListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = job_service.list_jobs(
            client, current_user.id, status=status_filter, search=search
        )
    except Exception as exc:
        raise _server_error("load your jobs") from exc
    return JobListResponse(jobs=rows)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    body: JobCreate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json")
    skills = payload.pop("skills")
    try:
        row = job_service.create_job(client, current_user.id, payload, skills)
    except job_service.InvalidSkillError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more selected skills are no longer available.",
        ) from exc
    except Exception as exc:
        raise _server_error("create the job") from exc
    return JobResponse(**row)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = job_service.get_job(client, current_user.id, str(job_id))
    except Exception as exc:
        raise _server_error("load the job") from exc
    if row is None:
        raise _not_found()
    return JobResponse(**row)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: UUID,
    body: JobUpdate,
    current_user: CurrentUser = Depends(require_industry),
) -> JobResponse:
    client = build_user_client(current_user.access_token)
    payload = body.model_dump(mode="json", exclude_unset=True)
    skills = payload.pop("skills", None)
    try:
        row = job_service.update_job(
            client, current_user.id, str(job_id), payload, skills
        )
    except job_service.InvalidSkillError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more selected skills are no longer available.",
        ) from exc
    except Exception as exc:
        raise _server_error("save the job") from exc
    if row is None:
        raise _not_found()
    return JobResponse(**row)


@router.post("/{job_id}/publish", response_model=JobResponse)
def publish_job(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = job_service.publish_job(client, current_user.id, str(job_id))
    except job_service.PublishValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This job isn't ready to publish. Add: " + ", ".join(exc.missing) + ".",
        ) from exc
    except job_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a draft or closed job can be published.",
        ) from exc
    except Exception as exc:
        raise _server_error("publish the job") from exc
    if row is None:
        raise _not_found()
    return JobResponse(**row)


@router.post("/{job_id}/close", response_model=JobResponse)
def close_job(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = job_service.close_job(client, current_user.id, str(job_id))
    except job_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a published job can be closed.",
        ) from exc
    except Exception as exc:
        raise _server_error("close the job") from exc
    if row is None:
        raise _not_found()
    return JobResponse(**row)


@router.post("/{job_id}/archive", response_model=JobResponse)
def archive_job(
    job_id: UUID,
    current_user: CurrentUser = Depends(require_industry),
) -> JobResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = job_service.archive_job(client, current_user.id, str(job_id))
    except job_service.InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job is already archived.",
        ) from exc
    except Exception as exc:
        raise _server_error("archive the job") from exc
    if row is None:
        raise _not_found()
    return JobResponse(**row)
