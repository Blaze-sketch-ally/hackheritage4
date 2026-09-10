"""System-context Faculty notification producers.

Mirrors app.services.notification_producer's own contract exactly:

`faculty_notifications` (database/migrations/066_faculty_notifications.sql)
has NO insert policy, so no RLS-governed caller -- Faculty or otherwise --
can create a notification. Rows are written ONLY here, and ONLY with the
service-role client (app.database.supabase.get_supabase), which bypasses
RLS.

Every function here is invoked from an already-successful backend action
on a state transition that is ITSELF already guarded against duplication
by an existing uniqueness constraint or state-machine check (see the
migration's own header, "Idempotency" section, Layer 1) -- a retried or
duplicated client request fails the underlying action before the emit
call is ever reached a second time. Each function additionally sets a
deterministic `dedupe_key`, enforced unique per faculty_id by a partial
unique index (Layer 2) -- true belt-and-suspenders, not merely
application-level "check then insert."

Best-effort by contract: every producer swallows its own errors and
returns None. A missing notification must never turn a successful
underlying action (the assignment, the decision, the status change)
into a failure. The caller therefore does not need its own try/except
around these calls.
"""

import contextlib

from app.database.supabase import get_supabase


def _student_label(client, student_id: str) -> str:
    """Best-effort display name for a notification body -- never raises;
    falls back to a generic label if the profile lookup fails for any
    reason (a missing/failed lookup must not block the notification
    itself, matching this module's own best-effort contract)."""
    with contextlib.suppress(Exception):
        response = (
            client.table("profiles").select("full_name, username").eq("id", student_id).maybe_single().execute()
        )
        row = response.data if response is not None else None
        if row:
            return row.get("full_name") or row.get("username") or "A student"
    return "A student"


def emit_evaluation_assigned(*, evaluator_id: str, assignment_id: str) -> None:
    """Notify an evaluator that they were just assigned to evaluate one
    (attempt, question). Called once, from the same request that just
    successfully created the evaluator_assignments row (which itself
    rejects a genuine duplicate with 23505 -- see the migration header).

    Resolves the sibling `evaluations` row (created atomically with the
    assignment by create_evaluator_assignment(), 045) so the deep link
    points at the actual Evaluation Workspace detail page
    (/faculty/evaluation-workspace/{evaluation_id}), not the assignment
    id, which has no dedicated route."""
    if not evaluator_id or not assignment_id:
        return

    with contextlib.suppress(Exception):
        client = get_supabase()
        evaluation = (
            client.table("evaluations").select("id").eq("assignment_id", assignment_id).maybe_single().execute()
        )
        evaluation_row = evaluation.data if evaluation is not None else None
        evaluation_id = evaluation_row["id"] if evaluation_row else None

        payload = {
            "faculty_id": evaluator_id,
            "type": "EVALUATION_ASSIGNED",
            "title": "You have been assigned an evaluation",
            "body": "A new evaluation is waiting for you in the Evaluation Workspace.",
            "dedupe_key": f"eval_assigned:{assignment_id}",
        }
        if evaluation_id:
            payload["related_entity_type"] = "EVALUATION"
            payload["related_entity_id"] = evaluation_id
        client.table("faculty_notifications").insert(payload).execute()


def emit_evaluation_revoked(*, evaluator_id: str, assignment_id: str) -> None:
    """Notify an evaluator that one of their assignments was revoked.
    Called once, from the same request that just successfully revoked
    the assignment (revoke_evaluator_assignment() rejects an
    already-revoked assignment with 55000 -- see the migration header).

    No related entity is set: once revoked, RLS immediately removes the
    evaluator's access to that evaluation (046/047/051, all ACTIVE-
    assignment-gated), so a deep link into a now-inaccessible page would
    only 403 -- the title/body alone communicate what happened."""
    if not evaluator_id or not assignment_id:
        return

    with contextlib.suppress(Exception):
        get_supabase().table("faculty_notifications").insert(
            {
                "faculty_id": evaluator_id,
                "type": "EVALUATION_REVOKED",
                "title": "An evaluation assignment was revoked",
                "body": "One of your evaluation assignments was revoked and is no longer in your queue.",
                "dedupe_key": f"eval_revoked:{assignment_id}",
            }
        ).execute()


_REVIEW_DECISION_TITLE = {
    "APPROVED": "Your question was approved",
    "REJECTED": "Your question needs changes",
}
_REVIEW_DECISION_PHRASE = {
    "APPROVED": "was approved",
    "REJECTED": "was rejected and needs changes before it can be resubmitted",
}


def emit_review_decision(*, author_id: str, question_id: str, decision: str, updated_at: str | None) -> None:
    """Notify a question's author that a reviewer approved or rejected it.
    Called once, from the same request that just successfully changed
    review_status (review_question() rejects a no-longer-PENDING question
    with 55000/409 -- see the migration header). No-op for a decision with
    no defined title (there is none outside APPROVED/REJECTED).

    dedupe_key includes `updated_at` (the row's own updated_at after this
    decision) rather than just question_id: a question may be rejected,
    revised back to PENDING by its author, and later approved -- two
    genuinely distinct decision events on the same question must both be
    allowed to notify, not be silently deduped against each other."""
    title = _REVIEW_DECISION_TITLE.get(decision)
    if title is None or not author_id or not question_id:
        return

    phrase = _REVIEW_DECISION_PHRASE[decision]
    body = f"Your question {phrase}."
    key_suffix = updated_at or "unknown"

    with contextlib.suppress(Exception):
        get_supabase().table("faculty_notifications").insert(
            {
                "faculty_id": author_id,
                "type": "REVIEW_DECISION",
                "title": title,
                "body": body,
                "related_entity_type": "QUESTION",
                "related_entity_id": question_id,
                "dedupe_key": f"review_decision:{question_id}:{key_suffix}",
            }
        ).execute()


