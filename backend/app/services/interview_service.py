"""Business logic for Industry interview scheduling (`interviews`,
database/migrations/030_industry_interviews.sql).

Same shape as application_service / industry_collaboration_service: every
function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) and RLS is the real access-control
boundary. Nothing here uses service_role.

Ownership: `interviews`' RLS scopes every read/write to
`auth.uid() = industry_id AND public.is_industry(auth.uid())`. On top of
that, every function here also filters explicitly by `industry_id`
(passed in as current_user.id) -- defence in depth, matching every other
service module.

`industry_id` / `student_id` on a row are derived by the
`set_interview_derived_ids` BEFORE INSERT trigger from the referenced
application; they are never client-supplied, and the
`prevent_interview_identity_change` trigger blocks any later change to
`application_id` / `industry_id` / `student_id`. This module reinforces
that by only ever writing the schedulable columns.

Lifecycle: SCHEDULED -> COMPLETED, SCHEDULED -> CANCELLED. Both terminal.
Rescheduling is an edit (`reschedule_interview`) of a still-SCHEDULED row,
not a status.

Eligibility: an interview can only be created for an application the
caller owns that is at the SHORTLISTED or INTERVIEW_SCHEDULED stage. When
the application is still SHORTLISTED, scheduling also advances it to
INTERVIEW_SCHEDULED through the existing, already-tested
application_service.update_status transition -- this module never
reimplements the application status pipeline, it calls it.
"""

import contextlib
from datetime import UTC, datetime

from supabase import Client

from app.services import application_service

# The schedulable columns -- the only ones a create/reschedule payload may
# touch. application_id is set at create time only; industry_id/student_id
# are trigger-derived; status moves through the lifecycle endpoints.
_EDITABLE_COLUMNS = frozenset({"scheduled_at", "duration_minutes", "mode", "location", "notes"})

_ELIGIBLE_APPLICATION_STATUSES = frozenset({"SHORTLISTED", "INTERVIEW_SCHEDULED"})

_COMPLETE_FROM = frozenset({"SCHEDULED"})
_CANCEL_FROM = frozenset({"SCHEDULED"})

_SELECT = (
    "id, application_id, industry_id, student_id, scheduled_at, duration_minutes, "
    "mode, location, notes, status, created_at, updated_at, "
    "application:applications(opportunity_type, "
    "internship:internships(id, title, status), job:jobs(id, title, status))"
)


class IneligibleApplicationError(Exception):
    """The application is not one the caller can schedule an interview for
    -- either it isn't owned by them / doesn't exist, or it isn't at the
    SHORTLISTED / INTERVIEW_SCHEDULED stage."""


class InvalidInterviewTimeError(Exception):
    """`scheduled_at` is not a usable interview time (e.g. in the past)."""


class SchedulingConflictError(Exception):
    """The requested slot clashes -- the application already has a live
    interview, or the time window overlaps another SCHEDULED interview of
    the caller's."""


