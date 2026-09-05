"""Service layer for the F8.3 evaluator workflow, the F8.4.2 fold-in
trigger, and Phase 2's admin evaluator-assignment management.

Every evaluator-facing function here takes the CALLER's own RLS-scoped
client (app.core.security.build_user_client) -- never a service-role
client -- with deliberate exceptions: fold_in_attempt() and every
admin_* function below, which MUST be called with the service-role
client (app.database.supabase.get_supabase()) for their actual
privileged write/read, exactly like assessment_service.score_attempt()'s
own established ownership-then-service_role pattern. F8.2's RLS
(046_evaluator_answer_access.sql, widened by 051 for candidate rubric
visibility) is the actual security boundary for everything
evaluator-facing here: an evaluator_id filter is added throughout as
defense in depth, matching this codebase's own established convention
(see assessment_service.get_own_attempt's identical reasoning), never as
the only thing standing between an evaluator and someone else's row.
For the admin_* functions, the route layer's own require_admin()
dependency is the real authorization boundary -- see each function's own
docstring.

Zero-row handling is the one thing every function here must get right:
an UPDATE that matches no row under RLS (revoked assignment, suspended/
expired capability, wrong evaluator, nonexistent id) returns an EMPTY
result from PostgREST, not an error -- see prevent_unauthorized_
evaluation_change's own header in 045_evaluation_foundation.sql and the
F8.2 audit's own documented case for this exact behavior. Every mutating
function below treats "zero rows returned" as "not found", identical to
question_bank_service.update_question's own convention.
"""

from decimal import Decimal
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

_QUESTION_COLUMNS = (
    "id, assessment_id, question_text, question_type, scoring_method, "
    "difficulty, points, display_order, "
    "options:assessment_question_options(id, question_id, option_text, display_order)"
)

_ANSWER_COLUMNS = (
    "id, attempt_id, question_id, answer_text, selected_option_ids, "
    "awarded_marks, is_correct, created_at, updated_at"
)

_RUBRIC_COLUMNS = (
    "id, question_id, name, description, max_marks, status, "
    "criteria:rubric_criteria(id, rubric_id, criterion, description, max_marks, display_order)"
)

_EVALUATION_WITH_ASSIGNMENT_COLUMNS = (
    "id, assignment_id, status, awarded_marks, feedback, rubric_id, "
    "submitted_at, finalized_at, finalized_by, "
    "evaluator_assignments(attempt_id, question_id, created_at)"
)

# Same shape as faculty_student_mentorship_service._TRANSITIONS_FROM --
# a target status maps to the ONLY status it may legally come from. The
# F8.1 trigger (prevent_unauthorized_evaluation_change) independently
# re-enforces this identical rule regardless of what reaches this
# function; this table exists purely to turn an invalid attempt into a
# clean typed exception instead of a raw APIError, and to let a
# duplicate/idempotent re-send of the CURRENT status short-circuit before
# ever reaching this table at all (see update_evaluation_status).
_TRANSITIONS_FROM: dict[str, frozenset[str]] = {
    "IN_PROGRESS": frozenset({"ASSIGNED"}),
    "SUBMITTED": frozenset({"IN_PROGRESS"}),
    "FINALIZED": frozenset({"SUBMITTED"}),
}


class EvaluationInvalidStatusTransitionError(Exception):
    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an evaluation from {current} to {target}.")


class EvaluationFinalizedError(Exception):
    """Raised when the database rejects a mutation because the
    evaluation is already FINALIZED -- SQLSTATE 42501, prevent_
    unauthorized_evaluation_change's finalized-immutable branch
    (045_evaluation_foundation.sql). Route layer: 409."""


class EvaluationValidationError(Exception):
    """Raised for a rubric/marks validation failure -- SQLSTATE 23514,
    either a plain CHECK constraint (awarded_marks >= 0, finalized
    requires marks) or an explicit trigger raise (a rubric that doesn't
    belong to this assignment's question, or awarded_marks exceeding the
    rubric's own max_marks). Route layer: 422."""


