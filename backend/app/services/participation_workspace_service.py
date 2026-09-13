"""Business logic for Participation Workspaces
(`participation_workspaces`, database/migrations/063_participation_workspaces.sql).

Every function takes an already-built *user-scoped* Supabase client;
RLS is the real access-control boundary. Generic by `kind`.
"""

import contextlib
from datetime import UTC, datetime

from postgrest.exceptions import APIError
from supabase import Client

from app.services._participation_common import (
    APPLICATION_FK,
    APPLICATION_TABLE,
    ELIGIBLE_APPLICATION_STATUSES,
    OPPORTUNITY_FK,
    WORKSPACE_SELECT,
    opportunity_ref,
)


class ApplicationNotEligibleError(Exception):
    """The referenced application is not yet at a status that grants a
    participation workspace (mirrors set_participation_workspace_derived_ids,
    063 -- this is a friendly pre-check, the DB trigger is the real
    backstop)."""

    def __init__(self, current_status: str | None) -> None:
        self.current_status = current_status
        super().__init__(f"Application status '{current_status}' does not grant a workspace yet.")


def _attach_applicant_name(client: Client, rows: list[dict]) -> list[dict]:
    """Best-effort student_name via the applicant-profile RPC matching
    each row's kind -- workshop/project/training each already have one
    (056/057/059), scoped to the caller's own industry ownership. Never
    raises: a lookup failure just leaves student_name None."""
    if not rows:
        return rows
    rpc_by_kind = {
        "PROJECT": ("project_applicant_profiles", "project_application_id"),
        "TRAINING": ("training_applicant_profiles", "training_application_id"),
        "WORKSHOP": ("workshop_applicant_profiles", "workshop_application_id"),
    }
    by_kind: dict[str, list[dict]] = {}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row)
    for kind, kind_rows in by_kind.items():
        rpc_name, app_fk = rpc_by_kind[kind]
        app_ids = [r[app_fk] for r in kind_rows if r.get(app_fk)]
        if not app_ids:
            continue
        try:
            response = client.rpc(rpc_name, {"application_ids": app_ids}).execute()
            names = {r["application_id"]: r.get("student_name") for r in (response.data or [])}
        except Exception:  # noqa: BLE001 -- enrichment only, never fatal
            names = {}
        for r in kind_rows:
            r["student_name"] = names.get(r.get(app_fk))
    return rows


def _attach_opportunity(client: Client, rows: list[dict]) -> list[dict]:
    for row in rows:
        kind = row["kind"]
        row["opportunity"] = opportunity_ref(client, kind, row.get(OPPORTUNITY_FK[kind]))
    return rows


def _attach_program_id(client: Client, rows: list[dict]) -> list[dict]:
    """Best-effort: the participation_programs.id for this workspace's
    opportunity, if a program has been authored yet. None (not an error)
    when it hasn't -- the workspace still exists and is usable, just with
    no content yet."""
    for row in rows:
        kind = row["kind"]
        opp_id = row.get(OPPORTUNITY_FK[kind])
        row["program_id"] = None
        if not opp_id:
            continue
        response = (
            client.table("participation_programs")
            .select("id")
            .eq(OPPORTUNITY_FK[kind], opp_id)
            .maybe_single()
            .execute()
        )
        r = response.data if response is not None else None
        row["program_id"] = r["id"] if r else None
    return rows


