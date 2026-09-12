"""The Career Advisor (Phase 6) -- a synthesis-ONLY agent.

Unlike the three specialists, this agent never reads Supabase and never
calls a Phase-2 tool: its entire input is built from the three
specialists' OWN already-grounded response objects (skill_gap_agent,
course_recommendation_agent, opportunity_recommendation_agent), passed
in by app.ai.orchestrator. It reasons only about what those agents
already validated -- it cannot introduce a new skill, course,
opportunity, or assessment, and it never recalculates readiness, match
scores, or verification.

`build_advisor_input` assigns a FRESH ref namespace (G#/C#/OP#/A#) over
the specialists' final objects for this agent's own prompt/output
contract -- these are NOT the same ref tokens the specialists used
internally with Groq (those don't survive into the final response
objects at all).
"""

from app.ai.client import groq_client
from app.ai.guardrails.career_advisor import GroundedAdvisorOutput, ground_advisor
from app.ai.prompts.career_advisor import CAREER_ADVISOR_SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas.career_guidance import (
    AdvisorInputAssessmentAction,
    AdvisorInputCourse,
    AdvisorInputOpportunity,
    AdvisorInputSkill,
    CareerAdvisorAgentInput,
    CareerAdvisorLLMOutput,
)
from app.ai.schemas.course_recommendation import CourseRecommendation, CourseRecommendationResponse
from app.ai.schemas.opportunity_recommendation import (
    OpportunityRecommendation,
    OpportunityRecommendationResponse,
)
from app.ai.schemas.skill_gap import AssessmentAction, PriorityGapAnalysis, SkillGapAgentResponse
from app.schemas.skill_gap import AnalysisMode

AdvisorIndexes = dict[str, dict[str, object]]


def build_advisor_input(
    skill_gap_response: SkillGapAgentResponse | None,
    course_response: CourseRecommendationResponse | None,
    opportunity_response: OpportunityRecommendationResponse | None,
    *,
    target_role: str | None,
    readiness_score: int | None,
    mode: AnalysisMode,
) -> tuple[CareerAdvisorAgentInput, AdvisorIndexes]:
    """Build the minimal, ref-annotated advisor input + the lookup
    indexes app.ai.guardrails.career_advisor will resolve LLM refs
    against. Never touches the DB; purely a projection over the three
    specialists' own output objects."""
    skill_index: dict[str, PriorityGapAnalysis] = {}
    if skill_gap_response is not None:
        for number, gap in enumerate(skill_gap_response.analysis.priority_gaps, 1):
            skill_index[f"G{number}"] = gap
    skill_id_to_ref = {gap.skill_id: ref for ref, gap in skill_index.items()}

    assessment_index: dict[str, AssessmentAction] = {}
    if skill_gap_response is not None:
        for number, action in enumerate(skill_gap_response.analysis.assessment_actions, 1):
            assessment_index[f"A{number}"] = action

    course_index: dict[str, CourseRecommendation] = {}
    if course_response is not None:
        for number, rec in enumerate(course_response.recommendations, 1):
            course_index[f"C{number}"] = rec

    opportunity_index: dict[str, OpportunityRecommendation] = {}
    if opportunity_response is not None:
        for number, rec in enumerate(opportunity_response.recommendations, 1):
            opportunity_index[f"OP{number}"] = rec

    agent_input = CareerAdvisorAgentInput(
        target_role=target_role[:200] if target_role else None,
        readiness_score=readiness_score,
        mode=mode,
        skills=[
            AdvisorInputSkill(
                ref=ref,
                skill_name=gap.skill_name[:120],
                canonical_status=gap.canonical_status,
                canonical_priority=gap.canonical_priority,
                canonical_importance=gap.canonical_importance,
            )
            for ref, gap in skill_index.items()
        ],
        courses=[
            AdvisorInputCourse(
                ref=ref,
                title=rec.course.title[:200],
                for_skill_ref=skill_id_to_ref.get(rec.for_skill.skill_id),
            )
            for ref, rec in course_index.items()
        ],
        opportunities=[
            AdvisorInputOpportunity(
                ref=ref,
                title=rec.opportunity.title[:200],
                opportunity_type=rec.opportunity.source_type,
                match_band=rec.match.recommendation,
                match_score=rec.match.score,
            )
            for ref, rec in opportunity_index.items()
        ],
        assessment_actions=[
            AdvisorInputAssessmentAction(
                ref=ref, skill_name=action.skill_name[:120], action=action.action.value
            )
            for ref, action in assessment_index.items()
        ],
    )

    indexes: AdvisorIndexes = {
        "skill": skill_index,
        "course": course_index,
        "opportunity": opportunity_index,
        "assessment": assessment_index,
    }
    return agent_input, indexes


def run_career_advisor(
    skill_gap_response: SkillGapAgentResponse | None,
    course_response: CourseRecommendationResponse | None,
    opportunity_response: OpportunityRecommendationResponse | None,
    *,
    target_role: str | None,
    readiness_score: int | None,
    mode: AnalysisMode,
) -> tuple[GroundedAdvisorOutput | None, AdvisorIndexes]:
    """Returns (None, indexes) without any Groq call when there is
    nothing grounded to synthesize (no priority gaps, courses,
    opportunities, or assessment actions at all) -- the same
    "skip when empty" pattern every earlier agent uses. Raises whatever
    groq_client.complete_structured raises on a real attempt; the
    caller (app.ai.orchestrator) decides how to degrade."""
    agent_input, indexes = build_advisor_input(
        skill_gap_response,
        course_response,
        opportunity_response,
        target_role=target_role,
        readiness_score=readiness_score,
        mode=mode,
    )

    if not (
        agent_input.skills
        or agent_input.courses
        or agent_input.opportunities
        or agent_input.assessment_actions
    ):
        return None, indexes

    llm_output: CareerAdvisorLLMOutput = groq_client.complete_structured(
        system=CAREER_ADVISOR_SYSTEM_PROMPT,
        user=build_user_prompt(agent_input),
        response_model=CareerAdvisorLLMOutput,
    )
    grounded = ground_advisor(
        llm_output,
        skill_index=indexes["skill"],
        course_index=indexes["course"],
        opportunity_index=indexes["opportunity"],
        assessment_index=indexes["assessment"],
    )
    return grounded, indexes
