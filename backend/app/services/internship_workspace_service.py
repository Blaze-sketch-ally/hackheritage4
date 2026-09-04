"""Business logic for provisioning and reading the per-student Internship
Workspace (database/migrations/038_internship_workspace.sql).

PHASE 2 SCOPE: workspace PROVISIONING on the SELECTED transition, plus a
minimal read surface. Nothing here implements acceptance, program
authoring, or submission review -- those are later phases (3-6). PHASE 7
adds completion + certificate. PHASE 8 adds stipend record-keeping (below)
-- both independent of one another and of everything above.

Every function takes an already-built Supabase client. The live path
(application_service.update_status) and the two read endpoints pass a
*user-scoped* client (app.core.security.build_user_client); the explicit
one-off backfill script passes the *service-role* client. RLS
(038_internship_workspace.sql) is the real access-control boundary in
both cases:

* internship_workspaces INSERT policy:
    with check (auth.uid() = industry_id AND public.is_industry(auth.uid()))
  When update_status() provisions, the caller IS that industry account,
  so a user-scoped insert is RLS-legal -- same construction as
  interview_service inserting `interviews` (030).
* set_workspace_derived_ids (BEFORE INSERT) fills student_id / industry_id
  / internship_id / work_mode from the referenced application + internship
  and RAISES unless applications.status = 'SELECTED' and
  internships.work_mode IN ('REMOTE','HYBRID'). So an ONSITE / NULL /
  non-SELECTED application can never receive a workspace -- not even
  through the service-role backfill.
* UNIQUE(application_id) makes provisioning idempotent: a duplicate insert
  raises 23505, which this module treats as "already provisioned".

This module NEVER modifies applications.status or internships.status.

PHASE 3 adds the student-facing read + acceptance surface on top:
get_student_workspace / accept_workspace / decline_workspace /
set_skill_selections. Acceptance and skill-selection are ultimately
enforced by the DB triggers enforce_workspace_status_transitions and
enforce_workspace_skill_selectable (038) -- this module re-checks the
same rules in Python only to return a clean 4xx instead of a 500.

`_resolve_internship_summaries` is the ONE deliberate, narrow service-role
touch (see its docstring): a student's RLS on `internships` exposes only
PUBLISHED postings, so once a posting they were SELECTED for is CLOSED /
ARCHIVED they can no longer read even its title -- but the workspace,
whose access is anchored on the workspace relationship and NEVER on
internships.status, is still theirs. Everything else stays user-scoped.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from postgrest.exceptions import APIError
from supabase import Client

from app.database.supabase import get_supabase

ProvisionOutcome = Literal[
    "CREATED",
    "ALREADY_EXISTS",
    "SKIPPED_WORK_MODE",
    "SKIPPED_NO_PROGRAM",
    "SKIPPED_NOT_SELECTED",
    "SKIPPED_NOT_INTERNSHIP",
]

_ELIGIBLE_WORK_MODES: frozenset[str] = frozenset({"REMOTE", "HYBRID"})

_WORKSPACE_COLUMNS = (
    "id, application_id, internship_id, student_id, industry_id, work_mode, "
    "workspace_status, accepted_at, started_at, completed_at, declined_at, "
    "decline_reason, rescinded_at, rescind_reason, created_at, updated_at"
)
# Industry-side only: an industry can read its own internships regardless
# of status (028), so a user-scoped embed is fine there.
_WORKSPACE_SELECT = f"{_WORKSPACE_COLUMNS}, internship:internships(id, title, status)"

_INTERNSHIP_SUMMARY_COLUMNS = "id, title, description, work_mode, status"

_PENDING_ACCEPTANCE = "PENDING_ACCEPTANCE"
# Product rule (Phase 1 lifecycle): pick training skills AFTER accepting.
# The DB trigger enforce_workspace_skill_selectable is more permissive
# (it also allows PENDING_ACCEPTANCE) and stays the final backstop.
_SKILL_SELECTABLE_STATES: frozenset[str] = frozenset({"ACCEPTED", "IN_PROGRESS"})
# The DB trigger set_workspace_submission_attempt_number enforces exactly
# this ('ACCEPTED', 'IN_PROGRESS') and stays the final backstop.
_SUBMISSION_STATES: frozenset[str] = frozenset({"ACCEPTED", "IN_PROGRESS"})
# A resubmission is only allowed once the previous attempt was sent back.
_RESUBMIT_AFTER: frozenset[str] = frozenset({"REVISION_REQUESTED", "REJECTED"})
# Accurate, per-status reason shown when a workspace's own status blocks
# submission (i.e. workspace_status not in _SUBMISSION_STATES). Only
# PENDING_ACCEPTANCE actually means "accept first" -- COMPLETED/DECLINED/
# RESCINDED are terminal states reached *after* acceptance, so reusing that
# same wording for them would falsely tell an already-accepted (and, for
# COMPLETED, already-finished) student that they still need to accept.
_BLOCKED_BY_STATUS_REASON: dict[str, str] = {
    "PENDING_ACCEPTANCE": "Accept the internship before submitting work.",
    "COMPLETED": "This internship has been completed. New submissions are no longer accepted.",
    "DECLINED": "You declined this internship offer.",
    "RESCINDED": "This internship offer was withdrawn.",
}

_STUDENT_ASSIGNMENT_COLUMNS = (
    "id, module_id, program_id, title, description, instructions, assignment_type, "
    "is_required, is_published, order_index, due_offset_days, submission_kind, "
    "repo_required, live_url_expected, max_score, linked_skill_id"
)
_OWN_SUBMISSION_COLUMNS = (
    "id, workspace_id, assignment_id, attempt_number, submission_status, "
    "repo_url, live_url, attachment_url, notes, submitted_at, created_at, updated_at"
)
# Phase 6: the student sees the industry's review of THEIR OWN attempts --
# verdict, feedback, score only. NO reviewer_id: the student never sees
# who reviewed (submission_reviews' "Students can view reviews of their
# own submissions" policy would allow it, but the product does not expose
# it). This module only ever READS submission_reviews, never writes it.
_OWN_SUBMISSION_EMBED = (
    f"{_OWN_SUBMISSION_COLUMNS}, submission_reviews(verdict, feedback, score, created_at)"
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ProvisionResult:
    """The outcome of one provision_for_selection() call. `workspace` is
    the workspace row for CREATED / ALREADY_EXISTS, else None. A no-op
    situation (wrong work mode, no program, not selected) is returned as
    one of the SKIPPED_* outcomes -- it is never an exception."""

    outcome: ProvisionOutcome
    detail: str
    application_id: str
    work_mode: str | None = None
    workspace: dict | None = None

    @property
    def created(self) -> bool:
        return self.outcome == "CREATED"


class ProvisionError(Exception):
    """Base for genuinely unexpected provisioning failures (distinct from
    the clean SKIPPED_* no-op outcomes)."""


class ApplicationNotFoundError(ProvisionError):
    """The referenced application row does not exist / is not visible to
    the caller."""


class InternshipNotFoundError(ProvisionError):
    """The application's internship row does not exist / is not visible to
    the caller."""


class ProvisionRejectedError(ProvisionError):
    """The database rejected a well-formed workspace insert (42501) -- the
    application or internship state changed during provisioning (no longer
    SELECTED, or the work_mode moved). The caller may retry."""


class WorkspaceNotFoundError(Exception):
    """No workspace with that id is visible to the current caller -- reused
    for both the student and the industry side (each scoped by its own
    ownership check); the route always turns this into a 404."""


class InvalidWorkspaceTransitionError(Exception):
    """The requested accept/decline is not valid from the workspace's
    current status (the DB trigger enforce_workspace_status_transitions is
    the final authority; this is raised so the API can return 409 instead
    of a 500)."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an internship workspace from {current} to {target}.")


