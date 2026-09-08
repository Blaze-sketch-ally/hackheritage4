"""Business logic for the STUDENT side of Job Training:

  * PROVISIONING an enrollment when a JOB application reaches SELECTED
    (database/migrations/040_job_training.sql), and
  * READING the student's own enrollments and one enrollment's PUBLISHED
    program (job + modules + published items + published assignments +
    skills).

PHASE J3 delivered provisioning + student reads. PHASE J4 adds the END of
the lifecycle (database/migrations/041_job_training_completion.sql):
  * get_student_completion / get_industry_completion -- read-only summary
  * get_student_certificate                          -- read-only
  * verify_completion                                -- the industry's
    explicit sign-off: records the completion (PASSED / FAILED), issues
    the certificate on PASS (one per completion, ever, server-generated
    AIC-JOB-{YYYY}-... number, frozen snapshot), and moves the enrollment
    ACTIVE -> COMPLETED. NEVER automatic -- there is no "requirements met"
    computation, and consuming modules never completes anything.

This module NEVER writes job_programs / job_program_modules /
job_program_items / job_program_skills / job_program_assignments /
applications / student_skills. It writes exactly: a job_training_enrollments
row (provisioning), a job_training_completions row + a
job_training_certificates row (verify), and the enrollment_status cache on
the ACTIVE -> COMPLETED transition. No submission / review / progress /
stipend table exists for Job Training.

Client handling mirrors internship_workspace_service:
  * The live path (application_service.update_status) and the industry
    self-heal endpoint pass a *user-scoped* client
    (app.core.security.build_user_client). The industry is the caller, and
    job_training_enrollments' INSERT policy is
      with check (auth.uid() = industry_id AND public.is_industry(auth.uid()))
    -- and industry_id is DERIVED from the application by
    set_job_training_enrollment_derived_ids (BEFORE INSERT) -- so a
    user-scoped insert by the owning industry is RLS-legal, the same
    construction as internship workspace provisioning.
  * The explicit operator backfill script passes the *service-role*
    client.
  * The student read functions ALWAYS use a user-scoped client. RLS
    (040_job_training.sql) is the real boundary:
      - "Students can view their own job training enrollment"
        (auth.uid() = student_id)
      - "Students can view published job programs for their enrollment"
        (public.student_can_access_job_program(id)) -- which requires a
        non-REVOKED enrollment AND program.status = 'PUBLISHED', and
        DELIBERATELY never looks at jobs.status (a CLOSED / ARCHIVED job
        does not revoke a selected candidate's access).

The J1 database trigger set_job_training_enrollment_derived_ids is the
FINAL gate: it RAISES unless applications.opportunity_type = 'JOB' AND
applications.status = 'SELECTED', and derives student_id / industry_id /
job_id from the application -- so an internship application, a
non-selected job, or a client-forged id can never produce an enrollment,
even via a direct insert. The checks here exist to return a clean typed
result instead of a raw 500 / DB error.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from postgrest.exceptions import APIError
from supabase import Client


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()

ProvisionOutcome = Literal[
    "CREATED",
    "ALREADY_EXISTS",
    "SKIPPED_NO_PROGRAM",
    "SKIPPED_NOT_SELECTED",
    "SKIPPED_NOT_JOB",
    "REVOKED_BLOCKED",
]

_ENROLLMENT_COLUMNS = (
    "id, application_id, job_id, student_id, industry_id, enrollment_status, "
    "completed_at, revoked_at, revoke_reason, created_at, updated_at"
)
_REVOKED = "REVOKED"

_STUDENT_ITEM_COLUMNS = (
    "id, title, item_type, content_url, content_text, order_index, is_published"
)
# NOTE: is_published is fetched so this layer can double-filter, but it is
# NOT surfaced to the student -- they only ever see published content.
_STUDENT_ASSIGNMENT_COLUMNS = (
    "id, title, description, instructions, assignment_type, is_required, "
    "order_index, due_offset_days, submission_kind, repo_required, "
    "live_url_expected, max_score, linked_skill_id, is_published"
)


@dataclass(frozen=True)
class ProvisionResult:
    """The outcome of one provision_for_selection() call. `enrollment` is
    the enrollment row for CREATED / ALREADY_EXISTS / REVOKED_BLOCKED, else
    None. Every ineligible-but-understood case is a SKIPPED_* / REVOKED_*
    outcome -- never an exception."""

    outcome: ProvisionOutcome
    detail: str
    application_id: str
    enrollment: dict | None = None

    @property
    def created(self) -> bool:
        return self.outcome == "CREATED"


class ProvisionError(Exception):
    """Base for genuinely unexpected provisioning failures (distinct from
    the clean SKIPPED_* / REVOKED_BLOCKED no-op outcomes)."""


class ApplicationNotFoundError(ProvisionError):
    """The referenced application row does not exist / is not visible to
    the caller."""


class ProvisionRejectedError(ProvisionError):
    """The database rejected a well-formed enrollment insert (42501) -- the
    application state changed during provisioning (no longer SELECTED, or
    no longer a JOB). The caller may retry."""


def _maybe_row(response) -> dict | None:
    return response.data if response is not None else None


def _read_enrollment(client: Client, application_id: str) -> dict | None:
    return _maybe_row(
        client.table("job_training_enrollments")
        .select(_ENROLLMENT_COLUMNS)
        .eq("application_id", application_id)
        .maybe_single()
        .execute()
    )


def _existing_result(enrollment: dict, application_id: str) -> ProvisionResult:
    if enrollment.get("enrollment_status") == _REVOKED:
        return ProvisionResult(
            "REVOKED_BLOCKED",
            "This application's job training enrollment was revoked -- it is not "
            "re-created automatically. An operator must restore it deliberately.",
            application_id,
            enrollment=enrollment,
        )
    return ProvisionResult(
        "ALREADY_EXISTS",
        "A job training enrollment already exists for this application.",
        application_id,
        enrollment=enrollment,
    )


def provision_for_selection(client: Client, application_id: str) -> ProvisionResult:
    """Ensure exactly one job_training_enrollment exists for
    `application_id` IF the application is SELECTED for a JOB whose
    industry has already authored a job_program. Idempotent and safe to
    call repeatedly -- an already-provisioned application comes back as
    ALREADY_EXISTS with the existing row, never a duplicate and never an
    error; a REVOKED enrollment comes back as REVOKED_BLOCKED and is NOT
    silently resurrected.

    Raises ProvisionError only for genuinely unexpected states
    (application not visible, or the DB rejecting a well-formed insert).
    Every ineligible-but-understood case is a SKIPPED_* / REVOKED_BLOCKED
    ProvisionResult.

    Does NOT touch applications.status, jobs.status, or any job_program
    table.
    """
    application = _maybe_row(
        client.table("applications")
        .select("id, job_id, opportunity_type, status")
        .eq("id", application_id)
        .maybe_single()
        .execute()
    )
    if application is None:
        raise ApplicationNotFoundError(application_id)

    if application.get("opportunity_type") != "JOB" or not application.get("job_id"):
        return ProvisionResult(
            "SKIPPED_NOT_JOB",
            "Only job applications get a job training enrollment "
            "(internships use the Internship Workspace).",
            application_id,
        )

    if application.get("status") != "SELECTED":
        return ProvisionResult(
            "SKIPPED_NOT_SELECTED",
            f"Application status is {application.get('status')!r}, not 'SELECTED'.",
            application_id,
        )

    job_id = application["job_id"]

    program = _maybe_row(
        client.table("job_programs")
        .select("id, status")
        .eq("job_id", job_id)
        .maybe_single()
        .execute()
    )
    if program is None:
        return ProvisionResult(
            "SKIPPED_NO_PROGRAM",
            "The job has no job training program yet -- provisioning is deferred "
            "until the industry creates one. Re-run afterwards "
            "(POST /api/v1/applications/{id}/provision-job-training, or the "
            "backfill script).",
            application_id,
        )

    existing = _read_enrollment(client, application_id)
    if existing is not None:
        return _existing_result(existing, application_id)

    try:
        client.table("job_training_enrollments").insert(
            {"application_id": application_id}
        ).execute()
    except APIError as exc:
        if exc.code == "23505":
            # UNIQUE(application_id): a concurrent provision beat us. Not an
            # error -- report the row that now exists.
            racer = _read_enrollment(client, application_id)
            if racer is not None:
                return _existing_result(racer, application_id)
            raise ProvisionError(
                "Job training enrollment insert hit a uniqueness conflict but the "
                "row could not be read back."
            ) from exc
        if exc.code == "42501":
            raise ProvisionRejectedError(
                "The database rejected the job training enrollment insert -- the "
                "application state changed during provisioning (no longer a SELECTED "
                "job)."
            ) from exc
        raise

    created = _read_enrollment(client, application_id)
    if created is None:
        raise ProvisionError(
            "Job training enrollment could not be read back after insert."
        )
    return ProvisionResult(
        "CREATED", "Job training enrollment provisioned.", application_id, enrollment=created
    )


# ============================================================
# student reads -- always user-scoped; RLS is the boundary
# ============================================================


def _enrollment_summary(enrollment: dict, program: dict | None, job: dict | None) -> dict:
    return {
        "enrollment_id": enrollment["id"],
        "application_id": enrollment["application_id"],
        "job_id": enrollment["job_id"],
        "job_title": job.get("title") if job else None,
        "program_id": program.get("id") if program else None,
        "program_title": program.get("title") if program else None,
        "program_status": program.get("status") if program else None,
        "enrollment_status": enrollment["enrollment_status"],
        "created_at": enrollment.get("created_at"),
        "completed_at": enrollment.get("completed_at"),
    }


def list_student_enrollments(client: Client, student_id: str) -> list[dict]:
    """Every non-REVOKED job training enrollment belonging to the
    authenticated student, newest first. Program title / status are filled
    only when the student can actually read the program (RLS
    student_can_access_job_program -> PUBLISHED + non-revoked enrollment),
    so a still-DRAFT program shows program_* as null. Job title is
    best-effort (a CLOSED / ARCHIVED job is not readable to the student,
    but that never affects access)."""
    enrollments = (
        client.table("job_training_enrollments")
        .select(_ENROLLMENT_COLUMNS)
        .eq("student_id", student_id)
        .neq("enrollment_status", _REVOKED)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    if not enrollments:
        return []

    job_ids = sorted({e["job_id"] for e in enrollments})
    programs = {
        row["job_id"]: row
        for row in (
            client.table("job_programs")
            .select("id, job_id, title, status")
            .in_("job_id", job_ids)
            .execute()
            .data
            or []
        )
    }
    jobs = {
        row["id"]: row
        for row in (
            client.table("jobs")
            .select("id, title")
            .in_("id", job_ids)
            .execute()
            .data
            or []
        )
    }
    return [
        _enrollment_summary(e, programs.get(e["job_id"]), jobs.get(e["job_id"]))
        for e in enrollments
    ]


def _shape_student_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "title": item["title"],
        "item_type": item["item_type"],
        "content_url": item.get("content_url"),
        "content_text": item.get("content_text"),
        "order_index": item.get("order_index") or 0,
    }


def _shape_student_assignment(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "instructions": row.get("instructions"),
        "assignment_type": row["assignment_type"],
        "is_required": bool(row.get("is_required")),
        "order_index": row.get("order_index") or 0,
        "due_offset_days": row.get("due_offset_days"),
        "submission_kind": row.get("submission_kind") or "LINK",
        "repo_required": bool(row.get("repo_required")),
        "live_url_expected": bool(row.get("live_url_expected")),
        "max_score": float(row["max_score"]) if row.get("max_score") is not None else None,
        "linked_skill_id": row.get("linked_skill_id"),
    }


def get_student_program(
    client: Client, student_id: str, enrollment_id: str
) -> dict | None:
    """The PUBLISHED job training program behind one of the student's own
    enrollments: program metadata + published modules (with their
    published items and published assignments) + program skills.

    Returns None -- the route turns it into a 404 -- for EVERY
    inaccessible case, indistinguishably: the enrollment is not the
    student's, the enrollment is REVOKED, no program exists, or the
    program is not PUBLISHED. Never reveals which.
    """
    enrollment = _maybe_row(
        client.table("job_training_enrollments")
        .select(_ENROLLMENT_COLUMNS)
        .eq("id", enrollment_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    if enrollment is None or enrollment.get("enrollment_status") == _REVOKED:
        return None

    job_id = enrollment["job_id"]

    # RLS "Students can view published job programs for their enrollment"
    # (student_can_access_job_program) returns a row ONLY when the program
    # is PUBLISHED and this student's enrollment is non-revoked -- and it
    # never checks jobs.status.
    program = _maybe_row(
        client.table("job_programs")
        .select("id, job_id, title, summary, estimated_weeks, status, published_at")
        .eq("job_id", job_id)
        .maybe_single()
        .execute()
    )
    if program is None:
        return None

    program_id = program["id"]

    modules_raw = (
        client.table("job_program_modules")
        .select(
            "id, title, description, order_index, "
            f"job_program_items({_STUDENT_ITEM_COLUMNS}), "
            f"job_program_assignments({_STUDENT_ASSIGNMENT_COLUMNS})"
        )
        .eq("program_id", program_id)
        .order("order_index")
        .execute()
        .data
        or []
    )
    modules: list[dict] = []
    for module in sorted(modules_raw, key=lambda m: m.get("order_index") or 0):
        items = sorted(
            (
                _shape_student_item(it)
                for it in (module.get("job_program_items") or [])
                if it.get("is_published")
            ),
            key=lambda it: it["order_index"],
        )
        assignments = sorted(
            (
                _shape_student_assignment(a)
                for a in (module.get("job_program_assignments") or [])
                if a.get("is_published")
            ),
            key=lambda a: a["order_index"],
        )
        modules.append(
            {
                "id": module["id"],
                "title": module["title"],
                "description": module.get("description"),
                "order_index": module.get("order_index") or 0,
                "items": items,
                "assignments": assignments,
            }
        )

    skills_raw = (
        client.table("job_program_skills")
        .select("skill_id, requirement, skill:skills(name)")
        .eq("program_id", program_id)
        .execute()
        .data
        or []
    )
    skills = [
        {
            "skill_id": s["skill_id"],
            "skill_name": (s.get("skill") or {}).get("name", ""),
            "requirement": s["requirement"],
        }
        for s in skills_raw
    ]
    skills.sort(key=lambda s: (s["requirement"] != "REQUIRED", s["skill_name"].lower()))

    job = _maybe_row(
        client.table("jobs").select("id, title").eq("id", job_id).maybe_single().execute()
    )

    return {
        "enrollment": _enrollment_summary(enrollment, program, job),
        "program": {
            "id": program["id"],
            "job_id": program["job_id"],
            "title": program["title"],
            "summary": program.get("summary"),
            "estimated_weeks": program.get("estimated_weeks"),
            "status": program["status"],
            "published_at": program.get("published_at"),
        },
        "modules": modules,
        "skills": skills,
    }


# ============================================================
# PHASE J4 -- completion + certificate
# ============================================================
# job_training_completions / job_training_certificates (041) are ONLY ever
# written here, and ONLY by the industry that owns the enrollment (the
# user-scoped client is the caller; RLS + the DB triggers are the real
# boundary). Nothing here stores a progress percentage -- there is none.
# The certificate's number is minted by the DB trigger
# (set_job_training_certificate_derived_ids); it is never sent from here.
#
# NOTHING here reads or writes student_skills. A verified completion and an
# issued certificate are job-training EVIDENCE only.

_COMPLETION_COLUMNS = (
    "id, enrollment_id, student_id, industry_id, job_id, program_id, "
    "completion_status, verified_by, verified_at, verification_notes, "
    "completed_at, created_at, updated_at"
)
_CERTIFICATE_COLUMNS = (
    "id, completion_id, enrollment_id, student_id, industry_id, job_id, program_id, "
    "certificate_number, details, issued_at, pdf_url, revoked_at, revoke_reason, "
    "created_at, updated_at"
)

# PASSED / FAILED are the two decided states; PENDING is the (rarely
# persisted) pre-decision state. A decided completion is idempotent-final.
_DECIDED_STATES: frozenset[str] = frozenset({"PASSED", "FAILED"})


class CompletionNotFoundError(Exception):
    """No job_training_completion exists yet for this enrollment."""


class EnrollmentNotFoundError(Exception):
    """The enrollment does not exist or is not visible to the caller."""


class EnrollmentRevokedError(Exception):
    """The enrollment is REVOKED -- it can never be completed."""


class ProgramMissingError(Exception):
    """The job has no authored job_program -- there is nothing to complete."""


class CompletionRejectedError(Exception):
    """The database rejected a well-formed completion / certificate write
    (42501) -- the caller does not own this enrollment, or the state
    changed underneath us."""


def _read_completion(client: Client, enrollment_id: str) -> dict | None:
    return _maybe_row(
        client.table("job_training_completions")
        .select(_COMPLETION_COLUMNS)
        .eq("enrollment_id", enrollment_id)
        .maybe_single()
        .execute()
    )


def _read_certificate(client: Client, completion_id: str) -> dict | None:
    return _maybe_row(
        client.table("job_training_certificates")
        .select(_CERTIFICATE_COLUMNS)
        .eq("completion_id", completion_id)
        .maybe_single()
        .execute()
    )


def _shape_certificate(row: dict) -> dict:
    details = row.get("details") or {}
    return {
        "certificate_number": row["certificate_number"],
        "student_name": details.get("student_name"),
        "company_name": details.get("company_name"),
        "job_title": details.get("job_title"),
        "program_title": details.get("program_title"),
        "issued_at": row.get("issued_at"),
        "revoked": row.get("revoked_at") is not None,
    }


def _build_completion_summary(
    enrollment_id: str,
    completion: dict | None,
    certificate: dict | None,
    *,
    newly_verified: bool = False,
    student_id: str | None = None,
) -> dict:
    verified = (
        completion is not None and completion.get("completion_status") in _DECIDED_STATES
    )
    result = {
        "enrollment_id": enrollment_id,
        "completion_status": (completion or {}).get("completion_status", "PENDING"),
        "industry_verified": verified,
        "verified_at": (completion or {}).get("verified_at"),
        "verification_notes": (completion or {}).get("verification_notes"),
        "completed_at": (completion or {}).get("completed_at"),
        "certificate": _shape_certificate(certificate) if certificate else None,
    }
    # Internal-only signals the verify route uses for the (best-effort,
    # exactly-once) student notification -- the response schema drops them.
    if newly_verified:
        result["_newly_verified"] = True
        result["_student_id"] = student_id
        result["_outcome"] = result["completion_status"]
    return result


# ---- student reads ----


def get_student_completion(
    client: Client, student_id: str, enrollment_id: str
) -> dict | None:
    """The completion summary for the student's own enrollment. None -> the
    route 404s. A REVOKED enrollment and one that is not the student's are
    both None, indistinguishably."""
    enrollment = _maybe_row(
        client.table("job_training_enrollments")
        .select("id, student_id, enrollment_status")
        .eq("id", enrollment_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    if enrollment is None or enrollment.get("enrollment_status") == _REVOKED:
        return None

    completion = _read_completion(client, enrollment_id)
    certificate = _read_certificate(client, completion["id"]) if completion else None
    return _build_completion_summary(enrollment_id, completion, certificate)


def get_student_certificate(
    client: Client, student_id: str, enrollment_id: str
) -> dict | None:
    """The student's own certificate for one enrollment, or None (route
    404s). Requires a non-revoked enrollment, a PASSED completion, and an
    issued certificate."""
    summary = get_student_completion(client, student_id, enrollment_id)
    if summary is None or summary.get("certificate") is None:
        return None
    return summary["certificate"]


# ---- industry reads ----


def get_industry_completion(
    client: Client, industry_id: str, enrollment_id: str
) -> dict | None:
    """The completion summary for one of the industry's own enrollments.
    None -> the route 404s (a foreign / unknown enrollment is
    indistinguishable from one with no completion record)."""
    enrollment = _maybe_row(
        client.table("job_training_enrollments")
        .select("id, industry_id, enrollment_status")
        .eq("id", enrollment_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    if enrollment is None:
        return None

    completion = _read_completion(client, enrollment_id)
    certificate = _read_certificate(client, completion["id"]) if completion else None
    return _build_completion_summary(enrollment_id, completion, certificate)


# ---- industry verify + issue ----


def _applicant_name(client: Client, application_id: str | None) -> str | None:
    """Best-effort, via the application_applicant_names RPC (036) --
    SECURITY DEFINER, scoped to the caller's own postings. A failure never
    blocks verification; the snapshot just carries a null name."""
    if not application_id:
        return None
    try:
        response = client.rpc(
            "application_applicant_names", {"application_ids": [application_id]}
        ).execute()
        rows = response.data or []
        return rows[0].get("student_name") if rows else None
    except Exception:  # noqa: BLE001 -- the name is optional enrichment, never fatal
        return None


def _company_name(client: Client, industry_id: str) -> str | None:
    row = _maybe_row(
        client.table("industry_profiles")
        .select("company_name")
        .eq("id", industry_id)
        .maybe_single()
        .execute()
    )
    return row.get("company_name") if row else None


def _job_and_program_titles(
    client: Client, job_id: str, program_id: str
) -> tuple[str | None, str | None]:
    job = _maybe_row(
        client.table("jobs").select("title").eq("id", job_id).maybe_single().execute()
    )
    program = _maybe_row(
        client.table("job_programs")
        .select("title")
        .eq("id", program_id)
        .maybe_single()
        .execute()
    )
    return (
        job.get("title") if job else None,
        program.get("title") if program else None,
    )


def _build_certificate_snapshot(client: Client, enrollment: dict, completion: dict) -> dict:
    """Captured ONCE, at issuance -- never re-derived from a live join
    afterwards (public.verify_job_training_certificate prefers this exact
    snapshot). Only the fields the public verifier + the student/industry
    certificate view need; no email, no UUIDs."""
    job_title, program_title = _job_and_program_titles(
        client, completion["job_id"], completion["program_id"]
    )
    return {
        "student_name": _applicant_name(client, enrollment.get("application_id")),
        "company_name": _company_name(client, completion["industry_id"]),
        "job_title": job_title,
        "program_title": program_title,
        "outcome": "PASS",
    }


def _get_or_create_completion(
    client: Client, enrollment_id: str, outcome: str, notes: str | None
) -> dict:
    """Idempotent via UNIQUE(enrollment_id). If the completion already
    exists and is DECIDED, it is returned UNCHANGED (a re-verify never
    flips PASSED <-> FAILED). A still-PENDING completion is transitioned.
    Otherwise a new row is created directly in the decided state -- the DB
    trigger set_job_training_completion_verifier stamps verified_by /
    verified_at / completed_at, and set_job_training_completion_derived_ids
    enforces every eligibility rule."""
    status_value = "PASSED" if outcome == "PASS" else "FAILED"

    existing = _read_completion(client, enrollment_id)
    if existing is not None:
        if existing["completion_status"] in _DECIDED_STATES:
            return existing
        payload: dict = {"completion_status": status_value}
        if notes and notes.strip():
            payload["verification_notes"] = notes.strip()
        try:
            (
                client.table("job_training_completions")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
        except APIError as exc:
            if exc.code == "42501":
                raise CompletionRejectedError(
                    "The database rejected the completion -- you may not own this enrollment."
                ) from exc
            raise
        updated = _read_completion(client, enrollment_id)
        if updated is None:  # pragma: no cover
            raise RuntimeError("job_training_completions could not be read back after update.")
        return updated

    payload = {"enrollment_id": enrollment_id, "completion_status": status_value}
    if notes and notes.strip():
        payload["verification_notes"] = notes.strip()
    try:
        client.table("job_training_completions").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            row = _read_completion(client, enrollment_id)
            if row is not None:
                return row
            raise RuntimeError("job_training_completions 23505 but row not readable.") from exc
        if exc.code == "42501":
            raise CompletionRejectedError(
                "The database rejected the completion -- you may not own this enrollment, "
                "or the enrollment/application is no longer eligible."
            ) from exc
        raise
    created = _read_completion(client, enrollment_id)
    if created is None:  # pragma: no cover
        raise RuntimeError("job_training_completions could not be read back after insert.")
    return created


def _get_or_create_certificate(client: Client, completion: dict, enrollment: dict) -> dict:
    """UNIQUE(completion_id) is the idempotency guarantee -- one
    certificate per completion, ever. certificate_number is never sent; the
    DB trigger (set_job_training_certificate_derived_ids) mints it and
    requires completion_status = 'PASSED'."""
    payload = {
        "completion_id": completion["id"],
        "details": _build_certificate_snapshot(client, enrollment, completion),
    }
    try:
        client.table("job_training_certificates").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            pass  # already issued -- fall through to the read-back
        elif exc.code == "42501":
            raise CompletionRejectedError(
                "The database rejected the certificate -- you may not own this enrollment."
            ) from exc
        else:
            raise
    existing = _read_certificate(client, completion["id"])
    if existing is None:  # pragma: no cover
        raise RuntimeError("job_training_certificates could not be read back after insert.")
    return existing


def verify_completion(
    client: Client,
    industry_id: str,
    enrollment_id: str,
    outcome: str,
    notes: str | None = None,
) -> dict:
    """The industry explicitly signs off a student's job training:
      1. records the completion (PASSED / FAILED) -- one row per
         enrollment, ever
      2. on PASS, issues the certificate -- one row per completion, ever,
         with a server-generated AIC-JOB number and a frozen snapshot
      3. moves the enrollment ACTIVE -> COMPLETED (best-effort cache).

    IDEMPOTENT: a re-verify of an already-DECIDED completion returns the
    existing completion + certificate UNCHANGED (it never flips
    PASSED / FAILED, never issues a second certificate). Raises
    EnrollmentNotFoundError / EnrollmentRevokedError / ProgramMissingError
    for a bad request; CompletionRejectedError for a DB-level rejection.
    NEVER touches applications.status, jobs.status, student_skills, or any
    job_program table.
    """
    enrollment = _maybe_row(
        client.table("job_training_enrollments")
        .select("id, application_id, student_id, industry_id, job_id, enrollment_status")
        .eq("id", enrollment_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    if enrollment is None:
        raise EnrollmentNotFoundError(enrollment_id)
    if enrollment.get("enrollment_status") == _REVOKED:
        raise EnrollmentRevokedError(enrollment_id)

    # Fast, friendly pre-check (the DB trigger is the real gate).
    program = _maybe_row(
        client.table("job_programs")
        .select("id")
        .eq("job_id", enrollment["job_id"])
        .maybe_single()
        .execute()
    )
    if program is None:
        raise ProgramMissingError(enrollment["job_id"])

    existing_completion = _read_completion(client, enrollment_id)
    already_decided = (
        existing_completion is not None
        and existing_completion["completion_status"] in _DECIDED_STATES
    )

    completion = _get_or_create_completion(client, enrollment_id, outcome, notes)

    certificate = None
    if completion["completion_status"] == "PASSED":
        certificate = _get_or_create_certificate(client, completion, enrollment)

    # Enrollment lifecycle: any decided completion ends the engagement.
    # ACTIVE -> COMPLETED. enforce_job_training_enrollment_transitions (040)
    # allows this for an industry caller; a student caller could never do
    # it. Best-effort: the completion + certificate are already recorded.
    if enrollment["enrollment_status"] == "ACTIVE":
        try:
            (
                client.table("job_training_enrollments")
                .update({"enrollment_status": "COMPLETED", "completed_at": _now_iso()})
                .eq("id", enrollment_id)
                .execute()
            )
        except APIError:
            pass

    return _build_completion_summary(
        enrollment_id,
        completion,
        certificate,
        newly_verified=not already_decided,
        student_id=enrollment["student_id"],
    )
