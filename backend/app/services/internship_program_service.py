"""Business logic for INDUSTRY internship-program authoring
(database/migrations/037_internship_program.sql).

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- never get_supabase() /
service_role -- so RLS is the real access-control boundary:

* internship_programs: "Industry can view / create / update their own
  internship programs" -- scoped through
  `exists (internships i where i.id = internship_id AND
  i.industry_id = auth.uid() AND public.is_industry(auth.uid()))`.
* program_modules / module_items: routed through
  public.owns_internship_program(program_id) (037).
* program_skills: a single `for all` owner policy (037) -- so the
  replace-set (DELETE + INSERT) below is RLS-legal, same pattern as
  internship_service._replace_skills on internship_skills.

On top of RLS, every function re-verifies ownership in Python (a
`.eq("industry_id", industry_id)` read on `internships`, then the program
/ module / item lineage) -- defence in depth, matching every other
service module. A resource the caller does not own is reported as
"not found", never distinguished from one that does not exist.

Lifecycle: create -> DRAFT. `status` is NEVER writable through
update_program; publish_program is the only DRAFT -> PUBLISHED path.
There is no un-publish and no new status. Content (metadata / modules /
items / skills) stays editable after publish -- the RLS UPDATE policies
allow it and the student preview (Phase 3) reflects changes live, exactly
like industry_training.update_training.

Phase 5 adds program_assignments authoring (create / update / reorder;
no delete -- 037 grants no DELETE policy, hide via is_published) and a
READ-ONLY industry view of workspace_submissions (list + detail + attempt
history).

Phase 6 adds the industry review of a submission attempt:
  * start_review     SUBMITTED -> UNDER_REVIEW (submission_status cache)
  * review_submission SUBMITTED|UNDER_REVIEW -> ACCEPTED|REVISION_REQUESTED
    |REJECTED -- appends a submission_reviews row (the source of truth,
    with the DB-forced reviewer_id) AND updates the submission_status
    cache. The student's submission content is never rewritten.
It still NEVER writes internship_completions, internship_certificates or
stipend_disbursements, never changes an internship's status / work_mode,
its program's publication state, or an application.
"""

from datetime import UTC, datetime

from postgrest.exceptions import APIError
from supabase import Client

_PROGRAM_META = (
    "id, internship_id, title, summary, estimated_weeks, status, "
    "published_at, created_at, updated_at"
)
_MODULE_COLUMNS = "id, title, description, order_index, is_published"
_ITEM_COLUMNS = (
    "id, module_id, title, item_type, content_url, content_text, "
    "order_index, is_published"
)
_ASSIGNMENT_COLUMNS = (
    "id, module_id, program_id, title, description, instructions, assignment_type, "
    "is_required, is_published, order_index, due_offset_days, submission_kind, "
    "repo_required, live_url_expected, max_score, linked_skill_id, created_at, updated_at"
)
_SUBMISSION_COLUMNS = (
    "id, workspace_id, assignment_id, attempt_number, submission_status, "
    "repo_url, live_url, attachment_url, notes, submitted_at, created_at, updated_at"
)
# database/migrations/039_workspace_submissions_completion.sql -- submission_reviews
_REVIEW_COLUMNS = "id, submission_id, verdict, feedback, score, reviewer_id, created_at"
# A review may only be recorded while the attempt is still open. Once a
# terminal verdict lands, the submission_status cache leaves this set and
# the student must create a NEW attempt (Phase 5 resubmission rule).
_REVIEWABLE_STATES = frozenset({"SUBMITTED", "UNDER_REVIEW"})
_REVIEW_VERDICTS = frozenset({"ACCEPTED", "REVISION_REQUESTED", "REJECTED"})

_PROGRAM_EDITABLE = frozenset({"title", "summary", "estimated_weeks"})
_MODULE_EDITABLE = frozenset({"title", "description", "is_published"})
_ITEM_EDITABLE = frozenset({"title", "item_type", "content_url", "content_text", "is_published"})
_ASSIGNMENT_EDITABLE = frozenset(
    {
        "title",
        "description",
        "instructions",
        "assignment_type",
        "is_required",
        "is_published",
        "due_offset_days",
        "submission_kind",
        "repo_required",
        "live_url_expected",
        "max_score",
        "linked_skill_id",
    }
)
_REPO_KINDS = frozenset({"REPO", "MIXED"})

