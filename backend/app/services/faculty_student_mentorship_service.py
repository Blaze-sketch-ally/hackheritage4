"""Business logic for Faculty <-> Student mentorship (Phase F4.2,
`faculty_student_mentorships`, 040_faculty_student_mentorships.sql).

Every function takes an already-constructed, user-scoped Supabase client
(app.core.security.build_user_client) -- RLS and the
guard_faculty_student_mentorship() trigger are the real enforcement for
identity, capability, and lifecycle legality; this module's own checks
(transition pre-validation, defense-in-depth id filters) exist to turn a
database rejection into a clean typed exception the API layer can map to
the right HTTP status, mirroring
industry_faculty_opportunity_service.update_engagement_status()'s own
pattern.

This is the ONE service module for both sides of the relationship
(Faculty and Student) -- unlike the EOI tables (037), there is only one
physical table here, so there is no reason to split per-role modules the
way industry_faculty_opportunity_service.py /
institution_faculty_opportunity_service.py are split (that split exists
because those are two separate physical tables with no-dynamic-SQL
constraints, which does not apply here).
"""

from postgrest.exceptions import APIError
from supabase import Client

from app.services import portfolio_service

_SELECT = (
    "id, faculty_id, student_id, requested_by, status, focus_area, "
    "start_date, end_date, created_at, updated_at"
)

_NOTE_SELECT = "id, mentorship_id, faculty_id, note, created_at, updated_at"


class MentorshipAuthorizationError(Exception):
    """Raised when the database rejects a creation attempt -- SQLSTATE
    42501, covering: caller is not FACULTY/STUDENT, caller lacks the
    faculty_mentor capability (as either the requester or the requested
    Faculty member), or the target id does not have the expected
    counterpart role. Route layer: 403."""


class DuplicateMentorshipError(Exception):
    """Raised when a mentorship already exists for this Faculty/Student
    pair -- SQLSTATE 23505 (faculty_student_mentorships_unique_pair).
    Route layer: 409."""


class MentorshipInvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a mentorship from {current} to {target}.")


class MentorshipSelfActionError(Exception):
    """Raised when the caller attempts a lifecycle action reserved for
    the OTHER participant (accepting/declining their own request) or
    exclusive to the requester (withdrawing a request they did not
    create). Route layer: 403."""


class MentorshipNotActiveError(Exception):
    """Raised by get_mentee_bundle() when the mentorship exists and is
    owned by the caller but is not currently ACTIVE -- per the approved
    scope, mentor visibility into student data is gated strictly on
    ACTIVE status. Route layer: 409."""


class AdminAuthorizationError(Exception):
    """Raised when admin_list_faculty_student_mentorships rejects the
    caller -- SQLSTATE 42501. Route layer: 403."""


_TRANSITIONS_FROM: dict[str, frozenset[str]] = {
    "ACCEPTED": frozenset({"REQUESTED"}),
    "DECLINED": frozenset({"REQUESTED"}),
    "WITHDRAWN": frozenset({"REQUESTED"}),
    "ACTIVE": frozenset({"ACCEPTED"}),
    "COMPLETED": frozenset({"ACTIVE"}),
    "ENDED": frozenset({"ACTIVE"}),
}

# Which transitions only the NON-requesting participant may perform, and
# which only the requester may perform -- mirrors
# guard_faculty_student_mentorship()'s own transition rules exactly, so a
# violation is caught here (typed 403) before it ever reaches the
# database trigger (which independently re-enforces the same rule).
_OTHER_PARTY_ONLY = frozenset({"ACCEPTED", "DECLINED"})
_REQUESTER_ONLY = frozenset({"WITHDRAWN"})


