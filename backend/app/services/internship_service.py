"""Business logic for Industry internships (`internships` +
`internship_skills`, database/migrations/018_internships.sql).

Same shape as the other service modules: every function takes an
already-built *user-scoped* Supabase client (app.core.security.
build_user_client) and RLS is the real access-control boundary. Nothing
here uses service_role.

`internships`' policies (018_internships.sql) scope every write to
`auth.uid() = industry_id AND public.is_industry(auth.uid())`, and
`internship_skills`' policies scope writes to skills of an internship the
caller owns. On top of that, every function here also filters explicitly
by `industry_id` (defence in depth, matching the convention in the other
service modules) and forces `industry_id` / `status` server-side -- a
client value for either is never trusted.

Lifecycle: DRAFT -> PUBLISHED -> CLOSED -> ARCHIVED (with ARCHIVED also
reachable directly from DRAFT / PUBLISHED). `create` always yields DRAFT;
`status` is never editable through `update_internship`.
"""

from supabase import Client

_SELECT = (
    "id, industry_id, title, description, location, work_mode, duration_months, "
    "stipend_amount, stipend_currency, openings, eligibility_criteria, "
    "application_deadline, start_date, status, created_at, updated_at, "
    "internship_skills(skill_id, required_level, importance, "
    "skill:skills(name, category:skill_categories(name)))"
)

_EDITABLE_COLUMNS = frozenset(
    {
        "title",
        "description",
        "location",
        "work_mode",
        "duration_months",
        "stipend_amount",
        "stipend_currency",
        "openings",
        "eligibility_criteria",
        "application_deadline",
        "start_date",
    }
)

# Fields that must be present (and a skill list that must be non-empty)
# before an internship can be published. title/description are NOT NULL
# columns so they are always present already.
_PUBLISH_REQUIRED = ("location", "work_mode", "duration_months", "application_deadline")

_CLOSE_FROM = frozenset({"PUBLISHED"})
_ARCHIVE_FROM = frozenset({"DRAFT", "PUBLISHED", "CLOSED"})


class InvalidSkillError(Exception):
    """One or more submitted skill ids are not active rows in the catalog."""

    def __init__(self, skill_ids: list[str]) -> None:
        self.skill_ids = skill_ids
        super().__init__("Unknown or inactive skill ids: " + ", ".join(skill_ids))


class PublishValidationError(Exception):
    """The internship is missing fields required to publish."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Missing before publish: " + ", ".join(missing))


class InvalidStatusTransitionError(Exception):
    """The requested lifecycle transition isn't allowed from the current status."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot move an internship from {current} to {target}.")


# ---- shaping ----


def _shape(row: dict) -> dict:
    """Flatten the nested internship_skills embed into a plain `skills` list."""
    skills = []
    for link in row.pop("internship_skills", None) or []:
        skill = link.get("skill") or {}
        category = skill.get("category") or {}
        skills.append(
            {
                "skill_id": link["skill_id"],
                "skill_name": skill.get("name", ""),
                "category_name": category.get("name"),
                "required_level": link["required_level"],
                "importance": link["importance"],
            }
        )
    skills.sort(key=lambda s: s["skill_name"].lower())
    row["skills"] = skills
    return row


# ---- reads ----


