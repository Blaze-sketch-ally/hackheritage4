"""API route for the aggregate Student recommendation surface (Phase S7).

Student-only, authenticated, read-only. The recommendation CONTEXT (target
role, skills, gap) is derived entirely from `current_user.id` via the
canonical `skill_gap_service` dispatch -- no `student_id`, `skill_id(s)`,
`target_job_role_id`, `match_score`, or `recommendation_score` is ever
read from the request. `limit` is the only query parameter and it is
bounded and non-authoritative (it changes page size, never whose
recommendations are returned).

Every read goes through build_user_client(current_user.access_token) --
never get_supabase() / service_role -- so RLS stays the real
access-control boundary. Nothing here writes: no application, no learning
progress, no skill change, no target-role change, no notification.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_student
from app.core.security import build_user_client
from app.schemas.student_learning import (
    LearningRecommendation,
    LearningResourceSummary,
    MatchedGapSkill,
)
from app.schemas.student_recommendation import (
    RecommendedOpportunity,
    RecommendedTargetRole,
    StudentRecommendationsResponse,
)
from app.services import student_recommendation_service

router = APIRouter(prefix="/student", tags=["student-recommendations"])


def _matched_gap_skill(skill: dict) -> MatchedGapSkill:
    """Only the four fields the UI needs from a canonical Skill Gap
    recommendation -- never echo the engine's internal fields. Mirrors the
    identical helper in app.api.student_learning."""
    return MatchedGapSkill(
        skill_id=str(skill["skill_id"]),
        skill_name=skill.get("skill_name", ""),
        reason=skill.get("reason", ""),
        priority=skill.get("priority", "LOW"),
    )


@router.get("/recommendations", response_model=StudentRecommendationsResponse)
def get_recommendations(
    limit: int = Query(
        default=student_recommendation_service.DEFAULT_LIMIT,
        ge=1,
        le=student_recommendation_service.MAX_LIMIT,
        description="Max items per section (opportunities, learning).",
    ),
    current_user: CurrentUser = Depends(require_student),
) -> StudentRecommendationsResponse:
    client = build_user_client(current_user.access_token)
    try:
        mode, job_role, analysis = student_recommendation_service.resolve_context(
            client, current_user.id
        )
        opportunities = student_recommendation_service.recommend_opportunities(
            client, current_user.id, limit=limit
        )
        learning = student_recommendation_service.recommend_learning(
            client, current_user.id, analysis, limit=limit
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your recommendations. Please try again.",
        ) from exc

    return StudentRecommendationsResponse(
        mode=mode,
        target_role=(
            RecommendedTargetRole(id=str(job_role["id"]), name=job_role["name"])
            if job_role
            else None
        ),
        opportunities=[RecommendedOpportunity(**item) for item in opportunities],
        learning=[
            LearningRecommendation(
                resource=LearningResourceSummary(**entry["resource"]),
                matched_skills=[_matched_gap_skill(s) for s in entry["matched_skills"]],
            )
            for entry in learning
        ],
    )
