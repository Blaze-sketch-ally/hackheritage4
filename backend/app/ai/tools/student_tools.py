"""Tools: the student's own basic identity + career-relevant profile info.

Reads `profiles` (present for every user from signup,
001_profiles.sql) and `student_profiles` (lazily created -- absent until
the student saves their profile at least once, 012_student_profiles.sql)
directly, through the caller's own user-scoped client. No reusable
backend service exists for a student reading their own basic info today
(frontend/lib/student/profile.ts talks to Supabase directly; this
mirrors that exact pattern server-side) -- see the app.ai.tools package
docstring for why a direct RLS-scoped read is the right call here rather
than inventing a service_role path.
"""

from supabase import Client

from app.ai.schemas.student_context import StudentBasicInfo

# Career-relevant fields only -- see app.ai.schemas.student_context's
# module docstring for what is deliberately excluded (phone,
# date_of_birth, gender, location, cgpa, percentage, department) and why.
_STUDENT_PROFILE_COLUMNS = (
    "degree, graduation_year, institution_name, career_goals, "
    "preferred_roles, preferred_locations"
)


def get_student_basic_info(client: Client, student_id: str) -> StudentBasicInfo:
    """The caller's own basic info.

    Never raises for a student who hasn't saved a student_profiles row
    yet -- every career-relevant field is simply None/[] in that case,
    the same "lazily created, absence is normal" handling this project
    already uses elsewhere (e.g. skill_gap_service.get_target_job_role).
    RLS ("Users can view their own profile" / the equivalent student_profiles
    policy) already scopes both reads to the caller; the explicit
    .eq("id", ...) here is defense in depth, matching every other read in
    this codebase.
    """
    profile_response = (
        client.table("profiles")
        .select("email, full_name")
        .eq("id", student_id)
        .maybe_single()
        .execute()
    )
    profile_row = (profile_response.data if profile_response is not None else None) or {}

    student_profile_response = (
        client.table("student_profiles")
        .select(_STUDENT_PROFILE_COLUMNS)
        .eq("id", student_id)
        .maybe_single()
        .execute()
    )
    student_profile_row = (
        student_profile_response.data if student_profile_response is not None else None
    ) or {}

    return StudentBasicInfo(
        student_id=student_id,
        full_name=profile_row.get("full_name"),
        email=profile_row.get("email"),
        degree=student_profile_row.get("degree"),
        graduation_year=student_profile_row.get("graduation_year"),
        institution_name=student_profile_row.get("institution_name"),
        career_goals=student_profile_row.get("career_goals"),
        preferred_roles=list(student_profile_row.get("preferred_roles") or []),
        preferred_locations=list(student_profile_row.get("preferred_locations") or []),
    )