def list_internships(
    client: Client,
    industry_id: str,
    *,
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """The caller's own internships (every status by default), newest
    change first. Optional exact `status` filter and case-insensitive
    title `search`."""
    query = client.table("internships").select(_SELECT).eq("industry_id", industry_id)
    if status:
        query = query.eq("status", status)
    if search and search.strip():
        query = query.ilike("title", f"%{search.strip()}%")
    response = query.order("updated_at", desc=True).execute()
    return [_shape(row) for row in (response.data or [])]


def get_internship(client: Client, industry_id: str, internship_id: str) -> dict | None:
    """One of the caller's own internships, or None -- callers turn None
    into a 404, so another Industry account's internship is indistinguishable
    from one that doesn't exist."""
    response = (
        client.table("internships")
        .select(_SELECT)
        .eq("id", internship_id)
        .eq("industry_id", industry_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape(row) if row else None


# ---- skills helpers ----


def _dedupe_skills(skills: list[dict]) -> list[dict]:
    """Collapse repeated skill_ids (last one wins) so a duplicate can
    never reach the unique (internship_id, skill_id) constraint."""
    by_id: dict[str, dict] = {}
    for entry in skills:
        by_id[str(entry["skill_id"])] = {
            "skill_id": str(entry["skill_id"]),
            "required_level": entry["required_level"],
            "importance": entry.get("importance", "IMPORTANT"),
        }
    return list(by_id.values())


def _validate_skill_ids(client: Client, skill_ids: list[str]) -> None:
    if not skill_ids:
        return
    response = (
        client.table("skills").select("id").in_("id", skill_ids).eq("is_active", True).execute()
    )
    found = {row["id"] for row in (response.data or [])}
    missing = [sid for sid in skill_ids if sid not in found]
    if missing:
        raise InvalidSkillError(missing)


def _replace_skills(client: Client, internship_id: str, skills: list[dict]) -> None:
    deduped = _dedupe_skills(skills)
    _validate_skill_ids(client, [s["skill_id"] for s in deduped])
    client.table("internship_skills").delete().eq("internship_id", internship_id).execute()
    if deduped:
        client.table("internship_skills").insert(
            [{"internship_id": internship_id, **s} for s in deduped]
        ).execute()


# ---- writes ----


def create_internship(
    client: Client, industry_id: str, data: dict, skills: list[dict]
) -> dict:
    """Always creates a DRAFT owned by `industry_id` (the authenticated
    caller). Any `status` / `industry_id` / `id` in `data` is overridden."""
    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    payload["industry_id"] = industry_id
    payload["status"] = "DRAFT"

    deduped = _dedupe_skills(skills)
    if deduped:
        _validate_skill_ids(client, [s["skill_id"] for s in deduped])

    response = client.table("internships").insert(payload).execute()
    new_id = response.data[0]["id"]

    if deduped:
        client.table("internship_skills").insert(
            [{"internship_id": new_id, **s} for s in deduped]
        ).execute()

    row = get_internship(client, industry_id, new_id)
    if row is None:
        raise RuntimeError("internship row could not be read back after create.")
    return row


def update_internship(
    client: Client,
    industry_id: str,
    internship_id: str,
    data: dict,
    skills: list[dict] | None,
) -> dict | None:
    """Edit the caller's own internship. `status` is never touched here.
    `skills=None` leaves the skill list alone; a list replaces it."""
    existing = get_internship(client, industry_id, internship_id)
    if existing is None:
        return None

    payload = {k: v for k, v in data.items() if k in _EDITABLE_COLUMNS}
    if payload:
        (
            client.table("internships")
            .update(payload)
            .eq("id", internship_id)
            .eq("industry_id", industry_id)
            .execute()
        )

    if skills is not None:
        _replace_skills(client, internship_id, skills)

    return get_internship(client, industry_id, internship_id)


def publish_internship(client: Client, industry_id: str, internship_id: str) -> dict | None:
    """DRAFT/CLOSED -> PUBLISHED, only if the fields needed to publish are
    present and at least one skill is attached."""
    existing = get_internship(client, industry_id, internship_id)
    if existing is None:
        return None

    missing = [field for field in _PUBLISH_REQUIRED if not existing.get(field)]
    if not existing.get("skills"):
        missing.append("at least one required skill")
    if missing:
        raise PublishValidationError(missing)

    if existing["status"] not in {"DRAFT", "CLOSED"}:
        raise InvalidStatusTransitionError(existing["status"], "PUBLISHED")

    (
        client.table("internships")
        .update({"status": "PUBLISHED"})
        .eq("id", internship_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_internship(client, industry_id, internship_id)


def _transition(
    client: Client,
    industry_id: str,
    internship_id: str,
    target: str,
    allowed_from: frozenset[str],
) -> dict | None:
    existing = get_internship(client, industry_id, internship_id)
    if existing is None:
        return None
    if existing["status"] not in allowed_from:
        raise InvalidStatusTransitionError(existing["status"], target)
    (
        client.table("internships")
        .update({"status": target})
        .eq("id", internship_id)
        .eq("industry_id", industry_id)
        .execute()
    )
    return get_internship(client, industry_id, internship_id)


def close_internship(client: Client, industry_id: str, internship_id: str) -> dict | None:
    """PUBLISHED -> CLOSED (stop accepting new applications)."""
    return _transition(client, industry_id, internship_id, "CLOSED", _CLOSE_FROM)


def archive_internship(client: Client, industry_id: str, internship_id: str) -> dict | None:
    """DRAFT/PUBLISHED/CLOSED -> ARCHIVED. This is the closest thing to a
    delete -- rows are never physically removed (018's FKs from
    applications are ON DELETE RESTRICT, and recruitment history must
    survive)."""
    return _transition(client, industry_id, internship_id, "ARCHIVED", _ARCHIVE_FROM)
