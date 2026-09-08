"""Business logic for the Institution Reports module (Phase 11;
backend/app/api/institution.py, GET /api/v1/institution/reports).

This module computes NOTHING new about placement/internship/company/
event/collaboration definitions -- it calls the EXISTING, already-tested
service function for each domain and reshapes the result into a report:

  PLACEMENT     -> institution_analytics_service.compute_institution_analytics
                   (Phase 6 -- already supports department_id/batch/
                   date_from/date_to filters; "placed" = SELECTED, same
                   as everywhere else)
  INTERNSHIP    -> institution_internship_service.compute_internship_overview
                   (Phase 7 -- institution-wide only, see its own note)
  STUDENT       -> institution_student_service.list_students (Phase 3 --
                   same privacy boundary: no email/phone)
  DEPARTMENT    -> institution_department_service.list_departments
                   (Phase 4) + one new, honestly-derived aggregate
                   (average CGPA, computed directly from
                   student_profiles.cgpa -- nothing else computes this,
                   so it is additive, not competing)
  INDUSTRY      -> institution_industry_service.list_partners /
                   compute_metrics (Phase 8) + institution_industry_
                   connection_service.list_connections (Phase 9) +
                   institution_event_service.list_events (Phase 10) +
                   industry_collaboration_service.list_incoming_
                   collaborations (existing) -- each fetched ONCE and
                   grouped by industry_id in Python, never per-company
                   (no N+1, Step 18)
  EVENTS        -> institution_event_service.list_events /
                   compute_event_overview (Phase 10 -- no registration/
                   attendance field exists anywhere, none is fabricated
                   here either)
  COLLABORATION -> industry_collaboration_service.list_incoming_
                   collaborations (existing, pre-Phase-8 module) -- the
                   bilateral proposal lifecycle is completely untouched;
                   this only reads it

No CSV/PDF generation happens here -- confirmed by a full-repo audit,
no such library exists anywhere in this project, so the frontend builds
CSV client-side from this same JSON (plain string-joining) and offers a
browser Print for a formatted copy. See the phase's own final report for
the full audit.
"""

from datetime import UTC, datetime

from supabase import Client

from app.services import (
    industry_collaboration_service,
    institution_analytics_service,
    institution_department_service,
    institution_event_service,
    institution_industry_connection_service,
    institution_industry_service,
    institution_internship_service,
    institution_student_service,
)
from app.services.institution_placement_service import _fetch_institution_students
from app.services.institution_service import _percentage

_INTERNSHIP_NOTE = (
    "Reflects only internships your institution has explicitly curated/selected -- not every internship on "
    "the platform. Department/batch/date filters are not applied to this report because the underlying "
    "internship analytics do not support filtering the KPIs and breakdown tables consistently. See the "
    "Internships module for department-level detail and to curate additional internships."
)

_STUDENT_NOTE = (
    "No email, phone number, or interview notes are shown -- this report uses the same privacy boundary as "
    "the Student Directory."
)

_DEPARTMENT_NOTE = (
    "Average CGPA is computed only from students who have a CGPA on file (shown as N/A when none do). "
    "Per-department industry activity is not shown -- no department-to-company relationship is modeled "
    "anywhere in this schema."
)

_INDUSTRY_NOTE = (
    "Covers every company with institution activity or an explicitly tracked relationship -- see Industry "
    "Partners for full detail on any one company."
)

_EVENTS_REGISTRATION_NOTE = "Registration and attendance tracking are not available in the current system."

