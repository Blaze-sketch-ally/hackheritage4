"""Business logic for the Assessment API -- Phase 1D (read-only) and
Phase 1E (attempt creation).

Every function here takes an already user-scoped Supabase client (see
app.core.security.build_user_client). RLS does the real access-control
work; these functions only shape the query and the return value. None of
them use the service-role client -- ordinary student operations must never
bypass RLS.
"""

from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

_ASSESSMENT_COLUMNS = (
    "id, skill_id, title, description, difficulty, duration_minutes, "
    "question_count, is_active, created_at, updated_at"
)

# options embedded via PostgREST's nested-resource syntax (a single query,
# not N+1) -- assessment_question_options.question_id is a real FK to
# assessment_questions.id, so Supabase can resolve this relationship
# automatically. Only the columns AssessmentQuestionResponse/
# AssessmentOptionResponse actually declare are selected -- no
# review_status/generation_source/generation_model/generated_at, which are
# real columns but deliberately excluded from the student-facing schema
# (see the Phase 1C report).
_QUESTION_COLUMNS = (
    "id, assessment_id, question_text, question_type, scoring_method, "
    "difficulty, points, display_order, "
    "options:assessment_question_options(id, question_id, option_text, display_order)"
)


def list_active_assessments(client: Client) -> list[dict]:
    """All assessments visible to the caller.

    RLS ("Authenticated users can view active assessments") already
    restricts this to is_active = true for any authenticated role; the
    explicit .eq() here is defense in depth, not the only enforcement --
    STUDENT-only is enforced by require_student() at the route layer, since
    RLS itself does not gate this table by role.
    """
    response = (
        client.table("assessments")
        .select(_ASSESSMENT_COLUMNS)
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )
    return response.data or []


def get_active_assessment(client: Client, assessment_id: UUID) -> dict | None:
    """One assessment, or None if it doesn't exist / isn't active / isn't
    visible to the caller. Callers must turn None into a 404 -- never
    reveal whether an inactive assessment exists.

    maybe_single().execute() returns None (not a response object) when
    zero rows match -- verified against the installed postgrest-py source,
    not assumed.
    """
    response = (
        client.table("assessments")
        .select(_ASSESSMENT_COLUMNS)
        .eq("id", str(assessment_id))
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def list_visible_questions(client: Client, assessment_id: UUID) -> list[dict]:
    """Approved, active, OBJECTIVE questions for one assessment, with their
    options embedded, both levels sorted by display_order.

    Filters scoring_method = OBJECTIVE: Phase 1 has no scoring path for
    AI_EVALUATED questions (Phase 1H rejects/defers submission of any
    attempt containing one), so this read endpoint excludes them rather
    than showing a student a question the system cannot yet grade -- see
    the Phase 1D report for the full reasoning. This does not filter out
    the parent assessment itself, only individual AI_EVALUATED questions
    within it.

    RLS ("Authenticated users can view approved active questions") already
    guarantees review_status/is_active/parent-assessment-active; the
    explicit filters here are defense in depth, matching the pattern in
    get_active_assessment/list_active_assessments. Options are ordered in
    Python rather than relying on PostgREST's embedded-resource ordering
    syntax, to avoid a dependency on behavior that's easy to get subtly
    wrong across postgrest-py versions.
    """
    response = (
        client.table("assessment_questions")
        .select(_QUESTION_COLUMNS)
        .eq("assessment_id", str(assessment_id))
        .eq("review_status", "APPROVED")
        .eq("is_active", True)
        .eq("scoring_method", "OBJECTIVE")
        .order("display_order")
        .execute()
    )
    questions = response.data or []
    for question in questions:
        question["options"] = sorted(
            question.get("options") or [], key=lambda option: option["display_order"]
        )
    return questions


class DuplicateInProgressAttemptError(Exception):
    """Raised when the student already has an IN_PROGRESS attempt for this
    assessment. Mirrors the DB's own partial unique index
    (assessment_attempts_one_in_progress_idx on (student_id, assessment_id)
    WHERE status = 'IN_PROGRESS') -- callers should turn this into a 409,
    not a generic 500."""


def create_attempt(client: Client, student_id: str, assessment_id: UUID) -> dict:
    """Start a new attempt for the calling student.

    RLS ("Students can start their own attempts") is the real enforcement:
    its WITH CHECK independently requires auth.uid() = student_id,
    is_student(), and a fresh IN_PROGRESS/unscored/unsubmitted row,
    regardless of what this function sends -- the explicit fields below
    mirror that policy as defense in depth, not the only guard. student_id
    must always be the authenticated caller's own id (never taken from a
    request body); this function has no way to accept one from a client at
    all, since the route never parses one.

    "No second concurrent attempt" is enforced by the DB's own partial
    unique index, not application logic -- a violation raises postgrest's
    APIError with code 23505 (unique_violation), which this function
    translates into DuplicateInProgressAttemptError so the route layer can
    return a clean 409 instead of a raw DB error. Same pattern already
    used for this exact error code in frontend/lib/student/skills.ts.
    """
    try:
        response = (
            client.table("assessment_attempts")
            .insert(
                {
                    "student_id": student_id,
                    "assessment_id": str(assessment_id),
                    "status": "IN_PROGRESS",
                }
            )
            .execute()
        )
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateInProgressAttemptError() from exc
        raise
    return response.data[0]
