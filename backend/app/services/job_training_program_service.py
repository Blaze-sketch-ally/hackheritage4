"""Business logic for INDUSTRY Job Training program authoring
(database/migrations/040_job_training.sql).

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- never get_supabase() /
service_role -- so RLS is the real access-control boundary:

* job_programs: "Industry can view / create / update their own job
  programs" -- scoped through
  `exists (jobs j where j.id = job_id AND j.industry_id = auth.uid()
  AND public.is_industry(auth.uid()))`.
* job_program_modules / job_program_items / job_program_assignments:
  routed through public.owns_job_program(program_id) (040).
* job_program_skills: a single `for all` owner policy (040) -- so the
  replace-set (DELETE + INSERT) below is RLS-legal, the same pattern as
  internship_program_service.set_program_skills on program_skills.

On top of RLS, every function re-verifies ownership in Python (a
`.eq("industry_id", industry_id)` read on `jobs`, then the program /
module / item / assignment lineage) -- defence in depth, matching every
other service module. A resource the caller does not own is reported as
"not found", never distinguished from one that does not exist.

Lifecycle: create -> DRAFT. `status` is NEVER writable through
update_program. publish_program is the only DRAFT -> PUBLISHED path (with
a structural readiness check); unpublish_program is the only PUBLISHED ->
DRAFT path. No ARCHIVED transition here, no new status. Content (metadata
/ modules / items / skills / assignments) stays editable after publish --
the RLS UPDATE policies allow it and the future student preview reflects
changes live, exactly like internship_program_service.

J2 scope stops at authoring. This module NEVER writes
job_training_enrollments, and has no concept of completion, certificates,
progress, notifications, or student access. Publishing a program does not
enrol anyone -- student access remains gated by
public.student_can_access_job_program (an enrollment + a PUBLISHED
program), which nothing here creates.
"""

from datetime import UTC, datetime

from postgrest.exceptions import APIError
from supabase import Client

_PROGRAM_META = (
    "id, job_id, title, summary, estimated_weeks, status, "
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


class JobNotFoundError(Exception):
    """The job does not exist or is not owned by the caller."""


class ProgramNotFoundError(Exception):
    """No job_program exists for this job yet."""


class ProgramExistsError(Exception):
    """A job_program already exists (UNIQUE(job_id))."""


class ModuleNotFoundError(Exception):
    """No such module in this program."""


class ItemNotFoundError(Exception):
    """No such item in this module."""


class AssignmentNotFoundError(Exception):
    """No such assignment in this module."""


class InvalidItemError(Exception):
    """The item's content does not match its type (job_program_items CHECK)."""


class InvalidReorderError(Exception):
    """The reorder list is not exactly the current set of children."""


class InvalidProgramSkillError(Exception):
    """A skill_id is not a real skill in the canonical `skills` catalog."""


class InvalidAssignmentError(Exception):
    """The assignment config is inconsistent (e.g. repo_required with a
    non-REPO/MIXED submission_kind) or references a skill the program does
    not train."""


class PublishValidationError(Exception):
    """The program is not structurally ready to publish."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Missing before publish: " + ", ".join(missing))


class InvalidStatusTransitionError(Exception):
    """publish is only valid from DRAFT; unpublish only from PUBLISHED."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move a job program from {current} to {target}.")


# ============================================================
# ownership + lineage helpers
# ============================================================


