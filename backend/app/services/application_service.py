"""Business logic for the Industry side of applications
(`applications`, database/migrations/020_applications.sql).

Same shape as the other service modules: every function takes an
already-built *user-scoped* Supabase client (app.core.security.
build_user_client) and RLS is the real access-control boundary. Nothing
here uses service_role.

Ownership: `applications`' RLS ("Industry can view / update applications
to their own postings") scopes every read and write to
`auth.uid() = industry_id AND public.is_industry(auth.uid())`. On top of
that, every function here also filters explicitly by `industry_id`
(passed in as `current_user.id`) -- defence in depth.

`industry_id` on a row is derived by the `set_application_industry_id`
BEFORE-INSERT trigger from the referenced posting; it is never
client-supplied. The `prevent_application_identity_change` trigger blocks
any change to `student_id` / `industry_id` / `opportunity_type` /
`internship_id` / `job_id`. This module reinforces that by only ever
writing `{"status": ...}`.

Status lifecycle: the migration's CHECK constraint allows the seven
status values but defines no transition graph. The migration's own header
documents the intended pipeline
    APPLIED -> UNDER_REVIEW -> SHORTLISTED -> INTERVIEW_SCHEDULED -> SELECTED
with REJECTED reachable from any active stage and WITHDRAWN owned by the
student. `_STATUS_TRANSITIONS` below is that pipeline, enforced here.
"""

from supabase import Client

# Industry-driven transitions only. WITHDRAWN is never a target (student
# action) and never a source with outgoing edges. SELECTED / REJECTED are
# terminal for Industry.
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "APPLIED": {"UNDER_REVIEW", "SHORTLISTED", "REJECTED"},
    "UNDER_REVIEW": {"SHORTLISTED", "REJECTED"},
    "SHORTLISTED": {"INTERVIEW_SCHEDULED", "REJECTED"},
    "INTERVIEW_SCHEDULED": {"SELECTED", "REJECTED"},
    "SELECTED": set(),
    "REJECTED": set(),
    "WITHDRAWN": set(),
}

_ALL_STATUSES: tuple[str, ...] = tuple(_STATUS_TRANSITIONS)

_SELECT = (
    "id, student_id, industry_id, opportunity_type, internship_id, job_id, status, "
    "cover_note, match_score, applied_at, created_at, updated_at, "
    "internship:internships(id, title, status), job:jobs(id, title, status)"
)


class InvalidStatusTransitionError(Exception):
    """The requested status change isn't a valid Industry transition from
    the application's current status."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an application from {current} to {target}.")


def _shape(row: dict) -> dict:
    """Collapse the internship / job embed into a single `opportunity`."""
    internship = row.pop("internship", None)
    job = row.pop("job", None)
    picked = internship or job
    row["opportunity"] = (
        {"id": picked["id"], "title": picked["title"], "status": picked["status"]}
        if picked
        else None
    )
    return row


def list_applications(
    client: Client,
    industry_id: str,
    *,
    status: str | None = None,
    opportunity_type: str | None = None,
    internship_id: str | None = None,
    job_id: str | None = None,
) -> list[dict]:
    """Applications submitted to the caller's own postings, newest first.
    Every filter is optional and additive."""
    query = client.table("applications").select(_SELECT).eq("industry_id", industry_id)
    if status:
        query = query.eq("status", status)
    if opportunity_type:
        query = query.eq("opportunity_type", opportunity_type)
    if internship_id:
        query = query.eq("internship_id", internship_id)
    if job_id:
        query = query.eq("job_id", job_id)
    response = query.order("applied_at", desc=True).execute()
    return [_shape(row) for row in (response.data or [])]


def get_status_summary(client: Client, industry_id: str) -> dict:
    """Per-status counts across all of the caller's own applications, plus
    the total -- drives the recruitment funnel. Reads only the `status`
    column. `counts` always has an entry for every status (0 when none)."""
    response = (
        client.table("applications").select("status").eq("industry_id", industry_id).execute()
    )
    rows = response.data or []
    counts = {name: 0 for name in _ALL_STATUSES}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"counts": counts, "total": len(rows)}


def get_application(client: Client, industry_id: str, application_id: str) -> dict | None:
    """One application to one of the caller's own postings, or None --
    callers turn None into a 404, so another Industry account's
    application is indistinguishable from one that doesn't exist."""
    response = (
        client.table("applications")
        .select(_SELECT)
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape(row) if row else None


def get_skill_match_rows(client: Client, application_id: str) -> list[dict]:
    """The posting-required-skill x candidate-skill overlap for one
    application, via the public.application_skill_match SECURITY DEFINER
    function (021_application_skill_match.sql). Runs through the same
    user-scoped client -- no service_role.

    Returns [] both when the caller does not own the application AND when
    the posting simply has no required skills; the route uses
    get_application() for the 404 decision, so this ambiguity is harmless.
    """
    response = client.rpc(
        "application_skill_match", {"p_application_id": application_id}
    ).execute()
    return response.data or []


def set_match_score(client: Client, industry_id: str, application_id: str, score: int) -> None:
    """Best-effort cache of a server-computed match score onto
    applications.match_score. RLS ("Industry can update applications to
    their own postings") permits it; the prevent_application_identity_change
    trigger still blocks student/opportunity/owner changes. Never accepts a
    client value -- `score` is always computed by match_service."""
    (
        client.table("applications")
        .update({"match_score": score})
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .execute()
    )


def update_status(
    client: Client, industry_id: str, application_id: str, target_status: str
) -> dict | None:
    """Move one of the caller's own applications to `target_status`, if
    that is a valid transition from its current status. Only `status` is
    ever written -- student / opportunity / industry_id are untouched (and
    the identity-change trigger would block them anyway)."""
    existing = get_application(client, industry_id, application_id)
    if existing is None:
        return None

    current = existing["status"]
    if target_status not in _STATUS_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransitionError(current, target_status)

    (
        client.table("applications")
        .update({"status": target_status})
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_application(client, industry_id, application_id)
