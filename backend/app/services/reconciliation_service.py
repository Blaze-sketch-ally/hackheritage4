"""Business logic for the assessment reconciliation surface (Faculty
Assessment Reconciliation -- Option C).

Every function calls one of the SECURITY DEFINER RPCs
(067_assessment_reconciliation_visibility.sql read-only;
068_assessment_reconciliation_decisions.sql for decision creation/
supersession) through the caller's own user-scoped client
(app.core.security.build_user_client) -- never service_role. The RPCs
themselves internally re-verify
has_assessment_capability(auth.uid(), 'assessment_moderator') and raise
42501 otherwise; the route layer's require_assessment_moderator
dependency is defense-in-depth on top of that, matching this project's
own established "capability enforced at the RPC/RLS layer, checked again
at the route layer for a clean error" pattern (e.g. review_question()).

This module never writes to `evaluations`/`evaluator_assignments`
directly, and never computes evaluation_status/final_* itself --
068's RPCs are the only write path, and they delegate all derived-result
computation to the existing, unmodified-in-signature
fold_in_attempt_evaluation() (049, extended by 068 via CREATE OR REPLACE).
"""

from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client


class NotModeratorError(Exception):
    """Raised when an RPC's own internal has_assessment_capability check
    rejects the caller -- SQLSTATE 42501. Route layer: 403. In practice
    the route's own require_assessment_moderator dependency already
    rejects a non-moderator before this is ever reached; this exists
    purely as defense-in-depth, matching question_bank_service.
    OwnQuestionReviewError's identical shape."""


class ReconciliationNotFoundError(Exception):
    """Raised for SQLSTATE P0002 -- the attempt, the question (within
    that attempt), or the decision (on supersede) doesn't exist / isn't
    visible to the caller. Route layer: 404. Mirrors this project's own
    "not found vs not visible are indistinguishable" convention
    throughout (get_student_skill_scores, get_notification, etc.)."""


class ReconciliationStateError(Exception):
    """Raised for SQLSTATE 55000 -- the attempt is not currently
    NEEDS_RECONCILIATION, the question is not currently in conflict, or
    the decision being superseded is no longer ACTIVE. Route layer: 409.
    The RPC's own RAISE message (preserved via str(exc)) already
    distinguishes which of the three applies -- one exception class is
    enough since all three map to the identical HTTP status."""


class DuplicateActiveDecisionError(Exception):
    """Raised for SQLSTATE 23505 -- an ACTIVE decision already exists for
    this (attempt_id, question_id); the caller must supersede it instead
    of creating a second one. Route layer: 409."""


class InvalidReconciliationRequestError(Exception):
    """Raised for SQLSTATE 23514 -- final_awarded_marks outside
    [0, question.points], or (defense-in-depth backstop; the Pydantic
    schema layer already rejects this first) a blank rationale. Route
    layer: 422."""


def list_cases(client: Client) -> list[dict]:
    """Every (attempt, question) currently in a genuine, unresolved
    conflict, across the whole catalog -- not scoped to "assigned to me":
    see the migration's own header for why every current
    assessment_moderator sees every current case (an explicit, documented
    interim default, not a final assignment model)."""
    try:
        response = client.rpc("list_reconciliation_cases").execute()
    except APIError as exc:
        if exc.code == "42501":
            raise NotModeratorError() from exc
        raise
    return response.data or []


def get_case(client: Client, attempt_id: UUID) -> list[dict] | None:
    """The conflicting FINALIZED marks for one attempt, or None if it
    doesn't exist or is no longer a live reconciliation case (P0002) --
    callers must turn None into a 404, so a case that was already
    legitimately resolved (once a resolution mechanism exists) is
    indistinguishable from one that never existed, matching this
    project's own convention throughout."""
    try:
        response = client.rpc(
            "get_reconciliation_case", {"p_attempt_id": str(attempt_id)}
        ).execute()
    except APIError as exc:
        if exc.code == "P0002":
            return None
        if exc.code == "42501":
            raise NotModeratorError() from exc
        raise
    return response.data or []


def _one_row(response) -> dict:
    data = response.data
    if isinstance(data, list):
        return data[0]
    return data


def create_decision(
    client: Client,
    attempt_id: UUID,
    question_id: UUID,
    final_awarded_marks,
    rationale: str,
) -> dict:
    """Create the first reconciliation decision for a genuinely
    conflicting question. moderator_id is never sent -- the RPC derives
    it exclusively from auth.uid(). Returns the new decision plus the
    freshly-refolded attempt's evaluation_status/final_percentage, plus
    the parallel affected_evaluator_ids/affected_evaluation_ids arrays
    (used by the route layer to emit RECONCILIATION_RESOLVED
    notifications -- this function itself never touches
    faculty_notifications)."""
    try:
        response = client.rpc(
            "create_reconciliation_decision",
            {
                "p_attempt_id": str(attempt_id),
                "p_question_id": str(question_id),
                "p_final_awarded_marks": str(final_awarded_marks),
                "p_rationale": rationale,
            },
        ).execute()
    except APIError as exc:
        _raise_typed(exc)
    return _one_row(response)


def supersede_decision(
    client: Client,
    decision_id: UUID,
    final_awarded_marks,
    rationale: str,
) -> dict:
    """Supersede an existing ACTIVE decision: the prior row is marked
    SUPERSEDED (with superseded_by set), a new ACTIVE row is inserted,
    and fold-in re-runs -- all in one transaction, inside the RPC.
    Deliberately not gated on the attempt's CURRENT evaluation_status
    (it may already be COMPLETE) -- see 068's own "Stage 7 edge case"
    comment for the full reasoning."""
    try:
        response = client.rpc(
            "supersede_reconciliation_decision",
            {
                "p_decision_id": str(decision_id),
                "p_final_awarded_marks": str(final_awarded_marks),
                "p_rationale": rationale,
            },
        ).execute()
    except APIError as exc:
        _raise_typed(exc)
    return _one_row(response)


def list_decision_history(client: Client, attempt_id: UUID, question_id: UUID) -> list[dict]:
    """The full ACTIVE + SUPERSEDED decision chain for one question --
    moderator-only (Stage 8). Never exposed to an evaluator or ordinary
    Faculty caller -- the RPC itself enforces this."""
    try:
        response = client.rpc(
            "list_reconciliation_decisions",
            {"p_attempt_id": str(attempt_id), "p_question_id": str(question_id)},
        ).execute()
    except APIError as exc:
        if exc.code == "42501":
            raise NotModeratorError() from exc
        raise
    return response.data or []


def _raise_typed(exc: APIError) -> None:
    if exc.code == "42501":
        raise NotModeratorError() from exc
    if exc.code == "P0002":
        raise ReconciliationNotFoundError(str(exc)) from exc
    if exc.code == "55000":
        raise ReconciliationStateError(str(exc)) from exc
    if exc.code == "23505":
        raise DuplicateActiveDecisionError(str(exc)) from exc
    if exc.code == "23514":
        raise InvalidReconciliationRequestError(str(exc)) from exc
    raise exc