def ensure_workspace(client: Client, industry_id: str, kind: str, application_id: str) -> dict:
    """Idempotent ensure-or-create: returns the existing workspace for this
    application if one already exists, otherwise provisions it. Never
    creates a duplicate (the DB's own unique partial index on the
    application-id column is the final backstop; this function also
    checks first to avoid a needless round trip / 23505 in the common
    case)."""
    app_fk = APPLICATION_FK[kind]
    existing = (
        client.table("participation_workspaces")
        .select(WORKSPACE_SELECT)
        .eq(app_fk, application_id)
        .maybe_single()
        .execute()
    )
    row = existing.data if existing is not None else None
    if row:
        return _attach_program_id(client, _attach_opportunity(client, _attach_applicant_name(client, [row])))[0]

    app_table = APPLICATION_TABLE[kind]
    app_response = (
        client.table(app_table)
        .select("id, industry_id, status")
        .eq("id", application_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    application = app_response.data if app_response is not None else None
    if application is None:
        raise LookupError(application_id)
    if application["status"] not in ELIGIBLE_APPLICATION_STATUSES[kind]:
        raise ApplicationNotEligibleError(application["status"])

    payload = {app_fk: application_id}
    try:
        response = client.table("participation_workspaces").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            # Lost a race with a concurrent ensure -- read back and return.
            existing = (
                client.table("participation_workspaces")
                .select(WORKSPACE_SELECT)
                .eq(app_fk, application_id)
                .maybe_single()
                .execute()
            )
            row = existing.data if existing is not None else None
            if row:
                return _attach_program_id(client, _attach_opportunity(client, _attach_applicant_name(client, [row])))[0]
        raise
    new_id = response.data[0]["id"]
    row = get_workspace(client, industry_id, new_id, as_industry=True)
    if row is None:
        raise RuntimeError("participation workspace could not be read back after create.")
    return row


def list_workspaces(
    client: Client, industry_id: str, *, kind: str | None = None, status: str | None = None
) -> list[dict]:
    query = client.table("participation_workspaces").select(WORKSPACE_SELECT).eq("industry_id", industry_id)
    if kind:
        query = query.eq("kind", kind)
    if status:
        query = query.eq("workspace_status", status)
    rows = query.order("created_at", desc=True).execute().data or []
    return _attach_program_id(client, _attach_opportunity(client, _attach_applicant_name(client, rows)))


def get_workspace(client: Client, user_id: str, workspace_id: str, *, as_industry: bool) -> dict | None:
    """One workspace, scoped to the caller (industry owner or the student
    themselves). Returns None if not found/not owned -- callers turn that
    into a 404."""
    column = "industry_id" if as_industry else "student_id"
    response = (
        client.table("participation_workspaces")
        .select(WORKSPACE_SELECT)
        .eq("id", workspace_id)
        .eq(column, user_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    rows = _attach_program_id(client, _attach_opportunity(client, [row]))
    if as_industry:
        rows = _attach_applicant_name(client, rows)
    return rows[0]


def list_my_workspaces(client: Client, student_id: str, *, kind: str | None = None) -> list[dict]:
    query = client.table("participation_workspaces").select(WORKSPACE_SELECT).eq("student_id", student_id)
    if kind:
        query = query.eq("kind", kind)
    rows = query.order("created_at", desc=True).execute().data or []
    return _attach_program_id(client, _attach_opportunity(client, rows))


def get_progress(client: Client, workspace_id: str) -> dict:
    """completed_required / published_required / percent, derived from
    required PUBLISHED assignments on the workspace's program vs. how many
    of those have at least one ACCEPTED (or REVIEWED, treated as
    satisfying) review. Zero published-required assignments -> percent 0,
    never a division by zero."""
    ws = client.table("participation_workspaces").select("kind, project_id, training_id, workshop_id").eq("id", workspace_id).maybe_single().execute()
    ws_row = ws.data if ws is not None else None
    if not ws_row:
        return {"completed_required": 0, "published_required": 0, "percent": 0}
    fk = OPPORTUNITY_FK[ws_row["kind"]]
    opp_id = ws_row.get(fk)
    program = (
        client.table("participation_programs").select("id").eq(fk, opp_id).maybe_single().execute()
    )
    program_row = program.data if program is not None else None
    if not program_row:
        return {"completed_required": 0, "published_required": 0, "percent": 0}

    assignments = (
        client.table("participation_assignments")
        .select("id")
        .eq("program_id", program_row["id"])
        .eq("is_required", True)
        .eq("is_published", True)
        .execute()
        .data
        or []
    )
    published_required = len(assignments)
    if published_required == 0:
        return {"completed_required": 0, "published_required": 0, "percent": 0}

    assignment_ids = [a["id"] for a in assignments]
    submissions = (
        client.table("participation_submissions")
        .select("id, assignment_id")
        .eq("workspace_id", workspace_id)
        .in_("assignment_id", assignment_ids)
        .execute()
        .data
        or []
    )
    submission_ids_by_assignment: dict[str, list[str]] = {}
    for s in submissions:
        submission_ids_by_assignment.setdefault(s["assignment_id"], []).append(s["id"])
    all_submission_ids = [s["id"] for s in submissions]
    accepted_submission_ids: set[str] = set()
    if all_submission_ids:
        reviews = (
            client.table("participation_submission_reviews")
            .select("submission_id, status")
            .in_("submission_id", all_submission_ids)
            .eq("status", "ACCEPTED")
            .execute()
            .data
            or []
        )
        accepted_submission_ids = {r["submission_id"] for r in reviews}

    completed_required = 0
    for assignment_id in assignment_ids:
        sids = submission_ids_by_assignment.get(assignment_id, [])
        if any(sid in accepted_submission_ids for sid in sids):
            completed_required += 1

    percent = round((completed_required / published_required) * 100)
    return {"completed_required": completed_required, "published_required": published_required, "percent": percent}


def sync_workspace_status(client: Client, kind: str, application_id: str, application_status: str) -> None:
    """Best-effort: keep an existing workspace's workspace_status in sync
    with its owning application's own status, called from the same
    service functions that transition industry_project_applications /
    _training_applications / _workshop_applications.status (never an
    independent second source of truth). No-op if no workspace exists yet
    (e.g. the application moved straight to a terminal status before a
    workspace was ever provisioned) or if the target status isn't one this
    table tracks."""
    if application_status not in ("ACTIVE", "COMPLETED"):
        return
    app_fk = APPLICATION_FK[kind]
    target = "COMPLETED" if application_status == "COMPLETED" else "ACTIVE"
    payload: dict = {"workspace_status": target}
    if target == "COMPLETED":
        payload["completed_at"] = datetime.now(UTC).isoformat()
    with contextlib.suppress(Exception):
        client.table("participation_workspaces").update(payload).eq(app_fk, application_id).execute()


def list_workspaces_for_opportunity(client: Client, kind: str, opportunity_id: str) -> list[dict]:
    """Every ACTIVE workspace for one opportunity (Industry-owned, already
    ownership-checked by the caller via the program) -- used to fan out a
    "new assignment published" notification to every current participant."""
    fk = OPPORTUNITY_FK[kind]
    rows = (
        client.table("participation_workspaces")
        .select("id, student_id")
        .eq(fk, opportunity_id)
        .eq("workspace_status", "ACTIVE")
        .execute()
        .data
        or []
    )
    return rows