def _require_owned_job(client: Client, industry_id: str, job_id: str) -> dict:
    row = _maybe_row(
        client.table("jobs")
        .select("id, title, status")
        .eq("id", job_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise JobNotFoundError(job_id)
    return row


def _read_program(client: Client, job_id: str) -> dict | None:
    return _maybe_row(
        client.table("job_programs")
        .select(_PROGRAM_META)
        .eq("job_id", job_id)
        .maybe_single()
        .execute()
    )


def _require_program(client: Client, industry_id: str, job_id: str) -> tuple[dict, dict]:
    """(job, program) -- raises JobNotFoundError / ProgramNotFoundError."""
    job = _require_owned_job(client, industry_id, job_id)
    program = _read_program(client, job_id)
    if program is None:
        raise ProgramNotFoundError(job_id)
    return job, program


def _require_module(client: Client, program_id: str, module_id: str) -> dict:
    row = _maybe_row(
        client.table("job_program_modules")
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
        client.table("job_program_items")
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
        client.table("job_program_assignments")
        .select(_ASSIGNMENT_COLUMNS)
        .eq("id", assignment_id)
        .eq("module_id", module_id)
        .maybe_single()
        .execute()
    )
    if row is None:
        raise AssignmentNotFoundError(assignment_id)
    return row


def _known_skill_ids(client: Client, skill_ids: set[str]) -> set[str]:
    """The subset of `skill_ids` that exist in the canonical `skills`
    catalog (RLS: active skills are readable by any authenticated user)."""
    if not skill_ids:
        return set()
    rows = (
        client.table("skills")
        .select("id")
        .in_("id", sorted(skill_ids))
        .execute()
        .data
        or []
    )
    return {row["id"] for row in rows}


def _program_skill_ids(client: Client, program_id: str) -> set[str]:
    return {
        row["skill_id"]
        for row in (
            client.table("job_program_skills")
            .select("skill_id")
            .eq("program_id", program_id)
            .execute()
            .data
            or []
        )
    }


def _validate_assignment_config(client: Client, program_id: str, merged: dict) -> None:
    """`merged` is the row that WILL exist (existing + updates). Mirrors the
    job_program_assignments_repo_kind_consistent CHECK, and constrains
    linked_skill_id to a skill the program actually trains."""
    if merged.get("repo_required") and merged.get("submission_kind") not in _REPO_KINDS:
        raise InvalidAssignmentError(
            "An assignment that requires a repository must use the REPO or MIXED "
            "submission kind."
        )
    linked = merged.get("linked_skill_id")
    if linked and str(linked) not in _program_skill_ids(client, program_id):
        raise InvalidAssignmentError(
            "The linked skill must be one of the program's skills."
        )


def _validate_item_content(
    item_type: str, content_url: str | None, content_text: str | None
) -> None:
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


def _available_skills(client: Client, job_id: str) -> list[dict]:
    response = (
        client.table("job_skills")
        .select("skill_id, required_level, importance, skill:skills(name)")
        .eq("job_id", job_id)
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
        client.table("job_program_modules")
        .select(
            f"{_MODULE_COLUMNS}, job_program_items({_ITEM_COLUMNS}), "
            f"job_program_assignments({_ASSIGNMENT_COLUMNS})"
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
                for item in (module.get("job_program_items") or [])
            ),
            key=lambda item: item["order_index"],
        )
        assignments = sorted(
            (_shape_assignment(a) for a in (module.get("job_program_assignments") or [])),
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


def _bundle(client: Client, job: dict, program: dict | None, job_id: str) -> dict:
    if program is None:
        return {
            "job": job,
            "program": None,
            "modules": [],
            "skills": [],
            "available_skills": _available_skills(client, job_id),
        }
    skills_response = (
        client.table("job_program_skills")
        .select("skill_id, requirement, skill:skills(name)")
        .eq("program_id", program["id"])
        .execute()
    )
    skills = [_shape_skill_link(link) for link in (skills_response.data or [])]
    skills.sort(key=lambda s: (s["requirement"] != "REQUIRED", s["skill_name"].lower()))
    return {
        "job": job,
        "program": program,
        "modules": _load_modules(client, program["id"]),
        "skills": skills,
        "available_skills": _available_skills(client, job_id),
    }


def get_program_bundle(client: Client, industry_id: str, job_id: str) -> dict:
    """The authoring bundle for one owned job. Raises JobNotFoundError if
    the job is not the caller's."""
    job = _require_owned_job(client, industry_id, job_id)
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


# ============================================================
# program metadata + lifecycle
# ============================================================


def create_program(client: Client, industry_id: str, job_id: str, data: dict) -> dict:
    """Create the one DRAFT program for an owned job. `status` is never
    accepted from the client. Raises ProgramExistsError when one already
    exists (checked here AND enforced by UNIQUE(job_id))."""
    job = _require_owned_job(client, industry_id, job_id)
    if _read_program(client, job_id) is not None:
        raise ProgramExistsError(job_id)

    payload = {k: v for k, v in data.items() if k in _PROGRAM_EDITABLE}
    payload["job_id"] = job_id
    payload["status"] = "DRAFT"
    try:
        client.table("job_programs").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":  # job_programs_one_per_job
            raise ProgramExistsError(job_id) from exc
        raise

    program = _read_program(client, job_id)
    if program is None:  # pragma: no cover -- just inserted
        raise RuntimeError("job_program could not be read back after create.")
    return _bundle(client, job, program, job_id)


def update_program(client: Client, industry_id: str, job_id: str, data: dict) -> dict:
    """Edit program metadata (title / summary / estimated_weeks). `status`,
    `published_at` and `job_id` are never touched here -- job association
    is immutable, and content stays editable after publish."""
    job, program = _require_program(client, industry_id, job_id)
    payload = {k: v for k, v in data.items() if k in _PROGRAM_EDITABLE}
    if payload:
        (
            client.table("job_programs")
            .update(payload)
            .eq("id", program["id"])
            .execute()
        )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def _publish_readiness(client: Client, program_id: str) -> list[str]:
    """What the program still needs before it can go PUBLISHED. A Job
    Training program is only usable to a selected candidate if it has real
    content, so this is stricter than the internship-program check (which
    requires only a title):
      * a non-blank title (checked by the caller from the program row),
      * at least one module,
      * at least one PUBLISHED module,
      * that published module carries at least one published learning item
        OR one published assignment.
    """
    modules = (
        client.table("job_program_modules")
        .select("id, is_published")
        .eq("program_id", program_id)
        .execute()
        .data
        or []
    )
    if not modules:
        return ["at least one module"]

    published_module_ids = [m["id"] for m in modules if m.get("is_published")]
    if not published_module_ids:
        return ["at least one published module"]

    items = (
        client.table("job_program_items")
        .select("module_id, is_published")
        .in_("module_id", published_module_ids)
        .execute()
        .data
        or []
    )
    assignments = (
        client.table("job_program_assignments")
        .select("module_id, is_published")
        .in_("module_id", published_module_ids)
        .execute()
        .data
        or []
    )
    has_content = any(i.get("is_published") for i in items) or any(
        a.get("is_published") for a in assignments
    )
    if not has_content:
        return ["at least one published learning item or assignment in a published module"]
    return []


def publish_program(client: Client, industry_id: str, job_id: str) -> dict:
    """DRAFT -> PUBLISHED, only when the program is structurally ready
    (see _publish_readiness). Only the owner can publish; RLS is the
    backstop. Publishing enrols NOBODY -- student access still needs a
    job_training_enrollment, which this phase never creates."""
    job, program = _require_program(client, industry_id, job_id)

    missing: list[str] = []
    if not (program.get("title") or "").strip():
        missing.append("a title")
    missing.extend(_publish_readiness(client, program["id"]))
    if missing:
        raise PublishValidationError(missing)

    if program["status"] != "DRAFT":
        raise InvalidStatusTransitionError(program["status"], "PUBLISHED")

    (
        client.table("job_programs")
        .update({"status": "PUBLISHED", "published_at": _now_iso()})
        .eq("id", program["id"])
        .execute()
    )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def unpublish_program(client: Client, industry_id: str, job_id: str) -> dict:
    """PUBLISHED -> DRAFT. Uses only the J1 status vocabulary (no new
    state). Existing job_training_enrollments are left untouched; a
    DRAFT program simply fails public.student_can_access_job_program's
    `prog.status = 'PUBLISHED'` check, so students lose preview access
    until it is published again. `published_at` is left as the record of
    when it last went live."""
    job, program = _require_program(client, industry_id, job_id)
    if program["status"] != "PUBLISHED":
        raise InvalidStatusTransitionError(program["status"], "DRAFT")
    (
        client.table("job_programs")
        .update({"status": "DRAFT"})
        .eq("id", program["id"])
        .execute()
    )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


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


def create_module(client: Client, industry_id: str, job_id: str, data: dict) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    payload = {k: v for k, v in data.items() if k in _MODULE_EDITABLE}
    payload["program_id"] = program["id"]
    payload["order_index"] = _next_order_index(
        client, "job_program_modules", "program_id", program["id"]
    )
    client.table("job_program_modules").insert(payload).execute()
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def update_module(
    client: Client, industry_id: str, job_id: str, module_id: str, data: dict
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    _require_module(client, program["id"], module_id)
    payload = {k: v for k, v in data.items() if k in _MODULE_EDITABLE}
    if payload:
        (
            client.table("job_program_modules")
            .update(payload)
            .eq("id", module_id)
            .eq("program_id", program["id"])
            .execute()
        )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def reorder_modules(
    client: Client, industry_id: str, job_id: str, ordered_ids: list[str]
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    existing = {
        row["id"]
        for row in (
            client.table("job_program_modules")
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
            client.table("job_program_modules")
            .update({"order_index": index})
            .eq("id", module_id)
            .eq("program_id", program["id"])
            .execute()
        )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


# ============================================================
# module items
# ============================================================


def create_item(
    client: Client, industry_id: str, job_id: str, module_id: str, data: dict
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    _require_module(client, program["id"], module_id)

    payload = {k: v for k, v in data.items() if k in _ITEM_EDITABLE}
    _validate_item_content(
        payload["item_type"], payload.get("content_url"), payload.get("content_text")
    )
    payload["module_id"] = module_id
    payload["order_index"] = _next_order_index(
        client, "job_program_items", "module_id", module_id
    )
    try:
        client.table("job_program_items").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23514":  # job_program_items_content_matches_type
            raise InvalidItemError("The item's content does not match its type.") from exc
        raise
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def update_item(
    client: Client,
    industry_id: str,
    job_id: str,
    module_id: str,
    item_id: str,
    data: dict,
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
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
                client.table("job_program_items")
                .update(payload)
                .eq("id", item_id)
                .eq("module_id", module_id)
                .execute()
            )
        except APIError as exc:
            if exc.code == "23514":
                raise InvalidItemError("The item's content does not match its type.") from exc
            raise
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def reorder_items(
    client: Client,
    industry_id: str,
    job_id: str,
    module_id: str,
    ordered_ids: list[str],
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    _require_module(client, program["id"], module_id)
    existing = {
        row["id"]
        for row in (
            client.table("job_program_items")
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
            client.table("job_program_items")
            .update({"order_index": index})
            .eq("id", item_id)
            .eq("module_id", module_id)
            .execute()
        )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


# ============================================================
# program skills (replace-set, constrained to the canonical catalog)
# ============================================================


def set_program_skills(
    client: Client, industry_id: str, job_id: str, skills: list[dict]
) -> dict:
    """Replace-set job_program_skills. Every skill_id must be a real skill
    in the canonical `skills` catalog -- an unknown / made-up id is
    rejected. Unlike the internship-program analog this is NOT restricted
    to the job's recruitment skills: a Job Training program may legitimately
    train skills beyond the screening set (040's job_program_skills.skill_id
    references the `skills` catalog, deliberately 'distinct from job_skills').
    Never modifies job_skills or the referenced skill rows."""
    job, program = _require_program(client, industry_id, job_id)

    # Dedupe, last requirement wins.
    by_id: dict[str, str] = {}
    for entry in skills:
        by_id[str(entry["skill_id"])] = entry.get("requirement", "REQUIRED")

    known = _known_skill_ids(client, set(by_id))
    unknown = set(by_id) - known
    if unknown:
        raise InvalidProgramSkillError(
            "A selected skill is not in the skills catalog."
        )

    client.table("job_program_skills").delete().eq("program_id", program["id"]).execute()
    if by_id:
        client.table("job_program_skills").insert(
            [
                {"program_id": program["id"], "skill_id": skill_id, "requirement": requirement}
                for skill_id, requirement in by_id.items()
            ]
        ).execute()

    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


# ============================================================
# assignments (within a module)
# ============================================================


def create_assignment(
    client: Client, industry_id: str, job_id: str, module_id: str, data: dict
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    _require_module(client, program["id"], module_id)

    payload = {k: v for k, v in data.items() if k in _ASSIGNMENT_EDITABLE}
    _validate_assignment_config(client, program["id"], payload)
    payload["module_id"] = module_id
    payload["order_index"] = _next_order_index(
        client, "job_program_assignments", "module_id", module_id
    )
    # program_id is trigger-derived (set_job_program_assignment_program_id,
    # 040) -- deliberately NOT sent from here.
    try:
        client.table("job_program_assignments").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23514":  # job_program_assignments_repo_kind_consistent
            raise InvalidAssignmentError(
                "The assignment's repository / submission-kind settings are inconsistent."
            ) from exc
        raise
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def update_assignment(
    client: Client,
    industry_id: str,
    job_id: str,
    module_id: str,
    assignment_id: str,
    data: dict,
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    _require_module(client, program["id"], module_id)
    existing = _require_assignment(client, module_id, assignment_id)

    payload = {k: v for k, v in data.items() if k in _ASSIGNMENT_EDITABLE}
    if payload:
        merged = {**existing, **payload}
        _validate_assignment_config(client, program["id"], merged)
        try:
            (
                client.table("job_program_assignments")
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
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)


def reorder_assignments(
    client: Client,
    industry_id: str,
    job_id: str,
    module_id: str,
    ordered_ids: list[str],
) -> dict:
    job, program = _require_program(client, industry_id, job_id)
    _require_module(client, program["id"], module_id)
    existing = {
        row["id"]
        for row in (
            client.table("job_program_assignments")
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
            client.table("job_program_assignments")
            .update({"order_index": index})
            .eq("id", assignment_id)
            .eq("module_id", module_id)
            .execute()
        )
    program = _read_program(client, job_id)
    return _bundle(client, job, program, job_id)
