"""Business logic for the Assessment API -- Phase 1D (read-only),
Phase 1E (attempt creation), Phase 1F (answer saving), Phase 1G
(submission), Phase 1H (scoring), and Phase 1I (results).

Every function here takes an already-constructed Supabase client. For
Phase 1D-1G and 1I this is always the user-scoped client (see
app.core.security.build_user_client) -- RLS does the real access-control
work, these functions only shape the query and the return value. The one
exception is score_attempt() (Phase 1H), which is explicitly designed to
be called with the service-role client (app.database.supabase.get_supabase)
-- RLS structurally forbids the writes it needs to make (see
score_assessment_attempt() in 014_score_assessment_attempt.sql). Ordinary
student operations must never bypass RLS; only the trusted scoring
operation does, and only after the caller has already verified attempt
ownership through the normal RLS-respecting path. get_attempt_result_rows()
(Phase 1I) deliberately reads answer-key data through the user-scoped
client too -- "Students can view answer keys for their own completed
attempts" already permits this for a COMPLETED, owned attempt, so no
service-role escalation is needed for that read.
"""

from datetime import UTC, datetime
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


_ATTEMPT_COLUMNS = (
    "id, student_id, assessment_id, status, started_at, submitted_at, "
    "score, total_marks, percentage, created_at, updated_at"
)

_ANSWER_COLUMNS = (
    "id, attempt_id, question_id, answer_text, selected_option_ids, "
    "awarded_marks, is_correct, created_at, updated_at"
)


