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


# Interview lifecycle (database/migrations/030_industry_interviews.sql).
# Scheduling already produces the "interview stage" application-status
# notification when it advances a SHORTLISTED application; these cover the
# events that do NOT move application status -- a reschedule and a
# cancellation -- plus scheduling an interview for an application already
# at INTERVIEW_SCHEDULED (where no status change fires). Routed at the
# APPLICATION entity, not INTERVIEW: the student's interview details render
# inline on /student/applications (there is no student interview route),
# and APPLICATION is the related_entity_type that links there.
_INTERVIEW_EVENT_TITLE: dict[str, str] = {
    "SCHEDULED": "An interview has been scheduled",
    "RESCHEDULED": "Your interview has been rescheduled",
    "CANCELLED": "Your interview has been cancelled",
}

_INTERVIEW_EVENT_PHRASE: dict[str, str] = {
    "SCHEDULED": "An interview has been scheduled",
    "RESCHEDULED": "Your interview time has changed",
    "CANCELLED": "Your scheduled interview has been cancelled",
}


def emit_interview_change(
    *,
    student_id: str,
    application_id: str,
    event: str,
    opportunity_title: str | None,
) -> None:
    """Notify a student that the Industry side scheduled, rescheduled, or
    cancelled an interview for their application. No-op for an unknown
    event.

    Writes exactly one `student_notifications` row via the service-role
    client (the table has no insert policy). `related_entity_type` /
    `related_entity_id` point at the APPLICATION -- interview details render
    inline on /student/applications -- so the frontend can offer a "view"
    link there. Best-effort by contract: a failed write never turns a
    successful scheduling action into an error. The caller invokes this
    exactly once per action, so no dedup check is needed."""
    title = _INTERVIEW_EVENT_TITLE.get(event)
    if title is None or not student_id or not application_id:
        return

    phrase = _INTERVIEW_EVENT_PHRASE[event]
    where = f' for "{opportunity_title}"' if opportunity_title else ""
    body = f"{phrase}{where}. Open your application to see the details."

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


def emit_job_training_completed(
    *,
    student_id: str,
    enrollment_id: str,
    job_title: str | None,
    program_title: str | None,
    outcome: str,
    certificate_number: str | None,
) -> None:
    """Notify a student that the industry verified their Job Training
    (Phase J4). The caller (the industry verify route) invokes this
    EXACTLY ONCE -- only on the call that actually recorded the decision
    (result["_newly_verified"]), never on a repeated/idempotent verify --
    so this never needs its own dedup check.

    Writes exactly one `student_notifications` row via the service-role
    client (the table has no insert policy). type 'JOB_TRAINING' +
    related_entity_type 'JOB_TRAINING_ENROLLMENT' were allowed by migration
    040's CHECK widening; `related_entity_id` is the enrollment so the
    frontend can link to /student/job-training/{enrollment_id}.
    Best-effort: a failed write never turns a successful verification into
    an error. `outcome` is 'PASSED' or 'FAILED' (the completion_status)."""
    if not student_id or not enrollment_id or outcome not in ("PASSED", "FAILED"):
        return

    where = f' for "{job_title or program_title}"' if (job_title or program_title) else ""
    if outcome == "PASSED":
        number = f" ({certificate_number})" if certificate_number else ""
        title = "Job training completed — certificate issued"
        body = f"Your job training{where} is complete. Your certificate{number} is ready to view."
    else:
        title = "Update on your job training"
        body = f"Your job training{where} has been reviewed by the company."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "JOB_TRAINING",
                "title": title,
                "body": body,
                "related_entity_type": "JOB_TRAINING_ENROLLMENT",
                "related_entity_id": enrollment_id,
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


# ============================================================
# Industry-facing producers (industry_notifications,
# database/migrations/055_industry_notifications.sql). Same best-effort,
# service-role, swallow-your-own-errors contract as every function above
# -- a missing notification must never turn a successful apply/withdraw
# into a failure for the STUDENT request that triggered it (these are
# invoked from Student request handlers, the mirror image of the
# Industry-triggered student producers above).
# ============================================================

_NEW_APPLICATION_ENTITY_TYPE: dict[str, str] = {
    "INTERNSHIP": "INTERNSHIP_APPLICATION",
    "JOB": "JOB_APPLICATION",
    "PROJECT": "PROJECT_APPLICATION",
    "WORKSHOP": "WORKSHOP_APPLICATION",
    "TRAINING": "TRAINING_APPLICATION",
}

_KIND_LABEL: dict[str, str] = {
    "INTERNSHIP": "internship",
    "JOB": "job",
    "PROJECT": "project",
    "WORKSHOP": "workshop",
    "TRAINING": "training",
}


