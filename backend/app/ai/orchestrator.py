"""The Career Orchestrator (Phase 6).

Deterministic coordination only -- see the Phase 6 report for why an
LLM-based planner was deliberately NOT introduced here: the set of
specialists to call never varies (always all three: Skill Gap, Course
Recommendation, Opportunity Recommendation), so there is no genuine
planning decision for an LLM to make. The only LLM call in this whole
module is the one Career Advisor synthesis call, made through
app.ai.agents.career_advisor_agent -- everything else is plain Python
control flow calling the EXISTING, already-validated specialist agents
verbatim.

`build_career_guidance` never queries Supabase directly (every read
happens inside the specialist agents it calls, each already scoped to
`client`/`student_id` the caller supplies), never recalculates
readiness/match/verification, and never writes anything. Each
specialist call is isolated in its own try/except so that one
specialist failing never takes the other two down with it -- see each
`_run_*` helper's own docstring for its specific degrade path.
"""

import logging

from supabase import Client

from app.ai.agents.career_advisor_agent import build_advisor_input, run_career_advisor
from app.ai.agents.course_recommendation_agent import recommend_courses
from app.ai.agents.opportunity_recommendation_agent import recommend_opportunities
from app.ai.agents.skill_gap_agent import analyze_student_skill_gap, build_canonical_summary_only
from app.ai.config import ai_settings
from app.ai.exceptions import AIError
from app.ai.guardrails.career_advisor import GroundedAdvisorOutput
from app.ai.schemas.base import AIResponseMeta
from app.ai.schemas.career_guidance import (
    AgentStatus,
    AssessmentRecommendationItem,
    CareerGuidanceAgentsUsed,
    CareerGuidanceMeta,
    CareerGuidanceResponse,
    CareerSummary,
    LearningRecommendationItem,
    NextAction,
    OpportunityRecommendationItem,
    PrioritySkill,
    YouTubeRecommendationItem,
)
from app.ai.schemas.course_recommendation import CourseRecommendationResponse
from app.ai.schemas.opportunity_recommendation import OpportunityRecommendationResponse
from app.ai.schemas.skill_gap import SkillGapAgentResponse, SkillGapAnalysis
from app.schemas.skill_gap import AnalysisMode

logger = logging.getLogger("app.ai")

_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}


def _run_skill_gap(client: Client, student_id: str) -> tuple[SkillGapAgentResponse | None, AgentStatus]:
    """Skill Gap Agent unavailable (Groq failure, or any unexpected
    error) -> still return the canonical summary alone
    (build_canonical_summary_only, no Groq call) whenever that canonical
    read itself succeeds; only a canonical-read failure too (Supabase
    itself unreachable) yields None."""
    try:
        result = analyze_student_skill_gap(client, student_id)
        return result, AgentStatus(available=True, fallback_used=False)
    except AIError as exc:
        logger.warning("Skill Gap Agent unavailable for student %s: %s", student_id, exc.__class__.__name__)
        detail = "AI interpretation unavailable; canonical skill-gap data is shown."
    except Exception:
        logger.exception("Skill Gap Agent failed unexpectedly for student %s", student_id)
        detail = "Skill Gap Agent failed unexpectedly; canonical skill-gap data is shown."

    try:
        canonical = build_canonical_summary_only(client, student_id)
    except Exception:
        logger.exception("Canonical skill-gap fallback also failed for student %s", student_id)
        return None, AgentStatus(available=False, fallback_used=True, detail="Skill Gap Agent unavailable.")

    fallback = SkillGapAgentResponse(
        canonical=canonical,
        analysis=SkillGapAnalysis(summary=detail),
        meta=AIResponseMeta(model=ai_settings.groq_model),
    )
    return fallback, AgentStatus(available=True, fallback_used=True, detail=detail)


def _run_courses(client: Client, student_id: str) -> tuple[CourseRecommendationResponse | None, AgentStatus]:
    """Course Recommendation Agent unavailable -> the whole section is
    omitted from the response (never fabricated); skill/opportunity
    guidance still returns normally. The agent's OWN internal
    deterministic fallback already covers a bare Groq failure (see
    app.ai.agents.course_recommendation_agent) -- this only catches a
    genuinely unexpected failure of the agent call itself."""
    try:
        result = recommend_courses(client, student_id)
        return result, AgentStatus(
            available=True, fallback_used=not result.meta.ai_ranking_available, detail=result.meta.message
        )
    except Exception:
        logger.exception("Course Recommendation Agent unavailable for student %s", student_id)
        return None, AgentStatus(
            available=False, fallback_used=True, detail="Course Recommendation Agent unavailable."
        )


def _run_opportunities(
    client: Client, student_id: str
) -> tuple[OpportunityRecommendationResponse | None, AgentStatus]:
    """Same pattern as _run_courses, for the Opportunity Recommendation
    Agent."""
    try:
        result = recommend_opportunities(client, student_id)
        return result, AgentStatus(
            available=True, fallback_used=not result.meta.ai_available, detail=result.meta.message
        )
    except Exception:
        logger.exception("Opportunity Recommendation Agent unavailable for student %s", student_id)
        return None, AgentStatus(
            available=False, fallback_used=True, detail="Opportunity Recommendation Agent unavailable."
        )


