"""Tools: the student's own current Skill Gap analysis.

`get_current_skill_gap` reproduces EXACTLY the same dispatch as
GET /api/v1/skill-gap (app.api.skill_gap.get_skill_gap): target-role
mode via skill_gap_service.compute_job_role_gap when the student has a
saved target role, personal mode via
skill_gap_service.compute_personal_analysis otherwise. No gap/readiness/
priority value is computed a second, different way here -- this module
only wraps the same service call's own return value into
app.ai.schemas.student_context.SkillGapSection.
"""

from uuid import UUID

from supabase import Client

from app.ai.schemas.student_context import SkillGapSection
from app.schemas.skill_gap import AnalysisMode, SkillGapJobRoleResponse, SkillGapPersonalResponse
from app.services import skill_gap_service


def get_current_skill_gap(client: Client, student_id: str) -> SkillGapSection:
    """The caller's own current analysis -- job-role mode if a target
    role is saved, personal mode otherwise. Never fails just because no
    target role is set; personal mode is a normal, complete result."""
    target = skill_gap_service.get_target_job_role(client, student_id)

    if target is None:
        analysis = skill_gap_service.compute_personal_analysis(client, student_id)
        return SkillGapSection(
            mode=AnalysisMode.PERSONAL,
            personal_analysis=SkillGapPersonalResponse(mode=AnalysisMode.PERSONAL, **analysis),
        )

    job_role = target["job_role"]
    requirements = skill_gap_service.get_job_role_requirements(client, UUID(job_role["id"]))
    gap = skill_gap_service.compute_job_role_gap(client, student_id, job_role, requirements)
    return SkillGapSection(
        mode=AnalysisMode.JOB_ROLE,
        job_role_analysis=SkillGapJobRoleResponse(
            mode=AnalysisMode.JOB_ROLE, job_role=job_role, **gap
        ),
    )
