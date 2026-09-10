"""API routes for job roles, the student's own target role, and Skill Gap
Analysis. Every route requires require_student(); every read/write goes
through build_user_client(access_token) -- never get_supabase() -- so RLS
stays the real access-control boundary. student_id is always
current_user.id, never accepted from a request body or query parameter.

No LLM anywhere in this module -- see app.services.skill_gap_service for
the deterministic gap/recommendation calculation itself.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.skill_gap import (
    AnalysisMode,
    JobRoleDetailResponse,
    JobRoleListResponse,
    SetTargetJobRoleRequest,
    SkillGapJobRoleResponse,
    SkillGapPersonalResponse,
    TargetJobRoleResponse,
)
from app.services import skill_gap_service

router = APIRouter(tags=["skill-gap"])


@router.get("/job-roles", response_model=JobRoleListResponse)
def list_job_roles(current_user: CurrentUser = Depends(require_student)) -> JobRoleListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = skill_gap_service.list_active_job_roles(client)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load job roles.",
        ) from exc
    return JobRoleListResponse(job_roles=rows)


@router.get("/job-roles/{job_role_id}", response_model=JobRoleDetailResponse)
def get_job_role(
    job_role_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> JobRoleDetailResponse:
    client = build_user_client(current_user.access_token)
    try:
        role = skill_gap_service.get_active_job_role(client, job_role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job role not found.")
        requirements = skill_gap_service.get_job_role_requirements(client, job_role_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the job role.",
        ) from exc
    return JobRoleDetailResponse(role=role, requirements=requirements)


@router.get("/student/target-job-role", response_model=TargetJobRoleResponse)
def get_target_job_role(current_user: CurrentUser = Depends(require_student)) -> TargetJobRoleResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = skill_gap_service.get_target_job_role(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your target job role.",
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No target job role set.")
    return TargetJobRoleResponse(**row)


@router.put("/student/target-job-role", response_model=TargetJobRoleResponse)
def set_target_job_role(
    body: SetTargetJobRoleRequest,
    current_user: CurrentUser = Depends(require_student),
) -> TargetJobRoleResponse:
    client = build_user_client(current_user.access_token)
    try:
        role = skill_gap_service.get_active_job_role(client, body.job_role_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job role not found.")
        row = skill_gap_service.set_target_job_role(client, current_user.id, body.job_role_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not set your target job role.",
        ) from exc
    return TargetJobRoleResponse(**row)


@router.delete("/student/target-job-role", status_code=status.HTTP_204_NO_CONTENT)
def clear_target_job_role(current_user: CurrentUser = Depends(require_student)) -> None:
    client = build_user_client(current_user.access_token)
    try:
        skill_gap_service.clear_target_job_role(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not clear your target job role.",
        ) from exc


@router.get(
    "/skill-gap",
    response_model=SkillGapJobRoleResponse | SkillGapPersonalResponse,
)
def get_skill_gap(current_user: CurrentUser = Depends(require_student)):
    """The student's own analysis: against their saved target role if one
    is set, otherwise the personal (no-job-role) analysis. Never accepts a
    job_role_id here -- that's GET /skill-gap/job-role/{id} below, for
    analyzing a role the student hasn't (yet) targeted."""
    client = build_user_client(current_user.access_token)
    try:
        target = skill_gap_service.get_target_job_role(client, current_user.id)
        if target is None:
            analysis = skill_gap_service.compute_personal_analysis(client, current_user.id)
            return SkillGapPersonalResponse(mode=AnalysisMode.PERSONAL, **analysis)

        job_role = target["job_role"]
        requirements = skill_gap_service.get_job_role_requirements(client, UUID(job_role["id"]))
        gap = skill_gap_service.compute_job_role_gap(client, current_user.id, job_role, requirements)
        return SkillGapJobRoleResponse(mode=AnalysisMode.JOB_ROLE, job_role=job_role, **gap)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not compute your skill gap analysis.",
        ) from exc


@router.get("/skill-gap/job-role/{job_role_id}", response_model=SkillGapJobRoleResponse)
def get_skill_gap_for_job_role(
    job_role_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> SkillGapJobRoleResponse:
    """Analyze the student's own skills against ANY active job role, not
    just the one they've saved as their target -- lets the frontend offer
    a preview before the student commits to a target role."""
    client = build_user_client(current_user.access_token)
    try:
        job_role = skill_gap_service.get_active_job_role(client, job_role_id)
        if job_role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job role not found.")
        requirements = skill_gap_service.get_job_role_requirements(client, job_role_id)
        gap = skill_gap_service.compute_job_role_gap(client, current_user.id, job_role, requirements)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not compute the skill gap analysis for this job role.",
        ) from exc
    return SkillGapJobRoleResponse(mode=AnalysisMode.JOB_ROLE, job_role=job_role, **gap)
