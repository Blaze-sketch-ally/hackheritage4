"""Business logic for the Assessment API -- Phase 1D (read-only),
Phase 1E (attempt creation), Phase 1F (answer saving), Phase 1G
(submission), Phase 1H (scoring), Phase 1I (results), and Phase 1K
(randomized per-attempt question selection).

Every function here takes an already-constructed Supabase client. For most
of these functions this is always the user-scoped client (see
app.core.security.build_user_client) -- RLS does the real access-control
work, these functions only shape the query and the return value. Two
functions are the deliberate exceptions, both requiring the service-role
client (app.database.supabase.get_supabase) because RLS structurally
forbids the writes they need to make: score_attempt() (Phase 1H, see
score_assessment_attempt() in 014_score_assessment_attempt.sql) and
create_attempt() (Phase 1K, see create_assessment_attempt() in
015_question_bank_random_assessment.sql -- starting an attempt now also
means atomically persisting its randomized question selection, the same
class of single-transaction privileged write scoring already required).
Ordinary student operations must never bypass RLS; only these two trusted
operations do, and only after the route layer has already verified
ownership/eligibility through the normal RLS-respecting path first.
get_attempt_result_rows() (Phase 1I) and get_attempt_questions() (Phase
1K) both deliberately read through the user-scoped client -- RLS alone
already permits both reads for their respective owned rows, so no
service-role escalation is needed for either.
"""

from datetime import UTC, datetime
from decimal import Decimal
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


class InsufficientQuestionPoolError(Exception):
    """Raised when create_assessment_attempt() (Phase 1K,
    015_question_bank_random_assessment.sql) finds too few APPROVED/
    active/OBJECTIVE questions in some blueprint difficulty bucket to
    satisfy the assessment's blueprint, or finds no blueprint configured
    for the assessment at all -- SQLSTATE 55000, same code
    AttemptNotEligibleForScoringError already uses for "object not in
    prerequisite state." Callers should turn this into a 409, never a
    silently-smaller question set."""


def create_attempt(client: Client, student_id: str, assessment_id: UUID) -> dict:
    """Start a new attempt for the calling student, with its randomized
    question selection (Phase 1K) persisted atomically alongside it.

    MUST be called with the service-role client (get_supabase()) --
    create_assessment_attempt() performs the same class of privileged,
    single-transaction write score_assessment_attempt() does (see that
    function's own header comment for why this can't be safely done as
    several separate REST calls): insert the attempt AND persist its
    assessment_attempt_questions rows together, so a failure partway
    through (insufficient pool, no blueprint configured) leaves no
    orphaned attempt behind. The route layer must verify the assessment
    exists/is active via the user-scoped client BEFORE calling this,
    exactly like score_attempt's existing ownership-then-service_role
    pattern.

    "No second concurrent attempt" is still enforced by the DB's own
    partial unique index, unchanged from before Phase 1K -- a violation
    raises postgrest's APIError with code 23505 (unique_violation), which
    this function translates into DuplicateInProgressAttemptError so the
    route layer can return a clean 409 instead of a raw DB error.
    Insufficient pool / no blueprint raises SQLSTATE 55000, translated
    into InsufficientQuestionPoolError, also a 409 at the route layer.
    """
    try:
        response = client.rpc(
            "create_assessment_attempt",
            {"p_assessment_id": str(assessment_id), "p_student_id": student_id},
        ).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateInProgressAttemptError() from exc
        if exc.code == "55000":
            raise InsufficientQuestionPoolError() from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def get_attempt_questions(client: Client, attempt_id: UUID) -> list[dict]:
    """The persisted, ordered question set selected for one attempt
    (Phase 1K) -- NOT re-derived from current eligibility. This is the
    student-taking UI's source of truth: it returns the identical set on
    every call for the life of the attempt, since nothing here can change
    what assessment_attempt_questions already recorded at attempt-creation
    time (see 015_question_bank_random_assessment.sql).

    RLS ("Students can view their own attempt's selected questions")
    scopes the join rows to the caller's own attempt. The nested
    "question"/"options" embed is additionally covered by "Students can
    view questions/options in their own attempts" (020, final Phase 1K
    hardening) -- a student can see a question's content, regardless of
    its CURRENT is_active/review_status, as long as it's part of one of
    their own persisted attempts. Before 020, this embed was gated only by
    the general "approved active" student policy, so a question
    deactivated after being selected into this attempt would come back
    with question=None -- callers must still treat a None embed as a hard
    failure (never silently drop the question) as a defensive fallback,
    but 020 means this should no longer happen for the ordinary "my own
    question was deactivated" case; a None embed now indicates a genuinely
    unexpected condition, not an accepted limitation.
    """
    response = (
        client.table("assessment_attempt_questions")
        .select(f"question_id, display_order, question:assessment_questions({_QUESTION_COLUMNS})")
        .eq("attempt_id", str(attempt_id))
        .order("display_order")
        .execute()
    )
    return response.data or []