def list_for_faculty(client: Client, faculty_id: str) -> list[dict]:
    """The caller's own mentorships (any status), as the Faculty
    participant."""
    response = (
        client.table("faculty_student_mentorships")
        .select(_SELECT)
        .eq("faculty_id", faculty_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return list(response.data or [])


def list_for_student(client: Client, student_id: str) -> list[dict]:
    """The caller's own mentorships (any status), as the Student
    participant."""
    response = (
        client.table("faculty_student_mentorships")
        .select(_SELECT)
        .eq("student_id", student_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return list(response.data or [])


def create_faculty_request(client: Client, faculty_id: str, student_id: str, focus_area: str | None) -> dict:
    """A Faculty member requests mentoring a specific student. RLS
    ("Faculty can request mentorship of a student") independently
    re-verifies the caller holds faculty_mentor and that student_id is
    genuinely a STUDENT account."""
    payload: dict = {
        "faculty_id": faculty_id,
        "student_id": student_id,
        "requested_by": faculty_id,
        "status": "REQUESTED",
    }
    if focus_area is not None:
        payload["focus_area"] = focus_area
    return _insert(client, payload)


def create_student_request(client: Client, student_id: str, faculty_id: str, focus_area: str | None) -> dict:
    """A Student requests a specific Faculty member as their mentor. RLS
    ("Students can request mentorship from a faculty member")
    independently re-verifies faculty_id is genuinely a FACULTY account
    that currently holds faculty_mentor."""
    payload = {
        "faculty_id": faculty_id,
        "student_id": student_id,
        "requested_by": student_id,
        "status": "REQUESTED",
    }
    if focus_area is not None:
        payload["focus_area"] = focus_area
    return _insert(client, payload)


def _insert(client: Client, payload: dict) -> dict:
    try:
        response = client.table("faculty_student_mentorships").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateMentorshipError(str(exc)) from exc
        if exc.code in {"42501", "23514"}:
            raise MentorshipAuthorizationError(str(exc)) from exc
        raise
    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def get_mentorship(client: Client, caller_id: str, mentorship_id: str) -> dict | None:
    """One mentorship the caller is a participant in. RLS already scopes
    this to the caller's own rows; the explicit filtering below happens
    entirely in Python for the two list_for_* callers instead -- this
    single-row lookup just re-fetches by id and lets RLS decide
    visibility, then confirms participancy as defence in depth."""
    response = (
        client.table("faculty_student_mentorships").select(_SELECT).eq("id", mentorship_id).maybe_single().execute()
    )
    row = response.data if response is not None else None
    if row is None:
        return None
    if row["faculty_id"] != caller_id and row["student_id"] != caller_id:
        return None
    return row


def update_status(client: Client, caller_id: str, mentorship_id: str, new_status: str) -> dict | None:
    """Transition one of the caller's own mentorships. Returns None if
    the mentorship doesn't exist or the caller isn't a participant. The
    actual legality is enforced by guard_faculty_student_mentorship()
    regardless of what reaches this function; the checks below exist to
    turn that into a clean typed exception instead of a raw APIError."""
    row = get_mentorship(client, caller_id, mentorship_id)
    if row is None:
        return None

    allowed_from = _TRANSITIONS_FROM.get(new_status)
    if allowed_from is None or row["status"] not in allowed_from:
        raise MentorshipInvalidStatusTransitionError(row["status"], new_status)

    if new_status in _OTHER_PARTY_ONLY and caller_id == row["requested_by"]:
        raise MentorshipSelfActionError("The requesting party cannot accept or decline their own request.")
    if new_status in _REQUESTER_ONLY and caller_id != row["requested_by"]:
        raise MentorshipSelfActionError("Only the requesting party may withdraw a request.")

    try:
        client.table("faculty_student_mentorships").update({"status": new_status}).eq("id", mentorship_id).execute()
    except APIError as exc:
        if exc.code == "42501":
            raise MentorshipSelfActionError(str(exc)) from exc
        raise

    return get_mentorship(client, caller_id, mentorship_id)


def get_mentee_bundle(client: Client, faculty_id: str, mentorship_id: str) -> dict | None:
    """The authorized subset of an active mentee's data (approved
    visibility matrix categories A/B/C/F/H), for GET /faculty/
    mentorships/{id}/student. Every read below goes through this SAME
    caller-scoped client -- RLS (040's own mentor-visibility policies) is
    the actual enforcement; the ACTIVE-status check here exists only to
    return a clean 409 instead of a set of silently-empty lists when the
    mentorship exists but hasn't been activated yet.

    Never touches assessment_answers, applications, or any industry_*
    table -- see 040's own header for why."""
    mentorship = get_mentorship(client, faculty_id, mentorship_id)
    if mentorship is None or mentorship["faculty_id"] != faculty_id:
        return None
    if mentorship["status"] != "ACTIVE":
        raise MentorshipNotActiveError()

    student_id = mentorship["student_id"]

    profile_resp = (
        client.table("profiles").select("id, full_name, email, username").eq("id", student_id).maybe_single().execute()
    )
    profile = profile_resp.data if profile_resp is not None else None

    academic_resp = (
        client.table("student_profiles")
        .select(
            "institution_name, department, degree, graduation_year, cgpa, percentage, "
            "career_goals, preferred_roles, interests"
        )
        .eq("id", student_id)
        .maybe_single()
        .execute()
    )
    academic = academic_resp.data if academic_resp is not None else None

    skills_resp = (
        client.table("student_skills")
        .select("skill_id, proficiency_level, proficiency_score, is_verified")
        .eq("student_id", student_id)
        .execute()
    )
    skills = list(skills_resp.data or [])

    attempts_resp = (
        client.table("assessment_attempts")
        .select("id, assessment_id, status, score, total_marks, percentage, submitted_at")
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
    )
    attempts = list(attempts_resp.data or [])

    portfolio = portfolio_service.get_student_portfolio(client, student_id)

    return {
        "mentorship_id": mentorship_id,
        "student_id": student_id,
        "full_name": profile.get("full_name") if profile else None,
        "email": profile.get("email") if profile else None,
        "username": profile.get("username") if profile else None,
        "academic_profile": academic,
        "skills": skills,
        "assessment_attempts": attempts,
        "projects": portfolio["projects"],
        "certifications": portfolio["certifications"],
        "achievements": portfolio["achievements"],
    }


# ---- Private mentor notes (faculty_mentorship_notes) ----


def get_note(client: Client, faculty_id: str, mentorship_id: str) -> dict | None:
    """The caller's own note for this mentorship. RLS ("Faculty can view
    their own mentorship notes") is the real enforcement; the explicit
    `.eq("faculty_id", ...)` here is defence in depth, matching the
    convention every other read in this module already follows."""
    response = (
        client.table("faculty_mentorship_notes")
        .select(_NOTE_SELECT)
        .eq("mentorship_id", mentorship_id)
        .eq("faculty_id", faculty_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def upsert_note(client: Client, faculty_id: str, mentorship_id: str, note_text: str) -> dict:
    """One note per mentorship, owned by the mentorship's own Faculty
    participant -- RLS ("Faculty can create/update their own mentorship
    notes") independently re-verifies faculty_id = auth.uid() and that
    the caller still holds faculty_mentor."""
    existing = get_note(client, faculty_id, mentorship_id)
    if existing is None:
        response = (
            client.table("faculty_mentorship_notes")
            .insert({"mentorship_id": mentorship_id, "faculty_id": faculty_id, "note": note_text})
            .execute()
        )
        data = response.data
        return data[0] if isinstance(data, list) and data else data

    client.table("faculty_mentorship_notes").update({"note": note_text}).eq("mentorship_id", mentorship_id).eq(
        "faculty_id", faculty_id
    ).execute()
    refreshed = get_note(client, faculty_id, mentorship_id)
    return refreshed if refreshed is not None else existing


# ---- Admin oversight (admin_list_faculty_student_mentorships RPC) ----


def admin_list_mentorships(client: Client) -> list[dict]:
    try:
        response = client.rpc("admin_list_faculty_student_mentorships").execute()
    except APIError as exc:
        if exc.code == "42501":
            raise AdminAuthorizationError(str(exc)) from exc
        raise
    return list(response.data or [])
