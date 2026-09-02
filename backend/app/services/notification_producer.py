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
