"""Tools: the student's own application history, opportunity
recommendations, and per-opportunity match.

Every function here wraps an EXISTING service call verbatim --
student_opportunity_service (list_my_applications, get_opportunity,
compute_opportunity_match) and student_recommendation_service
(recommend_opportunities, the canonical deterministic ranking). No
match/ranking formula is reimplemented; see app.services.match_service
for the one formula every score here traces back to.
"""

from supabase import Client

from app.ai.schemas.student_context import ApplicationHistorySummary
from app.schemas.student_opportunity import OpportunityMatchResponse, StudentApplicationResponse
from app.schemas.student_recommendation import RecommendedOpportunity
from app.services import student_opportunity_service, student_recommendation_service

# Context-size hygiene for a future agent's prompt budget -- the full
# history is still reachable through GET /api/v1/student/applications.
_RECENT_APPLICATIONS_LIMIT = 10


def get_application_history(client: Client, student_id: str) -> ApplicationHistorySummary:
    """The caller's own application history: per-status counts + the
    most recent applications. Empty/zeroed for a student who has never
    applied to anything -- not an error."""
    rows = student_opportunity_service.list_my_applications(client, student_id)
    applications = [StudentApplicationResponse(**row) for row in rows]

    by_status: dict[str, int] = {}
    for application in applications:
        by_status[application.status] = by_status.get(application.status, 0) + 1

    return ApplicationHistorySummary(
        total_applications=len(applications),
        by_status=by_status,
        recent_applications=applications[:_RECENT_APPLICATIONS_LIMIT],
    )


def get_recommended_opportunities(
    client: Client, student_id: str, *, limit: int | None = None
) -> list[RecommendedOpportunity]:
    """Published internships/jobs the student hasn't applied to yet,
    ranked by the canonical deterministic match score -- exactly
    student_recommendation_service.recommend_opportunities, the same
    data GET /api/v1/student/recommendations returns. Empty list if
    nothing currently qualifies (e.g. no skills overlap any posting) --
    not an error."""
    rows = student_recommendation_service.recommend_opportunities(client, student_id, limit=limit)
    return [RecommendedOpportunity(**row) for row in rows]


def get_opportunity_match(
    client: Client, student_id: str, opportunity_id: str
) -> OpportunityMatchResponse | None:
    """The caller's own advisory skill-fit against ONE opportunity --
    exactly student_opportunity_service.compute_opportunity_match, the
    same calculation GET /api/v1/student/opportunities/{id}/match
    returns. None if the opportunity doesn't exist or isn't currently
    visible to the caller, or malformed (never distinguishes which,
    matching that route's own 404 behavior) -- callers should treat None
    as "not available," not as an error."""
    try:
        opportunity = student_opportunity_service.get_opportunity(client, student_id, opportunity_id)
    except student_opportunity_service.InvalidOpportunityIdError:
        return None
    if opportunity is None:
        return None
    result = student_opportunity_service.compute_opportunity_match(
        client, student_id, opportunity_id
    )
    return OpportunityMatchResponse(**result)
