"""Business logic for the Question Bank + Assessment Blueprint API (Phase
1K) -- database/migrations/015_question_bank_random_assessment.sql and
016_review_question_rpc.sql.

Every function here takes an already-constructed, user-scoped Supabase
client (app.core.security.build_user_client) -- RLS is the real
access-control boundary for every operation in this module, exactly like
app.services.assessment_service's Phase 1D-1G/1I functions. Nothing here
ever uses the SERVICE-ROLE client -- there is no service_role write
anywhere in the question-bank/review/blueprint workflow (the one Phase 1K
operation that DOES need service-role, starting an attempt with its
randomized question selection, lives in
app.services.assessment_service.create_attempt, not here).
set_review_status() IS still user-scoped, but calls a SECURITY DEFINER
RPC (review_question(), granted directly to `authenticated`) instead of a
plain table update -- see 016's own header comment for the real-Supabase
bug this fixes; that function's own internal checks, not RLS on this
table's UPDATE policy, are what make cross-setter approve/reject safe.
"""

from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

_QUESTION_BANK_COLUMNS = (
    "id, assessment_id, question_text, question_type, scoring_method, "
    "difficulty, points, display_order, review_status, is_active, "
    "created_by, created_at, updated_at, "
    "options:assessment_question_options(id, question_id, option_text, display_order), "
    "answer_key:assessment_question_answers(correct_option_ids, correct_answer_text, explanation)"
)


def _shape_question(row: dict) -> dict:
    row["options"] = sorted(row.get("options") or [], key=lambda option: option["display_order"])
    # assessment_question_answers.question_id is `unique`, so PostgREST
    # returns this embedded relationship as a single object or None
    # directly -- never a list -- no extra unwrapping needed.
    return row


def list_my_questions(client: Client, assessment_id: UUID | None = None) -> list[dict]:
    """The full shared question bank, visible to any FACULTY caller
    regardless of who created each question or its review_status. RLS
    ("Faculty can view any question", 018_faculty_view_all_questions.sql)
    is the actual enforcement; the optional assessment_id filter here is a
    convenience, not a security boundary.

    This was originally scoped to "own questions + others' PENDING
    questions only" (015), but that left a reviewing faculty member unable
    to see a question immediately after approving or rejecting someone
    else's submission -- see 017/018's own header comments for the
    real-Supabase bugs this widening fixes. WRITE access (create/edit/
    approve/reject) remains exactly as ownership/status-scoped as before;
    only this READ was widened.
    """
    query = client.table("assessment_questions").select(_QUESTION_BANK_COLUMNS)
    if assessment_id is not None:
        query = query.eq("assessment_id", str(assessment_id))
    response = query.order("created_at", desc=True).execute()
    return [_shape_question(row) for row in (response.data or [])]


def get_my_question(client: Client, question_id: UUID) -> dict | None:
    """One question, or None if it doesn't exist or isn't visible to the
    caller under RLS (their own, or PENDING). Callers must turn None into
    a 404."""
    response = (
        client.table("assessment_questions")
        .select(_QUESTION_BANK_COLUMNS)
        .eq("id", str(question_id))
        .maybe_single()
        .execute()
    )
    if response is None or response.data is None:
        return None
    return _shape_question(response.data)


def create_question(client: Client, created_by: str, payload: dict) -> dict:
    """Insert a new question, always PENDING, always owned by the caller.

    RLS ("Faculty can create their own questions") independently requires
    created_by = auth.uid(), is_faculty(), and review_status = 'PENDING'
    regardless of what this function sends -- the explicit fields below
    mirror that policy as defense in depth, matching every other create_*
    function in this codebase.
    """
    response = (
        client.table("assessment_questions")
        .insert({**payload, "created_by": created_by, "review_status": "PENDING"})
        .execute()
    )
    return response.data[0]