_TEXT_ITEM = "TEXT"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _maybe_row(response) -> dict | None:
    return response.data if response is not None else None


# ============================================================
# errors -- routes map these to specific HTTP status codes
# ============================================================


class InternshipNotFoundError(Exception):
    """The internship does not exist or is not owned by the caller."""


class ProgramNotFoundError(Exception):
    """No internship_program exists for this internship yet."""


class ProgramExistsError(Exception):
    """An internship_program already exists (UNIQUE(internship_id))."""


class ModuleNotFoundError(Exception):
    """No such module in this program."""


class ItemNotFoundError(Exception):
    """No such item in this module."""


class AssignmentNotFoundError(Exception):
    """No such assignment in this module."""


class InvalidAssignmentError(Exception):
    """The assignment config is inconsistent (e.g. repo_required with a
    non-REPO/MIXED submission_kind) or references a skill the program does
    not train."""


class SubmissionNotFoundError(Exception):
    """No such submission for one of the caller's own internships."""


class InvalidReviewError(Exception):
    """The review payload is malformed for this assignment (e.g. a score
    above the assignment's max_score, or a verdict outside the CHECK)."""


class InvalidReviewTransitionError(Exception):
    """The submission is not in a state that can be reviewed right now
    (only SUBMITTED / UNDER_REVIEW attempts are reviewable; once a verdict
    lands the student must submit a new attempt)."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"A '{current}' submission cannot be moved to '{target}'.")


class ReviewRejectedError(Exception):
    """The database rejected a well-formed review write (42501) -- the
    caller does not own the internship behind this submission, or its
    state changed underneath us."""


class InvalidItemError(Exception):
    """The item's content does not match its type (module_items CHECK)."""


class InvalidReorderError(Exception):
    """The reorder list is not exactly the current set of children."""


class InvalidProgramSkillError(Exception):
    """A skill_id is not one of the internship's own recruitment skills."""


class PublishValidationError(Exception):
    """The program is not structurally ready to publish."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Missing before publish: " + ", ".join(missing))


class InvalidStatusTransitionError(Exception):
    """publish is only valid from DRAFT."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an internship program from {current} to {target}.")


# ============================================================
# ownership + lineage helpers
# ============================================================


