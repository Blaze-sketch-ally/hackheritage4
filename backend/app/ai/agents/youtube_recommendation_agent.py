"""Phase 4.7: YouTube video recommendations for a student's top actionable skill gaps.

Reuses the Course Recommendation Agent's own canonical skill selection
(course_recommendation_agent.select_skills) rather than re-deriving
anything from the Skill Gap engine -- this module only re-prioritizes
and truncates that already-canonical, already-deduped, already-G-ref'd
list to the top MAX_YOUTUBE_SKILLS actionable gaps, per this phase's own
quota-driven scope (see app.ai.tools.youtube_learning's module
docstring). Called from app.ai.agents.course_recommendation_agent so
CourseRecommendationResponse.youtube_videos is populated in the same
request, never a second canonical-skill computation.
"""

from app.ai.client import groq_client
from app.ai.exceptions import AIError
from app.ai.guardrails.youtube_learning import deterministic_recommendations, ground
from app.ai.prompts.youtube_learning import YOUTUBE_SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas.course_recommendation import CourseCanonical, CourseSkill
from app.ai.schemas.youtube_learning import (
    YouTubeInputVideo,
    YouTubeLLMOutput,
    YouTubeRecommendation,
    YouTubeRecommendationAgentInput,
    YouTubeSkillRef,
    YouTubeVideoCandidate,
)
from app.ai.tools import youtube_learning

MAX_YOUTUBE_SKILLS = 3
# Explicit combined tiers, NOT a lexicographic (status, importance)
# sort -- the required order groups by IMPORTANCE first, with status as
# the tiebreak within it (MISSING+CORE, NEEDS_IMPROVEMENT+CORE,
# MISSING+IMPORTANT, NEEDS_IMPROVEMENT+IMPORTANT), which a plain tuple
# sort would get wrong (it would group by status first instead).
_COMBINED_RANK = {
    ("MISSING", "CORE"): 0,
    ("NEEDS_IMPROVEMENT", "CORE"): 1,
    ("MISSING", "IMPORTANT"): 2,
    ("NEEDS_IMPROVEMENT", "IMPORTANT"): 3,
}
_UNRANKED_TIER = len(_COMBINED_RANK)


def select_youtube_skills(canonical: CourseCanonical) -> list[CourseSkill]:
    """Top actionable gaps only, per this phase's own priority scheme:
    MISSING+CORE, then NEEDS_IMPROVEMENT+CORE, then MISSING+IMPORTANT,
    then NEEDS_IMPROVEMENT+IMPORTANT, everything else (optional
    importance, matched status, or personal-progression skills with no
    status/importance at all) last, in original order. A
    re-prioritization of the SAME canonical.skills_considered the
    Course Recommendation Agent already selected -- never a fresh read
    of the Skill Gap engine, never a re-scoring of status/importance."""
    ranked = sorted(
        canonical.skills_considered,
        key=lambda s: _COMBINED_RANK.get((s.status, s.importance), _UNRANKED_TIER),
    )
    return ranked[:MAX_YOUTUBE_SKILLS]


def _to_skill_ref(skill: CourseSkill) -> YouTubeSkillRef:
    return YouTubeSkillRef(
        ref=skill.ref,
        skill_id=skill.skill_id,
        skill_name=skill.skill_name,
        status=skill.status,
        importance=skill.importance,
        target_level=skill.target_level,
    )


def build_agent_input(
    skills: list[YouTubeSkillRef], candidates: dict[str, YouTubeVideoCandidate]
) -> YouTubeRecommendationAgentInput:
    """No channel ID, URL, view/like counts, thumbnails or publish dates
    are sent -- skill status/importance/target_level are the relevant
    canonical context; every other fact stays server-owned candidate
    data (see YouTubeLLMOutput's extra="forbid")."""
    return YouTubeRecommendationAgentInput(
        top_skill_gaps=skills,
        video_candidates=[
            YouTubeInputVideo(
                ref=ref,
                title=video.title[:200],
                description=video.description[:600] if video.description else None,
                channel_title=video.channel_title[:100],
                duration_text=video.duration_text,
                skill_refs=[s.ref for s in skills if s.skill_id == video.skill_id],
            )
            for ref, video in candidates.items()
        ],
    )


def recommend_youtube_videos(
    canonical: CourseCanonical,
) -> tuple[list[YouTubeRecommendation], bool, bool, str]:
    """Returns (recommendations, available, ai_ranking_available, status).

    Never raises -- every YouTube/Groq failure degrades to a smaller or
    empty result, exactly like the Course Recommendation Agent's own
    pattern (see app.ai.agents.course_recommendation_agent). YouTube
    unavailability never depends on, and never blocks, internal course
    recommendations -- this function's caller merges its result
    additively.
    """
    top_skills = select_youtube_skills(canonical)
    if not top_skills:
        return [], False, False, "CONFIGURATION_REQUIRED"

    found, status = youtube_learning.discover_for_skills(top_skills)
    if not found:
        return [], status == "AVAILABLE", False, status

    skill_refs = [_to_skill_ref(s) for s in top_skills]
    skills_by_ref = {s.ref: s for s in skill_refs}
    candidates = {
        f"Y{n}": video.model_copy(update={"video_ref": f"Y{n}"}) for n, video in enumerate(found, 1)
    }

    recommendations = deterministic_recommendations(candidates, skills_by_ref)
    ai_ranking_available = False
    try:
        output = groq_client.complete_structured(
            system=YOUTUBE_SYSTEM_PROMPT,
            user=build_user_prompt(build_agent_input(skill_refs, candidates)),
            response_model=YouTubeLLMOutput,
        )
        ranked = ground(output, candidates, skills_by_ref)
        if ranked:
            recommendations = ranked
            ai_ranking_available = True
    except AIError:
        pass

    return recommendations, True, ai_ranking_available, "AVAILABLE"