class WorkspaceNotAcceptedError(Exception):
    """Skill selection was attempted before the workspace was accepted."""


class InvalidSkillSelectionError(Exception):
    """A requested skill id is not an OPTIONAL skill of the workspace's
    internship program (or the DB trigger enforce_workspace_skill_selectable
    rejected the write)."""


class AssignmentNotFoundError(Exception):
    """No published assignment with that id is visible in this workspace's
    program."""


class InvalidSubmissionError(Exception):
    """The submission payload doesn't satisfy the assignment's configured
    requirements (repo_required / live_url_expected / submission_kind)."""


class SubmissionRejectedError(Exception):
    """The DB rejected the submission (42501) -- the workspace is no longer
    active, or the previous attempt has not been sent back for revision."""


def _maybe_row(response) -> dict | None:
    return response.data if response is not None else None


def _shape(row: dict) -> dict:
    row = dict(row)
    internship = row.get("internship")
    row["internship"] = (
        {"id": internship["id"], "title": internship["title"], "status": internship["status"]}
        if internship
        else None
    )
    return row


def _read_workspace(client: Client, application_id: str) -> dict | None:
    response = (
        client.table("internship_workspaces")
        .select(_WORKSPACE_SELECT)
        .eq("application_id", application_id)
        .maybe_single()
        .execute()
    )
    row = _maybe_row(response)
    return _shape(row) if row else None


def provision_for_selection(client: Client, application_id: str) -> ProvisionResult:
    """Ensure exactly one internship_workspace exists for `application_id`
    IF the application is SELECTED for a REMOTE/HYBRID internship that
    already has an internship_program. Idempotent and safe to call
    repeatedly -- an already-provisioned application comes back as
    ALREADY_EXISTS with the existing row, never a duplicate and never an
    error.

    Raises ProvisionError only for genuinely unexpected states
    (application / internship not visible, or the DB rejecting a
    well-formed insert). Every ineligible-but-understood case is a
    SKIPPED_* ProvisionResult.

    Does NOT touch applications.status or internships.status.
    """
    app_response = (
        client.table("applications")
        .select("id, internship_id, opportunity_type, status")
        .eq("id", application_id)
        .maybe_single()
        .execute()
    )
    application = _maybe_row(app_response)
    if application is None:
        raise ApplicationNotFoundError(application_id)

    if application.get("opportunity_type") != "INTERNSHIP" or not application.get("internship_id"):
        return ProvisionResult(
            "SKIPPED_NOT_INTERNSHIP",
            "Only internship applications get an internship workspace.",
            application_id,
        )

    if application.get("status") != "SELECTED":
        return ProvisionResult(
            "SKIPPED_NOT_SELECTED",
            f"Application status is {application.get('status')!r}, not 'SELECTED'.",
            application_id,
        )

    internship_id = application["internship_id"]

    internship_response = (
        client.table("internships")
        .select("id, work_mode")
        .eq("id", internship_id)
        .maybe_single()
        .execute()
    )
    internship = _maybe_row(internship_response)
    if internship is None:
        raise InternshipNotFoundError(internship_id)

    work_mode = internship.get("work_mode")
    if work_mode not in _ELIGIBLE_WORK_MODES:
        return ProvisionResult(
            "SKIPPED_WORK_MODE",
            f"Internship work_mode is {work_mode!r} -- only REMOTE or HYBRID "
            "internships get a workspace.",
            application_id,
            work_mode=work_mode,
        )

    program_response = (
        client.table("internship_programs")
        .select("id, status")
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )
    program = _maybe_row(program_response)
    if program is None:
        return ProvisionResult(
            "SKIPPED_NO_PROGRAM",
            "The internship has no internship_program yet -- provisioning is deferred "
            "until the industry creates one. Re-run provisioning afterwards "
            "(POST /api/v1/applications/{id}/provision-workspace, or the backfill script).",
            application_id,
            work_mode=work_mode,
        )

    existing = _read_workspace(client, application_id)
    if existing is not None:
        return ProvisionResult(
            "ALREADY_EXISTS",
            "An internship workspace already exists for this application.",
            application_id,
            work_mode=work_mode,
            workspace=existing,
        )

    try:
        client.table("internship_workspaces").insert(
            {"application_id": application_id}
        ).execute()
    except APIError as exc:
        if exc.code == "23505":
            # UNIQUE(application_id): a concurrent provision beat us. Not
            # an error -- report the row that now exists.
            return ProvisionResult(
                "ALREADY_EXISTS",
                "An internship workspace already exists for this application (concurrent provision).",
                application_id,
                work_mode=work_mode,
                workspace=_read_workspace(client, application_id),
            )
        if exc.code == "42501":
            raise ProvisionRejectedError(
                "The database rejected the internship workspace insert -- the application "
                "or internship state changed during provisioning."
            ) from exc
        raise

    created = _read_workspace(client, application_id)
    if created is None:
        raise ProvisionError("Internship workspace could not be read back after insert.")
    return ProvisionResult(
        "CREATED",
        "Internship workspace provisioned.",
        application_id,
        work_mode=work_mode,
        workspace=created,
    )


def _resolve_internship_summaries(internship_ids: list[str]) -> dict[str, dict]:
    """Resolve id -> {id, title, description, work_mode, status} for a set
    of internship postings, via the service-role client.

    WHY service_role: a student's RLS on `internships` (018) exposes only
    `status = 'PUBLISHED'` rows, so once a posting they were SELECTED for
    is CLOSED / ARCHIVED they can no longer read even its title through a
    user-scoped client. The workspace itself is still theirs -- its access
    is anchored on the workspace relationship, NEVER on internships.status
    (verified live in Phase 1). This resolver closes ONLY that
    title/detail read gap.

    The caller MUST have already confirmed, with a user-scoped RLS read,
    that the current student owns a workspace for every internship_id
    passed here -- exactly the "independently verify ownership in Python
    first" rule in app.database.supabase.get_supabase's docstring. Only
    {id, title, description, work_mode, status} is ever exposed -- never
    industry contact info or any other posting column.
    """
    ids = sorted({i for i in internship_ids if i})
    if not ids:
        return {}
    response = (
        get_supabase()
        .table("internships")
        .select(_INTERNSHIP_SUMMARY_COLUMNS)
        .in_("id", ids)
        .execute()
    )
    return {row["id"]: row for row in (response.data or [])}


