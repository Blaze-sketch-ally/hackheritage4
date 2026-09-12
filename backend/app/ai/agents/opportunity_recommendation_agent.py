"""Phase 5 platform-only ranking. No external discovery or career orchestration."""
from supabase import Client

from app.ai.client import groq_client
from app.ai.config import ai_settings
from app.ai.exceptions import AIError
from app.ai.guardrails.opportunity_recommendation import (
    allowed_codes,
    deterministic_fallback,
    ground,
)
from app.ai.prompts.opportunity_recommendation import OPPORTUNITY_SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas.opportunity_recommendation import (
    OpportunityCanonical,
    OpportunityInputCandidate,
    OpportunityRecommendationAgentInput,
    OpportunityRecommendationLLMOutput,
    OpportunityRecommendationMeta,
    OpportunityRecommendationResponse,
)
from app.ai.tools import opportunity_candidates, skill_tools


def build_agent_input(candidates, target_role: str | None) -> OpportunityRecommendationAgentInput:
    """Selected-role context and bounded canonical match evidence, no student identity.

    Match skill lists already contain the relevant owned/verified-skill evidence;
    no full StudentCareerContext, independent gap calculation, or other agent call.
    """
    return OpportunityRecommendationAgentInput(target_role=target_role[:200] if target_role else None,
        opportunity_candidates=[OpportunityInputCandidate(ref=c.candidate_ref,
            opportunity_type=c.opportunity.source_type, title=c.opportunity.title[:200],
            description=c.opportunity.description[:500],
            location=c.opportunity.location[:120] if c.opportunity.location else None,
            work_mode=c.opportunity.work_mode, score=c.match.score, band=c.match.recommendation,
            matched_count=c.match.matched_count, improvement_count=c.match.needs_improvement_count,
            missing_count=c.match.missing_count,
            matched_skills=[s.skill_name[:80] for s in c.match.matched_skills[:8]],
            improvement_skills=[s.skill_name[:80] for s in c.match.needs_improvement_skills[:8]],
            missing_skills=[s.skill_name[:80] for s in c.match.missing_skills[:8]],
            allowed_reason_codes=allowed_codes(c, target_role)) for c in candidates])


def recommend_opportunities(client: Client, student_id: str) -> OpportunityRecommendationResponse:
    # Canonical source errors deliberately propagate to the API's generic 500.
    candidates = opportunity_candidates.get_candidates(client, student_id)
    target = skill_tools.get_target_job_role(client, student_id) if candidates else None
    target_role = target.job_role.name if target else None
    recommendations, plan = deterministic_fallback(candidates)
    status = "DETERMINISTIC" if candidates else "NO_CANDIDATES"
    ai_available = False
    message = None if candidates else "No current platform recommendations are available."
    if candidates:
        try:
            output = groq_client.complete_structured(system=OPPORTUNITY_SYSTEM_PROMPT,
                user=build_user_prompt(build_agent_input(candidates, target_role)),
                response_model=OpportunityRecommendationLLMOutput)
            ranked, order = ground(output, candidates, target_role)
            if ranked:
                recommendations, plan = ranked, order
                ai_available, status = True, "AI"
            else:
                message = "AI ranking could not be grounded; deterministic recommendations are shown."
        except AIError:
            message = "AI ranking is unavailable; deterministic recommendations are shown."
    return OpportunityRecommendationResponse(
        canonical=OpportunityCanonical(target_role=target_role, candidate_count=len(candidates)),
        recommendations=recommendations, application_order=plan,
        meta=OpportunityRecommendationMeta(model=ai_settings.groq_model,
            ai_available=ai_available, ranking_status=status, message=message))
