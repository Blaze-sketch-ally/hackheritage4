"""API routes for the STUDENT Learning module
(database/migrations/033_learning_resources.sql).

Every route is guarded by require_student() and every read/write goes
through build_user_client(current_user.access_token) -- never
get_supabase() / service_role -- so Supabase RLS stays the real
access-control boundary. `student_id` is always current_user.id, never
read from a request body, query parameter, or path parameter.

Scope (Phase 6B): browse the curated `learning_resources` catalog, see
each resource's mapped skills, and record a minimal per-resource progress
status (SAVED / IN_PROGRESS / COMPLETED). NO skill verification, NO write
to `student_skills` or any assessment table.

Phase 6D adds GET /recommended: learning resources mapped to the caller's
OWN canonical Skill Gap skills. The gap is computed by
`app.services.skill_gap_service` exactly as GET /api/v1/skill-gap does --
this module only maps that result's recommendation skills to resources
via `learning_resource_skills` (see
`app.services.learning_recommendation_service`). Still NO write anywhere,
still no skill verification.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_learning import (
    Difficulty,
    LearningRecommendation,
    LearningRecommendationListResponse,
    LearningResourceDetail,
    LearningResourceListResponse,
    LearningResourceSummary,
    MatchedGapSkill,
    ProgressUpdateRequest,
    ProgressUpdateResponse,
    ResourceType,
    StudentLearningProgressItem,
    StudentLearningProgressListResponse,
)
from app.services import (
    learning_recommendation_service,
    skill_gap_service,
    student_learning_service,
)

router = APIRouter(prefix="/student/learning", tags=["student-learning"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="This learning resource is not available."
    )


def _server_error(action: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Could not {action}. Please try again.",
    )


@router.get("/resources", response_model=LearningResourceListResponse)
def list_resources(
    skill_id: UUID | None = Query(default=None),
    difficulty: Difficulty | None = Query(default=None),
    resource_type: ResourceType | None = Query(default=None),
    current_user: CurrentUser = Depends(require_student),
) -> LearningResourceListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = student_learning_service.list_resources(
            client,
            current_user.id,
            skill_id=str(skill_id) if skill_id else None,
            difficulty=difficulty,
            resource_type=resource_type,
        )
    except Exception as exc:
        raise _server_error("load learning resources") from exc
    return LearningResourceListResponse(
        resources=[LearningResourceSummary(**row) for row in rows]
    )


@router.get("/progress", response_model=StudentLearningProgressListResponse)
def list_my_progress(
    current_user: CurrentUser = Depends(require_student),
) -> StudentLearningProgressListResponse:
    """The caller's own learning progress, newest activity first. Scoped
    to student_id = current_user.id -- another student's progress is never
    reachable here (RLS + explicit filter)."""
    client = build_user_client(current_user.access_token)
    try:
        rows = student_learning_service.list_my_progress(client, current_user.id)
    except Exception as exc:
        raise _server_error("load your learning progress") from exc
    return StudentLearningProgressListResponse(
        progress=[StudentLearningProgressItem(**row) for row in rows]
    )


def _matched_gap_skill(skill: dict) -> MatchedGapSkill:
    """Keep only the four fields the UI needs from a canonical Skill Gap
    recommendation -- never echo the engine's internal fields."""
    return MatchedGapSkill(
        skill_id=str(skill["skill_id"]),
        skill_name=skill.get("skill_name", ""),
        reason=skill.get("reason", ""),
        priority=skill.get("priority", "LOW"),
    )


@router.get("/recommended", response_model=LearningRecommendationListResponse)
def list_recommended_resources(
    current_user: CurrentUser = Depends(require_student),
) -> LearningRecommendationListResponse:
    """Learning resources mapped to the caller's OWN canonical Skill Gap
    skills.

    The gap itself is computed by `app.services.skill_gap_service`, using
    the same dispatch as GET /api/v1/skill-gap: target-role mode when the
    student has saved a target role, personal mode otherwise. This route
    never accepts a skill list, a job role, or a student id from the
    client -- the server derives every input from `current_user.id`.
    """
    client = build_user_client(current_user.access_token)
    try:
        target = skill_gap_service.get_target_job_role(client, current_user.id)
        if target is None:
            analysis = skill_gap_service.compute_personal_analysis(client, current_user.id)
            mode = "PERSONAL"
        else:
            job_role = target["job_role"]
            requirements = skill_gap_service.get_job_role_requirements(
                client, UUID(job_role["id"])
            )
            analysis = skill_gap_service.compute_job_role_gap(
                client, current_user.id, job_role, requirements
            )
            mode = "JOB_ROLE"

        gap_skills = analysis.get("recommendations", [])
        entries = learning_recommendation_service.get_recommended_resources(
            client, current_user.id, gap_skills
        )
    except Exception as exc:
        raise _server_error("load your learning recommendations") from exc

    return LearningRecommendationListResponse(
        mode=mode,
        recommendations=[
            LearningRecommendation(
                resource=LearningResourceSummary(**entry["resource"]),
                matched_skills=[
                    _matched_gap_skill(skill) for skill in entry["matched_skills"]
                ],
            )
            for entry in entries
        ],
    )


@router.get("/resources/{resource_id}", response_model=LearningResourceDetail)
def get_resource(
    resource_id: UUID,
    current_user: CurrentUser = Depends(require_student),
) -> LearningResourceDetail:
    client = build_user_client(current_user.access_token)
    try:
        row = student_learning_service.get_resource(client, current_user.id, str(resource_id))
    except Exception as exc:
        raise _server_error("load this learning resource") from exc
    if row is None:
        # Same response whether the resource never existed or is inactive --
        # never reveal which, even to a caller who knows the UUID.
        raise _not_found()
    return LearningResourceDetail(**row)


@router.post(
    "/resources/{resource_id}/progress",
    response_model=ProgressUpdateResponse,
    status_code=status.HTTP_200_OK,
)
def set_progress(
    resource_id: UUID,
    body: ProgressUpdateRequest,
    current_user: CurrentUser = Depends(require_student),
) -> ProgressUpdateResponse:
    """Create or move the caller's own progress on one resource. The path
    identifies the resource; the token identifies the student; the body
    carries only `status`. Timestamps are server-set."""
    client = build_user_client(current_user.access_token)

    # Verify the resource exists and is active FIRST (RLS-respecting read),
    # exactly like app.api.student_opportunities.apply_to_opportunity -- so
    # a bad/inactive id is a clean 404, not a progress row against content
    # a student should not be able to reach.
    try:
        resource = student_learning_service.get_resource(
            client, current_user.id, str(resource_id)
        )
    except Exception as exc:
        raise _server_error("load this learning resource") from exc
    if resource is None:
        raise _not_found()

    try:
        row = student_learning_service.set_progress(
            client, current_user.id, str(resource_id), body.status
        )
    except Exception as exc:
        raise _server_error("save your progress") from exc
    return ProgressUpdateResponse(**row)