def emit_new_application(
    *,
    industry_id: str,
    kind: str,
    related_entity_id: str,
    opportunity_title: str | None,
    student_name: str | None,
) -> None:
    """Notify an Industry account that a student applied to one of its
    postings. `kind` is one of INTERNSHIP/JOB/PROJECT/WORKSHOP.

    `related_entity_id` is the APPLICATION id for INTERNSHIP/JOB (Industry
    already has a per-application detail route,
    /industry/applicants/{id}), and the POSTING id for PROJECT/WORKSHOP
    (there is no per-application detail route there -- the destination is
    that posting's Applicants view). See app.schemas.industry_notification
    for the exact related_entity_type vocabulary.

    Writes exactly one `industry_notifications` row via the service-role
    client (the table has no insert policy). Best-effort: a failed write
    never turns a successful application submission into an error."""
    entity_type = _NEW_APPLICATION_ENTITY_TYPE.get(kind)
    if entity_type is None or not industry_id or not related_entity_id:
        return

    who = student_name or "A student"
    where = f' for "{opportunity_title}"' if opportunity_title else ""
    label = _KIND_LABEL.get(kind, "opportunity")
    body = f"{who} applied to your {label}{where}."

    with contextlib.suppress(Exception):
        get_supabase().table("industry_notifications").insert(
            {
                "industry_id": industry_id,
                "type": "NEW_APPLICATION",
                "title": f"New {label} application",
                "body": body,
                "related_entity_type": entity_type,
                "related_entity_id": related_entity_id,
            }
        ).execute()


def emit_application_withdrawn(
    *,
    industry_id: str,
    kind: str,
    related_entity_id: str,
    opportunity_title: str | None,
    student_name: str | None,
) -> None:
    """Notify an Industry account that a student withdrew their
    application. Same id/entity-type convention as emit_new_application.
    Best-effort, service-role, never fatal to the withdrawal itself."""
    entity_type = _NEW_APPLICATION_ENTITY_TYPE.get(kind)
    if entity_type is None or not industry_id or not related_entity_id:
        return

    who = student_name or "A student"
    where = f' for "{opportunity_title}"' if opportunity_title else ""
    label = _KIND_LABEL.get(kind, "opportunity")
    body = f"{who} withdrew their application{where}."

    with contextlib.suppress(Exception):
        get_supabase().table("industry_notifications").insert(
            {
                "industry_id": industry_id,
                "type": "WITHDRAWAL",
                "title": f"Applicant withdrew ({label})",
                "body": body,
                "related_entity_type": entity_type,
                "related_entity_id": related_entity_id,
            }
        ).execute()


# ---- Workshop / Project status changes -> student (student_notifications,
# widened by 058_student_notifications_workshop_project.sql) ----

_WORKSHOP_STATUS_TITLE: dict[str, str] = {
    "ACCEPTED": "You've been accepted",
    "REJECTED": "Update on your workshop application",
    "COMPLETED": "Workshop completed",
}

_WORKSHOP_STATUS_PHRASE: dict[str, str] = {
    "ACCEPTED": "has been accepted",
    "REJECTED": "was not accepted this time",
    "COMPLETED": "is marked completed",
}


def emit_workshop_status_change(
    *,
    student_id: str,
    workshop_id: str,
    new_status: str,
    workshop_title: str | None,
) -> None:
    """Notify a student that the Industry side moved their Workshop
    application to `new_status`. No-op for APPLIED/WITHDRAWN (student's
    own actions). `related_entity_id` is the workshop id -- links to
    /student/workshops/{id}."""
    title = _WORKSHOP_STATUS_TITLE.get(new_status)
    if title is None or not student_id or not workshop_id:
        return

    phrase = _WORKSHOP_STATUS_PHRASE[new_status]
    where = f' for "{workshop_title}"' if workshop_title else ""
    body = f"Your workshop application{where} {phrase}."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "APPLICATION_STATUS",
                "title": title,
                "body": body,
                "related_entity_type": "WORKSHOP",
                "related_entity_id": workshop_id,
            }
        ).execute()


_PROJECT_STATUS_TITLE: dict[str, str] = {
    "SHORTLISTED": "You've been shortlisted",
    "SELECTED": "You've been selected",
    "REJECTED": "Update on your project application",
    "COMPLETED": "Project completed",
}

_PROJECT_STATUS_PHRASE: dict[str, str] = {
    "SHORTLISTED": "has been shortlisted",
    "SELECTED": "was selected",
    "REJECTED": "was not selected this time",
    "COMPLETED": "is marked completed",
}


def emit_project_status_change(
    *,
    student_id: str,
    project_id: str,
    new_status: str,
    project_title: str | None,
) -> None:
    """Notify a student that the Industry side moved their Project
    application to `new_status`. No-op for a status with no student-facing
    meaning (APPLIED, ACTIVE, WITHDRAWN). `related_entity_id` is the
    project id -- links to /student/industry-projects/{id}."""
    title = _PROJECT_STATUS_TITLE.get(new_status)
    if title is None or not student_id or not project_id:
        return

    phrase = _PROJECT_STATUS_PHRASE[new_status]
    where = f' for "{project_title}"' if project_title else ""
    body = f"Your project application{where} {phrase}."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "APPLICATION_STATUS",
                "title": title,
                "body": body,
                "related_entity_type": "PROJECT",
                "related_entity_id": project_id,
            }
        ).execute()


