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

# The interview row itself -- flat columns only. The opportunity
# (title/type) is stitched on afterwards from a separate `applications`
# read (`_opportunity_index`) rather than a PostgREST embed: the
# interviews -> applications relationship is not something this read can
# depend on being present in PostgREST's schema cache, and stitching is
# the same pattern application_service uses for applicant names.
_SELECT = (
    "id, application_id, industry_id, student_id, scheduled_at, duration_minutes, "
    "mode, location, notes, status, created_at, updated_at"
)

# The owned-application read used to resolve each interview's opportunity.
# Goes through the same user-scoped client, so `applications`' own RLS
# ("Industry can view applications to their own postings") still applies.
_APPLICATION_SELECT = (
    "id, opportunity_type, "
    "internship:internships(id, title, status), job:jobs(id, title, status)"
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


def _opportunity_index(
    client: Client, industry_id: str, application_ids: list[str]
) -> dict[str, dict]:
    """Map application_id -> {"opportunity", "opportunity_type"} for the
    given applications, via ONE ownership-scoped `applications` read.

    Scoped two ways, matching every other function in this module:
    `applications`' own RLS ("Industry can view applications to their own
    postings") AND an explicit `.eq("industry_id", industry_id)` filter --
    so the enrichment read can only ever surface the caller's own
    applications, never another company's, even if RLS were somehow
    misconfigured.

    Best-effort enrichment, exactly like application_service's applicant
    names: a lookup failure (or an application the caller can no longer
    see) just leaves `opportunity` / `opportunity_type` as None on the
    interview -- it never turns a successful interview read into an error.
    """
    ids = [i for i in dict.fromkeys(application_ids) if i]
    if not ids:
        return {}
    try:
        response = (
            client.table("applications")
            .select(_APPLICATION_SELECT)
            .eq("industry_id", industry_id)
            .in_("id", ids)
            .execute()
        )
    except Exception:  # noqa: BLE001 -- opportunity is optional enrichment, never fatal
        return {}
    index: dict[str, dict] = {}
    for row in response.data or []:
        picked = row.get("internship") or row.get("job")
        index[row["id"]] = {
            "opportunity": (
                {"id": picked["id"], "title": picked["title"], "status": picked["status"]}
                if picked
                else None
            ),
            "opportunity_type": row.get("opportunity_type"),
        }
    return index


def _shape(row: dict, opportunity_index: dict[str, dict] | None = None) -> dict:
    """Attach the flat `opportunity` + `opportunity_type` an interview
    response carries, from the pre-fetched `_opportunity_index`."""
    info = (opportunity_index or {}).get(row.get("application_id")) or {}
    row["opportunity"] = info.get("opportunity")
    row["opportunity_type"] = info.get("opportunity_type")
    return row


def _attach_applicant_names(client: Client, rows: list[dict]) -> list[dict]:
    """Best-effort attach `student_name` to each interview row via the
    public.application_applicant_names RPC (036) -- the same
    ownership-scoped SECURITY DEFINER function application_service uses.
    It is scoped to the exact ownership predicate of `applications`' own
    RLS SELECT policy, so it can only ever name applicants for
    applications the caller owns, and it returns the applicant's
    `full_name` only -- never email / phone / avatar / anything else.

    Never raises: a lookup failure just leaves `student_name` as None on
    every row, so the scheduled-interview card falls back to the existing
    "Applicant <ref>" placeholder exactly as before. Keyed on
    `application_id` (each interview references exactly one application).
    """
    if not rows:
        return rows
    names: dict[str, str | None] = {}
    try:
        application_ids = list(
            dict.fromkeys(row["application_id"] for row in rows if row.get("application_id"))
        )
        if application_ids:
            response = client.rpc(
                "application_applicant_names", {"application_ids": application_ids}
            ).execute()
            names = {r["application_id"]: r["student_name"] for r in (response.data or [])}
    except Exception:  # noqa: BLE001 -- names are optional enrichment, never fatal
        names = {}
    for row in rows:
        row["student_name"] = names.get(row.get("application_id"))
    return rows


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
    rows = response.data or []
    index = _opportunity_index(client, industry_id, [row["application_id"] for row in rows])
    return _attach_applicant_names(client, [_shape(row, index) for row in rows])


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
    if not row:
        return None
    row = dict(row)
    index = _opportunity_index(client, industry_id, [row["application_id"]])
    return _attach_applicant_names(client, [_shape(row, index)])[0]


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
