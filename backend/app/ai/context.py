"""The StudentCareerContext builder (Phase 2).

`build_student_career_context` is a pure COMPOSER over the existing
deterministic services, through app.ai.tools -- it never queries
Supabase itself, never recomputes a skill-gap/match/verification value a
different way, and never calls an LLM. Its only job is to call each
existing read path exactly once and assemble the results into one typed
StudentCareerContext (app.ai.schemas.student_context).

Security: this function takes a `client` the CALLER already built via
app.core.security.build_user_client(current_user.access_token), and a
`student_id` the caller already resolved from current_user.id -- never
from a request body or query parameter (see app.api.ai's /context
route, the only caller in Phase 2). Every underlying read stays scoped
by the same RLS policies every other student-facing route already
relies on; this module adds no new access path and no service_role use.

Every section tolerates a genuinely empty student (no target role, no
skills, no assessment history, no portfolio, no learning progress, no
applications) -- see each app.ai.tools function's own docstring. None of
that is treated as a build failure; a StudentCareerContext with mostly
empty/None sections is a normal, valid result for a new student.
"""

from datetime import UTC, datetime

from supabase import Client

from app.ai.schemas.student_context import StudentCareerContext
from app.ai.tools import (
    assessment_tools,
    learning_tools,
    opportunity_tools,
    portfolio_tools,
    skill_gap_tools,
    skill_tools,
    student_tools,
)


def build_student_career_context(client: Client, student_id: str) -> StudentCareerContext:
    """Assemble the full context for one student. Each existing service
    is called exactly once (see the module docstring's N+1 note) --
    never repeated while building this one context."""
    basic_info = student_tools.get_student_basic_info(client, student_id)
    target_job_role = skill_tools.get_target_job_role(client, student_id)
    skills = skill_tools.get_student_skills(client, student_id)
    assessment_summary = assessment_tools.get_assessment_summary(client, student_id)
    skill_gap = skill_gap_tools.get_current_skill_gap(client, student_id)
    portfolio = portfolio_tools.get_student_portfolio(client, student_id)
    learning_progress = learning_tools.get_learning_progress(client, student_id)
    application_history = opportunity_tools.get_application_history(client, student_id)
    recommended_opportunities = opportunity_tools.get_recommended_opportunities(
        client, student_id
    )

    return StudentCareerContext(
        student_id=student_id,
        generated_at=datetime.now(UTC),
        basic_info=basic_info,
        target_job_role=target_job_role,
        skills=skills,
        assessment_summary=assessment_summary,
        skill_gap=skill_gap,
        portfolio=portfolio,
        learning_progress=learning_progress,
        application_history=application_history,
        recommended_opportunities=recommended_opportunities,
    )


# Alias matching the Phase 2 brief's suggested tool name -- lives here
# (not app.ai.tools.student_tools) to avoid a context.py <-> student_tools
# import cycle; this is the single source of truth for both names.
get_student_context = build_student_career_context