class EvaluationFoldInNotEligibleError(Exception):
    """Phase F8.4.2: raised when fold_in_attempt_evaluation() finds the
    attempt is not (yet) COMPLETED -- SQLSTATE 55000 (object_not_in_
    prerequisite_state), the same code assessment_service.score_attempt's
    own AttemptNotEligibleForScoringError translates for the identical
    reason.

    This is expected and benign, not a failure: create_evaluator_
    assignment (045_evaluation_foundation.sql) has no attempt-status
    precondition of its own, so an evaluator can legitimately be
    assigned to, and finalize, an evaluation before the student's
    attempt has ever been submitted/scored -- F8.3's own established
    workflow has always allowed this ordering, F8.4.2 does not change
    it. When this occurs there is simply nothing yet to fold in -- the
    route layer treats this as a normal 200 (the evaluation itself is
    genuinely finalized), silently deferring the fold-in rather than
    failing the request. See app.api.faculty_evaluations.
    update_evaluation_status's own docstring for the full handling, and
    its "KNOWN GAP" note for what re-triggers the deferred fold-in
    later."""


class EvaluatorIneligibleError(Exception):
    """Phase 2: raised when the Faculty member an admin is trying to
    assign does not currently hold an active, unexpired
    assessment_evaluator capability. create_evaluator_assignment()
    itself (045) only checks that the target is FACULTY at all -- it
    does not check assessment_evaluator, by design (assignment and
    capability are deliberately independent concepts) -- so this is the
    one place "eligible" is actually enforced. Route layer: 422."""


class EvaluatorAssignmentDuplicateError(Exception):
    """Phase 2: raised when the target evaluator already holds an
    ACTIVE assignment for this exact (attempt, question) -- SQLSTATE
    23505 on evaluator_assignments_unique_active_idx (045). Route
    layer: 409."""


class InvalidAssignmentTargetError(Exception):
    """Phase 2: raised when create_evaluator_assignment() rejects the
    target itself -- the evaluator profile doesn't exist or isn't
    FACULTY (SQLSTATE 42501), or the (attempt_id, question_id) pair
    doesn't exist in assessment_attempt_questions (SQLSTATE P0002).
    Route layer: 422."""


class EvaluatorAssignmentNotFoundError(Exception):
    """Phase 2: raised when revoke_evaluator_assignment() cannot find
    the assignment_id -- SQLSTATE P0002. Route layer: 404."""


class EvaluatorAssignmentAlreadyRevokedError(Exception):
    """Phase 2: raised when revoke_evaluator_assignment() finds the
    assignment already REVOKED -- SQLSTATE 55000. Route layer: 409 --
    the end state the caller wanted (revoked) already holds, but this
    is surfaced rather than silently treated as success, since a second
    caller revoking the same assignment is worth the caller knowing
    about, not swallowing."""


