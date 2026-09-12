"""Closed-vocabulary explanations, ref grounding, and server metadata
attachment -- the same boundary as app.ai.guardrails.course_recommendation,
for YouTube video candidates.

Unlike a source-listed course level (Microsoft Learn/an internal
resource's own `difficulty` column), a YouTube video carries no
independently-verified "level" or "format" field -- so every rationale
code here is grounded against the video's OWN title/description text
(real source evidence), never guessed and never something Groq can
supply freely (see YouTubeLLMOutput's extra="forbid").
"""

import re

from app.ai.schemas.youtube_learning import (
    YouTubeLLMOutput,
    YouTubeRecommendation,
    YouTubeSkillRef,
    YouTubeVideoCandidate,
)

_NOTE = re.compile(
    r"^(Y[1-9][0-9]*) -> (G[1-9][0-9]*): "
    r"(SKILL_GAP_MATCH|LEVEL_MATCH|FOUNDATION|PRACTICAL_TUTORIAL|DEEP_DIVE)$"
)
_REASONS = {
    "SKILL_GAP_MATCH": "This video is for a skill in your learning priorities.",
    "LEVEL_MATCH": "This video's own title or description names your target level for this skill.",
    "FOUNDATION": "This video introduces a skill you haven't started yet.",
    "PRACTICAL_TUTORIAL": "This video is a hands-on, practical tutorial.",
    "DEEP_DIVE": "This video is a deeper, more advanced treatment of this skill.",
}
_FOUNDATION_TERMS = ("beginner", "introduction", "basics", "getting started")
_PRACTICAL_TERMS = ("tutorial", "hands-on", "hands on", "practical", "project", "build")
_DEEP_DIVE_TERMS = ("advanced", "deep dive", "in depth", "in-depth", "masterclass", "complete guide")


def _video_text(video: YouTubeVideoCandidate) -> str:
    return f"{video.title} {video.description or ''}".lower()


def allowed_reason(code: str, video: YouTubeVideoCandidate, skill: YouTubeSkillRef) -> bool:
    if skill.skill_id != video.skill_id:
        return False
    text = _video_text(video)
    if code == "SKILL_GAP_MATCH":
        return True
    if code == "LEVEL_MATCH":
        return bool(skill.target_level) and skill.target_level.lower() in text
    if code == "FOUNDATION":
        return skill.status == "MISSING" and any(term in text for term in _FOUNDATION_TERMS)
    if code == "PRACTICAL_TUTORIAL":
        return any(term in text for term in _PRACTICAL_TERMS)
    if code == "DEEP_DIVE":
        return any(term in text for term in _DEEP_DIVE_TERMS)
    return False


def ground(
    output: YouTubeLLMOutput,
    candidates: dict[str, YouTubeVideoCandidate],
    skills: dict[str, YouTubeSkillRef],
) -> list[YouTubeRecommendation]:
    notes: dict[str, tuple[YouTubeSkillRef, str]] = {}
    for line in output.recommendation_codes:
        match = _NOTE.fullmatch(line.strip())
        if not match:
            continue
        y_ref, g_ref, code = match.groups()
        if (
            y_ref in candidates
            and g_ref in skills
            and allowed_reason(code, candidates[y_ref], skills[g_ref])
        ):
            notes.setdefault(y_ref, (skills[g_ref], code))

    selected: dict[str, tuple[YouTubeSkillRef, str]] = {}
    for y_ref in output.recommended_video_refs:
        # Exact closed-set membership, no fuzzy title or URL matching.
        if y_ref in selected or y_ref not in notes:
            continue
        selected[y_ref] = notes[y_ref]

    order = list(dict.fromkeys(ref for ref in output.learning_order if ref in selected))
    # A malformed/incomplete learning order cannot omit an accepted recommendation.
    order.extend(ref for ref in selected if ref not in order)

    recommendations = []
    for rank, ref in enumerate(order, 1):
        skill, code = selected[ref]
        recommendations.append(
            YouTubeRecommendation(
                video=candidates[ref], for_skill=skill, reason=_REASONS[code], rank=rank
            )
        )
    return recommendations


def deterministic_recommendations(
    candidates: dict[str, YouTubeVideoCandidate], skills: dict[str, YouTubeSkillRef]
) -> list[YouTubeRecommendation]:
    """Preserve source order and first canonical mapping when AI ranking fails."""
    notes = []
    for ref, video in candidates.items():
        skill = next((s for s in skills.values() if s.skill_id == video.skill_id), None)
        if skill:
            notes.append(f"{ref} -> {skill.ref}: SKILL_GAP_MATCH")
    refs = list(candidates)
    return ground(
        YouTubeLLMOutput(recommended_video_refs=refs, recommendation_codes=notes, learning_order=refs),
        candidates,
        skills,
    )
