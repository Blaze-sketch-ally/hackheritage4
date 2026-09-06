"""Business logic for the Institution Skill Gap Analysis
(backend/app/api/institution.py, GET /institution/skill-gaps,
GET /institution/skill-gaps/{application_id}).

This is deliberately an APPLICATION-scoped tool, not an institution-wide
skill dashboard: student -> application -> job/internship -> required
skills -> student skills -> gap. Nothing here is a second skill-matching
algorithm -- every score/status/coverage number comes from the EXACT same
`app.services.match_service.compute_match` Industry's own
GET /applications/{id}/match already uses (Phase 9). Only the row source
differs: Industry's own match reads through `application_skill_match`
(021_application_skill_match.sql, ownership = posting owner); this module
reads through `institution_visible_application_skill_match`
(048_institution_skill_gap.sql, ownership = the application's student is
one of the caller's own linked students). Same algorithm, same output
shape, two different -- both narrowly scoped -- row sources.

Every function takes an already-built *user-scoped* Supabase client and
RLS (037_institution_tenancy.sql: "Institution can view applications from
their own students" / "...their own students' skills") plus the
SECURITY DEFINER function above are the real access-control boundary --
nothing here uses service_role. `_fetch_names` / `_fetch_company_names`
are imported from institution_student_service / institution_service, not
redefined -- one source of truth for student-name and company-name
resolution across every institution module.
"""

from supabase import Client

from app.services import match_service
from app.services.institution_service import _fetch_company_names
from app.services.institution_student_service import _fetch_names

_APPLICATION_COLUMNS = "id, student_id, status, opportunity_type, internship_id, job_id, applied_at, industry_id"


def _fetch_institution_student_ids(client: Client, institution_id: str) -> list[str]:
    resp = client.table("student_profiles").select("id").eq("institution_id", institution_id).execute()
    return [row["id"] for row in (resp.data or [])]


def _fetch_applications(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select(_APPLICATION_COLUMNS)
        .in_("student_id", student_ids)
        .order("applied_at", desc=True)
        .execute()
    )
    return list(resp.data or [])


def _fetch_opportunity_titles(client: Client, internship_ids: list[str], job_ids: list[str]) -> dict[str, str]:
    """Reuses the exact same institution_visible_opportunity_titles RPC
    the Student Directory (institution_student_service.get_student_detail)
    already uses -- resolves a title regardless of the posting's current
    publish status, but only for a posting one of the caller's own
    students has actually applied to."""
    if not internship_ids and not job_ids:
        return {}
    resp = client.rpc(
        "institution_visible_opportunity_titles",
        {"internship_ids": internship_ids, "job_ids": job_ids},
    ).execute()
    return {row["id"]: row["title"] for row in (getattr(resp, "data", None) or [])}


def _fetch_skill_match_rows(client: Client, application_ids: list[str]) -> dict[str, list[dict]]:
    """{application_id: [rows]} via the institution-scoped SECURITY
    DEFINER RPC (048_institution_skill_gap.sql) -- the exact row shape
    match_service.compute_match already consumes, so the gap algorithm
    itself is never duplicated, only the ownership gate differs from
    Industry's own application_skill_match."""
    if not application_ids:
        return {}
    resp = client.rpc(
        "institution_visible_application_skill_match", {"p_application_ids": application_ids}
    ).execute()
    by_application: dict[str, list[dict]] = {}
    for row in getattr(resp, "data", None) or []:
        by_application.setdefault(row["application_id"], []).append(row)
    return by_application


def _fetch_student_skills(client: Client, student_id: str) -> list[dict]:
    """The student's own COMPLETE recorded skill list -- not just the
    subset a particular opportunity requires. Same shape/columns as
    institution_student_service._fetch_skills, scoped to one student."""
    resp = (
        client.table("student_skills")
        .select("proficiency_level, is_verified, skills(name)")
        .eq("student_id", student_id)
        .execute()
    )
    return [
        {
            "skill_name": (row.get("skills") or {}).get("name"),
            "proficiency_level": row.get("proficiency_level"),
            "is_verified": bool(row.get("is_verified")),
        }
        for row in (resp.data or [])
        if isinstance(row.get("skills"), dict) and row["skills"].get("name")
    ]