class InvalidStatusTransitionError(Exception):
    """The requested lifecycle action isn't valid from the interview's
    current status (e.g. completing an already-cancelled interview)."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an interview from {current} to {target}.")


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value) -> datetime:
    """Coerce an incoming scheduled_at (datetime or ISO string) to an
    aware UTC datetime."""
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _shape(row: dict) -> dict:
    """Collapse the nested application -> internship/job embed into a flat
    `opportunity` + `opportunity_type`, mirroring application_service._shape."""
    application = row.pop("application", None) or {}
    internship = application.get("internship")
    job = application.get("job")
    picked = internship or job
    row["opportunity"] = (
        {"id": picked["id"], "title": picked["title"], "status": picked["status"]}
        if picked
        else None
    )
    row["opportunity_type"] = application.get("opportunity_type")
    return row


def list_interviews(
    client: Client,
    industry_id: str,
    *,
    status: str | None = None,
    application_id: str | None = None,
    upcoming: bool | None = None,
) -> list[dict]:
    """The caller's own interviews, soonest first. Every filter optional
    and additive. `upcoming=True` limits to SCHEDULED interviews whose
    time has not passed."""
    query = client.table("interviews").select(_SELECT).eq("industry_id", industry_id)
    if status:
        query = query.eq("status", status)
    if application_id:
        query = query.eq("application_id", application_id)
    if upcoming:
        query = query.eq("status", "SCHEDULED").gte("scheduled_at", _now().isoformat())
    response = query.order("scheduled_at", desc=False).execute()
    return [_shape(row) for row in (response.data or [])]


def get_interview(client: Client, industry_id: str, interview_id: str) -> dict | None:
    """One of the caller's own interviews, or None -- callers turn None
    into a 404, so another Industry account's interview is
    indistinguishable from one that doesn't exist."""
    response = (
        client.table("interviews")
        .select(_SELECT)
        .eq("id", interview_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape(dict(row)) if row else None


def _live_interviews_for_conflict(
    client: Client, industry_id: str, *, exclude_id: str | None = None
) -> list[dict]:
    query = (
        client.table("interviews")
        .select("id, scheduled_at, duration_minutes")
        .eq("industry_id", industry_id)
        .eq("status", "SCHEDULED")
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    return list(query.execute().data or [])


def _overlaps(start: datetime, duration_minutes: int, others: list[dict]) -> bool:
    end_min = start.timestamp() / 60 + duration_minutes
    start_min = start.timestamp() / 60
    for other in others:
        try:
            o_start = _parse_dt(other["scheduled_at"]).timestamp() / 60
        except (ValueError, KeyError, TypeError):
            continue
        o_end = o_start + (other.get("duration_minutes") or 30)
        if start_min < o_end and o_start < end_min:
            return True
    return False


def create_interview(client: Client, industry_id: str, data: dict) -> dict:
    """Schedule an interview for one of the caller's own SHORTLISTED /
    INTERVIEW_SCHEDULED applications. Raises IneligibleApplicationError,
    InvalidInterviewTimeError, or SchedulingConflictError before writing
    anything. On success, if the application was still SHORTLISTED it is
    advanced to INTERVIEW_SCHEDULED via the existing application pipeline.
    """
    application_id = str(data["application_id"])

    application = application_service.get_application(client, industry_id, application_id)
    if application is None:
        raise IneligibleApplicationError(
            "That application does not exist or is not for one of your postings."
        )
    if application["status"] not in _ELIGIBLE_APPLICATION_STATUSES:
        raise IneligibleApplicationError(
            "An interview can only be scheduled for a shortlisted candidate."
        )

    scheduled_at = _parse_dt(data["scheduled_at"])
    if scheduled_at <= _now():
        raise InvalidInterviewTimeError("The interview time must be in the future.")

    duration = int(data.get("duration_minutes") or 30)

    existing_for_app = list_interviews(
        client, industry_id, status="SCHEDULED", application_id=application_id
    )
    if existing_for_app:
        raise SchedulingConflictError("This application already has a scheduled interview.")

    if _overlaps(scheduled_at, duration, _live_interviews_for_conflict(client, industry_id)):
        raise SchedulingConflictError(
            "This slot overlaps another interview you already have scheduled."
        )

    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    payload["application_id"] = application_id
    payload["scheduled_at"] = scheduled_at.isoformat()

    try:
        response = client.table("interviews").insert(payload).execute()
    except Exception as exc:
        raise IneligibleApplicationError(
            "This interview could not be scheduled for that application."
        ) from exc
    new_id = response.data[0]["id"]

    # Advancing the application to INTERVIEW_SCHEDULED is best-effort -- the
    # interview row already exists, and the recruiter can still move the
    # application by hand if this fails.
    if application["status"] == "SHORTLISTED":
        with contextlib.suppress(Exception):
            application_service.update_status(
                client, industry_id, application_id, "INTERVIEW_SCHEDULED"
            )

    row = get_interview(client, industry_id, new_id)
    if row is None:
        raise RuntimeError("interview row could not be read back after create.")
    return row


def reschedule_interview(
    client: Client, industry_id: str, interview_id: str, data: dict
) -> dict | None:
    """Edit a still-SCHEDULED interview (time, duration, mode, location,
    notes). Rejects any change once COMPLETED/CANCELLED. Re-runs the
    future-time and overlap checks when the time or duration changes."""
    existing = get_interview(client, industry_id, interview_id)
    if existing is None:
        return None
    if existing["status"] != "SCHEDULED":
        raise InvalidStatusTransitionError(existing["status"], "SCHEDULED")

    # scheduled_at / duration_minutes / mode are non-nullable columns -- a
    # `null` there means "not being changed" and is dropped. location /
    # notes are nullable, so an explicit `null` there clears the field.
    nullable = {"location", "notes"}
    payload = {
        k: v
        for k, v in data.items()
        if k in _EDITABLE_COLUMNS and (v is not None or k in nullable)
    }
    if not payload:
        return existing

    new_start = _parse_dt(payload["scheduled_at"]) if "scheduled_at" in payload else _parse_dt(
        existing["scheduled_at"]
    )
    new_duration = int(payload.get("duration_minutes") or existing["duration_minutes"])

    if "scheduled_at" in payload:
        if new_start <= _now():
            raise InvalidInterviewTimeError("The interview time must be in the future.")
        payload["scheduled_at"] = new_start.isoformat()

    if ("scheduled_at" in payload or "duration_minutes" in payload) and _overlaps(
        new_start,
        new_duration,
        _live_interviews_for_conflict(client, industry_id, exclude_id=interview_id),
    ):
        raise SchedulingConflictError(
            "This slot overlaps another interview you already have scheduled."
        )

    (
        client.table("interviews")
        .update(payload)
        .eq("id", interview_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_interview(client, industry_id, interview_id)


def _transition(
    client: Client,
    industry_id: str,
    interview_id: str,
    target: str,
    allowed_from: frozenset[str],
) -> dict | None:
    existing = get_interview(client, industry_id, interview_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("interviews")
        .update({"status": target})
        .eq("id", interview_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_interview(client, industry_id, interview_id)


def complete_interview(client: Client, industry_id: str, interview_id: str) -> dict | None:
    """SCHEDULED -> COMPLETED."""
    return _transition(client, industry_id, interview_id, "COMPLETED", _COMPLETE_FROM)


def cancel_interview(client: Client, industry_id: str, interview_id: str) -> dict | None:
    """SCHEDULED -> CANCELLED. The underlying application's status is left
    untouched -- whether to re-open, reject, or select the candidate after
    a cancelled interview is a recruiter decision, made through the
    existing recruitment pipeline."""
    return _transition(client, industry_id, interview_id, "CANCELLED", _CANCEL_FROM)
