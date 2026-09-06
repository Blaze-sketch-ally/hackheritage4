"""System-context notification producers (Phase S8).

`student_notifications` (database/migrations/035_student_notifications.sql)
has NO insert policy, so no RLS-governed caller -- student or otherwise --
can create a notification. Rows are written ONLY here, and ONLY with the
service-role client (app.database.supabase.get_supabase), which bypasses
RLS.

Every function here is invoked from an already-authorized, NON-Student
request path (currently: the Industry application-status route,
`require_industry`) or a future background job -- never from a Student
request handler, and never with a Student's own token. This keeps
`service_role` entirely out of ordinary Student request paths (Part U /
Part AE of the S8 brief).

Best-effort by contract: every producer swallows its own errors and
returns None. A missing notification must never turn a successful
underlying action (the status change itself) into a failure. The caller
therefore does not need its own try/except around these calls.
"""

import contextlib

from app.database.supabase import get_supabase

# Only transitions that are genuinely meaningful to a student get a
# notification. APPLIED is the student's own action (no notification), and
# WITHDRAWN is also student-initiated.
_APPLICATION_STATUS_TITLE: dict[str, str] = {
    "UNDER_REVIEW": "Your application is under review",
    "SHORTLISTED": "You've been shortlisted",
    "INTERVIEW_SCHEDULED": "An interview has been scheduled",
    "SELECTED": "You've been selected",
    "REJECTED": "Update on your application",
}

_APPLICATION_STATUS_PHRASE: dict[str, str] = {
    "UNDER_REVIEW": "is now under review",
    "SHORTLISTED": "has been shortlisted",
    "INTERVIEW_SCHEDULED": "has moved to the interview stage",
    "SELECTED": "was selected",
    "REJECTED": "was not selected this time",
}


def emit_application_status_change(
    *,
    student_id: str,
    application_id: str,
    new_status: str,
    opportunity_title: str | None,
) -> None:
    """Notify a student that the Industry side moved their application to
    `new_status`. No-op for a status with no student-facing meaning.

    Writes exactly one `student_notifications` row via the service-role
    client. `related_entity_type`/`related_entity_id` point at the
    application so the frontend can offer a "view" link to
    /student/applications (the only route APPLICATION maps to -- there is
    no per-id application route)."""
    title = _APPLICATION_STATUS_TITLE.get(new_status)
    if title is None:
        return

    phrase = _APPLICATION_STATUS_PHRASE[new_status]
    where = f' for "{opportunity_title}"' if opportunity_title else ""
    body = f"Your application{where} {phrase}."

    # Best-effort: the status change already succeeded. A failed
    # notification write (RLS, network, migration 035 not yet applied, ...)
    # must not propagate.
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "APPLICATION_STATUS",
                "title": title,
                "body": body,
                "related_entity_type": "APPLICATION",
                "related_entity_id": application_id,
            }
        ).execute()


# Only a terminal review verdict is meaningful to a student. UNDER_REVIEW
# is an internal industry step (no notification). Migration 039 widened the
# student_notifications CHECKs to allow type 'INTERNSHIP' +
# related_entity_type 'INTERNSHIP_WORKSPACE'.
_REVIEW_VERDICT_TITLE: dict[str, str] = {
    "ACCEPTED": "A submission was accepted",
    "REVISION_REQUESTED": "A submission needs revision",
    "REJECTED": "Update on a submission",
}

_REVIEW_VERDICT_PHRASE: dict[str, str] = {
    "ACCEPTED": "was accepted",
    "REVISION_REQUESTED": "needs revision before it can be accepted",
    "REJECTED": "was not accepted",
}


def emit_submission_review_decision(
    *,
    student_id: str,
    workspace_id: str,
    verdict: str,
    assignment_title: str | None,
) -> None:
    """Notify a student that the industry recorded a review verdict on one
    of their internship submission attempts. No-op for a verdict with no
    student-facing meaning (there is none outside the three below, and
    UNDER_REVIEW never reaches here).

    Writes exactly one `student_notifications` row via the service-role
    client (the table has no insert policy). `related_entity_type` /
    `related_entity_id` point at the workspace so the frontend can offer a
    link to /student/my-internships/{workspace_id}. Best-effort: a failed
    write never turns a successful review into an error, and the caller
    invokes this exactly once per review action so there is no
    duplication."""
    title = _REVIEW_VERDICT_TITLE.get(verdict)
    if title is None or not student_id or not workspace_id:
        return

    phrase = _REVIEW_VERDICT_PHRASE[verdict]
    where = f' for "{assignment_title}"' if assignment_title else ""
    body = f"Your submission{where} {phrase}."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "INTERNSHIP",
                "title": title,
                "body": body,
                "related_entity_type": "INTERNSHIP_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


def emit_internship_completed(
    *,
    student_id: str,
    workspace_id: str,
    internship_title: str | None,
    certificate_number: str | None,
) -> None:
    """Notify a student that the industry verified their internship
    complete and issued a certificate (Phase 7). The caller (the verify
    route) invokes this exactly once -- only on the call that actually
    created the completion record, never on a repeated/idempotent verify
    -- so this never needs its own dedup check.

    Writes exactly one `student_notifications` row via the service-role
    client (the table has no insert policy). Points at the workspace, same
    as `emit_submission_review_decision`, so the frontend can link to
    /student/my-internships/{workspace_id}. Best-effort: a failed write
    never turns a successful verification into an error."""
    if not student_id or not workspace_id:
        return

    where = f' for "{internship_title}"' if internship_title else ""
    number = f" ({certificate_number})" if certificate_number else ""
    body = f"Your internship{where} is complete. Your certificate{number} is ready to view."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "INTERNSHIP",
                "title": "Internship completed — certificate issued",
                "body": body,
                "related_entity_type": "INTERNSHIP_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


# Phase 8 -- stipend record-keeping. Only a transition meaningful to the
# student gets a notification (approved / released / cancelled); creating
# a PENDING record does not. RECORD-KEEPING ONLY: "released" means the
# industry recorded a disbursement in the portal, never that a real
# payment moved -- the wording below says exactly that.
_STIPEND_STATUS_TITLE: dict[str, str] = {
    "APPROVED": "Your stipend was approved",
    "RELEASED": "Your stipend was marked as released",
    "CANCELLED": "Your stipend record was cancelled",
}

_STIPEND_STATUS_PHRASE: dict[str, str] = {
    "APPROVED": "has been approved",
    "RELEASED": "has been marked as released in the portal",
    "CANCELLED": "was cancelled",
}


def emit_stipend_status_change(
    *,
    student_id: str,
    workspace_id: str,
    new_status: str,
) -> None:
    """Notify a student that their stipend record moved to `new_status`.
    No-op for a status with no student-facing meaning (PENDING). The
    caller (each transition route) invokes this exactly once, only on a
    transition that actually succeeded -- a repeated/rejected transition
    request never reaches here, so a duplicate notification is
    structurally impossible, not just avoided by convention.

    Writes exactly one `student_notifications` row via the service-role
    client (the table has no insert policy). Best-effort: a failed write
    never turns a successful transition into an error."""
    title = _STIPEND_STATUS_TITLE.get(new_status)
    if title is None or not student_id or not workspace_id:
        return

    phrase = _STIPEND_STATUS_PHRASE[new_status]
    body = f"Your internship stipend {phrase}."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "INTERNSHIP",
                "title": title,
                "body": body,
                "related_entity_type": "INTERNSHIP_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()
