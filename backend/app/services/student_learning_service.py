"""Business logic for the STUDENT Learning API
(database/migrations/033_learning_resources.sql).

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- RLS is the real access-control
boundary and nothing here uses service_role.

What RLS already guarantees, and this module relies on rather than
re-implements:

* `learning_resources`: "Authenticated users can view active learning
  resources" -- a student only ever sees `is_active = true` rows. The
  explicit `.eq("is_active", True)` here is defence in depth.
* `learning_resource_skills`: visible only for an active parent resource.
* `student_learning_progress`: "Students can view / start / update their
  own learning progress" -- every read and every write is scoped to
  `auth.uid() = student_id AND is_student(auth.uid())`. On top of that,
  every function here also filters/sets `student_id` explicitly from the
  authenticated caller.

Learning progress carries NO score / skill level / verification. This
module never reads or writes `student_skills`, `assessments`, or any
verification state.
"""

from datetime import UTC, datetime

from supabase import Client

_RESOURCE_COLUMNS = (
    "id, title, description, url, provider, resource_type, difficulty, estimated_minutes"
)
# learning_resource_skills.resource_id is a real FK to learning_resources.id,
# so PostgREST resolves this nested embed in a single query.
_RESOURCE_WITH_SKILLS = (
    f"{_RESOURCE_COLUMNS}, "
    "learning_resource_skills(skill_id, target_level, skill:skills(id, name))"
)
_PROGRESS_COLUMNS = "resource_id, status, started_at, completed_at, created_at, updated_at"
_PROGRESS_WITH_RESOURCE = (
    f"{_PROGRESS_COLUMNS}, "
    "resource:learning_resources(id, title, url, provider, resource_type, difficulty)"
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---- shaping ----


def _shape_skills(links: list[dict] | None) -> list[dict]:
    skills = []
    for link in links or []:
        skill = link.get("skill") or {}
        skills.append(
            {
                "skill_id": link["skill_id"],
                "skill_name": skill.get("name", ""),
                "target_level": link.get("target_level"),
            }
        )
    skills.sort(key=lambda s: s["skill_name"].lower())
    return skills


def _shape_progress(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "status": row["status"],
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "updated_at": row.get("updated_at"),
    }


def _shape_resource(row: dict, progress_by_resource: dict[str, dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "url": row["url"],
        "provider": row.get("provider"),
        "resource_type": row["resource_type"],
        "difficulty": row.get("difficulty"),
        "estimated_minutes": row.get("estimated_minutes"),
        "skills": _shape_skills(row.get("learning_resource_skills")),
        "progress": _shape_progress(progress_by_resource.get(row["id"])),
    }


# ---- own-progress lookup ----


def _own_progress_map(client: Client, student_id: str, resource_ids: list[str]) -> dict[str, dict]:
    """{resource_id: progress row} for the caller's own progress on the
    given resources. RLS already scopes `student_learning_progress` to the
    caller; the explicit `.eq("student_id", ...)` is defence in depth."""
    ids = sorted({rid for rid in resource_ids if rid})
    if not ids:
        return {}
    response = (
        client.table("student_learning_progress")
        .select(_PROGRESS_COLUMNS)
        .eq("student_id", student_id)
        .in_("resource_id", ids)
        .execute()
    )
    return {row["resource_id"]: row for row in (response.data or [])}


def get_own_progress(client: Client, student_id: str, resource_id: str) -> dict | None:
    response = (
        client.table("student_learning_progress")
        .select("id, resource_id, status, started_at, completed_at, created_at, updated_at")
        .eq("student_id", student_id)
        .eq("resource_id", resource_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


# ---- browse ----


def _resource_ids_for_skill(client: Client, skill_id: str) -> list[str]:
    """The resource_ids whose mapping includes this skill -- used to
    filter the catalog by skill_id without an awkward nested embed
    filter. RLS on learning_resource_skills already limits this to
    mappings whose parent resource is active."""
    response = (
        client.table("learning_resource_skills")
        .select("resource_id")
        .eq("skill_id", skill_id)
        .execute()
    )
    return sorted({row["resource_id"] for row in (response.data or [])})


def list_resources(
    client: Client,
    student_id: str,
    *,
    skill_id: str | None = None,
    difficulty: str | None = None,
    resource_type: str | None = None,
) -> list[dict]:
    """Active learning resources, normalized, title-sorted, each with its
    mapped skills and the caller's own progress. RLS already restricts
    every row to `is_active = true`; the explicit `.eq` is defence in
    depth. Every filter is optional and additive."""
    query = (
        client.table("learning_resources").select(_RESOURCE_WITH_SKILLS).eq("is_active", True)
    )
    if difficulty:
        query = query.eq("difficulty", difficulty)
    if resource_type:
        query = query.eq("resource_type", resource_type)
    if skill_id is not None:
        resource_ids = _resource_ids_for_skill(client, skill_id)
        if not resource_ids:
            return []
        query = query.in_("id", resource_ids)

    rows = query.order("title").execute().data or []
    progress_by_resource = _own_progress_map(client, student_id, [row["id"] for row in rows])
    return [_shape_resource(row, progress_by_resource) for row in rows]


def list_resources_by_ids(
    client: Client, student_id: str, resource_ids: list[str]
) -> list[dict]:
    """Active learning resources whose id is in `resource_ids`, shaped
    exactly like ``list_resources`` (mapped skills + the caller's own
    progress, title-sorted).

    Used by the Skill-Gap -> Learning recommendation adapter
    (app.services.learning_recommendation_service), which has already
    resolved the set of relevant resource ids from
    ``learning_resource_skills``. The catalog browse path uses
    ``list_resources`` instead. RLS restricts every row to
    ``is_active = true`` independently; the explicit ``.eq`` is defence in
    depth.
    """
    ids = sorted({rid for rid in resource_ids if rid})
    if not ids:
        return []
    rows = (
        client.table("learning_resources")
        .select(_RESOURCE_WITH_SKILLS)
        .eq("is_active", True)
        .in_("id", ids)
        .order("title")
        .execute()
        .data
        or []
    )
    progress_by_resource = _own_progress_map(client, student_id, [row["id"] for row in rows])
    return [_shape_resource(row, progress_by_resource) for row in rows]


def get_resource(client: Client, student_id: str, resource_id: str) -> dict | None:
    """One active learning resource with its skills and the caller's own
    progress, or None (callers turn None into a 404 -- an inactive or
    nonexistent resource is indistinguishable, even to a caller who knows
    the UUID). RLS enforces the active-only rule independently."""
    response = (
        client.table("learning_resources")
        .select(_RESOURCE_WITH_SKILLS)
        .eq("id", resource_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    progress_by_resource = _own_progress_map(client, student_id, [row["id"]])
    return _shape_resource(row, progress_by_resource)


# ---- my progress ----


def list_my_progress(client: Client, student_id: str) -> list[dict]:
    """Every progress row the caller owns, most recently touched first,
    with the resource embedded for rendering. RLS ("Students can view
    their own learning progress") plus the explicit `.eq("student_id",
    ...)` both scope this to the caller. The `resource` embed comes back
    null if that resource has since been deactivated -- the progress row
    (the student's history) still exists."""
    response = (
        client.table("student_learning_progress")
        .select(_PROGRESS_WITH_RESOURCE)
        .eq("student_id", student_id)
        .order("updated_at", desc=True)
        .execute()
    )
    rows = response.data or []
    shaped = []
    for row in rows:
        resource = row.pop("resource", None)
        row["resource"] = (
            {
                "id": resource["id"],
                "title": resource["title"],
                "url": resource["url"],
                "provider": resource.get("provider"),
                "resource_type": resource["resource_type"],
                "difficulty": resource.get("difficulty"),
            }
            if resource
            else None
        )
        shaped.append(row)
    return shaped


# ---- progress upsert ----


def set_progress(client: Client, student_id: str, resource_id: str, status: str) -> dict:
    """Create or move the caller's own progress on one resource to
    `status`, upserting on the (student_id, resource_id) natural key.

    MUST be called only after the route has confirmed the resource exists
    and is active (get_resource) -- this function does not re-check that,
    mirroring app.api.student_opportunities.apply_to_opportunity.

    Server-set timestamps (the client can never submit one -- see
    ProgressUpdateRequest's extra="forbid"):
        SAVED        -> completed_at cleared; started_at kept as-is
        IN_PROGRESS  -> started_at set to now() if not already set;
                        completed_at cleared
        COMPLETED    -> started_at set to now() if not already set;
                        completed_at set to now() if not already set
    Moving COMPLETED -> IN_PROGRESS / SAVED therefore clears completed_at;
    started_at is only ever set once and never rewound (the earliest time
    the student began the resource is a fact worth keeping). These match
    the DB CHECK constraints in 033 exactly (completed_at implies
    COMPLETED; a non-SAVED row has a started_at; completed_at >=
    started_at).
    """
    existing = get_own_progress(client, student_id, resource_id)
    existing_started = existing.get("started_at") if existing else None
    existing_completed = existing.get("completed_at") if existing else None
    now = _now()

    if status == "SAVED":
        started_at = existing_started
        completed_at = None
    elif status == "IN_PROGRESS":
        started_at = existing_started or now
        completed_at = None
    else:  # COMPLETED
        started_at = existing_started or now
        completed_at = existing_completed or now

    payload = {
        "student_id": student_id,
        "resource_id": resource_id,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    # RLS's own INSERT + UPDATE WITH CHECK both re-verify
    # auth.uid() = student_id, so even a mismatched student_id here would
    # be rejected -- but it is always current_user.id anyway.
    response = (
        client.table("student_learning_progress")
        .upsert(payload, on_conflict="student_id,resource_id")
        .execute()
    )
    row = (response.data or [None])[0]
    if row is None:
        raise RuntimeError("learning progress row could not be read back after upsert.")
    return {
        "resource_id": row["resource_id"],
        "status": row["status"],
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
