"""API routes for the AI subsystem.

Phase 1 (infrastructure): a read-only endpoint reporting whether the AI
subsystem (Groq) is configured, for any signed-in user.

Phase 2 (student context + tools) adds GET /context: the caller's own
StudentCareerContext (app.ai.schemas.student_context), built by
app.ai.context.build_student_career_context through the read-only tool
layer in app.ai.tools. This is a data/context endpoint, not a business
endpoint -- no agent runs here, and this route makes no Groq call. It
exists so Phase 2 can be verified end-to-end before any agent is built;
see the Phase 2 report for why returning the full context (rather than a
narrower summary) was judged safe here -- every field is already
independently reachable by the caller through an existing endpoint
(skills, assessments, portfolio, learning, applications,
recommendations), so this aggregates, but does not widen, what the
caller can already see.

Phase 3 adds POST /skill-gap: the first real AI agent
(app.ai.agents.skill_gap_agent), an interpretation layer over the
EXISTING deterministic Skill Gap engine (app.services.skill_gap_service,
via app.ai.tools.skill_gap_tools) -- never a replacement for it. POST is
used (not GET) because this route triggers an LLM generation, matching
this router's own docstring convention of GET for read-only /
side-effect-free routes only. GET /api/v1/skill-gap (app.api.skill_gap)
is completely unaffected by this module and remains fully functional
with zero Groq dependency -- see this route's own docstring for the
graceful-degradation behavior when Groq is unavailable.

None of the existing deterministic services (skill_gap_service,
match_service, learning_recommendation_service,
student_recommendation_service, assessment scoring) are touched by any
route in this module, and none of their formulas are reimplemented.

Uses the project's existing auth dependencies exactly like every other
router -- no new auth mechanism. /health uses get_current_user (any
signed-in role, matching app.api.skills); /context and /skill-gap use
require_student (STUDENT only, matching every other /student/* route)
and always resolve student_id from current_user.id -- never from a
query parameter or request body, so a caller cannot request another
student's data (see app.ai.context's own docstring on this).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.agents.course_recommendation_agent import recommend_courses
from app.ai.agents.opportunity_recommendation_agent import recommend_opportunities
from app.ai.agents.skill_gap_agent import analyze_student_skill_gap, build_canonical_summary_only
from app.ai.chat.career_chat import career_chat
from app.ai.config import ai_settings
from app.ai.context import build_student_career_context
from app.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIProviderError,
    AIResponseError,
    AIStructuredOutputError,
)
from app.ai.orchestrator import build_career_guidance
from app.ai.schemas.base import AIHealthResponse
from app.ai.schemas.career_chat import CareerChatRequest, CareerChatResponse
from app.ai.schemas.career_guidance import CareerGuidanceResponse
from app.ai.schemas.course_recommendation import CourseRecommendationResponse
from app.ai.schemas.opportunity_recommendation import OpportunityRecommendationResponse
from app.ai.schemas.skill_gap import SkillGapAgentResponse, SkillGapAIUnavailableResponse
from app.ai.schemas.student_context import StudentCareerContext
from app.core.dependencies import CurrentUser, get_current_user, require_student
from app.core.security import build_user_client

logger = logging.getLogger("app.ai")

router = APIRouter(prefix="/ai", tags=["ai"])

# Safe, client-facing reason strings -- never str(exc) (see
# app.ai.exceptions' own module docstring on why a raw provider message
# is never surfaced to a caller).
_AI_FAILURE_REASONS: dict[type[AIError], str] = {
    AIConfigurationError: "AI analysis is not currently configured.",
    AIProviderError: "The AI provider is temporarily unavailable. Please try again shortly.",
    AIResponseError: "The AI provider returned an unusable response. Please try again shortly.",
    AIStructuredOutputError: "The AI response could not be validated. Please try again shortly.",
}
_DEFAULT_AI_FAILURE_REASON = "AI analysis is temporarily unavailable."


@router.get("/health", response_model=AIHealthResponse)
def ai_health(current_user: CurrentUser = Depends(get_current_user)) -> AIHealthResponse:
    return AIHealthResponse(
        configured=ai_settings.is_configured,
        model=ai_settings.groq_model,
    )


@router.get("/context", response_model=StudentCareerContext)
def get_ai_context(
    current_user: CurrentUser = Depends(require_student),
) -> StudentCareerContext:
    """The calling student's own StudentCareerContext. No Groq call, no
    API key exposure, no service-role data -- every read here goes
    through build_user_client(current_user.access_token), so RLS stays
    the real access-control boundary exactly like every other student
    route. student_id is always current_user.id."""
    client = build_user_client(current_user.access_token)
    try:
        return build_student_career_context(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build your AI context. Please try again.",
        ) from exc


@router.post(
    "/skill-gap",
    response_model=SkillGapAgentResponse | SkillGapAIUnavailableResponse,
)
def get_skill_gap_analysis(
    current_user: CurrentUser = Depends(require_student),
):
    """The calling student's own AI-interpreted skill gap analysis.

    The canonical Skill Gap data (readiness/status/priority/importance/
    verification) always comes from app.services.skill_gap_service,
    completely independent of the LLM -- see
    app.ai.agents.skill_gap_agent's own docstring. GET /api/v1/skill-gap
    (app.api.skill_gap) is untouched by this route and keeps working
    with zero Groq dependency, including while this route is degraded.

    Graceful degradation: if the AI layer itself fails for any reason
    (missing API key, provider timeout/rate-limit/error, or a malformed/
    ungroundable structured response), this route does NOT fail the
    whole request or fabricate advice -- it re-fetches the canonical
    summary on its own (build_canonical_summary_only, no Groq call) and
    returns SkillGapAIUnavailableResponse (still HTTP 200) with a safe,
    generic reason. A genuinely unexpected error (e.g. the canonical
    re-fetch itself failing) is the only case that reaches HTTP 500.
    """
    client = build_user_client(current_user.access_token)
    try:
        return analyze_student_skill_gap(client, current_user.id)
    except AIError as exc:
        logger.warning(
            "Skill Gap Agent unavailable for student %s: %s",
            current_user.id,
            exc.__class__.__name__,
        )
        try:
            canonical = build_canonical_summary_only(client, current_user.id)
        except Exception as inner_exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not load your skill gap data. Please try again.",
            ) from inner_exc
        return SkillGapAIUnavailableResponse(
            canonical=canonical,
            reason=_AI_FAILURE_REASONS.get(type(exc), _DEFAULT_AI_FAILURE_REASON),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build your skill gap analysis. Please try again.",
        ) from exc


@router.post("/course-recommendations", response_model=CourseRecommendationResponse)
def get_course_recommendations(
    current_user: CurrentUser = Depends(require_student),
) -> CourseRecommendationResponse:
    """Own canonical learning priorities and source-backed courses; no database writes."""
    try:
        client = build_user_client(current_user.access_token)
        return recommend_courses(client, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail="Could not load your course recommendations. Please try again.") from exc


@router.post("/opportunity-recommendations", response_model=OpportunityRecommendationResponse)
def get_opportunity_recommendations(
    current_user: CurrentUser = Depends(require_student),
) -> OpportunityRecommendationResponse:
    """Platform opportunities and canonical matches for the authenticated student only."""
    try:
        client = build_user_client(current_user.access_token)
        return recommend_opportunities(client, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=500,
            detail="Could not load your opportunity recommendations. Please try again.") from exc


@router.post("/career-guidance", response_model=CareerGuidanceResponse)
def get_career_guidance(
    current_user: CurrentUser = Depends(require_student),
) -> CareerGuidanceResponse:
    """The calling student's own consolidated career guidance -- the
    Career Orchestrator (app.ai.orchestrator) coordinating the Skill
    Gap, Course Recommendation, and Opportunity Recommendation agents,
    then the Career Advisor synthesis on top of their grounded outputs.

    Every specialist call is isolated inside build_career_guidance
    itself: one specialist (or the Career Advisor) failing degrades
    that section only (see `meta.agents_used`) and never fails the
    whole request -- so this route's own bare except only ever catches
    a genuinely unexpected failure (e.g. build_user_client itself
    failing), never an ordinary AI/provider failure.
    """
    try:
        client = build_user_client(current_user.access_token)
        return build_career_guidance(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build your career guidance. Please try again.",
        ) from exc


@router.post("/career-chat", response_model=CareerChatResponse)
def post_career_chat(
    body: CareerChatRequest,
    current_user: CurrentUser = Depends(require_student),
) -> CareerChatResponse:
    """The calling student's own Career AI Chat turn (app.ai.chat.career_chat).

    Never accepts a student_id -- student_id is always current_user.id.
    `body` is validated by CareerChatRequest (extra="forbid", bounded
    message/history length) before this function ever runs. Every
    canonical fact behind a chat response is re-fetched fresh from this
    request's own specialist call -- history is conversational context
    only, never a source of canonical data (see app.ai.chat.career_chat's
    own module docstring). career_chat() isolates its own specialist
    failures internally; this route's bare except only ever catches a
    genuinely unexpected failure (e.g. build_user_client itself failing).
    """
    try:
        client = build_user_client(current_user.access_token)
        return career_chat(client, current_user.id, body.message, body.history)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process your message. Please try again.",
        ) from exc