def build_career_guidance(client: Client, student_id: str) -> CareerGuidanceResponse:
    """The caller's own consolidated career guidance. Calls each
    specialist exactly once; never re-derives any canonical fact the
    specialists already computed."""
    skill_gap_response, skill_gap_status = _run_skill_gap(client, student_id)
    course_response, course_status = _run_courses(client, student_id)
    opportunity_response, opportunity_status = _run_opportunities(client, student_id)

    target_role = skill_gap_response.canonical.target_role if skill_gap_response else None
    readiness_score = skill_gap_response.canonical.readiness_score if skill_gap_response else None
    mode = skill_gap_response.canonical.mode if skill_gap_response else AnalysisMode.PERSONAL

    advisor_output: GroundedAdvisorOutput | None = None
    indexes = None
    try:
        advisor_output, indexes = run_career_advisor(
            skill_gap_response,
            course_response,
            opportunity_response,
            target_role=target_role,
            readiness_score=readiness_score,
            mode=mode,
        )
        if advisor_output is None:
            advisor_status = AgentStatus(
                available=True, fallback_used=True, detail="No grounded data to synthesize yet."
            )
        else:
            advisor_status = AgentStatus(available=True, fallback_used=False)
    except AIError as exc:
        logger.warning("Career Advisor unavailable for student %s: %s", student_id, exc.__class__.__name__)
        _, indexes = build_advisor_input(
            skill_gap_response,
            course_response,
            opportunity_response,
            target_role=target_role,
            readiness_score=readiness_score,
            mode=mode,
        )
        advisor_status = AgentStatus(
            available=False, fallback_used=True, detail="AI synthesis unavailable; specialist data is shown."
        )
    except Exception:
        logger.exception("Career Advisor failed unexpectedly for student %s", student_id)
        try:
            _, indexes = build_advisor_input(
                skill_gap_response,
                course_response,
                opportunity_response,
                target_role=target_role,
                readiness_score=readiness_score,
                mode=mode,
            )
        except Exception:
            logger.exception("Advisor-input rebuild also failed for student %s", student_id)
            indexes = None
        advisor_status = AgentStatus(
            available=False, fallback_used=True, detail="Career Advisor unavailable; specialist data is shown."
        )

    return _assemble_response(
        skill_gap_response=skill_gap_response,
        course_response=course_response,
        opportunity_response=opportunity_response,
        advisor_output=advisor_output,
        indexes=indexes,
        target_role=target_role,
        readiness_score=readiness_score,
        mode=mode,
        statuses=(skill_gap_status, course_status, opportunity_status, advisor_status),
    )


def _assemble_response(
    *,
    skill_gap_response: SkillGapAgentResponse | None,
    course_response: CourseRecommendationResponse | None,
    opportunity_response: OpportunityRecommendationResponse | None,
    advisor_output: GroundedAdvisorOutput | None,
    indexes: dict[str, dict[str, object]] | None,
    target_role: str | None,
    readiness_score: int | None,
    mode: AnalysisMode,
    statuses: tuple[AgentStatus, AgentStatus, AgentStatus, AgentStatus],
) -> CareerGuidanceResponse:
    skill_gap_status, course_status, opportunity_status, advisor_status = statuses
    indexes = indexes or {"skill": {}, "course": {}, "opportunity": {}, "assessment": {}}

    focus_refs = advisor_output.focus_skill_refs if advisor_output else []
    course_refs = advisor_output.course_refs if advisor_output else []
    opportunity_refs = advisor_output.opportunity_refs if advisor_output else []
    action_pairs = advisor_output.actions if advisor_output else []

    priority_skills = _ordered_priority_skills(indexes["skill"], focus_refs)
    learning_recommendations = _ordered_learning(indexes["course"], course_refs)
    youtube_videos = _youtube_items(course_response)
    opportunity_recommendations = _ordered_opportunities(indexes["opportunity"], opportunity_refs)
    assessment_recommendations = _assessment_items(indexes["assessment"])
    next_actions = _build_next_actions(action_pairs, indexes)

    career_summary = CareerSummary(
        mode=mode,
        target_role=target_role,
        readiness_score=readiness_score,
        headline=advisor_output.headline if advisor_output and advisor_output.headline else None,
    )

    meta = CareerGuidanceMeta(
        model=ai_settings.groq_model,
        ai_available=advisor_status.available and not advisor_status.fallback_used,
        agents_used=CareerGuidanceAgentsUsed(
            skill_gap_agent=skill_gap_status,
            course_agent=course_status,
            opportunity_agent=opportunity_status,
            career_advisor=advisor_status,
        ),
    )

    return CareerGuidanceResponse(
        career_summary=career_summary,
        priority_skills=priority_skills,
        learning_recommendations=learning_recommendations,
        youtube_videos=youtube_videos,
        opportunity_recommendations=opportunity_recommendations,
        assessment_recommendations=assessment_recommendations,
        next_actions=next_actions,
        meta=meta,
    )


