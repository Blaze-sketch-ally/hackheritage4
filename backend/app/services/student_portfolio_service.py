"""Business logic for the STUDENT Portfolio API
(database/migrations/034_student_portfolio.sql).

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- RLS is the real access-control
boundary and nothing here uses service_role.

What RLS already guarantees, and this module relies on rather than
re-implements:

* `student_projects` / `student_certifications` / `student_achievements`:
  owner-only SELECT / INSERT / UPDATE / DELETE, scoped
  `auth.uid() = student_id AND public.is_student(auth.uid())`.
* `student_project_skills`: readable/writable only for a project the
  caller owns (EXISTS-on-parent policy).
* `student_skills`: "Students can view their own skills" -- the portfolio
  aggregate reads it read-only.

On top of RLS, every function here also filters/sets `student_id`
explicitly from the authenticated caller, and every ownership-sensitive
read/update/delete is gated on a prior `_own_*` lookup that returns None
(→ the route raises 404) when the row is not the caller's own -- so a
guessed id from another student is a clean 404, never a leak.

A project / certification / achievement is PORTFOLIO EVIDENCE ONLY. This
module never reads or writes `student_skills` proficiency/verification and
never creates a `student_skills` row.
"""

from datetime import date

from postgrest.exceptions import APIError
from supabase import Client

_PROJECT_COLUMNS = (
    "id, title, description, project_url, repo_url, start_date, end_date, "
    "is_ongoing, created_at, updated_at"
)
_PROJECT_WITH_SKILLS = (
    f"{_PROJECT_COLUMNS}, "
    "student_project_skills(skill_id, skill:skills(id, name, category:skill_categories(name)))"
)
_CERTIFICATION_COLUMNS = (
    "id, name, issuing_organization, issue_date, expiry_date, credential_id, "
    "credential_url, created_at, updated_at"
)
_ACHIEVEMENT_COLUMNS = (
    "id, title, description, achievement_date, issuing_organization, url, "
    "created_at, updated_at"
)


class InvalidSkillError(Exception):
    """One or more supplied skill_ids do not resolve to a real `skills`
    catalog row -- the route turns this into a 422."""


# ---- helpers ----


