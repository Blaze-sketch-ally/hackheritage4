"""Tools: the student's own skills + target job role.

`get_student_skills` reads `student_skills` directly (the same shape as
frontend/lib/student/skills.ts::fetchStudentSkills and
student_portfolio_service._own_skills, extended with `verified_at` --
neither existing reader exposes it, and Phase 2 needs it). No public
service function returns this exact shape today, so this is a direct,
RLS-scoped read rather than a new formula -- see the app.ai.tools
package docstring.

`get_target_job_role` is a thin wrapper around the EXISTING
skill_gap_service.get_target_job_role, composed into the same
TargetJobRoleResponse schema GET /api/v1/student/target-job-role already
returns (see app.api.skill_gap) -- never a second implementation of that
lookup.
"""

from supabase import Client

from app.ai.schemas.student_context import StudentSkillSummary
from app.schemas.skill_gap import TargetJobRoleResponse
from app.services import skill_gap_service

_STUDENT_SKILL_COLUMNS = (
    "skill_id, proficiency_level, is_verified, verified_at, "
    "skill:skills(name, category:skill_categories(name))"
)


def get_student_skills(client: Client, student_id: str) -> list[StudentSkillSummary]:
    """Every one of the caller's own active skills, verified or not.
    Empty list if the student has added none yet -- not an error."""
    response = (
        client.table("student_skills")
        .select(_STUDENT_SKILL_COLUMNS)
        .eq("student_id", student_id)
        .execute()
    )
    rows = response.data or []

    out: list[StudentSkillSummary] = []
    for row in rows:
        skill = row.get("skill") or {}
        category = skill.get("category") or {}
        out.append(
            StudentSkillSummary(
                skill_id=row["skill_id"],
                skill_name=skill.get("name", ""),
                category_name=category.get("name"),
                proficiency_level=row["proficiency_level"],
                is_verified=bool(row["is_verified"]),
                verified_at=row.get("verified_at"),
            )
        )
    out.sort(key=lambda s: s.skill_name.lower())
    return out


def get_verified_skills(client: Client, student_id: str) -> list[StudentSkillSummary]:
    """Only the subset of `get_student_skills` that has actually been
    assessment-verified (student_skills.is_verified) -- never a self-
    reported level treated as verified."""
    return [skill for skill in get_student_skills(client, student_id) if skill.is_verified]


def get_target_job_role(client: Client, student_id: str) -> TargetJobRoleResponse | None:
    """The caller's own saved target role, or None if they haven't set
    one (or the one they set has since been deactivated -- see
    skill_gap_service.get_target_job_role's own docstring)."""
    row = skill_gap_service.get_target_job_role(client, student_id)
    if row is None:
        return None
    return TargetJobRoleResponse(**row)
