"""API routes for career roles and skill-gap analysis (Phase 1L).

Read-only throughout. GET /career-roles and GET /career-roles/{id} are
open to any authenticated role (RLS itself never role-restricts career
role reference data -- same precedent as GET /assessments, see
app.api.assessments.list_assessments). GET /career-roles/{id}/skill-gap
is STUDENT-only (require_student): it is specifically "the caller's own
derived skill evidence compared against one role," which is meaningless
for any other role and, per the Phase 1L design brief, must not be
extended to industry/institution/admin access in this phase. The
authenticated identity is always the caller's own (current_user.id) --
no student_id is ever accepted from the client, matching every other
student-facing endpoint in this project (see app.api.attempts).

See app.services.career_role_service / app.services.skill_alignment_service
/ app.services.assessment_service.get_student_skill_scores for the actual
queries and computation.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import CurrentUser, get_current_user, require_student
from app.core.security import build_user_client
from app.schemas.career_role import (
    CareerRoleListResponse,
    CareerRoleResponse,
    SkillGapResponse,
    SkillGapSkillResponse,
)
from app.services import assessment_service, career_role_service
from app.services.skill_alignment_service import compute_alignment

router = APIRouter(prefix="/career-roles", tags=["career-roles"])


@router.get("", response_model=CareerRoleListResponse)
def list_career_roles(
    current_user: CurrentUser = Depends(get_current_user),
) -> CareerRoleListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = career_role_service.list_career_roles(client)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load career roles.",
        ) from exc
    return CareerRoleListResponse(career_roles=rows)


@router.get("/{career_role_id}", response_model=CareerRoleResponse)
def get_career_role(
    career_role_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> CareerRoleResponse:
    client = build_user_client(current_user.access_token)
    try:
        role = career_role_service.get_career_role(client, career_role_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this career role.",
        ) from exc
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career role not found.")
    return CareerRoleResponse(**role)


@router.get("/{career_role_id}/skill-gap", response_model=SkillGapResponse)
def get_skill_gap(
    career_role_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> SkillGapResponse:
    """Compares the AUTHENTICATED STUDENT's own derived skill evidence
    against one career role's requirements -- see
    app.services.skill_alignment_service.compute_alignment for the
    deterministic calculation. No AI is used anywhere in this endpoint.
    """
    client = build_user_client(current_user.access_token)

    try:
        role = career_role_service.get_career_role(client, career_role_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this career role.",
        ) from exc
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Career role not found.")

    try:
        requirements = career_role_service.get_career_role_requirements(client, career_role_id)
        student_scores = assessment_service.get_student_skill_scores(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not compute your skill gap for this role.",
        ) from exc

    summary = compute_alignment(requirements, student_scores)

    return SkillGapResponse(
        career_role=CareerRoleResponse(**role),
        overall_score=summary.overall_score,
        skills=[
            SkillGapSkillResponse(
                skill_id=result.skill_id,
                skill_name=result.skill_name,
                required_level=result.required_level,
                student_score=result.student_score,
                gap=result.gap,
                weight=result.weight,
                status=result.status.value,
            )
            for result in summary.results
        ],
    )