def _d(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _shape_project(row: dict) -> dict:
    skills = []
    for link in row.get("student_project_skills") or []:
        skill = link.get("skill") or {}
        category = skill.get("category") or {}
        skills.append(
            {
                "skill_id": link["skill_id"],
                "skill_name": skill.get("name", ""),
                "category_name": category.get("name"),
            }
        )
    skills.sort(key=lambda s: s["skill_name"].lower())
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row.get("description"),
        "project_url": row.get("project_url"),
        "repo_url": row.get("repo_url"),
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
        "is_ongoing": bool(row.get("is_ongoing")),
        "skills": skills,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _validate_skill_ids(client: Client, skill_ids: list[str]) -> None:
    """Every id must resolve to a real `skills` row. RLS on `skills`
    ("Authenticated users can view active skills") already scopes this."""
    if not skill_ids:
        return
    response = client.table("skills").select("id").in_("id", skill_ids).execute()
    found = {row["id"] for row in (response.data or [])}
    missing = [s for s in skill_ids if s not in found]
    if missing:
        raise InvalidSkillError(missing)


def _set_project_skills(client: Client, project_id: str, skill_ids: list[str]) -> None:
    """Replace the project's skill links with exactly `skill_ids`. The
    caller has already verified project ownership and skill validity."""
    client.table("student_project_skills").delete().eq("project_id", project_id).execute()
    if skill_ids:
        client.table("student_project_skills").insert(
            [{"project_id": project_id, "skill_id": sid} for sid in skill_ids]
        ).execute()


# ============================================================
# Projects
# ============================================================


def list_projects(client: Client, student_id: str) -> list[dict]:
    response = (
        client.table("student_projects")
        .select(_PROJECT_WITH_SKILLS)
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_shape_project(row) for row in (response.data or [])]


def _own_project(client: Client, student_id: str, project_id: str) -> dict | None:
    response = (
        client.table("student_projects")
        .select(_PROJECT_WITH_SKILLS)
        .eq("id", project_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    return _shape_project(row) if row else None


def get_project(client: Client, student_id: str, project_id: str) -> dict | None:
    return _own_project(client, student_id, project_id)


def create_project(client: Client, student_id: str, data: dict) -> dict:
    """`data` is a validated ProjectCreate dump. `student_id` comes from
    the caller argument only -- never from `data`."""
    skill_ids: list[str] = data.get("skill_ids") or []
    _validate_skill_ids(client, skill_ids)

    payload = {
        "student_id": student_id,
        "title": data["title"],
        "description": data.get("description"),
        "project_url": data.get("project_url"),
        "repo_url": data.get("repo_url"),
        "start_date": _d(data.get("start_date")),
        "end_date": _d(data.get("end_date")),
        "is_ongoing": bool(data.get("is_ongoing")),
    }
    response = client.table("student_projects").insert(payload).execute()
    new_id = (response.data or [{}])[0].get("id")
    if not new_id:
        raise RuntimeError("project row could not be read back after insert.")

    if skill_ids:
        try:
            _set_project_skills(client, new_id, skill_ids)
        except APIError as exc:
            if exc.code == "23503":  # skill vanished between validate + insert
                raise InvalidSkillError(skill_ids) from exc
            raise

    row = _own_project(client, student_id, new_id)
    if row is None:
        raise RuntimeError("project row could not be read back after insert.")
    return row


def update_project(client: Client, student_id: str, project_id: str, data: dict) -> dict | None:
    """Full replacement. Returns None if the project is not the caller's
    own (→ route 404)."""
    if _own_project(client, student_id, project_id) is None:
        return None

    skill_ids: list[str] = data.get("skill_ids") or []
    _validate_skill_ids(client, skill_ids)

    payload = {
        "title": data["title"],
        "description": data.get("description"),
        "project_url": data.get("project_url"),
        "repo_url": data.get("repo_url"),
        "start_date": _d(data.get("start_date")),
        "end_date": _d(data.get("end_date")),
        "is_ongoing": bool(data.get("is_ongoing")),
    }
    client.table("student_projects").update(payload).eq("id", project_id).eq(
        "student_id", student_id
    ).execute()

    try:
        _set_project_skills(client, project_id, skill_ids)
    except APIError as exc:
        if exc.code == "23503":
            raise InvalidSkillError(skill_ids) from exc
        raise

    return _own_project(client, student_id, project_id)


def delete_project(client: Client, student_id: str, project_id: str) -> bool:
    """Returns False if the project is not the caller's own (→ route 404).
    `student_project_skills` rows cascade-delete."""
    if _own_project(client, student_id, project_id) is None:
        return False
    client.table("student_projects").delete().eq("id", project_id).eq(
        "student_id", student_id
    ).execute()
    return True


# ============================================================
# Certifications
# ============================================================


def _cert_payload(data: dict) -> dict:
    return {
        "name": data["name"],
        "issuing_organization": data.get("issuing_organization"),
        "issue_date": _d(data.get("issue_date")),
        "expiry_date": _d(data.get("expiry_date")),
        "credential_id": data.get("credential_id"),
        "credential_url": data.get("credential_url"),
    }


def list_certifications(client: Client, student_id: str) -> list[dict]:
    response = (
        client.table("student_certifications")
        .select(_CERTIFICATION_COLUMNS)
        .eq("student_id", student_id)
        .order("issue_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def _own_certification(client: Client, student_id: str, cert_id: str) -> dict | None:
    response = (
        client.table("student_certifications")
        .select(_CERTIFICATION_COLUMNS)
        .eq("id", cert_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_certification(client: Client, student_id: str, cert_id: str) -> dict | None:
    return _own_certification(client, student_id, cert_id)


def create_certification(client: Client, student_id: str, data: dict) -> dict:
    payload = {"student_id": student_id, **_cert_payload(data)}
    response = client.table("student_certifications").insert(payload).execute()
    new_id = (response.data or [{}])[0].get("id")
    row = _own_certification(client, student_id, new_id) if new_id else None
    if row is None:
        raise RuntimeError("certification row could not be read back after insert.")
    return row


def update_certification(
    client: Client, student_id: str, cert_id: str, data: dict
) -> dict | None:
    if _own_certification(client, student_id, cert_id) is None:
        return None
    client.table("student_certifications").update(_cert_payload(data)).eq("id", cert_id).eq(
        "student_id", student_id
    ).execute()
    return _own_certification(client, student_id, cert_id)


def delete_certification(client: Client, student_id: str, cert_id: str) -> bool:
    if _own_certification(client, student_id, cert_id) is None:
        return False
    client.table("student_certifications").delete().eq("id", cert_id).eq(
        "student_id", student_id
    ).execute()
    return True


# ============================================================
# Achievements
# ============================================================


def _achievement_payload(data: dict) -> dict:
    return {
        "title": data["title"],
        "description": data.get("description"),
        "achievement_date": _d(data.get("achievement_date")),
        "issuing_organization": data.get("issuing_organization"),
        "url": data.get("url"),
    }


def list_achievements(client: Client, student_id: str) -> list[dict]:
    response = (
        client.table("student_achievements")
        .select(_ACHIEVEMENT_COLUMNS)
        .eq("student_id", student_id)
        .order("achievement_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def _own_achievement(client: Client, student_id: str, achievement_id: str) -> dict | None:
    response = (
        client.table("student_achievements")
        .select(_ACHIEVEMENT_COLUMNS)
        .eq("id", achievement_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_achievement(client: Client, student_id: str, achievement_id: str) -> dict | None:
    return _own_achievement(client, student_id, achievement_id)


def create_achievement(client: Client, student_id: str, data: dict) -> dict:
    payload = {"student_id": student_id, **_achievement_payload(data)}
    response = client.table("student_achievements").insert(payload).execute()
    new_id = (response.data or [{}])[0].get("id")
    row = _own_achievement(client, student_id, new_id) if new_id else None
    if row is None:
        raise RuntimeError("achievement row could not be read back after insert.")
    return row


def update_achievement(
    client: Client, student_id: str, achievement_id: str, data: dict
) -> dict | None:
    if _own_achievement(client, student_id, achievement_id) is None:
        return None
    client.table("student_achievements").update(_achievement_payload(data)).eq(
        "id", achievement_id
    ).eq("student_id", student_id).execute()
    return _own_achievement(client, student_id, achievement_id)


def delete_achievement(client: Client, student_id: str, achievement_id: str) -> bool:
    if _own_achievement(client, student_id, achievement_id) is None:
        return False
    client.table("student_achievements").delete().eq("id", achievement_id).eq(
        "student_id", student_id
    ).execute()
    return True


# ============================================================
# Portfolio aggregate (read-only)
# ============================================================


def _own_skills(client: Client, student_id: str) -> list[dict]:
    response = (
        client.table("student_skills")
        .select(
            "skill_id, proficiency_level, is_verified, "
            "skill:skills(name, category:skill_categories(name))"
        )
        .eq("student_id", student_id)
        .execute()
    )
    out = []
    for row in response.data or []:
        skill = row.get("skill") or {}
        category = skill.get("category") or {}
        out.append(
            {
                "skill_id": row["skill_id"],
                "skill_name": skill.get("name", ""),
                "category_name": category.get("name"),
                "proficiency_level": row["proficiency_level"],
                "is_verified": bool(row["is_verified"]),
            }
        )
    out.sort(key=lambda s: s["skill_name"].lower())
    return out


def get_portfolio(client: Client, student_id: str) -> dict:
    """Read-only aggregation of the caller's own portfolio. `skills` is a
    copy of the student's canonical `student_skills` -- never modified
    here."""
    return {
        "projects": list_projects(client, student_id),
        "certifications": list_certifications(client, student_id),
        "achievements": list_achievements(client, student_id),
        "skills": _own_skills(client, student_id),
    }