def get_own_attempt(client: Client, student_id: str, attempt_id: UUID) -> dict | None:
    """One attempt, scoped to the caller.

    RLS ("Students can view their own attempts") already restricts this to
    auth.uid() = student_id; the explicit .eq("student_id", ...) here is
    defense in depth, matching the pattern used throughout this module.
    Callers must turn None into a 404 -- never reveal whether another
    student's attempt exists.
    """
    response = (
        client.table("assessment_attempts")
        .select(_ATTEMPT_COLUMNS)
        .eq("id", str(attempt_id))
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_visible_question(client: Client, assessment_id: UUID, question_id: UUID) -> dict | None:
    """Confirms one question both exists and is eligible to be answered:
    belongs to the given assessment, and is approved/active/OBJECTIVE --
    the exact same eligibility filters as list_visible_questions (Phase
    1D), scoped to a single id instead of listing every question. A
    student may only answer a question that would actually appear on
    GET .../questions for this assessment; this is what stops answering a
    question from a different assessment, an unapproved/inactive one, or
    an AI_EVALUATED one Phase 1 has no scoring path for.
    """
    response = (
        client.table("assessment_questions")
        .select("id")
        .eq("id", str(question_id))
        .eq("assessment_id", str(assessment_id))
        .eq("review_status", "APPROVED")
        .eq("is_active", True)
        .eq("scoring_method", "OBJECTIVE")
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_existing_answer(client: Client, attempt_id: UUID, question_id: UUID) -> dict | None:
    """The caller's own existing answer for this (attempt, question) pair,
    if any -- assessment_answers_unique_per_attempt_question guarantees at
    most one row. RLS ("Students can view their own answers") already
    scopes this to the caller."""
    response = (
        client.table("assessment_answers")
        .select(_ANSWER_COLUMNS)
        .eq("attempt_id", str(attempt_id))
        .eq("question_id", str(question_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def save_answer(
    client: Client,
    attempt_id: UUID,
    question_id: UUID,
    answer_text: str | None,
    selected_option_ids: list[UUID] | None,
) -> dict:
    """Insert a new answer, or update the existing one for this
    (attempt_id, question_id) pair.

    assessment_answers_unique_per_attempt_question is the DB's own
    guarantee that at most one row exists per pair -- this function
    decides insert vs. update by checking first (get_existing_answer)
    rather than relying on upsert's on-conflict semantics, so the two
    paths map 1:1 onto the two separate RLS policies that govern them:
    "Students can answer questions in their own in-progress attempts"
    (insert) and "Students can revise their own in-progress answers"
    (update). Never sends awarded_marks/is_correct -- those columns are
    simply absent from every payload this function builds, so there is no
    value for the prevent_self_answer_scoring trigger to even reject.
    """
    payload = {
        "answer_text": answer_text,
        "selected_option_ids": (
            [str(option_id) for option_id in selected_option_ids] if selected_option_ids else None
        ),
    }

    existing = get_existing_answer(client, attempt_id, question_id)
    if existing is not None:
        response = (
            client.table("assessment_answers").update(payload).eq("id", existing["id"]).execute()
        )
    else:
        response = (
            client.table("assessment_answers")
            .insert({**payload, "attempt_id": str(attempt_id), "question_id": str(question_id)})
            .execute()
        )
    return response.data[0]


def get_answered_question_ids(client: Client, attempt_id: UUID) -> set[str]:
    """The set of question_ids the student has already saved an answer for
    within this attempt. RLS ("Students can view their own answers")
    already scopes this to the caller; filtering by attempt_id also means
    answers from the student's OTHER attempts (e.g. a previous retake)
    never count towards this one."""
    response = (
        client.table("assessment_answers")
        .select("question_id")
        .eq("attempt_id", str(attempt_id))
        .execute()
    )
    rows = response.data or []
    return {row["question_id"] for row in rows}


def mark_attempt_submitted(client: Client, attempt_id: UUID) -> dict | None:
    """Set submitted_at to the current time. Nothing else -- status stays
    IN_PROGRESS, score/total_marks/percentage stay untouched. Phase 1H
    (service_role) owns the eventual COMPLETED transition together with
    real score data, per assessment_attempts_completed_has_score and
    prevent_self_attempt_scoring, which unconditionally block any
    non-service_role caller from setting status = 'COMPLETED' -- this
    function makes no attempt to do so.

    The .is_("submitted_at", None) filter is an atomic guard against a
    double-submit race: only an attempt that STILL has a null submitted_at
    at the moment of the UPDATE actually matches and gets written. If two
    submit requests race, the loser's UPDATE matches zero rows and this
    function returns None -- callers must treat that as "already
    submitted," not a generic failure, and must never retry with a
    fabricated timestamp.
    """
    response = (
        client.table("assessment_attempts")
        .update({"submitted_at": datetime.now(UTC).isoformat()})
        .eq("id", str(attempt_id))
        .is_("submitted_at", None)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


class AttemptNotEligibleForScoringError(Exception):
    """Raised when score_assessment_attempt() finds the attempt is not
    (status='IN_PROGRESS' AND submitted_at IS NOT NULL) at the moment the
    RPC actually runs -- SQLSTATE 55000 (object_not_in_prerequisite_state).

    Under normal operation the route layer already checked this via
    get_own_attempt() before ever calling this function, so this is
    primarily the race-safe rejection path: the RPC's own
    `select ... for update` serializes concurrent scoring attempts on the
    same attempt, and the loser sees the winner's already-COMPLETED status
    once it acquires the lock.
    """


def score_attempt(client: Client, attempt_id: UUID, student_id: str) -> dict:
    """Trigger the trusted, atomic scoring operation for one attempt.

    MUST be called with the service-role client (get_supabase()) -- RLS
    and the prevent_self_attempt_scoring/prevent_self_answer_scoring
    triggers structurally forbid every other caller from making the
    writes this performs. MUST NOT be called before the route layer has
    already verified attempt ownership and eligibility through
    get_own_attempt() using the user-scoped client -- see
    app.api.attempts.score_attempt for that required ordering.

    All of the actual scoring logic (which questions are eligible, how
    each question_type is compared, total_marks/score/percentage,
    completing the attempt) lives entirely in the
    score_assessment_attempt() Postgres function
    (014_score_assessment_attempt.sql), not here -- that function's own
    header comment documents the approved scoring rules in full. This
    Python function only invokes it and translates its one meaningful
    failure mode (SQLSTATE 55000) into a typed exception; every other
    failure (missing answer key, unsupported question type, a genuine
    "attempt not found" anomaly) is deliberately left as a generic
    postgrest APIError for the route layer's broad except-clause to turn
    into a safe, generic 500 -- these are data-integrity problems, not
    normal client-facing outcomes, and must never be papered over as a
    silent zero score.

    INTENTIONAL DECISION -- assessments.is_active is deliberately NOT part
    of score_assessment_attempt()'s eligible-question query (only each
    question's own review_status/is_active/scoring_method are checked).
    assessments.is_active governs whether an assessment is currently
    discoverable/attemptable/visible through the student-facing read
    endpoints (list_active_assessments, get_active_assessment,
    list_visible_questions) -- it is a content-availability flag, not a
    precondition for scoring. Once a student has legitimately submitted
    an attempt (Phase 1G), deactivating the parent assessment afterward
    must not retroactively block that already-submitted attempt from
    being scored -- the student already did the work under a contract
    where the assessment was live. This was raised as an open design
    question during Phase 1H/1I verification and explicitly decided: keep
    the current behavior, do not add an assessments.is_active check to
    the scoring RPC.
    """
    try:
        response = client.rpc(
            "score_assessment_attempt",
            {"p_attempt_id": str(attempt_id), "p_student_id": student_id},
        ).execute()
    except APIError as exc:
        if exc.code == "55000":
            raise AttemptNotEligibleForScoringError() from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


# ------------------------------------------------------------
# Phase 1I: results
# ------------------------------------------------------------

# Reuses the exact same question+options embed shape as _QUESTION_COLUMNS
# (Phase 1D), just nested one level deeper under assessment_answers
# instead of being the top-level select -- same columns, same
# review_status/generation_* exclusion, same options sub-embed.
_RESULT_ANSWER_COLUMNS = (
    "id, attempt_id, question_id, answer_text, selected_option_ids, "
    "awarded_marks, is_correct, created_at, updated_at, "
    f"question:assessment_questions({_QUESTION_COLUMNS})"
)

_ANSWER_KEY_COLUMNS = "question_id, correct_option_ids, correct_answer_text, explanation"


def get_attempt_result_rows(client: Client, attempt_id: UUID) -> list[dict]:
    """The historical, per-question record of one COMPLETED attempt's
    scoring, ordered by the parent question's display_order, each row
    carrying its nested "question" (with options) and "answer_key".

    Deliberately queried FROM assessment_answers, not from
    list_visible_questions()/assessment_questions directly: after Phase
    1H's unanswered-question persistence fix (see
    score_assessment_attempt() in 014_score_assessment_attempt.sql),
    every question that was actually part of an attempt's scored
    population -- answered or not -- has exactly one assessment_answers
    row (selected_option_ids = [] is the internal "no answer was
    submitted" sentinel for that case, never a value a real student
    submission can produce). Querying from assessment_answers therefore
    reconstructs the REAL historical population, immune to any later
    change in a question's/assessment's review_status or is_active --
    unlike list_visible_questions(), which reflects only CURRENT
    eligibility and would silently diverge from what was actually scored
    if content changes after the fact.

    RLS ("Students can view their own answers") scopes the top-level rows
    to the caller's own attempts; the explicit .eq("attempt_id", ...)
    here is defense in depth. Callers are responsible for having already
    confirmed attempt ownership and COMPLETED status via get_own_attempt()
    before calling this -- this function does not re-check either.

    The nested "question"/"options" embed is independently subject to
    "Authenticated users can view approved active questions" (and the
    matching options policy), which are gated on the question/
    assessment's CURRENT review_status/is_active, NOT on attempt
    completion. If a question or its parent assessment is deactivated
    after this attempt was completed, that embed can come back None for
    this row even though the assessment_answers row itself remains
    visible -- a known, narrow limitation (not something this function
    papers over with service_role). This function does NOT drop or
    otherwise paper over such a row; it returns it with "question" (and/or
    "answer_key") set to None so the caller can decide what to do --
    app.api.attempts.get_attempt_result treats this as a hard failure
    (500), never a silently incomplete result. The separate answer_key
    lookup below does not have this particular gap: "Students can view
    answer keys for their own completed attempts" is gated only on the
    attempt's own completion.

    Two queries, not N+1: one for all of this attempt's answers (with
    question+options embedded), one for all of those questions' answer
    keys via .in_(...). A single deeply-nested embed
    (assessment_answers -> question -> answer_key) was deliberately
    avoided here in favor of this simpler, already-proven 1-level embed
    shape (identical to the one Phase 1D's list_visible_questions already
    uses) plus one extra flat query -- see the Phase 1I report for why.
    """
    answer_response = (
        client.table("assessment_answers")
        .select(_RESULT_ANSWER_COLUMNS)
        .eq("attempt_id", str(attempt_id))
        .execute()
    )
    rows = answer_response.data or []

    question_ids = [row["question_id"] for row in rows if row.get("question")]
    answer_keys_by_question: dict[str, dict] = {}
    if question_ids:
        key_response = (
            client.table("assessment_question_answers")
            .select(_ANSWER_KEY_COLUMNS)
            .in_("question_id", question_ids)
            .execute()
        )
        answer_keys_by_question = {
            key_row["question_id"]: key_row for key_row in (key_response.data or [])
        }

    for row in rows:
        question = row.get("question")
        if question:
            question["options"] = sorted(
                question.get("options") or [], key=lambda option: option["display_order"]
            )
        row["answer_key"] = answer_keys_by_question.get(row["question_id"])

    rows.sort(
        key=lambda row: (row["question"]["display_order"] if row.get("question") else float("inf"))
    )
    return rows
