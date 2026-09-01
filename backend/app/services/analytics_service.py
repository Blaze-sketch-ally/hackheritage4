"""Business logic for Industry Analytics
(backend/app/api/analytics.py, GET /api/v1/analytics/industry).

One aggregation call, computed live from the caller's OWN records through
a user-scoped RLS client (never service_role). Scoped by industry_id on
every query -- an Industry account can only ever see its own numbers.

Round trips: this makes ~9 scoped reads (applications, interviews,
collaborations, and the six opportunity modules), selecting only the
columns each metric needs -- never a full table, never a sensitive
candidate column (no student_id, no cover notes, no match detail). The
frontend then makes ONE call instead of the 9 the dashboard fan-out used
to make from the browser.

Historical honesty: the only timestamps in the schema are row-creation
dates (`created_at`, applications' `applied_at`). Nothing records WHEN a
status changed. So the timeline is strictly "records created per month";
funnel-movement-over-time and stage-conversion trends are not computed
here because the data to compute them truthfully does not exist. See
`_HISTORICAL_NOTE`.
"""

from collections import Counter
from datetime import UTC, datetime

from supabase import Client

from app.schemas.application import APPLICATION_STATUSES

_HISTORICAL_NOTE = (
    "Time-series reflects when records were created (opportunities by creation date, "
    "applications by application date). The database stores only each record's current "
    "status, not when it changed, so trends in pipeline movement over time "
    "(shortlist rate, selection rate, time-to-hire) are not shown -- they would require "
    "a status-history table that does not exist."
)