_TRAINING_STATUS_TITLE: dict[str, str] = {
    "ACCEPTED": "You've been enrolled",
    "REJECTED": "Update on your training application",
    "COMPLETED": "Training completed",
}

_TRAINING_STATUS_PHRASE: dict[str, str] = {
    "ACCEPTED": "has been accepted — you're enrolled",
    "REJECTED": "was not accepted this time",
    "COMPLETED": "is marked completed",
}


def emit_training_status_change(
    *,
    student_id: str,
    training_id: str,
    new_status: str,
    training_title: str | None,
) -> None:
    """Notify a student that the Industry side moved their Training
    application to `new_status`. No-op for APPLIED/WITHDRAWN.
    `related_entity_id` is the training id -- links to
    /student/trainings/{id}."""
    title = _TRAINING_STATUS_TITLE.get(new_status)
    if title is None or not student_id or not training_id:
        return

    phrase = _TRAINING_STATUS_PHRASE[new_status]
    where = f' for "{training_title}"' if training_title else ""
    body = f"Your training application{where} {phrase}."

    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "APPLICATION_STATUS",
                "title": title,
                "body": body,
                "related_entity_type": "TRAINING",
                "related_entity_id": training_id,
            }
        ).execute()


# ============================================================
# Participation Workspace producers (database/migrations/066_participation_notifications.sql).
# Both sides point related_entity_id at the participation_workspaces.id --
# one deep-link target for every event in this domain, never a specific
# assignment/submission/review row (mirrors the WORKSHOP/PROJECT/TRAINING
# convention above of linking at the coarsest useful level).
# ============================================================


def emit_participation_new_assignment(*, student_id: str, workspace_id: str, assignment_title: str) -> None:
    """Notify a student that Industry published a new assignment in their
    workspace. Best-effort, never fatal to the publish action."""
    if not student_id or not workspace_id:
        return
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "PARTICIPATION",
                "title": "New assignment added",
                "body": f'A new assignment, "{assignment_title}", was added to your workspace.',
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


_REVIEW_VERDICT_TITLE_PARTICIPATION: dict[str, str] = {
    "ACCEPTED": "Your submission was accepted",
    "NEEDS_REVISION": "Revision requested",
    "REVIEWED": "Your submission was reviewed",
}


def emit_participation_submission_reviewed(
    *, student_id: str, workspace_id: str, verdict: str, assignment_title: str
) -> None:
    """Notify a student that Industry reviewed one of their submissions."""
    title = _REVIEW_VERDICT_TITLE_PARTICIPATION.get(verdict)
    if title is None or not student_id or not workspace_id:
        return
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "PARTICIPATION",
                "title": title,
                "body": f'Your submission for "{assignment_title}" was reviewed.',
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


def emit_participation_new_feedback(*, student_id: str, workspace_id: str) -> None:
    if not student_id or not workspace_id:
        return
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "PARTICIPATION",
                "title": "New feedback from Industry",
                "body": "Industry left new feedback on your participation workspace.",
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


def emit_participation_new_recommendation(*, student_id: str, workspace_id: str, skill_name: str) -> None:
    if not student_id or not workspace_id:
        return
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "PARTICIPATION",
                "title": "New skill recommendation",
                "body": f'Industry recommended you strengthen "{skill_name}".',
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


def emit_participation_evaluation_finalized(*, student_id: str, workspace_id: str) -> None:
    if not student_id or not workspace_id:
        return
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "PARTICIPATION",
                "title": "Final evaluation completed",
                "body": "Industry finalized your evaluation for this workspace.",
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


def emit_participation_completed(*, student_id: str, workspace_id: str) -> None:
    if not student_id or not workspace_id:
        return
    with contextlib.suppress(Exception):
        get_supabase().table("student_notifications").insert(
            {
                "student_id": student_id,
                "type": "PARTICIPATION",
                "title": "Participation completed",
                "body": "Your participation has been marked completed.",
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()


def emit_participation_submission(
    *, industry_id: str, workspace_id: str, student_name: str | None, assignment_title: str, is_resubmission: bool
) -> None:
    """Notify Industry that a student submitted (or resubmitted) an
    assignment in a participation workspace they own."""
    if not industry_id or not workspace_id:
        return
    who = student_name or "A student"
    verb = "resubmitted" if is_resubmission else "submitted"
    with contextlib.suppress(Exception):
        get_supabase().table("industry_notifications").insert(
            {
                "industry_id": industry_id,
                "type": "NEW_APPLICATION",
                "title": f"Assignment {verb}",
                "body": f'{who} {verb} "{assignment_title}".',
                "related_entity_type": "PARTICIPATION_WORKSPACE",
                "related_entity_id": workspace_id,
            }
        ).execute()
