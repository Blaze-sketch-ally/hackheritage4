"""Closed-vocabulary explanations, ref grounding, and server metadata attachment."""

import re

from app.ai.schemas.course_recommendation import (
    CourseCandidate,
    CourseLLMOutput,
    CoursePlanStep,
    CourseRecommendation,
    CourseSkill,
)

_NOTE = re.compile(r"^(C[1-9][0-9]*) -> (G[1-9][0-9]*): (SKILL_MATCH|LEVEL_MATCH|FOUNDATION)$")
_REASONS = {
    "SKILL_MATCH": "The source maps this resource to a skill in your learning priorities.",
    "LEVEL_MATCH": "The source lists this resource at the target level for this skill.",
    "FOUNDATION": "The source lists an introductory resource for a skill you have not added yet.",
}


def allowed_reason(code: str, course: CourseCandidate, skill: CourseSkill) -> bool:
    if skill.skill_id not in course.skill_ids:
        return False
    if code == "LEVEL_MATCH":
        return skill.target_level is not None and course.level == skill.target_level
    if code == "FOUNDATION":
        return skill.current_level is None and course.level == "Beginner"
    return code == "SKILL_MATCH"


def ground(
    output: CourseLLMOutput, candidates: dict[str, CourseCandidate], skills: dict[str, CourseSkill]
) -> tuple[list[CourseRecommendation], list[CoursePlanStep]]:
    notes = {}
    for line in output.recommendation_notes:
        match = _NOTE.fullmatch(line.strip())
        if not match:
            continue
        c_ref, g_ref, code = match.groups()
        if (
            c_ref in candidates
            and g_ref in skills
            and allowed_reason(code, candidates[c_ref], skills[g_ref])
        ):
            notes.setdefault(c_ref, (skills[g_ref], code))
    recommendations = []
    selected = {}
    for c_ref in output.recommended_course_refs:
        # Exact closed-set membership, no fuzzy title or URL matching.
        if c_ref in selected or c_ref not in notes:
            continue
        skill, code = notes[c_ref]
        item = CourseRecommendation(
            course=candidates[c_ref],
            for_skill=skill,
            reason=_REASONS[code],
            rank=len(recommendations) + 1,
        )
        recommendations.append(item)
        selected[c_ref] = item
    order = list(dict.fromkeys(ref for ref in output.learning_order if ref in selected))
    # A malformed/incomplete learning order cannot omit an accepted recommendation.
    order.extend(ref for ref in selected if ref not in order)
    plan = [
        CoursePlanStep(
            order=n,
            candidate_id=selected[ref].course.candidate_id,
            skill_id=selected[ref].for_skill.skill_id,
        )
        for n, ref in enumerate(order, 1)
    ]
    return recommendations, plan


def deterministic_recommendations(
    candidates: dict[str, CourseCandidate], skills: dict[str, CourseSkill]
):
    """Preserve source order and first canonical mapping when AI ranking fails."""
    notes = []
    for ref, candidate in candidates.items():
        skill = next((s for s in skills.values() if s.skill_id in candidate.skill_ids), None)
        if skill:
            notes.append(f"{ref} -> {skill.ref}: SKILL_MATCH")
    refs = list(candidates)
    return ground(
        CourseLLMOutput(
            recommended_course_refs=refs, recommendation_notes=notes, learning_order=refs
        ),
        candidates,
        skills,
    )
