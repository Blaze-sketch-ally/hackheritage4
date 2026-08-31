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
    "question_count, passing_percentage, is_active, created_at, updated_at"
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


def get_assessment_by_id(client: Client, assessment_id: UUID) -> dict | None:
    """One assessment regardless of is_active -- unlike get_active_assessment,
    used only for post-attempt enrichment (passing_percentage/skill_id for
    the score and result responses), where a since-deactivated assessment
    must not make an already-scored attempt's response unfetchable. Mirrors
    the same "is_active governs discoverability, not historical facts"
    principle score_assessment_attempt() itself already applies (see that
    function's own header comment in the migration)."""
    response = (
        client.table("assessments")
        .select(_ASSESSMENT_COLUMNS)
        .eq("id", str(assessment_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_skill_verification(client: Client, student_id: str, skill_id: str, proficiency_level: str) -> bool:
    """Whether the student's own student_skills row for this EXACT
    (skill_id, proficiency_level) pair is currently verified. False --
    never an error -- when no such row exists at all (the student never
    declared this skill at this level): this function only ever reports
    existing state, never implies a row should exist. RLS ("Students can
    view their own skills") already scopes this to the caller when called
    with a user-scoped client."""
    response = (
        client.table("student_skills")
        .select("is_verified")
        .eq("student_id", student_id)
        .eq("skill_id", skill_id)
        .eq("proficiency_level", proficiency_level)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return bool(row and row.get("is_verified"))


def get_attempt_questions(client: Client, attempt_id: UUID) -> list[dict]:
    """The FROZEN, per-attempt question set persisted by
    create_assessment_attempt() (015_assessment_verification.sql) -- never
    the live question bank. This is the only question data the taking UI
    (and the submission-completeness check) may read: refreshing the
    browser, or resuming later, always returns exactly the same questions
    in exactly the same order, because this reads a permanent historical
    record, not a live query re-run against current bank content.

    Deliberately does NOT filter by review_status/is_active/scoring_method
    -- a question already persisted into this attempt stays part of it
    even if later deactivated (assessment_attempt_questions' own RLS,
    widened by 015_assessment_verification.sql, already allows the student
    to keep seeing it). RLS ("Students can view their own attempt's
    selected questions") scopes the top-level read to the caller's own
    attempt; the nested question/options embed is independently covered by
    both the original "approved active" policies and the widened
    "in their own attempts" ones from the same migration.

    Ordered by assessment_attempt_questions.display_order (the FROZEN exam
    order for this specific attempt) -- NOT by
    assessment_questions.display_order, which only reflects the bank's own
    arbitrary authoring order and is irrelevant here.
    """
    response = (
        client.table("assessment_attempt_questions")
        .select(f"display_order, question:assessment_questions({_QUESTION_COLUMNS})")
        .eq("attempt_id", str(attempt_id))
        .order("display_order")
        .execute()
    )
    rows = response.data or []
    questions = []
    for row in rows:
        question = row.get("question")
        if question is None:
            continue
        # The frozen exam position overrides the bank's own display_order.
        question["display_order"] = row["display_order"]
        question["options"] = sorted(
            question.get("options") or [], key=lambda option: option["display_order"]
        )
        questions.append(question)
    return questions


def get_attempt_question_ids(client: Client, attempt_id: UUID) -> set[str]:
    """The set of question_ids frozen into this attempt -- what submission
    completeness (Phase 1G) must check against, replacing the live-pool
    check that existed before per-attempt question freezing."""
    response = (
        client.table("assessment_attempt_questions")
        .select("question_id")
        .eq("attempt_id", str(attempt_id))
        .execute()
    )
    rows = response.data or []
    return {row["question_id"] for row in rows}


def is_question_in_attempt(client: Client, attempt_id: UUID, question_id: UUID) -> bool:
    """Whether question_id was frozen into this specific attempt --
    replaces the old "is this question currently eligible in the live
    pool" check (get_visible_question) as the eligibility gate for
    POST /attempts/{id}/answers. Deliberately does not re-check the
    question's current review_status/is_active/scoring_method: a question
    legitimately selected into this attempt must remain answerable through
    it for as long as the attempt itself is IN_PROGRESS, even if it is
    deactivated at some point during the attempt -- otherwise a routine
    content change could permanently strand an in-progress attempt with an
    unanswerable, un-submittable question through no fault of the student.
    """
    response = (
        client.table("assessment_attempt_questions")
        .select("question_id")
        .eq("attempt_id", str(attempt_id))
        .eq("question_id", str(question_id))
        .maybe_single()
        .execute()
    )
    return response is not None and response.data is not None


class DuplicateInProgressAttemptError(Exception):
    """Raised when the student already has an IN_PROGRESS attempt for this
    assessment. Mirrors the DB's own partial unique index
    (assessment_attempts_one_in_progress_idx on (student_id, assessment_id)
    WHERE status = 'IN_PROGRESS') -- callers should turn this into a 409,
    not a generic 500."""


class AssessmentNotConfiguredError(Exception):
    """Raised when create_assessment_attempt() (015_assessment_verification.sql)
    finds no blueprint configured for this assessment, or an insufficient
    approved/active/OBJECTIVE question pool for some blueprint difficulty
    bucket (SQLSTATE 55000, object_not_in_prerequisite_state). This is a
    content-configuration problem, not something the student did wrong or
    something a retry fixes -- callers should turn this into a 503, not a
    409 or a generic 500."""


def get_in_progress_attempt(client: Client, student_id: str, assessment_id: UUID) -> dict | None:
    """The caller's own IN_PROGRESS attempt at this assessment, if any --
    lets a student who navigates back to an assessment resume it instead
    of hitting the 409 from a second POST .../attempts. RLS ("Students can
    view their own attempts") already scopes this to the caller; the
    explicit .eq("student_id", ...) is defense in depth, matching every
    other read in this module. At most one row can ever match, by the same
    partial unique index that makes concurrent double-starts impossible."""
    response = (
        client.table("assessment_attempts")
        .select(_ATTEMPT_COLUMNS)
        .eq("student_id", student_id)
        .eq("assessment_id", str(assessment_id))
        .eq("status", "IN_PROGRESS")
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def create_attempt(service_client: Client, student_id: str, assessment_id: UUID) -> dict:
    """Start a new attempt for the calling student AND persist its random
    question selection, in one atomic transaction.

    MUST be called with the service-role client (app.database.supabase.
    get_supabase()) -- create_assessment_attempt() is service_role-only
    (see the REVOKE/GRANT at the end of that function's definition in
    015_assessment_verification.sql), for the same reason
    score_assessment_attempt() already is: PostgREST gives no
    cross-statement transaction to an external client, and "insert the
    attempt, then separately insert its question selection" as ordinary
    REST calls would risk an orphaned, question-less attempt if the
    process died in between.

    MUST NOT be called before the route layer has already verified the
    assessment exists/is active through the normal RLS-respecting path
    (get_active_assessment with the user-scoped client) -- see
    app.api.assessments.create_attempt for that required ordering.
    student_id must always be the authenticated caller's own id (never
    taken from a request body); this function has no way to accept one
    from a client at all, and the RPC itself re-verifies it as a second,
    defense-in-depth check inside the trusted function.

    "No second concurrent attempt" is still enforced by the DB's own
    partial unique index, unchanged -- a violation raises postgrest's
    APIError with code 23505 (unique_violation), translated here into
    DuplicateInProgressAttemptError exactly as before. A missing blueprint
    or an insufficient question pool raises SQLSTATE 55000, translated
    into AssessmentNotConfiguredError.
    """
    try:
        response = service_client.rpc(
            "create_assessment_attempt",
            {"p_assessment_id": str(assessment_id), "p_student_id": student_id},
        ).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateInProgressAttemptError() from exc
        if exc.code == "55000":
            raise AssessmentNotConfiguredError() from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


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
    get_attempt_questions) -- it is a content-availability flag, not a
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
    get_attempt_questions()/assessment_questions directly: after Phase
    1H's unanswered-question persistence fix (see
    score_assessment_attempt() in 015_assessment_verification.sql),
    every question that was actually part of an attempt's scored
    population -- answered or not -- has exactly one assessment_answers
    row (selected_option_ids = [] is the internal "no answer was
    submitted" sentinel for that case, never a value a real student
    submission can produce). Querying from assessment_answers therefore
    reconstructs the REAL historical population, immune to any later
    change in a question's/assessment's review_status or is_active.

    RLS ("Students can view their own answers") scopes the top-level rows
    to the caller's own attempts; the explicit .eq("attempt_id", ...)
    here is defense in depth. Callers are responsible for having already
    confirmed attempt ownership and COMPLETED status via get_own_attempt()
    before calling this -- this function does not re-check either.

    The nested "question"/"options" embed is independently subject to RLS
    on assessment_questions/assessment_question_options. Since
    015_assessment_verification.sql, that RLS includes "a question that is
    part of one of my own attempts" (via assessment_attempt_questions) as
    an additional, permissive path alongside the original "approved
    active" one -- so a question/option deactivated after this attempt
    completed no longer makes this embed come back None (a real, narrow
    limitation the original 014-era implementation had). This function
    still does NOT drop or paper over a None embed if one somehow occurs
    (e.g. a genuinely missing row) -- it returns it as None so the caller
    can decide what to do; app.api.attempts.get_attempt_result treats that
    as a hard failure (500), never a silently incomplete result. The
    separate answer_key lookup below never had this gap at all: "Students
    can view answer keys for their own completed attempts" is gated only
    on the attempt's own completion.

    Two queries, not N+1: one for all of this attempt's answers (with
    question+options embedded), one for all of those questions' answer
    keys via .in_(...). A single deeply-nested embed
    (assessment_answers -> question -> answer_key) was deliberately
    avoided here in favor of this simpler, already-proven 1-level embed
    shape (identical to the one get_attempt_questions already uses) plus
    one extra flat query -- see the Phase 1I report for why.
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


# ------------------------------------------------------------
# Assessment history
# ------------------------------------------------------------

_HISTORY_ATTEMPT_COLUMNS = (
    "id, status, started_at, submitted_at, score, total_marks, percentage, "
    f"assessment:assessments({_ASSESSMENT_COLUMNS})"
)


def list_own_attempts(client: Client, student_id: str) -> list[dict]:
    """Every attempt the caller has ever made, most recent first, with its
    assessment embedded -- the read behind the assessment history page.
    RLS ("Students can view their own attempts") already scopes this to
    the caller; the explicit .eq("student_id", ...) here is defense in
    depth, matching every other read in this module.

    The embedded "assessment" can come back None for an attempt whose
    assessment has since been deactivated ("Students can view active
    assessments" requires is_active = true, and no widened policy exists
    for this embed the way 015_assessment_verification.sql widened
    question/option visibility for a student's own attempts) -- a known,
    narrow limitation: that row's skill/difficulty/passing_percentage
    simply aren't shown. This function does not drop such a row or treat
    it as an error; it is real historical data (the attempt itself always
    exists) with an unavailable content embed, and callers decide how to
    render that.
    """
    response = (
        client.table("assessment_attempts")
        .select(_HISTORY_ATTEMPT_COLUMNS)
        .eq("student_id", student_id)
        .order("started_at", desc=True)
        .execute()
    )
    return response.data or []