_COLLABORATION_NOTE = (
    "Reflects the existing collaboration proposal workflow exactly as shown on the Collaborations page -- "
    "this report does not change or reinterpret collaboration status."
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _institution_name(client: Client, institution_id: str) -> str | None:
    resp = (
        client.table("institution_profiles")
        .select("institution_name")
        .eq("id", institution_id)
        .maybe_single()
        .execute()
    )
    return (resp.data or {}).get("institution_name") if resp and resp.data else None


# ============================================================
# PLACEMENT
# ============================================================


def _placement_report(
    client: Client,
    institution_id: str,
    *,
    department_id: str | None,
    batch: int | None,
    date_from: str | None,
    date_to: str | None,
) -> dict:
    analytics = institution_analytics_service.compute_institution_analytics(
        client, institution_id, department_id=department_id, batch=batch, date_from=date_from, date_to=date_to
    )
    overview = analytics["overview"]

    summary = {
        "total_students": overview["total_students"],
        "students_with_applications": overview["students_with_applications"],
        "students_selected": overview["placed_students"],
        "placement_rate": overview["placement_rate"],
        "companies_involved": len(analytics["companies"]),
        "active_placement_drives": overview["active_placement_drives"],
    }
    department_breakdown = [
        {
            "department_id": d["id"],
            "department": d["name"],
            "student_count": d["student_count"],
            "placed_count": d["placed_count"],
            "placement_rate": d["placement_rate"],
        }
        for d in analytics["departments"]
    ]
    company_breakdown = [
        {
            "company_name": c["company_name"],
            "applicants": c["applicants"],
            "selected_offers": c["selected_offers"],
            "unique_students_placed": c["unique_students_placed"],
            "selection_rate": _percentage(c["selected_offers"], c["applicants"]),
        }
        for c in analytics["companies"]
    ]
    status_breakdown = [
        {"label": s["status"], "count": s["count"]} for s in analytics["applications"]["status_distribution"]
    ]

    return {
        "summary": summary,
        "department_breakdown": department_breakdown,
        "company_breakdown": company_breakdown,
        "status_breakdown": status_breakdown,
        "note": analytics["filter_scope_note"],
    }


# ============================================================
# INTERNSHIP
# ============================================================


def _internship_report(client: Client, institution_id: str) -> dict:
    overview = institution_internship_service.compute_internship_overview(client, institution_id)

    department_breakdown = [
        {
            "department_id": d["id"],
            "department": d["name"],
            "student_count": d["student_count"],
            "participants": d["participants"],
            "participation_rate": d["participation_rate"],
            "selected_count": d["selected_count"],
            "completed_count": d["completed_count"],
        }
        for d in overview["departments"]
    ]
    company_breakdown = [
        {
            "company_name": c["company_name"],
            "opportunities": c["opportunities"],
            "applicants": c["applicants"],
            "selected": c["selected"],
            "completed": c["completed"],
        }
        for c in overview["companies"]
    ]
    mode_distribution = [{"label": m["mode"], "count": m["count"]} for m in overview["mode_distribution"]]
    status_breakdown = [{"label": s["status"], "count": s["count"]} for s in overview["application_status_distribution"]]

    return {
        "kpis": overview["kpis"],
        "department_breakdown": department_breakdown,
        "company_breakdown": company_breakdown,
        "mode_distribution": mode_distribution,
        "status_breakdown": status_breakdown,
        "stipend_by_currency": overview["stipend"]["by_currency"],
        "note": _INTERNSHIP_NOTE,
    }


# ============================================================
# STUDENT
# ============================================================


def _student_report(
    client: Client,
    institution_id: str,
    *,
    department_id: str | None,
    batch: int | None,
    status_filter: str | None,
    page: int,
    page_size: int,
) -> dict:
    result = institution_student_service.list_students(
        client,
        institution_id,
        department=department_id,
        batch=batch,
        placement_status=status_filter,
        sort_by="name",
        sort_dir="asc",
        page=page,
        page_size=page_size,
    )
    students = [
        {
            "full_name": s["full_name"],
            "username": s["username"],
            "department": s["department"],
            "batch": s["batch"],
            "cgpa": s["cgpa"],
            "placement_status": s["placement_status"],
            "internship_status": s["internship_status"],
            "top_skills": s["top_skills"],
        }
        for s in result["students"]
    ]
    return {
        "students": students,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "summary": result["summary"],
        "note": _STUDENT_NOTE,
    }


# ============================================================
# DEPARTMENT
# ============================================================


def _department_report(client: Client, institution_id: str) -> dict:
    departments = institution_department_service.list_departments(client, institution_id)
    students = _fetch_institution_students(client, institution_id)

    cgpa_by_dept: dict[str, list[float]] = {}
    apps_count_by_dept: dict[str, int] = {}
    for s in students:
        dept_id = s.get("department_id")
        if not dept_id:
            continue
        if s.get("cgpa") is not None:
            cgpa_by_dept.setdefault(dept_id, []).append(float(s["cgpa"]))

    student_ids = [s["id"] for s in students]
    dept_by_student = {s["id"]: s.get("department_id") for s in students}
    if student_ids:
        apps_resp = (
            client.table("applications")
            .select("student_id")
            .in_("student_id", student_ids)
            .execute()
        )
        for row in apps_resp.data or []:
            dept_id = dept_by_student.get(row["student_id"])
            if dept_id:
                apps_count_by_dept[dept_id] = apps_count_by_dept.get(dept_id, 0) + 1

    rows = []
    for d in departments:
        cgpas = cgpa_by_dept.get(d["id"], [])
        rows.append(
            {
                "id": d["id"],
                "name": d["name"],
                "code": d.get("code"),
                "student_count": d["student_count"],
                "average_cgpa": round(sum(cgpas) / len(cgpas), 2) if cgpas else None,
                "placed_count": d["placed_count"],
                "placement_rate": d["placement_rate"],
                "internship_selected_count": d["internship_selected_count"],
                "applications_total": apps_count_by_dept.get(d["id"], 0),
            }
        )

    return {"departments": rows, "note": _DEPARTMENT_NOTE}


# ============================================================
# INDUSTRY / COMPANY
# ============================================================


def _company_report(client: Client, institution_id: str, *, company_id: str | None) -> dict:
    partners = institution_industry_service.list_partners(client, institution_id)
    metrics = institution_industry_service.compute_metrics(client, institution_id)

    connections = institution_industry_connection_service.list_connections(client, institution_id)
    connections_by_company: dict[str, int] = {}
    for c in connections:
        connections_by_company[c["industry_id"]] = connections_by_company.get(c["industry_id"], 0) + 1

    events = institution_event_service.list_events(client, institution_id)["events"]
    events_by_company: dict[str, int] = {}
    for e in events:
        if e.get("industry_id"):
            events_by_company[e["industry_id"]] = events_by_company.get(e["industry_id"], 0) + 1

    collaborations = industry_collaboration_service.list_incoming_collaborations(client, institution_id)
    collabs_by_company: dict[str, int] = {}
    for c in collaborations:
        collabs_by_company[c["industry_id"]] = collabs_by_company.get(c["industry_id"], 0) + 1

    rows = []
    for p in partners["partners"]:
        if company_id and p["id"] != company_id:
            continue
        rows.append(
            {
                "id": p["id"],
                "company_name": p["company_name"],
                "industry_sector": p["industry_sector"],
                "relationship_type": p["relationship_type"],
                "relationship_status": p["relationship_status"],
                "has_explicit_relationship": p["has_explicit_relationship"],
                "jobs_opportunities": p["jobs_opportunities"],
                "jobs_selected_students": p["jobs_selected_students"],
                "internship_opportunities": p["internship_opportunities"],
                "internship_selected": p["internship_selected"],
                "placement_drives_count": p["placement_drives_count"],
                "students_selected": p["students_selected"],
                "connections_count": connections_by_company.get(p["id"], 0),
                "events_count": events_by_company.get(p["id"], 0),
                "collaborations_count": collabs_by_company.get(p["id"], 0),
                "last_activity_at": p["last_activity_at"],
            }
        )

    return {"companies": rows, "metrics": metrics["metrics"], "note": _INDUSTRY_NOTE}


# ============================================================
# EVENTS
# ============================================================


def _events_report(
    client: Client, institution_id: str, *, event_type: str | None, status_filter: str | None
) -> dict:
    data = institution_event_service.list_events(client, institution_id, event_type=event_type, status=status_filter)
    events = [
        {
            "id": e["id"],
            "source": e["source"],
            "title": e["title"],
            "event_type": e["event_type"],
            "status": e["status"],
            "company_name": e["company_name"],
            "start_at": e["start_at"],
            "end_at": e["end_at"],
            "target_department_names": e["target_department_names"],
            "target_batches": e["target_batches"],
            "platform_wide": e["platform_wide"],
        }
        for e in data["events"]
    ]
    return {
        "events": events,
        "total_events": len(events),
        "upcoming_events": sum(1 for e in events if e["status"] == "PUBLISHED"),
        "completed_events": sum(1 for e in events if e["status"] == "COMPLETED"),
        "registration_note": _EVENTS_REGISTRATION_NOTE,
    }


# ============================================================
# COLLABORATION
# ============================================================


def _collaboration_report(client: Client, institution_id: str, *, collaboration_status: str | None) -> dict:
    collaborations = industry_collaboration_service.list_incoming_collaborations(
        client, institution_id, status=collaboration_status
    )
    rows = [
        {
            "id": c["id"],
            "title": c["title"],
            "company_name": c.get("industry_name"),
            "status": c["status"],
            "created_at": c.get("created_at"),
            "updated_at": c.get("updated_at"),
        }
        for c in collaborations
    ]
    status_counts: dict[str, int] = {}
    for c in rows:
        status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
    status_breakdown = [{"label": status, "count": count} for status, count in sorted(status_counts.items())]

    return {"collaborations": rows, "status_breakdown": status_breakdown, "note": _COLLABORATION_NOTE}


# ============================================================
# entry point
# ============================================================


def generate_report(
    client: Client,
    institution_id: str,
    *,
    report_type: str,
    department_id: str | None = None,
    batch: int | None = None,
    company_id: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
    collaboration_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    envelope = {
        "report_type": report_type,
        "institution_name": _institution_name(client, institution_id),
        "generated_at": _now_iso(),
        "filters_applied": {
            "department_id": department_id,
            "batch": batch,
            "company_id": company_id,
            "status": status,
            "event_type": event_type,
            "collaboration_status": collaboration_status,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    if report_type == "PLACEMENT":
        envelope["placement"] = _placement_report(
            client, institution_id, department_id=department_id, batch=batch, date_from=date_from, date_to=date_to
        )
    elif report_type == "INTERNSHIP":
        envelope["internship"] = _internship_report(client, institution_id)
    elif report_type == "STUDENT":
        envelope["student"] = _student_report(
            client,
            institution_id,
            department_id=department_id,
            batch=batch,
            status_filter=status,
            page=page,
            page_size=page_size,
        )
    elif report_type == "DEPARTMENT":
        envelope["department"] = _department_report(client, institution_id)
    elif report_type == "INDUSTRY":
        envelope["industry"] = _company_report(client, institution_id, company_id=company_id)
    elif report_type == "EVENTS":
        envelope["events"] = _events_report(client, institution_id, event_type=event_type, status_filter=status)
    elif report_type == "COLLABORATION":
        envelope["collaboration"] = _collaboration_report(
            client, institution_id, collaboration_status=collaboration_status
        )

    return envelope