# The six opportunity modules, in a stable order. Each tuple is
# (table, response opportunity_type label).
_OPPORTUNITY_MODULES = (
    ("internships", "INTERNSHIP"),
    ("jobs", "JOB"),
    ("industry_projects", "PROJECT"),
    ("industry_training", "TRAINING"),
    ("industry_workshops", "WORKSHOP"),
    ("industry_mentorship", "MENTORSHIP"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _month_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return f"{dt.year:04d}-{dt.month:02d}"


def _recent_month_keys(count: int = 6) -> list[str]:
    """The last `count` calendar months, oldest first, as 'YYYY-MM'."""
    now = _now()
    keys: list[str] = []
    year, month = now.year, now.month
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def _fetch_opportunity_rows(client: Client, industry_id: str) -> dict[str, list[dict]]:
    """One scoped read per opportunity module -- id/title/status/created_at
    only. Titles are only needed for internships/jobs (the only modules
    that feed applications / top-opportunities), but selecting the same
    small column set everywhere keeps this simple and the payloads tiny."""
    out: dict[str, list[dict]] = {}
    for table, _label in _OPPORTUNITY_MODULES:
        resp = (
            client.table(table)
            .select("id, title, status, created_at")
            .eq("industry_id", industry_id)
            .execute()
        )
        out[table] = list(resp.data or [])
    return out


def _fetch_interview_rows(client: Client, industry_id: str) -> tuple[list[dict], bool]:
    """Scoped read of interview status + time. Returns ([], False) when
    the interviews table (migration 030) is not present yet -- analytics
    still works, interview metrics just read as zero with a note."""
    try:
        resp = (
            client.table("interviews")
            .select("status, scheduled_at")
            .eq("industry_id", industry_id)
            .execute()
        )
        return list(resp.data or []), True
    except Exception:  # noqa: BLE001 -- migration 030 not applied: degrade gracefully
        return [], False


def compute_industry_analytics(client: Client, industry_id: str) -> dict:
    applications = list(
        client.table("applications")
        .select("id, status, applied_at, opportunity_type, internship_id, job_id")
        .eq("industry_id", industry_id)
        .execute()
        .data
        or []
    )
    collaborations = list(
        client.table("industry_collaborations")
        .select("status")
        .eq("industry_id", industry_id)
        .execute()
        .data
        or []
    )
    opportunity_rows = _fetch_opportunity_rows(client, industry_id)
    interview_rows, interviews_available = _fetch_interview_rows(client, industry_id)

    now = _now()

    # ---- application status distribution + funnel ----
    status_counter = Counter(row.get("status") for row in applications)
    funnel_counts = {name: int(status_counter.get(name, 0)) for name in APPLICATION_STATUSES}
    status_distribution = [
        {"status": name, "count": funnel_counts[name]} for name in APPLICATION_STATUSES
    ]

    # ---- opportunity breakdown ----
    breakdown: list[dict] = []
    opportunities_total = 0
    opportunities_published = 0
    for table, label in _OPPORTUNITY_MODULES:
        rows = opportunity_rows.get(table, [])
        published = sum(1 for r in rows if r.get("status") == "PUBLISHED")
        breakdown.append({"opportunity_type": label, "total": len(rows), "published": published})
        opportunities_total += len(rows)
        opportunities_published += published

    # ---- interview metrics ----
    iv_counter = Counter(row.get("status") for row in interview_rows)
    iv_upcoming = 0
    for row in interview_rows:
        if row.get("status") != "SCHEDULED":
            continue
        try:
            when = datetime.fromisoformat(str(row["scheduled_at"]))
        except (ValueError, KeyError, TypeError):
            continue
        if when >= now:
            iv_upcoming += 1
    interview_metrics = {
        "total": len(interview_rows),
        "scheduled": int(iv_counter.get("SCHEDULED", 0)),
        "completed": int(iv_counter.get("COMPLETED", 0)),
        "cancelled": int(iv_counter.get("CANCELLED", 0)),
        "upcoming": iv_upcoming,
    }

    # ---- collaborations ----
    collab_counter = Counter(row.get("status") for row in collaborations)

    # ---- top opportunities by application volume ----
    title_by_id: dict[str, dict] = {}
    for table in ("internships", "jobs"):
        for r in opportunity_rows.get(table, []):
            title_by_id[r["id"]] = {
                "title": r.get("title") or "(untitled)",
                "opportunity_type": "INTERNSHIP" if table == "internships" else "JOB",
            }
    app_by_opportunity: Counter = Counter()
    for row in applications:
        opp_id = row.get("internship_id") or row.get("job_id")
        if opp_id:
            app_by_opportunity[opp_id] += 1
    top_opportunities = [
        {
            "id": opp_id,
            "title": title_by_id.get(opp_id, {}).get("title", "(posting unavailable)"),
            "opportunity_type": title_by_id.get(opp_id, {}).get("opportunity_type", "UNKNOWN"),
            "application_count": count,
        }
        for opp_id, count in app_by_opportunity.most_common(5)
    ]

    # ---- timeline (creation dates only) ----
    months = _recent_month_keys(6)
    opp_created_by_month: Counter = Counter()
    for table, _label in _OPPORTUNITY_MODULES:
        for r in opportunity_rows.get(table, []):
            key = _month_key(r.get("created_at"))
            if key:
                opp_created_by_month[key] += 1
    apps_received_by_month: Counter = Counter()
    for row in applications:
        key = _month_key(row.get("applied_at"))
        if key:
            apps_received_by_month[key] += 1
    timeline = [
        {
            "period": m,
            "opportunities_created": int(opp_created_by_month.get(m, 0)),
            "applications_received": int(apps_received_by_month.get(m, 0)),
        }
        for m in months
    ]

    kpis = {
        "opportunities_total": opportunities_total,
        "opportunities_published": opportunities_published,
        "applications_total": len(applications),
        "shortlisted": funnel_counts["SHORTLISTED"],
        "interviews_total": len(interview_rows),
        "interviews_upcoming": iv_upcoming,
        "selected": funnel_counts["SELECTED"],
        "collaborations_total": len(collaborations),
        "collaborations_active": int(collab_counter.get("ACTIVE", 0)),
    }

    note = _HISTORICAL_NOTE
    if not interviews_available:
        note += (
            " Interview metrics are shown as zero because the interviews table "
            "(migration 030) has not been applied to this database yet."
        )

    return {
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "funnel_counts": funnel_counts,
        "funnel_total": len(applications),
        "application_status_distribution": status_distribution,
        "opportunity_breakdown": breakdown,
        "interview_metrics": interview_metrics,
        "top_opportunities": top_opportunities,
        "timeline": timeline,
        "historical_note": note,
        "interviews_available": interviews_available,
    }