def _assignment_scope(client: Client, assignment_id: str) -> dict | None:
    """attempt_id/question_id/created_at for one of the caller's OWN
    assignments -- relies on evaluator_assignments' own SELECT policy
    (046) to scope this to rows the caller actually owns; a foreign
    assignment_id (which should never occur here, since it always comes
    from a row the caller's own evaluations query already returned)
    would simply come back empty. created_at is exposed to the route
    layer as assigned_at (Phase 2)."""
    response = (
        client.table("evaluator_assignments")
        .select("attempt_id, question_id, created_at")
        .eq("id", assignment_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def _attempt_context(client: Client, attempt_id: str) -> dict | None:
    """student_id + assessment_title for one attempt, in a single call --
    relies on the evaluator's own assessment_attempts SELECT policy
    (046_evaluator_answer_access.sql) -- only ever resolves for an
    attempt the caller actually has an ACTIVE assignment against. The
    assessments(title) embed rides the existing assessment_id FK -- no
    separate query, no new RLS needed (assessments' own "authenticated
    can view active assessments" policy, 1D, already covers this read
    regardless of the attempt-scoped policy above)."""
    response = (
        client.table("assessment_attempts")
        .select("student_id, assessments(title)")
        .eq("id", attempt_id)
        .maybe_single()
        .execute()
    )
    if response is None or response.data is None:
        return None
    assessment = response.data.get("assessments") or {}
    return {"student_id": response.data["student_id"], "assessment_title": assessment.get("title")}


def _to_summary(client: Client, row: dict) -> dict:
    """Flattens one evaluations row (plus its assignment's attempt_id/
    question_id/assigned_at and the attempt's student_id/
    assessment_title) into the shape EvaluationSummaryResponse expects."""
    scope = _assignment_scope(client, row["assignment_id"])
    attempt_id = scope["attempt_id"] if scope else None
    context = _attempt_context(client, attempt_id) if attempt_id else None
    return {
        "evaluation_id": row["id"],
        "assignment_id": row["assignment_id"],
        "status": row["status"],
        "awarded_marks": row["awarded_marks"],
        "attempt_id": attempt_id,
        "question_id": scope["question_id"] if scope else None,
        "assigned_at": scope["created_at"] if scope else None,
        "student_id": context["student_id"] if context else None,
        "assessment_title": context["assessment_title"] if context else None,
    }


def list_my_evaluations(client: Client, evaluator_id: str, status: str | None = None) -> list[dict]:
    """The caller's own work queue. evaluations' own SELECT policy (045)
    already scopes this to evaluator_id = auth.uid(); the explicit .eq()
    here is defense in depth, matching this module's own convention
    throughout."""
    query = (
        client.table("evaluations")
        .select(_EVALUATION_WITH_ASSIGNMENT_COLUMNS)
        .eq("evaluator_id", evaluator_id)
    )
    if status is not None:
        query = query.eq("status", status)
    rows = query.execute().data or []

    # Batch-resolve student_id/assessment_title for every distinct
    # attempt_id in one extra query, rather than one per row -- the only
    # place in this module that batches, since list results can be many
    # rows while every other function here handles exactly one.
    attempt_ids = sorted({row["evaluator_assignments"]["attempt_id"] for row in rows if row.get("evaluator_assignments")})
    context_by_attempt: dict[str, dict] = {}
    if attempt_ids:
        attempts = (
            client.table("assessment_attempts")
            .select("id, student_id, assessments(title)")
            .in_("id", attempt_ids)
            .execute()
            .data
            or []
        )
        context_by_attempt = {
            a["id"]: {"student_id": a["student_id"], "assessment_title": (a.get("assessments") or {}).get("title")}
            for a in attempts
        }

    summaries = []
    for row in rows:
        assignment = row.get("evaluator_assignments") or {}
        attempt_id = assignment.get("attempt_id")
        context = context_by_attempt.get(attempt_id) if attempt_id else None
        summaries.append(
            {
                "evaluation_id": row["id"],
                "assignment_id": row["assignment_id"],
                "status": row["status"],
                "awarded_marks": row["awarded_marks"],
                "attempt_id": attempt_id,
                "question_id": assignment.get("question_id"),
                "assigned_at": assignment.get("created_at"),
                "student_id": context["student_id"] if context else None,
                "assessment_title": context["assessment_title"] if context else None,
            }
        )
    return summaries


def get_evaluation_detail(client: Client, evaluator_id: str, evaluation_id: UUID) -> dict | None:
    """One assigned evaluation, with everything needed to actually
    evaluate it: question content (student-facing shape, no answer key
    -- see AssessmentQuestionResponse's own docstring), the student's
    submitted answer if any, and the attached rubric+criteria if any.
    Returns None if the evaluation doesn't exist, isn't the caller's own,
    or the caller's assignment is no longer ACTIVE -- route layer maps
    that to 404, same convention as every other "not found or not yours"
    case in this codebase.

    The ACTIVE check here is deliberate, not incidental: evaluations'
    own SELECT policy (045) keeps an evaluator's row visible even after
    their assignment is revoked (a historical-record choice), but
    assessment_attempts/assessment_answers/assessment_questions (046,
    047) all correctly stop resolving the moment the assignment is no
    longer ACTIVE. Without this check, a revoked evaluator would get a
    200 with silently-nulled question/student_id fields instead of a
    clean 404 -- this treats "assignment no longer active" the same as
    "not found", matching every other revocation behavior in this
    codebase, rather than exposing a half-populated detail view."""
    response = (
        client.table("evaluations")
        .select(_EVALUATION_WITH_ASSIGNMENT_COLUMNS)
        .eq("id", str(evaluation_id))
        .eq("evaluator_id", evaluator_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if row is None:
        return None

    assignment_status_response = (
        client.table("evaluator_assignments").select("status").eq("id", row["assignment_id"]).maybe_single().execute()
    )
    assignment_status = assignment_status_response.data if assignment_status_response is not None else None
    if assignment_status is None or assignment_status["status"] != "ACTIVE":
        return None

    assignment = row.get("evaluator_assignments") or {}
    attempt_id = assignment.get("attempt_id")
    question_id = assignment.get("question_id")
    context = _attempt_context(client, attempt_id) if attempt_id else None

    question_response = (
        client.table("assessment_questions").select(_QUESTION_COLUMNS).eq("id", question_id).maybe_single().execute()
    )
    question = question_response.data if question_response is not None else None
    if question is not None:
        question["options"] = sorted(question.get("options") or [], key=lambda o: o["display_order"])

    answer_response = (
        client.table("assessment_answers")
        .select(_ANSWER_COLUMNS)
        .eq("attempt_id", attempt_id)
        .eq("question_id", question_id)
        .maybe_single()
        .execute()
    )
    student_answer = answer_response.data if answer_response is not None else None

    rubric = None
    if row.get("rubric_id"):
        rubric_response = (
            client.table("rubrics").select(_RUBRIC_COLUMNS).eq("id", row["rubric_id"]).maybe_single().execute()
        )
        rubric = rubric_response.data if rubric_response is not None else None
        if rubric is not None:
            rubric["criteria"] = sorted(rubric.get("criteria") or [], key=lambda c: c["display_order"])

    return {
        "evaluation_id": row["id"],
        "assignment_id": row["assignment_id"],
        "status": row["status"],
        "awarded_marks": row["awarded_marks"],
        "feedback": row["feedback"],
        "rubric_id": row["rubric_id"],
        "submitted_at": row["submitted_at"],
        "finalized_at": row["finalized_at"],
        "finalized_by": row["finalized_by"],
        "attempt_id": attempt_id,
        "question_id": question_id,
        "assigned_at": assignment.get("created_at"),
        "student_id": context["student_id"] if context else None,
        "assessment_title": context["assessment_title"] if context else None,
        "question": question,
        "student_answer": student_answer,
        "rubric": rubric,
    }


def list_candidate_rubrics(client: Client, evaluator_id: str, evaluation_id: UUID) -> list[dict] | None:
    """Phase 2: ACTIVE rubrics that exist for the question the caller's
    own evaluation is assigned against -- what SaveEvaluationRequest.
    rubric_id can legitimately be set to. Relies entirely on 051's new
    "candidate rubric" SELECT policy (evaluator-assignment-scoped, same
    shape as 047's question/option visibility) -- this function performs
    no additional filtering itself beyond status='ACTIVE' (never offer
    an ARCHIVED rubric as a new selection, though one already saved onto
    a past evaluation stays visible via 046's own separate policy).

    Returns None (-> 404, same convention as get_evaluation_detail) if
    the evaluation doesn't exist, isn't the caller's own, or the
    caller's assignment is no longer ACTIVE -- computing question_id
    from the evaluation the exact same ownership-verified way
    get_evaluation_detail does, never trusting a client-supplied
    question_id.
    """
    response = (
        client.table("evaluations")
        .select(_EVALUATION_WITH_ASSIGNMENT_COLUMNS)
        .eq("id", str(evaluation_id))
        .eq("evaluator_id", evaluator_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if row is None:
        return None

    assignment_status_response = (
        client.table("evaluator_assignments").select("status").eq("id", row["assignment_id"]).maybe_single().execute()
    )
    assignment_status = assignment_status_response.data if assignment_status_response is not None else None
    if assignment_status is None or assignment_status["status"] != "ACTIVE":
        return None

    assignment = row.get("evaluator_assignments") or {}
    question_id = assignment.get("question_id")

    rubrics = (
        client.table("rubrics")
        .select(_RUBRIC_COLUMNS)
        .eq("question_id", question_id)
        .eq("status", "ACTIVE")
        .execute()
        .data
        or []
    )
    for rubric in rubrics:
        rubric["criteria"] = sorted(rubric.get("criteria") or [], key=lambda c: c["display_order"])
    return rubrics


def save_evaluation(client: Client, evaluator_id: str, evaluation_id: UUID, updates: dict) -> dict | None:
    """Content only (rubric_id/awarded_marks/feedback) -- never status.
    updates is already exclude_unset-filtered by the route layer
    (mirrors question_bank_service.update_question's own
    payload-built-at-the-route-layer convention). The database remains
    authoritative for rubric/question compatibility, the max-marks
    ceiling, and finalized-immutability regardless of what reaches this
    function -- see prevent_unauthorized_evaluation_change.

    Decimal fields (awarded_marks) are converted to str before the
    update -- the postgrest client does not serialize Decimal to JSON on
    its own, matching how the route layer elsewhere always calls
    body.model_dump(mode="json", ...) before handing a payload to a
    service function.
    """
    payload = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in updates.items()}
    try:
        response = (
            client.table("evaluations")
            .update(payload)
            .eq("id", str(evaluation_id))
            .eq("evaluator_id", evaluator_id)
            .execute()
        )
    except APIError as exc:
        if exc.code == "42501":
            raise EvaluationFinalizedError() from exc
        if exc.code == "23514":
            raise EvaluationValidationError(str(exc)) from exc
        raise
    rows = response.data or []
    if not rows:
        return None
    return _to_summary(client, rows[0])


def update_evaluation_status(client: Client, evaluator_id: str, evaluation_id: UUID, new_status: str) -> dict | None:
    """ASSIGNED -> IN_PROGRESS -> SUBMITTED -> FINALIZED, one hop at a
    time. A re-send of the CURRENT status is treated as an idempotent
    success (no write attempted) rather than an error -- the F8.1
    trigger's own transition check only fires when status actually
    changes, so two concurrent requests reaching the same target status
    are both safe; this mirrors that property rather than fighting it
    with extra locking. See the F8.3 architecture audit's concurrency
    analysis for the full reasoning.

    Phase F8.4.2.1 (Fix B): the idempotent short-circuit below is the
    ONE path through this function that returns a summary WITHOUT ever
    going through the ACTIVE-assignment-gated UPDATE RLS policy
    ("Evaluators can update their own evaluations while assigned is
    active", 045_evaluation_foundation.sql) -- a genuine transition
    attempt against a revoked assignment already correctly 404s today
    (that policy makes the UPDATE affect zero rows, handled below by the
    existing `if not rows: return None`). Without this explicit check, a
    revoked-but-still-capable evaluator resending an already-FINALIZED
    status would fall through to _to_summary(), whose
    _student_id_for_attempt() call silently resolves to None once 046's
    ACTIVE-only assessment_attempts policy stops matching -- producing a
    non-nullable EvaluationSummaryResponse.student_id validation failure
    (500) instead of a clean 404. This mirrors get_evaluation_detail's
    own identical ACTIVE check (F8.2.1) exactly: "assignment no longer
    active" is treated the same as "not found", matching every other
    revocation behavior in this codebase, rather than exposing a
    half-populated summary. Capability expiry does not need this check:
    evaluations' own SELECT policy (045) is itself capability-gated, so
    current_row is already None above once the capability lapses --
    this branch is unreached in that case.
    """
    current_response = (
        client.table("evaluations")
        .select("id, assignment_id, status, awarded_marks")
        .eq("id", str(evaluation_id))
        .eq("evaluator_id", evaluator_id)
        .maybe_single()
        .execute()
    )
    current_row = current_response.data if current_response is not None else None
    if current_row is None:
        return None

    if current_row["status"] == new_status:
        assignment_status_response = (
            client.table("evaluator_assignments")
            .select("status")
            .eq("id", current_row["assignment_id"])
            .maybe_single()
            .execute()
        )
        assignment_status = assignment_status_response.data if assignment_status_response is not None else None
        if assignment_status is None or assignment_status["status"] != "ACTIVE":
            return None
        return _to_summary(client, current_row)

    allowed_from = _TRANSITIONS_FROM.get(new_status)
    if allowed_from is None or current_row["status"] not in allowed_from:
        raise EvaluationInvalidStatusTransitionError(current_row["status"], new_status)

    try:
        response = (
            client.table("evaluations")
            .update({"status": new_status})
            .eq("id", str(evaluation_id))
            .eq("evaluator_id", evaluator_id)
            .execute()
        )
    except APIError as exc:
        if exc.code == "42501":
            raise EvaluationFinalizedError() from exc
        if exc.code == "22023":
            raise EvaluationInvalidStatusTransitionError(current_row["status"], new_status) from exc
        if exc.code == "23514":
            raise EvaluationValidationError(str(exc)) from exc
        raise
    rows = response.data or []
    if not rows:
        return None
    return _to_summary(client, rows[0])


def fold_in_attempt(service_client: Client, attempt_id: UUID | str) -> None:
    """Phase F8.4.2: trigger the trusted F8.4.1 fold-in RPC
    (fold_in_attempt_evaluation, 049_evaluation_status_and_final_score.sql)
    for one attempt, after a caller-verified FINALIZED transition has
    already committed.

    MUST be called with the service-role client (app.database.supabase.
    get_supabase()) -- the RPC is granted to service_role only and is not
    reachable through any RLS-scoped evaluator client, matching
    assessment_service.score_attempt()'s identical ownership-then-
    service_role structure. MUST NOT be called before the route layer has
    already confirmed, through the caller's own RLS-scoped client, that
    the evaluation genuinely reached FINALIZED -- see
    app.api.faculty_evaluations.update_evaluation_status for that
    required ordering.

    This function is a pure trigger: it does not read, return, or
    interpret the fold-in result, and does not calculate or decide
    anything about evaluation_status/final_score/final_total_marks/
    final_percentage/disagreement -- all of that logic lives entirely
    inside fold_in_attempt_evaluation() itself, per F8.4.1's own
    contract. It is intentionally safe to call more than once for the
    same attempt (fold_in_attempt_evaluation() always recomputes from
    scratch and is row-locked) -- every FINALIZED transition, including
    an idempotent duplicate re-send of the same target status, re-invokes
    this, which is exactly what makes a failed fold-in safely retryable:
    simply re-sending the identical PATCH .../status request re-triggers
    it, with no separate retry endpoint needed. See that route's own
    docstring for the chosen failure-response contract.

    Raises EvaluationFoldInNotEligibleError (SQLSTATE 55000 -- the
    attempt is not yet COMPLETED) for the route layer to treat as a
    benign, expected no-op rather than a failure; any other exception
    propagates untouched as a genuine, unexpected fold-in failure.
    """
    try:
        service_client.rpc("fold_in_attempt_evaluation", {"p_attempt_id": str(attempt_id)}).execute()
    except APIError as exc:
        if exc.code == "55000":
            raise EvaluationFoldInNotEligibleError() from exc
        raise


# ============================================================
# Phase 2 -- ADMIN evaluator assignment management.
#
# Every function below is called with TWO clients, matching this
# module's own already-established "ownership/eligibility verified via
# the user-scoped client FIRST, privileged write only through the
# service-role client afterward" pattern (fold_in_attempt above;
# assessment_service.score_attempt). create_evaluator_assignment()/
# revoke_evaluator_assignment() (045_evaluation_foundation.sql) are
# reused completely unmodified -- service_role-only, exactly as F8.1
# left them; no new RPC, no new migration for these two. The route
# layer's own require_admin() dependency is what makes calling the
# service-role client here safe -- see 045's own migration header for
# why this (not is_admin() baked into the RPC, not assessment_moderator/
# assessment_lead) is the governance decision this phase makes.
# ============================================================


def admin_list_attempts_for_assignment(service_client: Client, assessment_id: UUID) -> list[dict]:
    """COMPLETED attempts for one assessment, each with its
    AI_EVALUATED questions (the only ones fold_in_attempt_evaluation(),
    049, ever treats as requiring human evaluation) and any
    evaluator_assignments already made against them -- the data source
    for an admin choosing who to assign next, including for
    co-evaluation (seeing who is already assigned before adding
    another).

    MUST be called with the service-role client -- no RLS policy grants
    an admin visibility into another student's assessment_attempts/
    assessment_attempt_questions/evaluator_assignments at all (unlike
    Faculty capability grants, this data was never opened to
    `authenticated` for any role, admin included). The route layer's
    require_admin() dependency is the sole authorization boundary for
    this read, exactly like Fix A's completion trigger relies on the
    route layer having already verified FINALIZED before ever
    constructing a service-role client.

    student_id is never exposed as more than a short, truncated label
    (student_label) -- matching this project's own established
    reviewer-anonymization convention (question-detail-view.tsx's
    reviewerLabel) -- no student email/name/profile is read here at all.
    """
    attempts = (
        service_client.table("assessment_attempts")
        .select("id, student_id, status")
        .eq("assessment_id", str(assessment_id))
        .eq("status", "COMPLETED")
        .execute()
        .data
        or []
    )
    if not attempts:
        return []

    attempt_ids = [a["id"] for a in attempts]

    attempt_questions = (
        service_client.table("assessment_attempt_questions")
        .select("attempt_id, question_id, assessment_questions(id, question_text, points, scoring_method)")
        .in_("attempt_id", attempt_ids)
        .execute()
        .data
        or []
    )

    assignments = (
        service_client.table("evaluator_assignments")
        .select(
            "id, evaluator_id, attempt_id, question_id, status, "
            "profiles!evaluator_id(email, full_name), evaluations(status)"
        )
        .in_("attempt_id", attempt_ids)
        .execute()
        .data
        or []
    )
    assignments_by_question: dict[tuple[str, str], list[dict]] = {}
    for a in assignments:
        key = (a["attempt_id"], a["question_id"])
        profile = a.get("profiles") or {}
        evaluation = a.get("evaluations") or {}
        assignments_by_question.setdefault(key, []).append(
            {
                "assignment_id": a["id"],
                "evaluator_id": a["evaluator_id"],
                "evaluator_email": profile.get("email"),
                "evaluator_full_name": profile.get("full_name"),
                "assignment_status": a["status"],
                "evaluation_status": evaluation.get("status"),
            }
        )

    questions_by_attempt: dict[str, list[dict]] = {}
    for aq in attempt_questions:
        question = aq.get("assessment_questions")
        if question is None or question.get("scoring_method") != "AI_EVALUATED":
            continue
        key = (aq["attempt_id"], aq["question_id"])
        questions_by_attempt.setdefault(aq["attempt_id"], []).append(
            {
                "question_id": question["id"],
                "question_text": question["question_text"],
                "points": question["points"],
                "existing_assignments": assignments_by_question.get(key, []),
            }
        )

    result = []
    for attempt in attempts:
        questions = questions_by_attempt.get(attempt["id"], [])
        if not questions:
            continue  # No AI_EVALUATED question in this attempt -- nothing to assign here.
        result.append(
            {
                "attempt_id": attempt["id"],
                "student_label": f"Student {attempt['student_id'][:8]}…",
                "status": attempt["status"],
                "questions": questions,
            }
        )
    return result


def admin_create_assignment(
    user_client: Client,
    service_client: Client,
    evaluator_id: str,
    attempt_id: UUID,
    question_id: UUID,
    created_by: str,
) -> dict:
    """Create one evaluator_assignments row via the existing, unmodified
    create_evaluator_assignment() RPC.

    user_client independently re-verifies, fresh, that the target
    currently holds assessment_evaluator (has_assessment_capability,
    027_faculty_assessment_permissions.sql -- grantable to any
    authenticated caller, called here as the admin, not the target) --
    create_evaluator_assignment() itself only checks that the target is
    FACULTY at all, so this is the one place "eligible" is actually
    enforced, per this phase's own explicit requirement (a FACULTY user
    having assessment_evaluator means eligible to evaluate; it does not
    mean automatically assigned, and the reverse must also hold: nobody
    without that capability may be assigned regardless of what an admin
    requests). service_client then performs the actual privileged
    write -- never called before the eligibility check above passes.
    """
    eligible = user_client.rpc(
        "has_assessment_capability",
        {"profile_id": str(evaluator_id), "requested_capability": "assessment_evaluator"},
    ).execute()
    if not eligible.data:
        raise EvaluatorIneligibleError(
            "The selected Faculty member does not currently hold an active Evaluator capability."
        )

    try:
        response = service_client.rpc(
            "create_evaluator_assignment",
            {
                "p_evaluator_id": str(evaluator_id),
                "p_attempt_id": str(attempt_id),
                "p_question_id": str(question_id),
                "p_created_by": created_by,
            },
        ).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise EvaluatorAssignmentDuplicateError(
                "This evaluator is already actively assigned to this question."
            ) from exc
        if exc.code in ("42501", "P0002"):
            raise InvalidAssignmentTargetError(str(exc)) from exc
        raise

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def admin_revoke_assignment(service_client: Client, assignment_id: UUID, revoked_by: str) -> dict:
    """Revoke one evaluator_assignments row via the existing, unmodified
    revoke_evaluator_assignment() RPC. MUST only be called after the
    route layer's own require_admin() dependency has already verified
    the caller -- this RPC has no is_admin() check of its own (045's own
    header explains why: the governance-actor question was deliberately
    left to this exact phase to decide, not baked into the RPC).
    Revocation never deletes evaluation_history or a FINALIZED
    evaluation's own row -- both remain exactly as immutable as F8.1
    already made them; this function touches only evaluator_assignments.
    """
    try:
        response = service_client.rpc(
            "revoke_evaluator_assignment",
            {"p_assignment_id": str(assignment_id), "p_revoked_by": revoked_by},
        ).execute()
    except APIError as exc:
        if exc.code == "P0002":
            raise EvaluatorAssignmentNotFoundError(str(exc)) from exc
        if exc.code == "55000":
            raise EvaluatorAssignmentAlreadyRevokedError(str(exc)) from exc
        raise
    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data