def emit_mentorship_request(*, faculty_id: str, student_id: str, mentorship_id: str) -> None:
    """Notify a Faculty member that a student requested them as a mentor.
    Called once, from the same request that just successfully created the
    mentorship row (create_student_request() rejects a duplicate pair
    with 23505 -- see the migration header)."""
    if not faculty_id or not student_id or not mentorship_id:
        return

    with contextlib.suppress(Exception):
        client = get_supabase()
        name = _student_label(client, student_id)
        client.table("faculty_notifications").insert(
            {
                "faculty_id": faculty_id,
                "type": "MENTORSHIP",
                "title": "New mentorship request",
                "body": f"{name} requested you as a mentor.",
                "related_entity_type": "MENTORSHIP",
                "related_entity_id": mentorship_id,
                "dedupe_key": f"mentorship_requested:{mentorship_id}",
            }
        ).execute()


_MENTORSHIP_STATUS_TITLE = {
    "ACCEPTED": "A student accepted your mentorship request",
    "DECLINED": "A student declined your mentorship request",
    "WITHDRAWN": "A mentorship request was withdrawn",
    "ACTIVE": "A mentorship is now active",
    "COMPLETED": "A mentorship was marked completed",
    "ENDED": "A mentorship was ended",
}
_MENTORSHIP_STATUS_PHRASE = {
    "ACCEPTED": "accepted your mentorship request",
    "DECLINED": "declined your mentorship request",
    "WITHDRAWN": "withdrew their mentorship request to you",
    "ACTIVE": "activated your mentorship",
    "COMPLETED": "marked your mentorship completed",
    "ENDED": "ended your mentorship",
}


def emit_mentorship_status_change(
    *, faculty_id: str, student_id: str, mentorship_id: str, new_status: str
) -> None:
    """Notify a Faculty member that the STUDENT side changed the status of
    one of their shared mentorships. Callers must only invoke this when
    the acting caller was genuinely the student (never when the Faculty
    member changed their own mentorship's status) -- see
    app.api.student_mentorships.update_mentorship_status, the only call
    site, which by construction only ever runs for a student-authenticated
    request. Called once, from the same request that just successfully
    performed the transition (update_status() rejects a transition from
    the wrong FROM state -- see the migration header). No-op for a status
    with no defined title."""
    title = _MENTORSHIP_STATUS_TITLE.get(new_status)
    if title is None or not faculty_id or not student_id or not mentorship_id:
        return

    phrase = _MENTORSHIP_STATUS_PHRASE[new_status]
    with contextlib.suppress(Exception):
        client = get_supabase()
        name = _student_label(client, student_id)
        client.table("faculty_notifications").insert(
            {
                "faculty_id": faculty_id,
                "type": "MENTORSHIP",
                "title": title,
                "body": f"{name} {phrase}.",
                "related_entity_type": "MENTORSHIP",
                "related_entity_id": mentorship_id,
                "dedupe_key": f"mentorship_status:{mentorship_id}:{new_status}",
            }
        ).execute()


def emit_reconciliation_resolved(*, evaluator_id: str, evaluation_id: str, decision_id: str) -> None:
    """Notify an evaluator that a reconciliation decision was recorded
    for a question they evaluated (Faculty Assessment Reconciliation --
    Option C, approved decision #13). Called once per affected evaluator,
    from the same request that just successfully created or superseded a
    decision (068_assessment_reconciliation_decisions.sql's partial
    unique index makes a genuine duplicate ACTIVE decision for the same
    question impossible, so this is never re-triggered for the same
    resolution event).

    Deliberately narrow: the body never includes the other evaluator's
    mark, the moderator's rationale, or the moderator's identity --
    exactly the approved boundary. The deep link points at the
    evaluator's OWN evaluation (/faculty/evaluation-workspace/{evaluation_id}),
    never at the reconciliation case itself (which remains
    assessment_moderator-only).

    dedupe_key includes decision_id (not just evaluation_id): a question
    can be superseded later, which is a second, genuinely distinct
    resolution event the same evaluator should be informed of again --
    keying only on evaluation_id would incorrectly suppress that second,
    real notification."""
    if not evaluator_id or not evaluation_id or not decision_id:
        return

    with contextlib.suppress(Exception):
        get_supabase().table("faculty_notifications").insert(
            {
                "faculty_id": evaluator_id,
                "type": "RECONCILIATION_RESOLVED",
                "title": "A reconciliation decision was recorded",
                "body": "A moderator recorded a reconciliation decision for a question you evaluated.",
                "related_entity_type": "EVALUATION",
                "related_entity_id": evaluation_id,
                "dedupe_key": f"reconciliation_resolved:{decision_id}:{evaluator_id}",
            }
        ).execute()
