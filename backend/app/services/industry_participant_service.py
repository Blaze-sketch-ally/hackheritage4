"""Business logic for the cross-module Industry Participant view -- see
app.schemas.industry_participant for the shape and reasoning.

This is a pure composition layer: every row comes from one of the four
existing, already ownership-scoped list functions
(app.services.application_service.list_applications,
industry_project_application_service.list_applications,
industry_workshop_application_service.list_applications,
industry_training_application_service.list_applications). Nothing here
touches a table directly, introduces a new RLS boundary, or uses
service_role -- ownership is exactly whatever each of those four functions
already enforces (RLS + the explicit industry_id filter each one applies).
"""

from supabase import Client

from app.services import (
    application_service,
    industry_project_application_service,
    industry_training_application_service,
    industry_workshop_application_service,
)


def _from_applications(client: Client, industry_id: str, opportunity_type: str | None) -> list[dict]:
    if opportunity_type not in (None, "INTERNSHIP", "JOB"):
        return []
    rows = application_service.list_applications(
        client,
        industry_id,
        opportunity_type=opportunity_type if opportunity_type in ("INTERNSHIP", "JOB") else None,
    )
    records = []
    for row in rows:
        opportunity = row.get("opportunity") or {}
        records.append(
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "student_name": row.get("student_name"),
                "institution_name": row.get("institution_name"),
                "department": row.get("department"),
                "graduation_year": row.get("graduation_year"),
                "skills": row.get("skills"),
                "opportunity_type": row["opportunity_type"],
                "opportunity_id": opportunity.get("id") or "",
                "opportunity_title": opportunity.get("title") or "(posting unavailable)",
                "opportunity_href": f"/industry/applicants/{row['id']}",
                "status": row["status"],
                "applied_at": row.get("applied_at"),
            }
        )
    return records


def _from_projects(client: Client, industry_id: str, opportunity_type: str | None) -> list[dict]:
    if opportunity_type not in (None, "PROJECT"):
        return []
    rows = industry_project_application_service.list_applications(client, industry_id)
    records = []
    for row in rows:
        project = row.get("project") or {}
        records.append(
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "student_name": row.get("student_name"),
                "institution_name": row.get("institution_name"),
                "department": row.get("department"),
                "graduation_year": row.get("graduation_year"),
                "skills": row.get("skills"),
                "opportunity_type": "PROJECT",
                "opportunity_id": row["project_id"],
                "opportunity_title": project.get("title") or "(posting unavailable)",
                "opportunity_href": f"/industry/projects/{row['project_id']}/applicants",
                "status": row["status"],
                "applied_at": row.get("applied_at"),
            }
        )
    return records


def _from_workshops(client: Client, industry_id: str, opportunity_type: str | None) -> list[dict]:
    if opportunity_type not in (None, "WORKSHOP"):
        return []
    rows = industry_workshop_application_service.list_applications(client, industry_id)
    records = []
    for row in rows:
        workshop = row.get("workshop") or {}
        records.append(
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "student_name": row.get("student_name"),
                "institution_name": row.get("institution_name"),
                "department": row.get("department"),
                "graduation_year": row.get("graduation_year"),
                "skills": row.get("skills"),
                "opportunity_type": "WORKSHOP",
                "opportunity_id": row["workshop_id"],
                "opportunity_title": workshop.get("title") or "(posting unavailable)",
                "opportunity_href": f"/industry/workshops/{row['workshop_id']}/applicants",
                "status": row["status"],
                "applied_at": row.get("applied_at"),
            }
        )
    return records


def _from_training(client: Client, industry_id: str, opportunity_type: str | None) -> list[dict]:
    if opportunity_type not in (None, "TRAINING"):
        return []
    rows = industry_training_application_service.list_applications(client, industry_id)
    records = []
    for row in rows:
        training = row.get("training") or {}
        records.append(
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "student_name": row.get("student_name"),
                "institution_name": row.get("institution_name"),
                "department": row.get("department"),
                "graduation_year": row.get("graduation_year"),
                "skills": row.get("skills"),
                "opportunity_type": "TRAINING",
                "opportunity_id": row["training_id"],
                "opportunity_title": training.get("title") or "(posting unavailable)",
                "opportunity_href": f"/industry/training/{row['training_id']}/applicants",
                "status": row["status"],
                "applied_at": row.get("applied_at"),
            }
        )
    return records


def list_participants(
    client: Client,
    industry_id: str,
    *,
    opportunity_type: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Every student's participation across all of the caller's own
    postings (Job/Internship/Project/Workshop/Training), newest first.
    `opportunity_type` narrows to one source; `search` is a
    case-insensitive substring match against the resolved student name
    (rows with no resolved name never match a non-empty search)."""
    records: list[dict] = [
        *_from_applications(client, industry_id, opportunity_type),
        *_from_projects(client, industry_id, opportunity_type),
        *_from_workshops(client, industry_id, opportunity_type),
        *_from_training(client, industry_id, opportunity_type),
    ]

    if search and search.strip():
        needle = search.strip().lower()
        records = [r for r in records if (r.get("student_name") or "").lower().find(needle) != -1]

    records.sort(key=lambda r: r.get("applied_at") or "", reverse=True)
    return records