def _highlighted_first(items_by_ref: dict[str, object], highlighted_refs: list[str]) -> list[tuple[str, object]]:
    """Advisor-selected refs first (in the advisor's own order), then
    everything else in original index order -- a deterministic,
    always-defined ordering whether or not the advisor ran."""
    highlighted = [(ref, items_by_ref[ref]) for ref in highlighted_refs if ref in items_by_ref]
    rest = [(ref, item) for ref, item in items_by_ref.items() if ref not in highlighted_refs]
    return highlighted + rest


def _ordered_priority_skills(skill_index: dict, focus_refs: list[str]) -> list[PrioritySkill]:
    highlighted_set = set(focus_refs)
    ordered = _highlighted_first(skill_index, focus_refs)
    if not focus_refs:
        # No advisor input to order by -- deterministic canonical-priority fallback.
        ordered = sorted(ordered, key=lambda pair: _PRIORITY_RANK.get(pair[1].canonical_priority))
    return [
        PrioritySkill(
            skill_id=gap.skill_id,
            skill_name=gap.skill_name,
            canonical_status=gap.canonical_status,
            canonical_priority=gap.canonical_priority,
            canonical_importance=gap.canonical_importance,
            reason=gap.reason,
            suggested_action=gap.suggested_action,
            highlighted_by_advisor=ref in highlighted_set,
        )
        for ref, gap in ordered
    ]


def _ordered_learning(course_index: dict, course_refs: list[str]) -> list[LearningRecommendationItem]:
    highlighted_set = set(course_refs)
    ordered = _highlighted_first(course_index, course_refs)
    return [
        LearningRecommendationItem(
            course=rec.course,
            for_skill_id=rec.for_skill.skill_id,
            for_skill_name=rec.for_skill.skill_name,
            reason=rec.reason,
            highlighted_by_advisor=ref in highlighted_set,
        )
        for ref, rec in ordered
    ]


def _youtube_items(
    course_response: CourseRecommendationResponse | None,
) -> list[YouTubeRecommendationItem]:
    """Straight passthrough of the Course Recommendation Agent's own
    additive YouTube channel (app.ai.agents.youtube_recommendation_agent)
    -- already grounded there; never touched by the Career Advisor,
    which has no Y-ref namespace (see YouTubeRecommendationItem's own
    docstring). An unavailable/failed course_response yields none,
    same as every other section here."""
    if course_response is None:
        return []
    return [
        YouTubeRecommendationItem(
            video=rec.video,
            for_skill_id=rec.for_skill.skill_id,
            for_skill_name=rec.for_skill.skill_name,
            reason=rec.reason,
        )
        for rec in course_response.youtube_videos
    ]


def _ordered_opportunities(
    opportunity_index: dict, opportunity_refs: list[str]
) -> list[OpportunityRecommendationItem]:
    highlighted_set = set(opportunity_refs)
    ordered = _highlighted_first(opportunity_index, opportunity_refs)
    return [
        OpportunityRecommendationItem(
            opportunity=rec.opportunity,
            match=rec.match,
            reason=rec.reason,
            highlighted_by_advisor=ref in highlighted_set,
        )
        for ref, rec in ordered
    ]


def _assessment_items(assessment_index: dict) -> list[AssessmentRecommendationItem]:
    return [
        AssessmentRecommendationItem(
            skill_id=action.skill_id,
            skill_name=action.skill_name,
            action=action.action,
            assessment_available=action.assessment_available,
            note=action.note,
        )
        for action in assessment_index.values()
    ]


_ENTITY_TYPE_BY_NAMESPACE = {"G": "SKILL", "C": "COURSE", "OP": "OPPORTUNITY", "A": "ASSESSMENT"}


def _build_next_actions(
    action_pairs: list[tuple[str, str]], indexes: dict[str, dict[str, object]]
) -> list[NextAction]:
    """Built ONLY from grounded (ref, code) pairs the guardrail already
    validated -- entity_id/entity_name are copied from the referenced
    specialist object, never from LLM text."""
    from app.ai.guardrails.career_advisor import ref_namespace

    actions: list[NextAction] = []
    for order, (ref, code) in enumerate(action_pairs, 1):
        namespace = ref_namespace(ref)
        if namespace is None:
            continue
        entity_type = _ENTITY_TYPE_BY_NAMESPACE[namespace]
        index_key = {"G": "skill", "C": "course", "OP": "opportunity", "A": "assessment"}[namespace]
        entity = indexes.get(index_key, {}).get(ref)
        if entity is None:
            continue
        entity_id, entity_name = _entity_identity(namespace, entity)
        actions.append(
            NextAction(
                order=order,
                type=code,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
            )
        )
    return actions


def _entity_identity(namespace: str, entity: object) -> tuple[str, str]:
    if namespace == "G":
        return entity.skill_id, entity.skill_name
    if namespace == "C":
        return entity.course.candidate_id, entity.course.title
    if namespace == "OP":
        return entity.opportunity.id, entity.opportunity.title
    return entity.skill_id, entity.skill_name
