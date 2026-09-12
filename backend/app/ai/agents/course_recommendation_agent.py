"""Phase 4 only: canonical skill selection, source discovery, one bounded ranking call."""

from supabase import Client

from app.ai.agents.youtube_recommendation_agent import recommend_youtube_videos
from app.ai.client import groq_client
from app.ai.config import ai_settings
from app.ai.exceptions import AIError
from app.ai.guardrails.course_recommendation import deterministic_recommendations, ground
from app.ai.prompts.course_recommendation import COURSE_SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas.course_recommendation import (
    CourseCanonical,
    CourseInputCandidate,
    CourseInputSkill,
    CourseLLMOutput,
    CourseRecommendationAgentInput,
    CourseRecommendationResponse,
    CourseResponseMeta,
    CourseSkill,
)
from app.ai.schemas.student_context import SkillGapSection
from app.ai.tools import course_discovery, skill_gap_tools
from app.schemas.skill_gap import AnalysisMode

MAX_SKILLS = 5
_PRIORITY = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}
_IMPORTANCE = {"CORE": 0, "IMPORTANT": 1, "OPTIONAL": 2, None: 3}


def select_skills(section: SkillGapSection) -> CourseCanonical:
    """Select, never rescore. Personal progression has no invented status/priority."""
    selected = []
    target_role = None
    if section.mode == AnalysisMode.JOB_ROLE and section.job_role_analysis:
        analysis = section.job_role_analysis
        target_role = analysis.job_role.name
        reasons = {str(r.skill_id): r.reason for r in analysis.recommendations}
        for item in analysis.skills:
            if item.status.value == "MATCHED":
                continue
            selected.append(
                CourseSkill(
                    ref="",
                    skill_id=str(item.skill_id),
                    skill_name=item.skill_name,
                    status=item.status.value,
                    priority=item.priority.value,
                    importance=item.importance.value,
                    current_level=item.current_level.value if item.current_level else None,
                    target_level=item.required_level.value,
                    reason=reasons.get(str(item.skill_id)),
                )
            )
    elif section.mode == AnalysisMode.PERSONAL and section.personal_analysis:
        for rec in section.personal_analysis.recommendations:
            selected.append(
                CourseSkill(
                    ref="",
                    skill_id=str(rec.skill_id),
                    skill_name=rec.skill_name,
                    priority=rec.priority.value,
                    reason=rec.reason,
                    current_level=rec.current_level.value if rec.current_level else None,
                    target_level=rec.target_level.value if rec.target_level else None,
                )
            )
        for prog in section.personal_analysis.progressable_skills:
            selected.append(
                CourseSkill(
                    ref="",
                    skill_id=str(prog.skill_id),
                    skill_name=prog.skill_name,
                    current_level=prog.current_level.value,
                    target_level=prog.next_level.value,
                )
            )
    selected.sort(key=lambda s: (_PRIORITY[s.priority], _IMPORTANCE[s.importance]))
    unique = {}
    for skill in selected:
        unique.setdefault(skill.skill_id, skill)
    skills = [
        skill.model_copy(update={"ref": f"G{n}"})
        for n, skill in enumerate(list(unique.values())[:MAX_SKILLS], 1)
    ]
    return CourseCanonical(mode=section.mode, target_role=target_role, skills_considered=skills)


def build_agent_input(canonical, candidates) -> CourseRecommendationAgentInput:
    """No identity, URLs, application history or unrelated owned skills are sent.

    Current levels on selected gaps are the relevant owned-skill context. IDs,
    prices, certificates and provider labels stay in server-owned candidate data.
    """
    return CourseRecommendationAgentInput(
        target_role=canonical.target_role[:200] if canonical.target_role else None,
        top_skill_gaps=[
            CourseInputSkill(
                ref=s.ref,
                name=s.skill_name[:120],
                status=s.status,
                priority=s.priority,
                importance=s.importance,
                current_level=s.current_level,
                target_level=s.target_level,
            )
            for s in canonical.skills_considered
        ],
        course_candidates=[
            CourseInputCandidate(
                ref=ref,
                title=c.title[:200],
                description=c.description[:600] if c.description else None,
                level=c.level,
                skill_refs=[
                    s.ref for s in canonical.skills_considered if s.skill_id in c.skill_ids
                ],
            )
            for ref, c in candidates.items()
        ],
    )


def recommend_courses(client: Client, student_id: str) -> CourseRecommendationResponse:
    canonical = select_skills(skill_gap_tools.get_current_skill_gap(client, student_id))
    if not canonical.skills_considered:
        return CourseRecommendationResponse(
            canonical=canonical,
            meta=CourseResponseMeta(
                model=ai_settings.groq_model,
                ranking_status="NO_GAPS",
                external_discovery_status="CONFIGURATION_REQUIRED",
                message="No canonical learning priorities are available.",
            ),
        )
    found, internal_available, external_status = course_discovery.discover_candidates(
        client, student_id, canonical.skills_considered
    )
    candidates = {f"C{n}": c for n, c in enumerate(found, 1)}
    skills = {s.ref: s for s in canonical.skills_considered}
    recommendations, plan = deterministic_recommendations(candidates, skills)
    ai_available = False
    ranking_status = "DETERMINISTIC" if candidates else "NO_COURSES"
    message = "No source-backed resources are currently available." if not candidates else None
    if candidates:
        try:
            output = groq_client.complete_structured(
                system=COURSE_SYSTEM_PROMPT,
                user=build_user_prompt(build_agent_input(canonical, candidates)),
                response_model=CourseLLMOutput,
            )
            ranked, ordered = ground(output, candidates, skills)
            if ranked:
                recommendations, plan = ranked, ordered
                ai_available, ranking_status = True, "AI"
            else:
                message = "AI ranking could not be grounded; source recommendations are shown."
        except AIError:
            message = "AI ranking is unavailable; source recommendations are shown."
    # YouTube (Phase 4.7) is a fully separate, additive channel -- its
    # own failure never touches the course pipeline above, and vice
    # versa. recommend_youtube_videos() already never raises for an
    # ordinary AI/provider failure; this only guards a genuinely
    # unexpected bug in that agent itself.
    try:
        youtube_videos, youtube_available, youtube_ai_available, youtube_status = (
            recommend_youtube_videos(canonical)
        )
    except Exception:  # noqa: BLE001 -- isolate the YouTube channel; never fail this endpoint for it
        youtube_videos, youtube_available, youtube_ai_available, youtube_status = [], False, False, "FAILED"
    return CourseRecommendationResponse(
        canonical=canonical,
        recommendations=recommendations,
        learning_plan=plan,
        youtube_videos=youtube_videos,
        meta=CourseResponseMeta(
            model=ai_settings.groq_model,
            ai_ranking_available=ai_available,
            ranking_status=ranking_status,
            external_discovery_available=external_status == "AVAILABLE",
            external_discovery_status=external_status,
            internal_discovery_available=internal_available,
            message=message,
            youtube_available=youtube_available,
            youtube_ai_ranking_available=youtube_ai_available,
            youtube_status=youtube_status,
        ),
    )
