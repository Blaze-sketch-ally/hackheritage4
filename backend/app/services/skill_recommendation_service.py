"""Aggregate skill-gap recommendations, built on this project's own
career-role skill-gap engine (app.services.career_role_service +
app.services.skill_alignment_service, Phase 1L) -- NOT the retired
job_roles/skill_gap_service concept a collaborator branch's Learning
Recommendations feature (Phase 6D) originally depended on.

That collaborator feature let a student persist ONE "target job role"
and computed gaps against just that role. This project has no such
persisted target (a deliberate Phase 1L design choice -- see
022_career_roles_skill_gap.sql's own header on why no student-skill-level
table exists), so there is no direct equivalent of that "personal mode"
here. Per explicit product decision, this module instead AGGREGATES
across every career role in the catalog: a skill that shows GAP or
NOT_ASSESSED status (app.services.skill_alignment_service.AlignmentStatus)
for more of those roles is ranked as a higher-priority recommendation.

This is the ONLY thing this module decides. It produces plain dicts
shaped exactly like app.services.learning_recommendation_service's own
`gap_skills` input contract ({"skill_id", "skill_name", "priority",
"reason"}) -- that module is otherwise completely unmodified and unaware
of where its input came from.

Read-only: issues SELECTs through career_role_service /
assessment_service only, computes everything else in Python, writes
nothing.
"""

from decimal import Decimal
from uuid import UUID

from supabase import Client

from app.services import assessment_service, career_role_service
from app.services.skill_alignment_service import AlignmentStatus, compute_alignment

_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Fraction of considered career roles a skill must be a gap in to earn
# each priority tier. Deterministic, not tunable per request -- same
# "no invented relevance score" posture as the module this feeds.
_HIGH_THRESHOLD = Decimal("0.5")
_MEDIUM_THRESHOLD = Decimal("0.25")


def _priority_for(fraction: Decimal) -> str:
    if fraction >= _HIGH_THRESHOLD:
        return "HIGH"
    if fraction >= _MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def get_aggregate_skill_gaps(client: Client, student_id: str) -> list[dict]:
    """Every skill that is GAP or NOT_ASSESSED for at least one career
    role in the catalog, ranked by how many of those roles need it.

    Returns [] if the catalog has no career role with at least one
    requirement -- there is nothing to recommend against, not an error.
    """
    student_scores = assessment_service.get_student_skill_scores(client, student_id)

    gap_counts: dict[str, int] = {}
    skill_names: dict[str, str] = {}
    considered_roles = 0

    for role in career_role_service.list_career_roles(client):
        requirements = career_role_service.get_career_role_requirements(
            client, UUID(role["id"])
        )
        if not requirements:
            continue
        considered_roles += 1

        summary = compute_alignment(requirements, student_scores)
        for result in summary.results:
            if result.status == AlignmentStatus.STRONG:
                continue
            gap_counts[result.skill_id] = gap_counts.get(result.skill_id, 0) + 1
            skill_names[result.skill_id] = result.skill_name

    if considered_roles == 0 or not gap_counts:
        return []

    recommendations: list[dict] = []
    for skill_id, count in gap_counts.items():
        fraction = Decimal(count) / Decimal(considered_roles)
        priority = _priority_for(fraction)
        role_word = "career role" if considered_roles == 1 else "career roles"
        recommendations.append(
            {
                "skill_id": skill_id,
                "skill_name": skill_names[skill_id],
                "priority": priority,
                "reason": (
                    f"A skill gap in {count} of {considered_roles} {role_word} "
                    "in the catalog."
                ),
            }
        )

    recommendations.sort(
        key=lambda r: (_PRIORITY_RANK[r["priority"]], r["skill_name"].lower())
    )
    return recommendations