def update_question(client: Client, question_id: UUID, payload: dict) -> dict | None:
    """Update a question's own content fields.

    RLS + the prevent_unauthorized_question_review trigger (015) are the
    real enforcement: an approved question, or content fields touched by
    anyone but its own creator, are rejected at the database layer
    regardless of what reaches this function -- a trigger rejection
    surfaces here as a postgrest APIError with code 42501, which the route
    layer maps to 403. Returns None if the row didn't match any
    RLS-visible row at all (the route layer maps that to 404).
    """
    response = (
        client.table("assessment_questions").update(payload).eq("id", str(question_id)).execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


class OwnQuestionReviewError(Exception):
    """Raised when review_question() rejects the caller for being the
    question's own creator -- SQLSTATE 42501, same code the
    prevent_unauthorized_question_review trigger already uses for this
    exact rule. Route layer: 403."""


class QuestionNotPendingError(Exception):
    """Raised when review_question() finds the question is no longer
    PENDING at the moment it actually runs -- SQLSTATE 55000 (object not
    in prerequisite state), same code InsufficientQuestionPoolError and
    AttemptNotEligibleForScoringError already use for this class of race.
    Route layer: 409, not a silent no-op or a generic 500."""


def set_review_status(client: Client, question_id: UUID, review_status: str) -> dict | None:
    """Approve or reject a question via the review_question() RPC
    (016_review_question_rpc.sql) -- NOT a plain table update. See that
    migration's header comment for the real-Supabase bug this fixes: a
    plain RLS-gated UPDATE unreliably rejected exactly this
    review-status-changing transition even though every policy condition
    it depends on was independently confirmed true for the caller.

    Still called with the user-scoped client (build_user_client), never
    service_role -- review_question() is SECURITY DEFINER and granted
    directly to `authenticated`, so its own internal is_faculty/ownership/
    pending checks are the real security boundary for this one call, not
    RLS on this table's UPDATE policy.

    Returns None if the question doesn't exist (SQLSTATE P0002 -- route
    layer: 404, matching the previous plain-UPDATE function's contract).
    """
    try:
        response = client.rpc(
            "review_question",
            {"p_question_id": str(question_id), "p_decision": review_status},
        ).execute()
    except APIError as exc:
        if exc.code == "P0002":
            return None
        if exc.code == "42501":
            raise OwnQuestionReviewError() from exc
        if exc.code == "55000":
            raise QuestionNotPendingError() from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def replace_options(client: Client, question_id: UUID, options: list[dict]) -> list[dict]:
    """Replace a question's entire option set: a delete-then-insert, not a
    diff -- the simplest correct behavior for the "still-editing-a-draft"
    case this exists for. RLS's own review_status <> 'APPROVED' scoping on
    both operations is what makes this safe to call at all only
    pre-approval."""
    client.table("assessment_question_options").delete().eq(
        "question_id", str(question_id)
    ).execute()
    if not options:
        return []
    response = (
        client.table("assessment_question_options")
        .insert([{**option, "question_id": str(question_id)} for option in options])
        .execute()
    )
    return response.data or []


def upsert_answer_key(client: Client, question_id: UUID, payload: dict) -> dict:
    """Create or replace the answer key for one question.
    assessment_question_answers.question_id is `unique`, so this is a
    delete-then-insert rather than relying on upsert's on_conflict target
    matching across postgrest-py versions -- same reasoning as
    replace_options above."""
    client.table("assessment_question_answers").delete().eq(
        "question_id", str(question_id)
    ).execute()
    response = (
        client.table("assessment_question_answers")
        .insert({**payload, "question_id": str(question_id)})
        .execute()
    )
    return response.data[0]


def clear_answer_key(client: Client, question_id: UUID) -> None:
    """Remove a question's answer key entirely (PATCH .../questions/{id}
    with `"answer_key": null` explicitly). Deletion is scoped by RLS's own
    review_status <> 'APPROVED' condition, same as every other write in
    this module."""
    client.table("assessment_question_answers").delete().eq(
        "question_id", str(question_id)
    ).execute()


# ============================================================
# Assessment blueprint
# ============================================================

_BLUEPRINT_COLUMNS = "id, assessment_id, difficulty, question_count, created_at, updated_at"


def get_blueprint(client: Client, assessment_id: UUID) -> list[dict]:
    """RLS ("Authenticated users can view blueprint rules for active
    assessments") allows any authenticated caller to read this -- a
    difficulty/count breakdown carries no sensitive information."""
    response = (
        client.table("assessment_blueprint_rules")
        .select(_BLUEPRINT_COLUMNS)
        .eq("assessment_id", str(assessment_id))
        .order("difficulty")
        .execute()
    )
    return response.data or []


def replace_blueprint(client: Client, assessment_id: UUID, rules: list[dict]) -> list[dict]:
    """Replace an assessment's entire blueprint (delete-then-insert, same
    reasoning as replace_options) -- RLS ("Faculty can create/update/
    delete blueprint rules") is the real enforcement that only FACULTY may
    call this at all."""
    client.table("assessment_blueprint_rules").delete().eq(
        "assessment_id", str(assessment_id)
    ).execute()
    if not rules:
        return []
    response = (
        client.table("assessment_blueprint_rules")
        .insert([{**rule, "assessment_id": str(assessment_id)} for rule in rules])
        .execute()
    )
    return response.data or []