def get_attempt_question_ids(client: Client, attempt_id: UUID) -> set[str]:
    """The set of question_ids persisted for this attempt (Phase 1K) --
    used by the submit-completeness check in place of the old Phase 1G
    live-pool check (list_visible_questions), which compared against the
    CURRENT assessment-wide eligible pool rather than this attempt's own
    fixed selection. A blueprint-driven attempt only ever contains a
    SUBSET of the assessment's full approved pool, so the old check would
    incorrectly demand answers to questions that were never part of this
    attempt at all. Deliberately selects only question_id, not the nested
    question embed -- a later-deactivated question must still count
    toward completeness (it was legitimately part of this attempt's
    selection), so this must never depend on RLS visibility of the
    embedded question content the way get_attempt_questions() does.
    """
    response = (
        client.table("assessment_attempt_questions")
        .select("question_id")
        .eq("attempt_id", str(attempt_id))
        .execute()
    )
    return {row["question_id"] for row in (response.data or [])}


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


def is_question_in_attempt(client: Client, attempt_id: UUID, question_id: UUID) -> bool:
    """Whether question_id is part of THIS attempt's PERSISTED selection
    (assessment_attempt_questions) -- the sole authority for "does this
    question belong to this attempt" once an attempt exists (Phase 1K).

    Bug fixed here: this function replaces the old Phase 1F
    get_visible_question(), which gated answer-saving on the question's
    CURRENT review_status/is_active/scoring_method -- a live-eligibility
    check that predates Phase 1K's persisted-attempt-set model and was
    never revisited for it. Once a question has been selected into an
    attempt, deactivating it (or any other later change to the question
    bank) must not retroactively make it unanswerable through that
    attempt -- exactly the same "historical membership, not current
    eligibility" rule score_assessment_attempt() and
    get_attempt_question_ids() already follow. Deliberately does NOT
    query assessment_questions or check any of its columns at all: only
    membership in assessment_attempt_questions matters here, which is why
    an unselected question (never part of this attempt, even if currently
    APPROVED/active) is correctly rejected too -- this is a membership
    check, not a relaxed eligibility check.

    RLS ("Students can view their own attempt's selected questions")
    already scopes this to the caller's own attempt for read access; the
    real authorization for the WRITE this guards (inserting into
    assessment_answers) is enforced independently by that table's own RLS
    policy (ownership + IN_PROGRESS status, no eligibility dependency at
    all -- confirmed directly against 004_assessments.sql), so this
    function's job is purely "does this question belong to this attempt,"
    not a security boundary by itself.
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
# Phase 1L: derived skill evidence (read-only)
# ------------------------------------------------------------


def get_student_skill_scores(client: Client, student_id: str) -> dict[str, Decimal]:
    """Phase 1L: the calling student's current skill evidence, derived
    entirely from their own COMPLETED assessment_attempts -- read-only,
    adds no new table, computes nothing this module doesn't already have
    the data for. This is the ONLY place Phase 1L reads assessment
    history from; it does not touch student_skills (see the header
    comment on 022_career_roles_skill_gap.sql for why that table is a
    different concept -- self-reported, not assessed -- and deliberately
    left alone), and it does not modify assessment_attempts, scoring, or
    anything else Phase 1K owns.

    For each skill covered by at least one of the student's COMPLETED
    attempts, returns the BEST percentage achieved across all such
    attempts, keyed by skill_id -- mirroring this project's existing
    "duplicate attempts for the same target -> take the best one" pattern
    (there is no other precedent to follow here, since this is Phase 1L's
    first aggregation across multiple attempts, but "best, not most
    recent or average" is the natural reading of "skill evidence" and is
    documented here as the explicit rule). A skill the student has never
    completed an assessment for is simply ABSENT from the returned dict --
    callers (skill_alignment_service.compute_alignment) must treat a
    missing key as "not yet assessed," never silently default it to a
    score of 0 in a way that's indistinguishable from an assessed-and-
    failed 0.

    IN_PROGRESS/ABANDONED attempts never contribute -- only
    status = 'COMPLETED' rows are read, so an attempt that was started but
    never finished (or was abandoned) contributes nothing, matching the
    same "only a COMPLETED attempt is authoritative" rule
    get_attempt_result_rows() already follows.

    RLS ("Students can view their own attempts") already scopes this to
    the caller; the explicit .eq("student_id", ...) here is defense in
    depth, matching the pattern used throughout this module. The nested
    "assessment" embed is independently subject to assessments' own
    "Authenticated users can view active assessments" policy
    (is_active = true) -- if the parent assessment was deactivated after
    the student completed it, that embed can come back None for that row.
    Unlike get_attempt_result_rows() (where a None embed on a
    completion-critical read is treated as a hard failure), this function
    simply excludes that row from the aggregate: a skill-gap summary
    silently reflecting one fewer contributing attempt is a narrow,
    acceptable limitation for a derived analysis view, not a correctness
    bug the way silently dropping a question from a submission-
    completeness or scoring check would be.
    """
    response = (
        client.table("assessment_attempts")
        .select("percentage, assessment:assessments(skill_id)")
        .eq("student_id", student_id)
        .eq("status", "COMPLETED")
        .execute()
    )
    best_by_skill: dict[str, Decimal] = {}
    for row in response.data or []:
        assessment = row.get("assessment")
        if not assessment or row.get("percentage") is None:
            continue
        skill_id = assessment["skill_id"]
        percentage = Decimal(str(row["percentage"]))
        if skill_id not in best_by_skill or percentage > best_by_skill[skill_id]:
            best_by_skill[skill_id] = percentage
    return best_by_skill


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