def _require_owned_internship(client: Client, industry_id: str, internship_id: str) -> dict:
    row = _maybe_row(
        client.table("internships")
        .select("id, title, status")
        .eq("id", internship_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise InternshipNotFoundError(internship_id)
    return row


def _read_program(client: Client, internship_id: str) -> dict | None:
    return _maybe_row(
        client.table("internship_programs")
        .select(_PROGRAM_META)
        .eq("internship_id", internship_id)
        .maybe_single()
        .execute()
    )


def _require_program(client: Client, industry_id: str, internship_id: str) -> tuple[dict, dict]:
    """(internship, program) -- raises InternshipNotFoundError /
    ProgramNotFoundError."""
    internship = _require_owned_internship(client, industry_id, internship_id)
    program = _read_program(client, internship_id)
    if program is None:
        raise ProgramNotFoundError(internship_id)
    return internship, program


def _require_module(client: Client, program_id: str, module_id: str) -> dict:
    row = _maybe_row(
        client.table("program_modules")
        .select(f"{_MODULE_COLUMNS}, program_id")
        .eq("id", module_id)
        .eq("program_id", program_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise ModuleNotFoundError(module_id)
    return row


def _require_item(client: Client, module_id: str, item_id: str) -> dict:
    row = _maybe_row(
        client.table("module_items")
        .select(_ITEM_COLUMNS)
        .eq("id", item_id)
        .eq("module_id", module_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise ItemNotFoundError(item_id)
    return row


def _require_assignment(client: Client, module_id: str, assignment_id: str) -> dict:
    row = _maybe_row(
        client.table("program_assignments")
        .select(_ASSIGNMENT_COLUMNS)
        .eq("id", assignment_id)
        .eq("module_id", module_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise AssignmentNotFoundError(assignment_id)
    return row


def _validate_assignment_config(client: Client, program_id: str, merged: dict) -> None:
    """`merged` is the row that WILL exist (existing + updates). Mirrors the
    program_assignments_repo_kind_consistent CHECK, and constrains
    linked_skill_id to a skill the program actually trains."""
    if merged.get("repo_required") and merged.get("submission_kind") not in _REPO_KINDS:
        raise InvalidAssignmentError(
            "An assignment that requires a repository must use the REPO or MIXED "
            "submission kind."
        )
    linked = merged.get("linked_skill_id")
    if linked:
        allowed = {
            row["skill_id"]
            for row in (
                client.table("program_skills")
                .select("skill_id")
                .eq("program_id", program_id)
                .execute()
                .data
                or []
            )
        }
        if str(linked) not in allowed:
            raise InvalidAssignmentError(
                "The linked skill must be one of the program's skills."
            )


def _validate_item_content(item_type: str, content_url: str | None, content_text: str | None) -> None:
    if item_type == _TEXT_ITEM:
        if not (content_text or "").strip():
            raise InvalidItemError("A TEXT item needs content text.")
    elif not (content_url or "").strip():
        raise InvalidItemError(f"A {item_type} item needs a URL.")


# ============================================================
# read -- the full authoring bundle
# ============================================================


def _shape_skill_link(link: dict) -> dict:
    skill = link.get("skill") or {}
    return {
        "skill_id": link["skill_id"],
        "skill_name": skill.get("name", ""),
        "requirement": link["requirement"],
    }


def _available_skills(client: Client, internship_id: str) -> list[dict]:
    response = (
        client.table("internship_skills")
        .select("skill_id, required_level, importance, skill:skills(name)")
        .eq("internship_id", internship_id)
        .execute()
    )
    rows = [
        {
            "skill_id": link["skill_id"],
            "skill_name": (link.get("skill") or {}).get("name", ""),
            "required_level": link.get("required_level"),
            "importance": link.get("importance"),
        }
        for link in (response.data or [])
    ]
    rows.sort(key=lambda s: s["skill_name"].lower())
    return rows


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
        "is_published": bool(row.get("is_published")),
        "order_index": row.get("order_index") or 0,
        "due_offset_days": row.get("due_offset_days"),
        "submission_kind": row.get("submission_kind") or "LINK",
        "repo_required": bool(row.get("repo_required")),
        "live_url_expected": bool(row.get("live_url_expected")),
        "max_score": float(row["max_score"]) if row.get("max_score") is not None else None,
        "linked_skill_id": row.get("linked_skill_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _load_modules(client: Client, program_id: str) -> list[dict]:
    response = (
        client.table("program_modules")
        .select(
            f"{_MODULE_COLUMNS}, module_items({_ITEM_COLUMNS}), "
            f"program_assignments({_ASSIGNMENT_COLUMNS})"
        )
        .eq("program_id", program_id)
        .order("order_index")
        .execute()
    )
    modules: list[dict] = []
    for module in response.data or []:
        items = sorted(
            (
                {
                    "id": item["id"],
                    "module_id": item["module_id"],
                    "title": item["title"],
                    "item_type": item["item_type"],
                    "content_url": item.get("content_url"),
                    "content_text": item.get("content_text"),
                    "order_index": item.get("order_index") or 0,
                    "is_published": bool(item.get("is_published")),
                }
                for item in (module.get("module_items") or [])
            ),
            key=lambda item: item["order_index"],
        )
        assignments = sorted(
            (_shape_assignment(a) for a in (module.get("program_assignments") or [])),
            key=lambda a: a["order_index"],
        )
        modules.append(
            {
                "id": module["id"],
                "title": module["title"],
                "description": module.get("description"),
                "order_index": module.get("order_index") or 0,
                "is_published": bool(module.get("is_published")),
                "items": items,
                "assignments": assignments,
            }
        )
    return modules


def _bundle(client: Client, internship: dict, program: dict | None, internship_id: str) -> dict:
    if program is None:
        return {
            "internship": internship,
            "program": None,
            "modules": [],
            "skills": [],
            "available_skills": _available_skills(client, internship_id),
        }
    skills_response = (
        client.table("program_skills")
        .select("skill_id, requirement, skill:skills(name)")
        .eq("program_id", program["id"])
        .execute()
    )
    skills = [_shape_skill_link(link) for link in (skills_response.data or [])]
    skills.sort(key=lambda s: (s["requirement"] != "REQUIRED", s["skill_name"].lower()))
    return {
        "internship": internship,
        "program": program,
        "modules": _load_modules(client, program["id"]),
        "skills": skills,
        "available_skills": _available_skills(client, internship_id),
    }


def get_program_bundle(client: Client, industry_id: str, internship_id: str) -> dict:
    """The authoring bundle for one owned internship. Raises
    InternshipNotFoundError if the internship is not the caller's."""
    internship = _require_owned_internship(client, industry_id, internship_id)
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


# ============================================================
# program metadata + lifecycle
# ============================================================


def create_program(client: Client, industry_id: str, internship_id: str, data: dict) -> dict:
    """Create the one DRAFT program for an owned internship. `status` is
    never accepted from the client. Raises ProgramExistsError when one
    already exists (checked here AND enforced by
    UNIQUE(internship_id))."""
    internship = _require_owned_internship(client, industry_id, internship_id)
    if _read_program(client, internship_id) is not None:
        raise ProgramExistsError(internship_id)

    payload = {k: v for k, v in data.items() if k in _PROGRAM_EDITABLE}
    payload["internship_id"] = internship_id
    payload["status"] = "DRAFT"
    try:
        client.table("internship_programs").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise ProgramExistsError(internship_id) from exc
        raise

    program = _read_program(client, internship_id)
    if program is None:  # pragma: no cover -- just inserted
        raise RuntimeError("internship_program could not be read back after create.")
    return _bundle(client, internship, program, internship_id)


def update_program(client: Client, industry_id: str, internship_id: str, data: dict) -> dict:
    """Edit program metadata (title / summary / estimated_weeks). `status`
    and `published_at` are never touched here -- content stays editable
    after publish."""
    internship, program = _require_program(client, industry_id, internship_id)
    payload = {k: v for k, v in data.items() if k in _PROGRAM_EDITABLE}
    if payload:
        (
            client.table("internship_programs")
            .update(payload)
            .eq("id", program["id"])
            .execute()
        )
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def publish_program(client: Client, industry_id: str, internship_id: str) -> dict:
    """DRAFT -> PUBLISHED. Minimal validation (the schema requires neither
    modules nor skills): a non-blank title. Only the owner can publish;
    RLS is the backstop. After this, the Phase 3 student preview can see
    the program."""
    internship, program = _require_program(client, industry_id, internship_id)

    if not (program.get("title") or "").strip():
        raise PublishValidationError(["title"])

    if program["status"] != "DRAFT":
        raise InvalidStatusTransitionError(program["status"], "PUBLISHED")

    (
        client.table("internship_programs")
        .update({"status": "PUBLISHED", "published_at": _now_iso()})
        .eq("id", program["id"])
        .execute()
    )
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


# ============================================================
# modules
# ============================================================


def _next_order_index(client: Client, table: str, fk_field: str, fk_value: str) -> int:
    response = (
        client.table(table)
        .select("order_index")
        .eq(fk_field, fk_value)
        .order("order_index", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return (rows[0]["order_index"] + 1) if rows else 0


def create_module(client: Client, industry_id: str, internship_id: str, data: dict) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    payload = {k: v for k, v in data.items() if k in _MODULE_EDITABLE}
    payload["program_id"] = program["id"]
    payload["order_index"] = _next_order_index(
        client, "program_modules", "program_id", program["id"]
    )
    client.table("program_modules").insert(payload).execute()
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def update_module(
    client: Client, industry_id: str, internship_id: str, module_id: str, data: dict
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)
    payload = {k: v for k, v in data.items() if k in _MODULE_EDITABLE}
    if payload:
        (
            client.table("program_modules")
            .update(payload)
            .eq("id", module_id)
            .eq("program_id", program["id"])
            .execute()
        )
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def reorder_modules(
    client: Client, industry_id: str, internship_id: str, ordered_ids: list[str]
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    existing = {
        row["id"]
        for row in (
            client.table("program_modules")
            .select("id")
            .eq("program_id", program["id"])
            .execute()
            .data
            or []
        )
    }
    wanted = [str(mid) for mid in ordered_ids]
    if set(wanted) != existing or len(wanted) != len(set(wanted)):
        raise InvalidReorderError(
            "The reorder list must contain exactly the current modules, once each."
        )
    for index, module_id in enumerate(wanted):
        (
            client.table("program_modules")
            .update({"order_index": index})
            .eq("id", module_id)
            .eq("program_id", program["id"])
            .execute()
        )
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


# ============================================================
# module items
# ============================================================


def create_item(
    client: Client, industry_id: str, internship_id: str, module_id: str, data: dict
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)

    payload = {k: v for k, v in data.items() if k in _ITEM_EDITABLE}
    _validate_item_content(
        payload["item_type"], payload.get("content_url"), payload.get("content_text")
    )
    payload["module_id"] = module_id
    payload["order_index"] = _next_order_index(client, "module_items", "module_id", module_id)
    try:
        client.table("module_items").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23514":  # module_items_content_matches_type
            raise InvalidItemError("The item's content does not match its type.") from exc
        raise
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def update_item(
    client: Client,
    industry_id: str,
    internship_id: str,
    module_id: str,
    item_id: str,
    data: dict,
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)
    existing = _require_item(client, module_id, item_id)

    payload = {k: v for k, v in data.items() if k in _ITEM_EDITABLE}
    if payload:
        merged = {**existing, **payload}
        _validate_item_content(
            merged["item_type"], merged.get("content_url"), merged.get("content_text")
        )
        try:
            (
                client.table("module_items")
                .update(payload)
                .eq("id", item_id)
                .eq("module_id", module_id)
                .execute()
            )
        except APIError as exc:
            if exc.code == "23514":
                raise InvalidItemError("The item's content does not match its type.") from exc
            raise
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def reorder_items(
    client: Client,
    industry_id: str,
    internship_id: str,
    module_id: str,
    ordered_ids: list[str],
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)
    existing = {
        row["id"]
        for row in (
            client.table("module_items")
            .select("id")
            .eq("module_id", module_id)
            .execute()
            .data
            or []
        )
    }
    wanted = [str(iid) for iid in ordered_ids]
    if set(wanted) != existing or len(wanted) != len(set(wanted)):
        raise InvalidReorderError(
            "The reorder list must contain exactly the current items, once each."
        )
    for index, item_id in enumerate(wanted):
        (
            client.table("module_items")
            .update({"order_index": index})
            .eq("id", item_id)
            .eq("module_id", module_id)
            .execute()
        )
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


# ============================================================
# program skills (replace-set, scoped to internship_skills)
# ============================================================


def set_program_skills(
    client: Client, industry_id: str, internship_id: str, skills: list[dict]
) -> dict:
    """Replace-set program_skills. Every skill_id must be one of the
    internship's own recruitment skills (internship_skills) -- an
    arbitrary catalog id or another internship's skill is rejected. Does
    not modify internship_skills or program_skills' referenced skills."""
    internship, program = _require_program(client, industry_id, internship_id)

    # Dedupe, last requirement wins.
    by_id: dict[str, str] = {}
    for entry in skills:
        by_id[str(entry["skill_id"])] = entry.get("requirement", "REQUIRED")

    allowed = {
        row["skill_id"]
        for row in (
            client.table("internship_skills")
            .select("skill_id")
            .eq("internship_id", internship_id)
            .execute()
            .data
            or []
        )
    }
    if any(skill_id not in allowed for skill_id in by_id):
        raise InvalidProgramSkillError(
            "A skill is not one of this internship's required skills. Add it to the "
            "internship first."
        )

    client.table("program_skills").delete().eq("program_id", program["id"]).execute()
    if by_id:
        client.table("program_skills").insert(
            [
                {"program_id": program["id"], "skill_id": skill_id, "requirement": requirement}
                for skill_id, requirement in by_id.items()
            ]
        ).execute()

    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


# ============================================================
# Phase 5 -- assignments (within a module)
# ============================================================


def create_assignment(
    client: Client, industry_id: str, internship_id: str, module_id: str, data: dict
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)

    payload = {k: v for k, v in data.items() if k in _ASSIGNMENT_EDITABLE}
    _validate_assignment_config(client, program["id"], payload)
    payload["module_id"] = module_id
    payload["order_index"] = _next_order_index(
        client, "program_assignments", "module_id", module_id
    )
    try:
        client.table("program_assignments").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23514":  # program_assignments_repo_kind_consistent
            raise InvalidAssignmentError(
                "The assignment's repository / submission-kind settings are inconsistent."
            ) from exc
        raise
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def update_assignment(
    client: Client,
    industry_id: str,
    internship_id: str,
    module_id: str,
    assignment_id: str,
    data: dict,
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)
    existing = _require_assignment(client, module_id, assignment_id)

    payload = {k: v for k, v in data.items() if k in _ASSIGNMENT_EDITABLE}
    if payload:
        merged = {**existing, **payload}
        _validate_assignment_config(client, program["id"], merged)
        try:
            (
                client.table("program_assignments")
                .update(payload)
                .eq("id", assignment_id)
                .eq("module_id", module_id)
                .execute()
            )
        except APIError as exc:
            if exc.code == "23514":
                raise InvalidAssignmentError(
                    "The assignment's repository / submission-kind settings are inconsistent."
                ) from exc
            raise
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


def reorder_assignments(
    client: Client,
    industry_id: str,
    internship_id: str,
    module_id: str,
    ordered_ids: list[str],
) -> dict:
    internship, program = _require_program(client, industry_id, internship_id)
    _require_module(client, program["id"], module_id)
    existing = {
        row["id"]
        for row in (
            client.table("program_assignments")
            .select("id")
            .eq("module_id", module_id)
            .execute()
            .data
            or []
        )
    }
    wanted = [str(aid) for aid in ordered_ids]
    if set(wanted) != existing or len(wanted) != len(set(wanted)):
        raise InvalidReorderError(
            "The reorder list must contain exactly the current assignments, once each."
        )
    for index, assignment_id in enumerate(wanted):
        (
            client.table("program_assignments")
            .update({"order_index": index})
            .eq("id", assignment_id)
            .eq("module_id", module_id)
            .execute()
        )
    program = _read_program(client, internship_id)
    return _bundle(client, internship, program, internship_id)


# ============================================================
# Phase 5 / 6 -- industry view + review of workspace_submissions
# ============================================================
# NEVER writes internship_completions, internship_certificates or
# stipend_disbursements, and never changes an application or a program's
# publication state. Phase 6 DOES write submission_reviews (append-only)
# and the workspace_submissions.submission_status cache.

_SUBMISSION_EMBED = (
    f"{_SUBMISSION_COLUMNS}, "
    "workspace:internship_workspaces!inner("
    "id, internship_id, application_id, industry_id, student_id), "
    "assignment:program_assignments(id, title, max_score, module_id, "
    "module:program_modules(id, title)), "
    f"submission_reviews({_REVIEW_COLUMNS})"
)
_ATTEMPT_EMBED = f"{_SUBMISSION_COLUMNS}, submission_reviews({_REVIEW_COLUMNS})"


def _applicant_names(client: Client, application_ids: list[str]) -> dict[str, str | None]:
    """Resolve application_id -> student display name via the
    public.application_applicant_names RPC (036) -- SECURITY DEFINER,
    scoped to the caller's own postings. Best-effort: a failure just
    leaves names as None (no service_role, never fatal)."""
    ids = sorted({a for a in application_ids if a})
    if not ids:
        return {}
    try:
        response = client.rpc(
            "application_applicant_names", {"application_ids": ids}
        ).execute()
        return {r["application_id"]: r.get("student_name") for r in (response.data or [])}
    except Exception:  # noqa: BLE001 -- names are optional enrichment, never fatal
        return {}


def _shape_review(row: dict) -> dict:
    return {
        "id": row["id"],
        "verdict": row["verdict"],
        "feedback": row.get("feedback"),
        "score": float(row["score"]) if row.get("score") is not None else None,
        "reviewer_id": row.get("reviewer_id"),
        "created_at": row.get("created_at"),
    }


def _shape_submission(row: dict) -> dict:
    reviews = sorted(
        (_shape_review(r) for r in (row.get("submission_reviews") or [])),
        key=lambda r: r.get("created_at") or "",
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


def list_submissions(
    client: Client,
    industry_id: str,
    internship_id: str,
    *,
    assignment_id: str | None = None,
    workspace_id: str | None = None,
) -> list[dict]:
    """Every submission attempt for the caller's own internship, newest
    first. RLS ("Industry can view submissions for their own internships")
    + the !inner embed filter on internship_id / industry_id all scope
    this to the caller. READ-ONLY."""
    _require_owned_internship(client, industry_id, internship_id)

    query = (
        client.table("workspace_submissions")
        .select(_SUBMISSION_EMBED)
        .eq("workspace.internship_id", internship_id)
        .eq("workspace.industry_id", industry_id)
    )
    if assignment_id:
        query = query.eq("assignment_id", assignment_id)
    if workspace_id:
        query = query.eq("workspace_id", workspace_id)
    rows = query.order("submitted_at", desc=True).execute().data or []

    names = _applicant_names(
        client, [(r.get("workspace") or {}).get("application_id") for r in rows]
    )
    counts: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r["workspace_id"], r["assignment_id"])
        counts[key] = counts.get(key, 0) + 1

    shaped: list[dict] = []
    for r in rows:
        assignment = r.get("assignment") or {}
        module = assignment.get("module") or {}
        base = _shape_submission(r)
        base["student_name"] = names.get((r.get("workspace") or {}).get("application_id"))
        base["assignment_title"] = assignment.get("title")
        base["module_title"] = module.get("title")
        base["attempt_count"] = counts.get((r["workspace_id"], r["assignment_id"]), 1)
        shaped.append(base)
    return shaped


def get_submission_detail(
    client: Client, industry_id: str, internship_id: str, submission_id: str
) -> dict | None:
    """One submission + every attempt for the same (workspace, assignment).
    None -> the route 404s. READ-ONLY."""
    _require_owned_internship(client, industry_id, internship_id)

    row = _maybe_row(
        client.table("workspace_submissions")
        .select(_SUBMISSION_EMBED)
        .eq("id", submission_id)
        .eq("workspace.internship_id", internship_id)
        .eq("workspace.industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        return None

    assignment = row.get("assignment") or {}
    module = assignment.get("module") or {}
    application_id = (row.get("workspace") or {}).get("application_id")
    names = _applicant_names(client, [application_id] if application_id else [])

    attempts = (
        client.table("workspace_submissions")
        .select(_ATTEMPT_EMBED)
        .eq("workspace_id", row["workspace_id"])
        .eq("assignment_id", row["assignment_id"])
        .order("attempt_number", desc=True)
        .execute()
        .data
        or []
    )
    workspace = row.get("workspace") or {}
    return {
        "submission": _shape_submission(row),
        "student_name": names.get(application_id),
        "assignment_title": assignment.get("title"),
        "module_title": module.get("title"),
        "assignment_max_score": (
            float(assignment["max_score"]) if assignment.get("max_score") is not None else None
        ),
        "attempts": [_shape_submission(a) for a in attempts],
        # internal only -- the response schema drops these; the route uses
        # them for the student notification and nothing else.
        "student_id": workspace.get("student_id"),
        "workspace_id": row["workspace_id"],
    }


# ============================================================
# Phase 6 -- industry review of a submission attempt
# ============================================================


def _load_reviewable_submission(
    client: Client, industry_id: str, internship_id: str, submission_id: str
) -> dict:
    """The one submission attempt, scoped to the caller's own internship
    (RLS + the !inner workspace embed filters). Raises
    SubmissionNotFoundError -- a foreign / missing submission is a 404."""
    _require_owned_internship(client, industry_id, internship_id)
    row = _maybe_row(
        client.table("workspace_submissions")
        .select(_SUBMISSION_EMBED)
        .eq("id", submission_id)
        .eq("workspace.internship_id", internship_id)
        .eq("workspace.industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise SubmissionNotFoundError(submission_id)
    return row


def start_review(
    client: Client, industry_id: str, internship_id: str, submission_id: str
) -> dict:
    """SUBMITTED -> UNDER_REVIEW on the submission_status cache. Idempotent
    only in the sense that an already-UNDER_REVIEW attempt is a no-op
    error (409) -- there is no reverse transition. Writes NO
    submission_reviews row (that is the verdict step)."""
    row = _load_reviewable_submission(client, industry_id, internship_id, submission_id)
    current = row["submission_status"]
    if current != "SUBMITTED":
        raise InvalidReviewTransitionError(current, "UNDER_REVIEW")

    try:
        (
            client.table("workspace_submissions")
            .update({"submission_status": "UNDER_REVIEW"})
            .eq("id", submission_id)
            .execute()
        )
    except APIError as exc:
        if exc.code == "42501":
            raise ReviewRejectedError(
                "The database rejected the review -- you may not own this internship."
            ) from exc
        raise
    return get_submission_detail(client, industry_id, internship_id, submission_id)


def review_submission(
    client: Client,
    industry_id: str,
    internship_id: str,
    submission_id: str,
    data: dict,
) -> dict:
    """Record a terminal verdict (ACCEPTED / REVISION_REQUESTED /
    REJECTED). Appends a submission_reviews row -- the SOURCE OF TRUTH,
    with reviewer_id forced to the caller by the DB trigger -- then
    updates the submission_status cache to match. The student's submission
    row content is never touched. NEVER writes internship_completions /
    internship_certificates / stipend_disbursements and never changes an
    application or the program's publication state."""
    verdict = data["verdict"]
    if verdict not in _REVIEW_VERDICTS:  # pragma: no cover -- schema-guarded
        raise InvalidReviewError(f"Unknown review verdict {verdict!r}.")

    row = _load_reviewable_submission(client, industry_id, internship_id, submission_id)
    current = row["submission_status"]
    if current not in _REVIEWABLE_STATES:
        raise InvalidReviewTransitionError(current, verdict)

    assignment = row.get("assignment") or {}
    max_score = assignment.get("max_score")
    score = data.get("score")
    if score is not None:
        if score < 0:
            raise InvalidReviewError("A score cannot be negative.")
        if max_score is not None and score > float(max_score):
            raise InvalidReviewError(
                f"The score cannot exceed this assignment's maximum of {float(max_score)}."
            )

    review_row: dict = {"submission_id": submission_id, "verdict": verdict}
    feedback = (data.get("feedback") or "").strip()
    if feedback:
        review_row["feedback"] = feedback
    if score is not None:
        review_row["score"] = score

    try:
        client.table("submission_reviews").insert(review_row).execute()
    except APIError as exc:
        if exc.code == "42501":
            raise ReviewRejectedError(
                "The database rejected the review -- you may not own this internship, "
                "or the submission changed state."
            ) from exc
        if exc.code == "23514":
            raise InvalidReviewError("That review value is not allowed.") from exc
        raise

    # Denormalized cache on the attempt. The prevent_workspace_submission_
    # content_change trigger allows exactly this one column to change.
    try:
        (
            client.table("workspace_submissions")
            .update({"submission_status": verdict})
            .eq("id", submission_id)
            .execute()
        )
    except APIError as exc:
        if exc.code == "42501":
            raise ReviewRejectedError(
                "The review was recorded but the submission status could not be updated."
            ) from exc
        raise

    return get_submission_detail(client, industry_id, internship_id, submission_id)