def _summary_row(application: dict, names: dict, titles: dict, company_names: dict, match: dict) -> dict:
    name_row = names.get(application["student_id"], {})
    opportunity_id = application.get("internship_id") or application.get("job_id")
    return {
        "application_id": application["id"],
        "student_id": application["student_id"],
        "full_name": name_row.get("full_name"),
        "username": name_row.get("username"),
        "opportunity_type": application["opportunity_type"],
        "opportunity_title": titles.get(opportunity_id),
        "company_name": company_names.get(application.get("industry_id")),
        "status": application["status"],
        "applied_at": application.get("applied_at"),
        "score": match["score"],
        "recommendation": match["recommendation"],
        "skill_coverage": match["skill_coverage"],
        "matched_count": match["matched_count"],
        "needs_improvement_count": match["needs_improvement_count"],
        "missing_count": match["missing_count"],
    }


def list_skill_gap_applications(
    client: Client,
    institution_id: str,
    *,
    search: str | None = None,
    opportunity_type: str | None = None,
    status_filter: str | None = None,
) -> list[dict]:
    """Every application by one of the institution's own linked students --
    across every application flow (general marketplace, institution-curated
    internship, placement drive) -- with its deterministic skill match.
    Never assumes every application came from a placement drive."""
    student_ids = _fetch_institution_student_ids(client, institution_id)
    applications = _fetch_applications(client, student_ids)
    if not applications:
        return []

    names = _fetch_names(client, [a["student_id"] for a in applications])
    titles = _fetch_opportunity_titles(
        client,
        [a["internship_id"] for a in applications if a.get("internship_id")],
        [a["job_id"] for a in applications if a.get("job_id")],
    )
    company_names = _fetch_company_names(
        client, [a["industry_id"] for a in applications if a.get("industry_id")]
    )
    match_rows_by_application = _fetch_skill_match_rows(client, [a["id"] for a in applications])

    rows = []
    for application in applications:
        match = match_service.compute_match(
            application["id"], match_rows_by_application.get(application["id"], [])
        )
        rows.append(_summary_row(application, names, titles, company_names, match))

    if opportunity_type:
        rows = [r for r in rows if r["opportunity_type"] == opportunity_type]
    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]
    if search and search.strip():
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in (r["full_name"] or "").lower()
            or needle in (r["username"] or "").lower()
            or needle in (r["opportunity_title"] or "").lower()
            or needle in (r["company_name"] or "").lower()
        ]
    return rows


def get_skill_gap_detail(client: Client, institution_id: str, application_id: str) -> dict | None:
    """One application's full skill-gap breakdown, or None if it doesn't
    exist or does not belong to one of the caller's own linked students --
    indistinguishable, so no cross-institution existence is ever leaked."""
    student_ids = _fetch_institution_student_ids(client, institution_id)
    if not student_ids:
        return None

    resp = (
        client.table("applications")
        .select(_APPLICATION_COLUMNS)
        .eq("id", application_id)
        .in_("student_id", student_ids)
        .maybe_single()
        .execute()
    )
    application = resp.data if resp is not None else None
    if not application:
        return None

    names = _fetch_names(client, [application["student_id"]])
    titles = _fetch_opportunity_titles(
        client,
        [application["internship_id"]] if application.get("internship_id") else [],
        [application["job_id"]] if application.get("job_id") else [],
    )
    company_names = _fetch_company_names(
        client, [application["industry_id"]] if application.get("industry_id") else []
    )

    match_rows_by_application = _fetch_skill_match_rows(client, [application_id])
    match = match_service.compute_match(application_id, match_rows_by_application.get(application_id, []))
    student_skills = _fetch_student_skills(client, application["student_id"])

    return {
        **_summary_row(application, names, titles, company_names, match),
        "required_count": match["required_count"],
        "matched_skills": match["matched_skills"],
        "needs_improvement_skills": match["needs_improvement_skills"],
        "missing_skills": match["missing_skills"],
        "student_skills": student_skills,
    }
