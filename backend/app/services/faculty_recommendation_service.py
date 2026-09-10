"""Deterministic Faculty task/recommendation aggregation (Faculty Module
audit). No LLM call anywhere in this module -- same "no invented score,
rank by a real signal" posture as app.services.student_recommendation_service
and app.services.skill_recommendation_service.

A thin ADAPTER/COMPOSER over three canonical, UNCHANGED-here sources. It
recomputes nothing, invents no relevance score, and writes nothing:

  1. app.services.question_bank_service.list_my_questions
     -- RLS already scopes this to "the caller's own questions, plus
        every question if the caller holds assessment_reviewer" (041_
        assessment_capability_authorization.sql). Filtering to PENDING
        questions NOT authored by the caller reuses that existing scope
        rather than adding a new query or a new authorization rule --
        for a caller who does not hold assessment_reviewer, every row
        returned is already the caller's own, so this filter naturally
        yields [] with no extra capability check required for
        *correctness*; the explicit capability gate in get_faculty_tasks()
        below exists only to skip the query entirely for performance.

  2. app.services.evaluation_service.list_my_evaluations
     -- evaluations' own SELECT policy (045_evaluation_foundation.sql)
        scopes this to evaluator_id = auth.uid() already. Filtering to
        ASSIGNED/IN_PROGRESS reuses the exact status vocabulary that
        table's own CHECK constraint defines -- no new state invented.

  3. app.services.faculty_student_mentorship_service.list_for_faculty
     -- RLS scopes this to faculty_id = auth.uid() already. The two
        statuses surfaced here (REQUESTED awaiting the caller's decision,
        ACCEPTED awaiting activation) are exactly the two documented
        checkpoints from 040_faculty_student_mentorships.sql's own status
        comment where the NEXT action is the caller's, not the student's.

  4. app.services.reconciliation_service.list_cases (Faculty Assessment
     Governance audit) -- reuses the read-only
     list_reconciliation_cases() RPC (067_assessment_reconciliation_
     visibility.sql) verbatim. Same "broadcast to every current holder
     of the capability" model as pending_reviews above (an explicit,
     documented interim default -- see that migration's own header for
     why there is no per-moderator assignment mechanism yet).

Ranking in every category is by a real lifecycle timestamp (oldest first
-- the longest-waiting item is the most overdue for attention), never a
fabricated priority score. This mirrors this project's own established
"rank by a real signal, explain the ranking, no LLM in the decision
layer" rule for recommendations.
"""

from supabase import Client

from app.schemas.faculty_permissions import AssessmentCapability
from app.services import (
    evaluation_service,
    faculty_student_mentorship_service,
    question_bank_service,
    reconciliation_service,
)

_PENDING_EVALUATION_STATUSES = {"ASSIGNED", "IN_PROGRESS"}

# Exactly the two documented "next action is the Faculty member's"
# mentorship checkpoints (see module docstring) -- REQUESTED ranks above
# ACCEPTED because an unanswered request blocks the relationship from
# existing at all, while an ACCEPTED-but-not-yet-ACTIVE mentorship is
# already confirmed and only needs activation.
_MENTORSHIP_STATUS_RANK = {"REQUESTED": 0, "ACCEPTED": 1}
_MENTORSHIP_REASON = {
    "REQUESTED": "Awaiting your response to a student's mentorship request.",
    "ACCEPTED": "Both sides have accepted -- activate this mentorship to begin.",
}


def list_pending_reviews(client: Client, faculty_id: str) -> list[dict]:
    """PENDING questions authored by a DIFFERENT faculty member, oldest
    first. Empty for a caller who doesn't currently hold
    assessment_reviewer (see module docstring) -- callers should still
    prefer the capability gate in get_faculty_tasks() to avoid the query
    entirely in that case."""
    questions = question_bank_service.list_my_questions(client)
    pending = [
        {
            "question_id": q["id"],
            "assessment_id": q["assessment_id"],
            "question_text": q["question_text"],
            "created_at": q["created_at"],
        }
        for q in questions
        if q.get("review_status") == "PENDING" and q.get("created_by") != faculty_id
    ]
    pending.sort(key=lambda item: item["created_at"])
    return pending