def _internship_ref(internship_id: str, summaries: dict[str, dict]) -> dict | None:
    row = summaries.get(internship_id)
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row.get("title"),
        "description": row.get("description"),
        "work_mode": row.get("work_mode"),
        "status": row.get("status"),
    }


def _read_own_workspace(client: Client, student_id: str, workspace_id: str) -> dict | None:
    """One workspace, scoped to the current student by RLS AND an explicit
    .eq("student_id", ...). Returns None for a workspace the student does
    not own -- callers turn that into a 404, so a foreign workspace is
    indistinguishable from one that does not exist."""
    response = (
        client.table("internship_workspaces")
        .select(_WORKSPACE_COLUMNS)
        .eq("id", workspace_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    return _maybe_row(response)


def list_student_workspaces(client: Client, student_id: str) -> list[dict]:
    """The authenticated student's own internship workspaces, newest
    first. RLS ("Students can view their own internship workspace") plus
    the explicit .eq("student_id", ...) both scope this to the caller.

    The query NEVER filters on internships.status. The internship
    title/details are resolved via _resolve_internship_summaries (see its
    docstring) so a workspace keeps its label after the posting is CLOSED
    / ARCHIVED, while the workspace row itself is always fully readable.
    """
    response = (
        client.table("internship_workspaces")
        .select(_WORKSPACE_COLUMNS)
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = response.data or []
    summaries = _resolve_internship_summaries([r["internship_id"] for r in rows])
    shaped: list[dict] = []
    for row in rows:
        row = dict(row)
        row["internship"] = _internship_ref(row["internship_id"], summaries)
        shaped.append(row)
    return shaped


def list_industry_workspaces(
    client: Client,
    industry_id: str,
    *,
    internship_id: str | None = None,
    workspace_status: str | None = None,
) -> list[dict]:
    """Internship workspaces for the caller's own internships, newest
    first. RLS ("Industry can view internship workspaces for their own
    internships") plus the explicit .eq("industry_id", ...) both scope
    this to the caller. Both filters are optional and additive."""
    query = (
        client.table("internship_workspaces")
        .select(_WORKSPACE_SELECT)
        .eq("industry_id", industry_id)
    )
    if internship_id:
        query = query.eq("internship_id", internship_id)
    if workspace_status:
        query = query.eq("workspace_status", workspace_status)
    response = query.order("created_at", desc=True).execute()
    return [_shape(row) for row in (response.data or [])]


def _read_industry_workspace(client: Client, industry_id: str, workspace_id: str) -> dict | None:
    """One workspace, scoped to the current industry by RLS AND an
    explicit .eq("industry_id", ...). Returns None for a workspace the
    industry does not own -- callers turn that into a 404, mirroring
    _read_own_workspace on the student side."""
    response = (
        client.table("internship_workspaces")
        .select(_WORKSPACE_COLUMNS)
        .eq("id", workspace_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    return _maybe_row(response)


# ============================================================
# Phase 3 -- student detail + program preview + acceptance
# ============================================================


def _load_program_preview(client: Client, internship_id: str) -> dict | None:
    """The PUBLISHED internship_program for `internship_id`, with its
    published modules (+ items) and its skills -- read through the
    student's OWN user-scoped client. `student_can_access_program` (038)
    gates this on program.status = 'PUBLISHED' and the workspace NOT being
    DECLINED / RESCINDED, and NEVER on internships.status. Returns None
    when no readable program exists yet (the industry has not published a
    curriculum). Students cannot write any of this -- there is no write
    policy for them on these tables."""
    program = _maybe_row(
        client.table("internship_programs")
        .select("id, title, summary, status")
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )
    if program is None:
        return None

    modules_response = (
        client.table("program_modules")
        .select(
            "id, title, description, order_index, "
            "module_items(id, title, item_type, content_url, content_text, "
            "order_index, is_published)"
        )
        .eq("program_id", program["id"])
        .eq("is_published", True)
        .order("order_index")
        .execute()
    )
    modules: list[dict] = []
    for module in modules_response.data or []:
        items = sorted(
            (
                {
                    "id": item["id"],
                    "title": item["title"],
                    "item_type": item["item_type"],
                    "content_url": item.get("content_url"),
                    "content_text": item.get("content_text"),
                    "order_index": item.get("order_index") or 0,
                }
                for item in (module.get("module_items") or [])
                if item.get("is_published")
            ),
            key=lambda item: item["order_index"],
        )
        modules.append(
            {
                "id": module["id"],
                "title": module["title"],
                "description": module.get("description"),
                "order_index": module.get("order_index") or 0,
                "items": items,
            }
        )

    skills_response = (
        client.table("program_skills")
        .select("skill_id, requirement, skill:skills(id, name)")
        .eq("program_id", program["id"])
        .execute()
    )
    skills: list[dict] = []
    for link in skills_response.data or []:
        skill = link.get("skill") or {}
        skills.append(
            {
                "skill_id": link["skill_id"],
                "skill_name": skill.get("name", ""),
                "requirement": link["requirement"],
            }
        )
    # REQUIRED first, then alphabetical.
    skills.sort(key=lambda s: (s["requirement"] != "REQUIRED", s["skill_name"].lower()))

    return {
        "id": program["id"],
        "title": program["title"],
        "summary": program.get("summary"),
        "status": program["status"],
        "modules": modules,
        "skills": skills,
    }


def _load_selected_skill_ids(client: Client, workspace_id: str) -> list[str]:
    response = (
        client.table("workspace_skill_selections")
        .select("skill_id")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    return sorted({row["skill_id"] for row in (response.data or [])})


def _program_optional_skill_ids(client: Client, internship_id: str) -> set[str]:
    program = _maybe_row(
        client.table("internship_programs")
        .select("id")
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )
    if program is None:
        return set()
    response = (
        client.table("program_skills")
        .select("skill_id")
        .eq("program_id", program["id"])
        .eq("requirement", "OPTIONAL")
        .execute()
    )
    return {row["skill_id"] for row in (response.data or [])}


def _shape_detail(
    workspace: dict,
    *,
    internship: dict | None,
    program: dict | None,
    selected_skill_ids: list[str],
) -> dict:
    row = dict(workspace)
    row["internship"] = internship
    row["program"] = program
    row["selected_skill_ids"] = selected_skill_ids
    return row


def get_student_workspace(client: Client, student_id: str, workspace_id: str) -> dict | None:
    """One workspace the current student owns, with the PUBLISHED program
    preview and the student's current OPTIONAL skill selections. Returns
    None for a workspace the student cannot access -> the route 404s."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        return None

    # Ownership confirmed above (RLS + explicit student_id filter). Only
    # now is the service-role internship resolver called.
    internship = _internship_ref(
        workspace["internship_id"],
        _resolve_internship_summaries([workspace["internship_id"]]),
    )
    program = _load_program_preview(client, workspace["internship_id"])
    selected = _load_selected_skill_ids(client, workspace_id)
    return _shape_detail(
        workspace, internship=internship, program=program, selected_skill_ids=selected
    )


def _apply_student_transition(
    client: Client,
    student_id: str,
    workspace_id: str,
    *,
    target: str,
    extra: dict,
) -> dict:
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)

    current = workspace["workspace_status"]
    # Product + DB rule: a student may only accept/decline a still-pending
    # offer. The enforce_workspace_status_transitions trigger is the final
    # authority; this early check gives a clean 409.
    if current != _PENDING_ACCEPTANCE:
        raise InvalidWorkspaceTransitionError(current, target)

    try:
        (
            client.table("internship_workspaces")
            .update({"workspace_status": target, **extra})
            .eq("id", workspace_id)
            .eq("student_id", student_id)
            .execute()
        )
    except APIError as exc:
        if exc.code == "42501":
            # The DB transition trigger rejected it (a race changed the
            # status underneath us).
            raise InvalidWorkspaceTransitionError(current, target) from exc
        raise

    detail = get_student_workspace(client, student_id, workspace_id)
    if detail is None:  # pragma: no cover -- just updated our own row
        raise WorkspaceNotFoundError(workspace_id)
    return detail


def accept_workspace(client: Client, student_id: str, workspace_id: str) -> dict:
    """PENDING_ACCEPTANCE -> ACCEPTED for the caller's own workspace.
    Never touches applications.status / internships.status / work_mode."""
    return _apply_student_transition(
        client,
        student_id,
        workspace_id,
        target="ACCEPTED",
        extra={"accepted_at": _now_iso()},
    )


def decline_workspace(
    client: Client, student_id: str, workspace_id: str, reason: str | None = None
) -> dict:
    """PENDING_ACCEPTANCE -> DECLINED for the caller's own workspace.
    Never touches applications.status / internships.status."""
    extra: dict = {"declined_at": _now_iso()}
    cleaned = (reason or "").strip()
    if cleaned:
        extra["decline_reason"] = cleaned
    return _apply_student_transition(
        client, student_id, workspace_id, target="DECLINED", extra=extra
    )


def set_skill_selections(
    client: Client, student_id: str, workspace_id: str, skill_ids: list[str]
) -> dict:
    """Replace-set the student's OPTIONAL training-skill selections for
    their own workspace. REQUIRED program skills are always in scope and
    are never stored here. Rejects a skill that is not an OPTIONAL skill
    of this workspace's internship program. The DB trigger
    enforce_workspace_skill_selectable is the final backstop. Does not
    modify program_skills or internship_skills."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)

    if workspace["workspace_status"] not in _SKILL_SELECTABLE_STATES:
        raise WorkspaceNotAcceptedError(
            "Accept the internship workspace before choosing training skills."
        )

    # Normalise: dedupe, drop blanks, preserve order.
    wanted = list(dict.fromkeys(sid for sid in skill_ids if sid))

    optional_ids = _program_optional_skill_ids(client, workspace["internship_id"])
    if any(sid not in optional_ids for sid in wanted):
        raise InvalidSkillSelectionError(
            "One or more skills are not optional skills of this internship program."
        )

    # Replace-set, mirroring internship_service._replace_skills.
    client.table("workspace_skill_selections").delete().eq(
        "workspace_id", workspace_id
    ).execute()
    if wanted:
        try:
            client.table("workspace_skill_selections").insert(
                [{"workspace_id": workspace_id, "skill_id": sid} for sid in wanted]
            ).execute()
        except APIError as exc:
            if exc.code in ("42501", "23503", "23505"):
                raise InvalidSkillSelectionError(
                    "That skill selection was rejected. Only optional program skills can be "
                    "chosen while the workspace is active."
                ) from exc
            raise

    detail = get_student_workspace(client, student_id, workspace_id)
    if detail is None:  # pragma: no cover -- just wrote to our own workspace
        raise WorkspaceNotFoundError(workspace_id)
    return detail


# ============================================================
# Phase 5 -- assignments + student submissions
# ============================================================
# Everything append-only and state-gated is enforced by the DB
# (set_workspace_submission_attempt_number,
# prevent_workspace_submission_content_change, and the RLS policies on
# workspace_submissions / program_assignments in 038 + 039). This module
# re-checks the same rules only to return clean 4xx codes, and NEVER
# writes submission_reviews / internship_completions /
# internship_certificates / stipend_disbursements.
#
# Phase 6: each of the student's own attempts also carries the industry's
# review of it (verdict / feedback / score). submission_reviews is READ
# here and never written; reviewer identity is never exposed.


def _shape_assignment(row: dict) -> dict:
    return {
        "id": row["id"],
        "module_id": row["module_id"],
        "program_id": row["program_id"],
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


def _shape_student_review(row: dict) -> dict:
    """A review as the STUDENT sees it -- no reviewer_id, `reviewed_at`
    from the row's created_at (submission_reviews has no separate
    reviewed_at column)."""
    return {
        "verdict": row["verdict"],
        "feedback": row.get("feedback"),
        "score": float(row["score"]) if row.get("score") is not None else None,
        "reviewed_at": row.get("created_at"),
    }


def _shape_submission(row: dict) -> dict:
    reviews = sorted(
        (_shape_student_review(r) for r in (row.get("submission_reviews") or [])),
        key=lambda r: r.get("reviewed_at") or "",
        reverse=True,
    )
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "assignment_id": row["assignment_id"],
        "attempt_number": row["attempt_number"],
        "submission_status": row["submission_status"],
        "repo_url": row.get("repo_url"),
        "live_url": row.get("live_url"),
        "attachment_url": row.get("attachment_url"),
        "notes": row.get("notes"),
        "submitted_at": row.get("submitted_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "reviews": reviews,
        "latest_review": reviews[0] if reviews else None,
    }


def _visible_assignments(client: Client, internship_id: str) -> list[dict]:
    """Published assignments the student may see in this workspace's
    program. RLS ("Students can view published assignments for their
    workspace", 038) already requires is_published + module.is_published +
    student_can_access_program; the !inner embed filter scopes it to this
    internship's program."""
    response = (
        client.table("program_assignments")
        .select(
            f"{_STUDENT_ASSIGNMENT_COLUMNS}, "
            "module:program_modules!inner(id, title, order_index), "
            "program:internship_programs!inner(internship_id)"
        )
        .eq("program.internship_id", internship_id)
        .execute()
    )
    rows = []
    for row in response.data or []:
        module = row.get("module") or {}
        shaped = _shape_assignment(row)
        shaped["module_id"] = module.get("id", shaped["module_id"])
        shaped["module_title"] = module.get("title")
        shaped["module_order_index"] = module.get("order_index") or 0
        rows.append(shaped)
    rows.sort(key=lambda a: (a["module_order_index"], a["order_index"]))
    return rows


def _own_submissions(client: Client, workspace_id: str) -> list[dict]:
    response = (
        client.table("workspace_submissions")
        .select(_OWN_SUBMISSION_EMBED)
        .eq("workspace_id", workspace_id)
        .order("attempt_number", desc=True)
        .execute()
    )
    return [_shape_submission(r) for r in (response.data or [])]


def _can_submit(workspace_status: str, attempts: list[dict]) -> tuple[bool, str | None]:
    if workspace_status not in _SUBMISSION_STATES:
        return False, _BLOCKED_BY_STATUS_REASON.get(
            workspace_status, "You can't submit to this assignment right now."
        )
    if not attempts:
        return True, None
    latest = attempts[0]["submission_status"]  # attempts are newest-first
    if latest in _RESUBMIT_AFTER:
        return True, None
    if latest == "ACCEPTED":
        return False, "This assignment has already been accepted."
    return False, "Your latest submission is still being reviewed."


def list_workspace_assignments(client: Client, student_id: str, workspace_id: str) -> list[dict]:
    """Every published assignment in the student's own workspace's
    program, with the student's latest submission summary."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)

    assignments = _visible_assignments(client, workspace["internship_id"])
    by_assignment: dict[str, list[dict]] = {}
    for sub in _own_submissions(client, workspace_id):
        by_assignment.setdefault(sub["assignment_id"], []).append(sub)

    result = []
    for assignment in assignments:
        attempts = by_assignment.get(assignment["id"], [])
        can_submit, reason = _can_submit(workspace["workspace_status"], attempts)
        result.append(
            {
                **assignment,
                "attempt_count": len(attempts),
                "latest_submission": attempts[0] if attempts else None,
                "can_submit": can_submit,
                "submit_blocked_reason": reason,
            }
        )
    return result


def get_workspace_assignment(
    client: Client, student_id: str, workspace_id: str, assignment_id: str
) -> dict | None:
    """One visible assignment + every attempt the student has made against
    it. None -> the route 404s."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        return None

    assignment = next(
        (
            a
            for a in _visible_assignments(client, workspace["internship_id"])
            if a["id"] == assignment_id
        ),
        None,
    )
    if assignment is None:
        return None

    attempts = [
        s
        for s in _own_submissions(client, workspace_id)
        if s["assignment_id"] == assignment_id
    ]
    can_submit, reason = _can_submit(workspace["workspace_status"], attempts)
    return {
        "assignment": {
            k: v for k, v in assignment.items() if k not in ("module_title", "module_order_index")
        },
        "module": {"id": assignment["module_id"], "title": assignment.get("module_title")},
        "submissions": attempts,
        "attempt_count": len(attempts),
        "can_submit": can_submit,
        "submit_blocked_reason": reason,
    }


_SUBMISSION_KIND_REQUIRES: dict[str, tuple[str, ...]] = {
    "REPO": ("repo_url",),
    "TEXT": ("notes",),
    "FILE": ("attachment_url",),
    "LINK": ("repo_url", "live_url"),
    "MIXED": ("repo_url", "live_url", "attachment_url", "notes"),
}


def _validate_submission_payload(assignment: dict, payload: dict) -> None:
    def has(field: str) -> bool:
        return bool((payload.get(field) or "").strip())

    if assignment.get("repo_required") and not has("repo_url"):
        raise InvalidSubmissionError("This assignment requires a repository URL.")
    if assignment.get("live_url_expected") and not has("live_url"):
        raise InvalidSubmissionError("This assignment expects a live / deployed URL.")

    needed = _SUBMISSION_KIND_REQUIRES.get(assignment.get("submission_kind") or "LINK", ())
    if needed and not any(has(field) for field in needed):
        label = {
            "repo_url": "a repository URL",
            "live_url": "a live URL",
            "attachment_url": "a file / attachment link",
            "notes": "a written response",
        }
        raise InvalidSubmissionError(
            "This assignment needs " + " or ".join(label[f] for f in needed) + "."
        )


def create_submission(
    client: Client,
    student_id: str,
    workspace_id: str,
    assignment_id: str,
    payload: dict,
) -> dict:
    """Create the next append-only attempt. The DB trigger assigns
    attempt_number, blocks a non-active workspace, blocks an assignment
    that isn't in this workspace's published program, and blocks a
    resubmission before the previous attempt was sent back -- this method
    re-checks the same so the API returns a clean 409/422 instead of 500.
    NEVER writes submission_reviews."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    if workspace["workspace_status"] not in _SUBMISSION_STATES:
        raise WorkspaceNotAcceptedError(
            "You can only submit work while the internship workspace is active."
        )

    assignment = next(
        (
            a
            for a in _visible_assignments(client, workspace["internship_id"])
            if a["id"] == assignment_id
        ),
        None,
    )
    if assignment is None:
        raise AssignmentNotFoundError(assignment_id)

    _validate_submission_payload(assignment, payload)

    row = {"workspace_id": workspace_id, "assignment_id": assignment_id}
    for field in ("repo_url", "live_url", "attachment_url", "notes"):
        value = (payload.get(field) or "").strip()
        if value:
            row[field] = value

    try:
        client.table("workspace_submissions").insert(row).execute()
    except APIError as exc:
        if exc.code == "42501":
            raise SubmissionRejectedError(
                "This submission was rejected -- the workspace may no longer be active, or "
                "your previous attempt is still under review."
            ) from exc
        if exc.code == "23505":  # concurrent attempt won the race -- fine
            pass
        else:
            raise

    detail = get_workspace_assignment(client, student_id, workspace_id, assignment_id)
    if detail is None:  # pragma: no cover -- just submitted against our own workspace
        raise AssignmentNotFoundError(assignment_id)
    return detail


# ============================================================
# Phase 7 -- completion + certificate
# ============================================================
# internship_completions / internship_certificates (039) are ONLY ever
# written here, from the industry side, on EXPLICIT verification -- never
# automatically just because requirements happen to be met. "Requirements
# met" is always computed LIVE from program_assignments (is_required AND
# is_published) + workspace_submissions (an ACCEPTED attempt); nothing
# here stores a completion percentage as authoritative. The certificate's
# `details` snapshot is captured ONCE, at issuance, and never re-derived
# from a live join afterwards. NEVER touches applications.status,
# internship_programs' publication state, stipend_disbursements, a
# submission's content, or review history.

_COMPLETION_COLUMNS = (
    "id, workspace_id, verified_by, completion_status, outcome, summary, "
    "verified_at, created_at, updated_at"
)
_CERTIFICATE_COLUMNS = (
    "id, completion_id, workspace_id, student_id, industry_id, internship_id, "
    "certificate_number, details, issued_at, pdf_url, revoked_at, revoke_reason"
)
# A workspace must have been accepted at some point to be completable.
# PENDING_ACCEPTANCE (never started) and DECLINED/RESCINDED (soft-terminal,
# never active) can never be verified; COMPLETED is the idempotent no-op case.
_COMPLETABLE_STATES = frozenset({"ACCEPTED", "IN_PROGRESS", "COMPLETED"})


class RequirementsNotMetError(Exception):
    """Industry attempted to verify completion while one or more REQUIRED,
    published assignments still lack an ACCEPTED submission."""

    def __init__(self, outstanding: list[dict]) -> None:
        self.outstanding = outstanding
        titles = ", ".join(r["title"] for r in outstanding) or "(unknown)"
        super().__init__(f"Outstanding requirements: {titles}.")


class InvalidWorkspaceStateError(Exception):
    """The workspace has never been accepted, or is soft-terminal
    (DECLINED / RESCINDED) -- completion cannot be verified."""

    def __init__(self, current: str) -> None:
        self.current = current
        super().__init__(f"An internship workspace at '{current}' cannot be completed.")


def _required_assignments(client: Client, internship_id: str) -> list[dict]:
    """Every REQUIRED, PUBLISHED assignment in this internship's program --
    the same visibility rule the student-facing assignment list uses
    (037/038: a required-but-unpublished assignment is invisible to the
    student, so it can never gate completion). Empty if there is no
    program yet, or it defines no required assignments -- vacuously met,
    exactly like an internship program with no assignments at all."""
    program = _maybe_row(
        client.table("internship_programs")
        .select("id")
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )
    if program is None:
        return []
    response = (
        client.table("program_assignments")
        .select("id, title")
        .eq("program_id", program["id"])
        .eq("is_required", True)
        .eq("is_published", True)
        .execute()
    )
    return [dict(r) for r in (response.data or [])]


def _accepted_assignment_ids(client: Client, workspace_id: str) -> set[str]:
    """assignment_ids with an ACCEPTED attempt in this workspace. At most
    one ACCEPTED attempt can ever exist per assignment -- Phase 5/6 block a
    resubmission once an attempt is accepted -- so this is exactly the set
    of satisfied requirements. SUBMITTED / UNDER_REVIEW / REVISION_REQUESTED
    / REJECTED attempts never count."""
    response = (
        client.table("workspace_submissions")
        .select("assignment_id")
        .eq("workspace_id", workspace_id)
        .eq("submission_status", "ACCEPTED")
        .execute()
    )
    return {r["assignment_id"] for r in (response.data or [])}


def _compute_requirements(
    client: Client, internship_id: str, workspace_id: str
) -> tuple[list[dict], list[dict]]:
    """(required, outstanding) -- required is every REQUIRED+published
    assignment; outstanding is the subset with no ACCEPTED attempt yet."""
    required = _required_assignments(client, internship_id)
    accepted = _accepted_assignment_ids(client, workspace_id)
    outstanding = [r for r in required if r["id"] not in accepted]
    return required, outstanding


def _read_completion(client: Client, workspace_id: str) -> dict | None:
    return _maybe_row(
        client.table("internship_completions")
        .select(_COMPLETION_COLUMNS)
        .eq("workspace_id", workspace_id)
        .maybe_single()
        .execute()
    )


def _read_certificate(client: Client, completion_id: str) -> dict | None:
    return _maybe_row(
        client.table("internship_certificates")
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
        "internship_title": details.get("title"),
        "issued_at": row.get("issued_at"),
        "skills": details.get("skills") or [],
        "revoked": row.get("revoked_at") is not None,
    }


def _build_completion_summary(
    workspace_id: str,
    required: list[dict],
    outstanding: list[dict],
    completion: dict | None,
    certificate: dict | None,
    *,
    newly_verified: bool = False,
    student_id: str | None = None,
) -> dict:
    verified = completion is not None and completion.get("completion_status") == "COMPLETED"
    # Once verified, the requirements section is FROZEN to "fully
    # satisfied" -- never recomputed against a program that may have
    # changed SINCE verification (e.g. a new required assignment added
    # afterwards). Phase 7 already guarantees the completion/certificate
    # themselves stay frozen; without this, a later program edit would
    # make an already-certified workspace's own summary contradict its
    # own certificate (e.g. "Outstanding: ..." shown next to "Completed --
    # Certificate issued"). Nothing here re-derives PASS/the certificate --
    # only the live "outstanding" *display* is suppressed once verified.
    if verified:
        outstanding = []
        completed_count = len(required)
    else:
        completed_count = len(required) - len(outstanding)
    return {
        "workspace_id": workspace_id,
        "_student_id": student_id,
        "required_count": len(required),
        "completed_count": completed_count,
        "requirements_met": verified or not outstanding,
        "outstanding": [{"kind": "ASSIGNMENT", **r} for r in outstanding],
        "industry_verified": verified,
        "result": completion.get("outcome") if completion else None,
        "verified_at": completion.get("verified_at") if completion else None,
        "certificate": _shape_certificate(certificate) if certificate else None,
        # Internal only -- CompletionSummary has no such field, so it is
        # silently dropped from the API response. The route uses it to
        # decide whether THIS call is the one that should notify the
        # student, so a repeated idempotent verify never re-notifies.
        "_newly_verified": newly_verified,
    }


def get_student_completion(client: Client, student_id: str, workspace_id: str) -> dict | None:
    """The completion summary for the student's own workspace. None -> the
    route 404s."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        return None
    required, outstanding = _compute_requirements(
        client, workspace["internship_id"], workspace_id
    )
    completion = _read_completion(client, workspace_id)
    certificate = _read_certificate(client, completion["id"]) if completion else None
    return _build_completion_summary(workspace_id, required, outstanding, completion, certificate)


def get_industry_completion(client: Client, industry_id: str, workspace_id: str) -> dict | None:
    """The completion summary for one of the industry's own workspaces.
    None -> the route 404s."""
    workspace = _read_industry_workspace(client, industry_id, workspace_id)
    if workspace is None:
        return None
    required, outstanding = _compute_requirements(
        client, workspace["internship_id"], workspace_id
    )
    completion = _read_completion(client, workspace_id)
    certificate = _read_certificate(client, completion["id"]) if completion else None
    return _build_completion_summary(workspace_id, required, outstanding, completion, certificate)


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


def _internship_title(client: Client, internship_id: str) -> str | None:
    row = _maybe_row(
        client.table("internships")
        .select("title")
        .eq("id", internship_id)
        .maybe_single()
        .execute()
    )
    return row.get("title") if row else None


def _required_program_skills(client: Client, internship_id: str) -> list[dict]:
    program = _maybe_row(
        client.table("internship_programs")
        .select("id")
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )
    if program is None:
        return []
    response = (
        client.table("program_skills")
        .select("skill_id, requirement, skill:skills(name)")
        .eq("program_id", program["id"])
        .eq("requirement", "REQUIRED")
        .execute()
    )
    return [
        {"skill_id": r["skill_id"], "skill_name": (r.get("skill") or {}).get("name", "")}
        for r in (response.data or [])
    ]


def _build_certificate_snapshot(client: Client, workspace: dict) -> dict:
    """Captured ONCE, at issuance -- never re-derived from a live join
    afterwards (public.verify_internship_certificate prefers this exact
    snapshot over a live join for that reason). Only the fields the public
    verifier + the student/industry certificate view need; no email, no
    UUIDs, no submission/stipend data."""
    return {
        "student_name": _applicant_name(client, workspace.get("application_id")),
        "company_name": _company_name(client, workspace["industry_id"]),
        "title": _internship_title(client, workspace["internship_id"]),
        "skills": _required_program_skills(client, workspace["internship_id"]),
        "outcome": "PASS",
    }


def _get_or_create_completion(client: Client, workspace_id: str, summary: str | None) -> dict:
    """UNIQUE(workspace_id) is the idempotency guarantee: a concurrent
    verify racing this one gets 23505, and both converge on the SAME row."""
    payload: dict = {
        "workspace_id": workspace_id,
        "completion_status": "COMPLETED",
        "outcome": "PASS",
    }
    if summary and summary.strip():
        payload["summary"] = summary.strip()
    try:
        client.table("internship_completions").insert(payload).execute()
    except APIError as exc:
        if exc.code != "23505":
            raise
    existing = _read_completion(client, workspace_id)
    if existing is None:  # pragma: no cover -- just inserted (or lost a race to one that did)
        raise RuntimeError("internship_completions could not be read back after insert.")
    return existing


def _get_or_create_certificate(client: Client, completion: dict, workspace: dict) -> dict:
    """UNIQUE(completion_id) is the idempotency guarantee -- one
    certificate per completion, ever. certificate_number is never sent;
    the DB trigger (set_internship_certificate_derived_ids) mints it."""
    payload = {
        "completion_id": completion["id"],
        "details": _build_certificate_snapshot(client, workspace),
    }
    try:
        client.table("internship_certificates").insert(payload).execute()
    except APIError as exc:
        if exc.code != "23505":
            raise
    existing = _read_certificate(client, completion["id"])
    if existing is None:  # pragma: no cover -- just inserted (or lost a race to one that did)
        raise RuntimeError("internship_certificates could not be read back after insert.")
    return existing


def verify_workspace_completion(
    client: Client, industry_id: str, workspace_id: str, summary: str | None = None
) -> dict:
    """Industry explicitly verifies that every REQUIRED, published
    assignment has an ACCEPTED submission, then:
      1. records the completion (PASS) -- one row per workspace, ever
      2. issues the certificate -- one row per completion, ever, with a
         server-generated number (AIC-INT-{YYYY}-{base32}) and a frozen
         snapshot
      3. moves the workspace to COMPLETED.

    IDEMPOTENT: if this workspace was already verified, the existing
    completion + certificate are returned UNCHANGED -- a later program
    edit (e.g. a new required assignment added afterwards) can never
    retroactively revoke or alter an already-issued certificate. A
    concurrent first-time verify is still race-safe via the UNIQUE
    constraints in _get_or_create_completion / _get_or_create_certificate.
    """
    workspace = _read_industry_workspace(client, industry_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)

    existing_completion = _read_completion(client, workspace_id)
    if existing_completion is not None:
        certificate = _read_certificate(client, existing_completion["id"])
        required, outstanding = _compute_requirements(
            client, workspace["internship_id"], workspace_id
        )
        return _build_completion_summary(
            workspace_id, required, outstanding, existing_completion, certificate
        )

    if workspace["workspace_status"] not in _COMPLETABLE_STATES:
        raise InvalidWorkspaceStateError(workspace["workspace_status"])

    required, outstanding = _compute_requirements(
        client, workspace["internship_id"], workspace_id
    )
    if outstanding:
        raise RequirementsNotMetError(outstanding)

    completion = _get_or_create_completion(client, workspace_id, summary)
    certificate = _get_or_create_certificate(client, completion, workspace)

    if workspace["workspace_status"] != "COMPLETED":
        try:
            (
                client.table("internship_workspaces")
                .update({"workspace_status": "COMPLETED", "completed_at": _now_iso()})
                .eq("id", workspace_id)
                .execute()
            )
        except APIError:
            # The completion + certificate are already safely recorded --
            # the workspace-status cache update can simply be retried on
            # the next call (its own idempotent short-circuit above).
            pass

    return _build_completion_summary(
        workspace_id,
        required,
        outstanding,
        completion,
        certificate,
        newly_verified=True,
        student_id=workspace["student_id"],
    )


# ============================================================
# Phase 8 -- stipend record-keeping (stipend_disbursements)
# ============================================================
# RECORD-KEEPING ONLY -- no payment gateway, no bank/UPI integration, no
# real money movement anywhere here. "RELEASED" means the industry
# recorded that a disbursement happened; it never triggers one.
# Independent of completion/certificate: nothing here reads or writes
# internship_completions / internship_certificates, and nothing there
# reads or writes stipend_disbursements. NEVER touches applications.status,
# internships.status, workspace_status, a submission, or a review.
#
# Lifecycle (service-enforced; the DB trigger only blocks a workspace_id
# change and any further change once RELEASED/CANCELLED -- it does NOT by
# itself stop e.g. PENDING -> RELEASED or APPROVED -> PENDING, so the exact
# state machine below is this module's job, same as every other
# transition guard in this codebase):
#   create        (none) -> PENDING
#   approve       PENDING -> APPROVED
#   release       APPROVED -> RELEASED   (released_by/released_at: DB-forced)
#   cancel        PENDING -> CANCELLED
# RELEASED and CANCELLED are terminal. A repeat of an already-applied
# transition is REJECTED (409), not silently re-accepted -- unlike Phase 7
# certificate issuance, which is deliberately idempotent-success.

_STIPEND_COLUMNS = (
    "id, workspace_id, released_by, amount, currency, disbursement_status, "
    "reference, notes, released_at, created_at, updated_at"
)
_STIPEND_MUTABLE_FIELDS = frozenset({"amount", "currency", "reference", "notes"})


class StipendNotFoundError(Exception):
    """No stipend record exists yet for this (owned) workspace."""


class StipendExistsError(Exception):
    """A stipend record already exists for this workspace (UNIQUE(workspace_id))."""


class StipendImmutableError(Exception):
    """The stipend's financial details can only be edited while PENDING."""

    def __init__(self, current: str) -> None:
        self.current = current
        super().__init__(f"A '{current}' stipend record can no longer be edited.")


class InvalidStipendTransitionError(Exception):
    """The requested transition is not valid from the record's current
    status -- including re-applying a transition that already happened
    (e.g. APPROVED -> APPROVED), which is rejected, never a silent no-op."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"A '{current}' stipend record cannot be moved to '{target}'.")


class StipendRejectedError(Exception):
    """The database rejected a well-formed stipend write (42501) -- the
    caller does not own this workspace, or the record's state changed
    underneath us."""


def _read_stipend(client: Client, workspace_id: str) -> dict | None:
    return _maybe_row(
        client.table("stipend_disbursements")
        .select(_STIPEND_COLUMNS)
        .eq("workspace_id", workspace_id)
        .maybe_single()
        .execute()
    )


def _shape_stipend(row: dict) -> dict:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "amount": float(row["amount"]),
        "currency": row["currency"],
        "disbursement_status": row["disbursement_status"],
        "reference": row.get("reference"),
        "notes": row.get("notes"),
        "released_at": row.get("released_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _build_stipend_summary(
    workspace_id: str, stipend: dict | None, *, student_id: str | None = None
) -> dict:
    return {
        "workspace_id": workspace_id,
        "stipend": _shape_stipend(stipend) if stipend else None,
        # Internal only -- StipendSummary has no such field, so it is
        # silently dropped from the API response. The route uses it to
        # notify the right student after a transition.
        "_student_id": student_id,
    }


def get_student_stipend(client: Client, student_id: str, workspace_id: str) -> dict | None:
    """The stipend summary for the student's OWN workspace -- read-only,
    students never write a stipend record. None -> the route 404s (a
    workspace that is not theirs); `stipend: null` inside a 200 means the
    workspace is theirs but no record has been configured yet."""
    workspace = _read_own_workspace(client, student_id, workspace_id)
    if workspace is None:
        return None
    return _build_stipend_summary(
        workspace_id, _read_stipend(client, workspace_id), student_id=workspace["student_id"]
    )


def get_industry_stipend(client: Client, industry_id: str, workspace_id: str) -> dict | None:
    """Same as get_student_stipend, scoped to one of the industry's own
    workspaces."""
    workspace = _read_industry_workspace(client, industry_id, workspace_id)
    if workspace is None:
        return None
    return _build_stipend_summary(
        workspace_id, _read_stipend(client, workspace_id), student_id=workspace["student_id"]
    )


def create_stipend(client: Client, industry_id: str, workspace_id: str, data: dict) -> dict:
    """Configure the ONE stipend record for this workspace -- starts
    PENDING. `disbursement_status` is never accepted from the client.
    UNIQUE(workspace_id) is the idempotency guarantee: a concurrent create
    racing this one gets 23505, reported as StipendExistsError exactly
    like a pre-existing record -- never a duplicate."""
    workspace = _read_industry_workspace(client, industry_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    if _read_stipend(client, workspace_id) is not None:
        raise StipendExistsError(workspace_id)

    payload = {k: v for k, v in data.items() if k in _STIPEND_MUTABLE_FIELDS}
    payload["workspace_id"] = workspace_id
    try:
        client.table("stipend_disbursements").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise StipendExistsError(workspace_id) from exc
        raise

    stipend = _read_stipend(client, workspace_id)
    if stipend is None:  # pragma: no cover -- just inserted
        raise RuntimeError("stipend_disbursements could not be read back after insert.")
    return _build_stipend_summary(workspace_id, stipend, student_id=workspace["student_id"])


def update_stipend_details(
    client: Client, industry_id: str, workspace_id: str, data: dict
) -> dict:
    """Edit amount / currency / reference / notes -- allowed ONLY while
    PENDING. The DB trigger does not itself lock these fields once
    APPROVED/RELEASED/CANCELLED (only `disbursement_status`), so this
    module enforces the immutability boundary."""
    workspace = _read_industry_workspace(client, industry_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    existing = _read_stipend(client, workspace_id)
    if existing is None:
        raise StipendNotFoundError(workspace_id)
    if existing["disbursement_status"] != "PENDING":
        raise StipendImmutableError(existing["disbursement_status"])

    payload = {k: v for k, v in data.items() if k in _STIPEND_MUTABLE_FIELDS}
    if payload:
        (
            client.table("stipend_disbursements")
            .update(payload)
            .eq("workspace_id", workspace_id)
            .execute()
        )
    stipend = _read_stipend(client, workspace_id)
    return _build_stipend_summary(workspace_id, stipend, student_id=workspace["student_id"])


def _transition_stipend(
    client: Client, industry_id: str, workspace_id: str, *, frm: str, to: str
) -> dict:
    """Atomic PENDING/APPROVED-scoped compare-and-swap: the `.eq(
    "disbursement_status", frm)` on the UPDATE itself is what makes two
    concurrent transition requests race-safe -- only one can match and
    update a row at a time. A repeat call (already in `to`, or in any
    other state) is REJECTED, never a silent success."""
    workspace = _read_industry_workspace(client, industry_id, workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    existing = _read_stipend(client, workspace_id)
    if existing is None:
        raise StipendNotFoundError(workspace_id)
    if existing["disbursement_status"] != frm:
        raise InvalidStipendTransitionError(existing["disbursement_status"], to)

    try:
        response = (
            client.table("stipend_disbursements")
            .update({"disbursement_status": to})
            .eq("workspace_id", workspace_id)
            .eq("disbursement_status", frm)
            .execute()
        )
    except APIError as exc:
        if exc.code == "42501":
            raise StipendRejectedError(
                "The database rejected this transition -- you may not own this workspace."
            ) from exc
        raise

    if not response.data:
        # Lost a race: another request already moved this record between
        # our read and this write. Report the ACTUAL current state.
        current = _read_stipend(client, workspace_id)
        raise InvalidStipendTransitionError(
            current["disbursement_status"] if current else frm, to
        )

    stipend = _read_stipend(client, workspace_id)
    return _build_stipend_summary(workspace_id, stipend, student_id=workspace["student_id"])


def approve_stipend(client: Client, industry_id: str, workspace_id: str) -> dict:
    """PENDING -> APPROVED."""
    return _transition_stipend(client, industry_id, workspace_id, frm="PENDING", to="APPROVED")


def release_stipend(client: Client, industry_id: str, workspace_id: str) -> dict:
    """APPROVED -> RELEASED. `released_by` / `released_at` are DB-forced
    (enforce_stipend_disbursement_transitions) to the caller and now() --
    never accepted from the client. RECORD-KEEPING ONLY: this never moves
    money, calls a payment gateway, or contacts a bank/UPI/card network."""
    return _transition_stipend(client, industry_id, workspace_id, frm="APPROVED", to="RELEASED")


def cancel_stipend(client: Client, industry_id: str, workspace_id: str) -> dict:
    """PENDING -> CANCELLED. Terminal; matches the approved architecture's
    stated lifecycle exactly (no APPROVED -> CANCELLED path was asked
    for, so none is implemented)."""
    return _transition_stipend(client, industry_id, workspace_id, frm="PENDING", to="CANCELLED")