def list_pending_evaluations(client: Client, evaluator_id: str) -> list[dict]:
    """The caller's own ASSIGNED/IN_PROGRESS evaluations, oldest-assigned
    first."""
    evaluations = evaluation_service.list_my_evaluations(client, evaluator_id)
    pending = [
        {
            "evaluation_id": e["evaluation_id"],
            "attempt_id": e["attempt_id"],
            "assessment_title": e["assessment_title"],
            "status": e["status"],
            "assigned_at": e["assigned_at"],
        }
        for e in evaluations
        if e.get("status") in _PENDING_EVALUATION_STATUSES
    ]
    pending.sort(key=lambda item: item["assigned_at"] or "")
    return pending


def list_mentorships_needing_attention(client: Client, faculty_id: str) -> list[dict]:
    """The caller's own mentorships sitting at a REQUESTED (awaiting the
    caller's decision, not self-requested) or ACCEPTED (awaiting
    activation) checkpoint. Batch-resolves student names in one extra
    query -- never one query per mentorship, matching
    evaluation_service.list_my_evaluations' own anti-N+1 convention."""
    mentorships = faculty_student_mentorship_service.list_for_faculty(client, faculty_id)
    candidates = [
        m
        for m in mentorships
        if (m["status"] == "REQUESTED" and m["requested_by"] != faculty_id) or m["status"] == "ACCEPTED"
    ]
    if not candidates:
        return []

    student_ids = sorted({m["student_id"] for m in candidates})
    profiles = (
        client.table("profiles").select("id, full_name, username").in_("id", student_ids).execute().data or []
    )
    name_by_id = {p["id"]: (p.get("full_name") or p.get("username") or "Student") for p in profiles}

    items = [
        {
            "mentorship_id": m["id"],
            "student_id": m["student_id"],
            "student_name": name_by_id.get(m["student_id"], "Student"),
            "status": m["status"],
            "reason": _MENTORSHIP_REASON[m["status"]],
            "updated_at": m["updated_at"],
        }
        for m in candidates
    ]
    items.sort(key=lambda item: item["updated_at"])
    items.sort(key=lambda item: _MENTORSHIP_STATUS_RANK[item["status"]])
    return items


def list_pending_reconciliations(client: Client) -> list[dict]:
    """Every (attempt, question) currently in a genuine, unresolved
    evaluator conflict, across the whole catalog -- reuses
    reconciliation_service.list_cases verbatim (itself a thin wrapper
    over the read-only list_reconciliation_cases() RPC). Already ordered
    server-side (most recently updated attempt first); not re-sorted
    here."""
    return reconciliation_service.list_cases(client)


def get_faculty_tasks(client: Client, faculty_id: str, capabilities: set[AssessmentCapability]) -> dict:
    """The full composed response: pending_reviews, pending_evaluations,
    and pending_reconciliations are only ever computed for a caller who
    currently holds the matching capability (skips the query entirely
    otherwise -- a plain FACULTY account with none of these never pays
    for any of the three lookups). mentorship_attention needs no
    capability gate: list_for_faculty is already RLS-scoped to the
    caller's own rows, so a caller who has never held faculty_mentor
    simply has none."""
    return {
        "pending_reviews": (
            list_pending_reviews(client, faculty_id)
            if AssessmentCapability.REVIEWER in capabilities
            else []
        ),
        "pending_evaluations": (
            list_pending_evaluations(client, faculty_id)
            if AssessmentCapability.EVALUATOR in capabilities
            else []
        ),
        "mentorship_attention": list_mentorships_needing_attention(client, faculty_id),
        "pending_reconciliations": (
            list_pending_reconciliations(client)
            if AssessmentCapability.MODERATOR in capabilities
            else []
        ),
    }
