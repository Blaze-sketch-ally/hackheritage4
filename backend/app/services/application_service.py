"""Business logic for the Application API (Phase 1M).

Two deliberate exceptions to this project's "always use the user-scoped
client" rule, both narrowly scoped and both documented at their call
site: list_opportunity_applicants() needs each applicant's aggregate
match score, which requires reading OTHER students' assessment_attempts
-- something RLS correctly never grants to an industry account directly
(assessment_attempts' only SELECT policy is "own attempts"). This mirrors
the same class of trusted, narrow service-role use already established in
this project (Phase 1K's create_attempt()/score_attempt(), and the
service-role aggregate pattern anticipated for institution analytics in
the Phase 1L+ architecture planning pass) -- ownership is verified FIRST,
through the caller's own RLS-scoped client, before any service-role read
happens, and only a computed, aggregate score is ever returned, never a
raw assessment_attempts row.
"""

from decimal import Decimal
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import Client

from app.services import assessment_service, opportunity_service
from app.services.skill_alignment_service import compute_alignment

_APPLICATION_COLUMNS = (
    "id, opportunity_id, student_id, status, cover_note, created_at, updated_at"
)


class DuplicateApplicationError(Exception):
    """Raised when a student has already applied to this opportunity --
    mirrors the DB's own unique(opportunity_id, student_id) constraint.
    Callers should turn this into a 409, not a generic 500."""


class OpportunityNotPublishedError(Exception):
    """Raised when a student attempts to apply to a DRAFT/CLOSED
    opportunity -- the RLS INSERT policy's own WITH CHECK is the real
    enforcement (SQLSTATE 42501, row-level security violation); this
    class exists so the route layer can distinguish "not published" from
    a genuine unexpected authorization failure and return a clean 409."""


def create_application(
    client: Client, student_id: str, opportunity_id: UUID, cover_note: str | None
) -> dict:
    """Applies the authenticated student to one opportunity. student_id
    always comes from the caller's own authenticated identity -- never
    accepted from the request body (see ApplicationCreateRequest, which
    has no such field at all)."""
    try:
        response = (
            client.table("applications")
            .insert(
                {
                    "opportunity_id": str(opportunity_id),
                    "student_id": student_id,
                    "cover_note": cover_note,
                }
            )
            .execute()
        )
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateApplicationError() from exc
        if exc.code == "42501":
            raise OpportunityNotPublishedError() from exc
        raise
    return response.data[0]


def list_student_applications(client: Client, student_id: str) -> list[dict]:
    """The authenticated student's own applications, each with its
    opportunity embedded -- RLS ("Students can view their own
    applications") already scopes this to the caller; the explicit
    .eq("student_id", ...) here is defense in depth, matching the pattern
    used throughout this project."""
    response = (
        client.table("applications")
        .select(f"{_APPLICATION_COLUMNS}, opportunity:opportunities(*)")
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_application(client: Client, application_id: UUID) -> dict | None:
    """One application, scoped by RLS to the caller (either the applying
    student or the owning industry). Callers must turn None into a 404."""
    response = (
        client.table("applications")
        .select(_APPLICATION_COLUMNS)
        .eq("id", str(application_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def update_application_status(client: Client, application_id: UUID, status: str) -> dict | None:
    """Industry-only status update -- RLS's own UPDATE policy ("Industry
    can update application status for their own opportunities") is the
    real ownership enforcement; prevent_unauthorized_application_change
    (024_opportunities_and_applications.sql) independently blocks this
    call from ever changing opportunity_id/student_id/cover_note, so
    passing only `status` here is not merely convention -- it's the only
    field this function is capable of changing even if called
    differently. Returns None if the row doesn't exist or isn't owned by
    the caller's opportunity."""
    response = (
        client.table("applications").update({"status": status}).eq("id", str(application_id)).execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def list_opportunity_applicants(
    client: Client, service_client: Client, opportunity_id: UUID
) -> list[dict]:
    """The industry owner's applicant list for one opportunity, each row
    carrying a freshly-computed match score -- never a stored value, same
    "current derived view" rule Phase 1L's skill-gap already follows.

    `client`: the caller's own user-scoped client -- used for every read
    that RLS already permits an industry owner to make (the application
    rows themselves, the opportunity's own requirements, the applicant's
    profile name via the new "Industry can view profiles of their own
    applicants" policy). Ownership is proven here, by RLS, BEFORE any
    service-role read happens below -- if the caller doesn't own this
    opportunity, `applications` comes back empty and this function
    returns an empty list, never reaching the service-role step at all.

    `service_client`: get_supabase() -- used ONLY to read each already-
    proven-legitimate applicant's assessment_attempts (RLS has no
    industry-visibility policy for that table, correctly), so this
    function's match computation can proceed. Never returns anything from
    assessment_attempts itself -- only the aggregate score
    compute_alignment() produces.
    """
    applications = (
        client.table("applications")
        .select(_APPLICATION_COLUMNS)
        .eq("opportunity_id", str(opportunity_id))
        .order("created_at")
        .execute()
        .data
        or []
    )
    if not applications:
        return []

    requirements = opportunity_service.get_requirements(client, opportunity_id)

    student_ids = [app["student_id"] for app in applications]
    profiles_by_id = {
        row["id"]: row
        for row in (
            client.table("profiles")
            .select("id, full_name, username")
            .in_("id", student_ids)
            .execute()
            .data
            or []
        )
    }

    applicants = []
    for app in applications:
        student_scores = assessment_service.get_student_skill_scores(service_client, app["student_id"])
        summary = compute_alignment(requirements, student_scores)
        profile = profiles_by_id.get(app["student_id"])
        applicants.append(
            {
                "id": app["id"],
                "student_id": app["student_id"],
                "student_name": (profile or {}).get("full_name") or (profile or {}).get("username"),
                "status": app["status"],
                "cover_note": app["cover_note"],
                "overall_match_score": summary.overall_score,
                "created_at": app["created_at"],
                "updated_at": app["updated_at"],
            }
        )
    return applicants


def get_applicant_detail(
    client: Client, service_client: Client, opportunity_id: UUID, application_id: UUID
) -> dict | None:
    """One applicant, industry-facing, WITH the per-skill breakdown
    list_opportunity_applicants computes internally but discards (Phase
    1N: GET /opportunities/{id}/applicants/{application_id}, the
    "Applicant" step of Industry -> My Opportunities -> Applicants ->
    Applicant -> Portfolio). Same ownership-then-service-role shape as
    list_opportunity_applicants: the application row is fetched through
    the caller's own RLS-scoped client first (scoped to both this
    opportunity_id AND this application_id -- an unrelated industry, or
    an application belonging to a different opportunity, gets None here,
    never reaching the service-role step below), and the target
    student's assessment evidence is read via service_client only
    because RLS correctly has no cross-student assessment_attempts
    visibility policy for any role. Returns None (-> 404) rather than
    ever distinguishing "wrong opportunity" from "not your opportunity"
    from "doesn't exist" -- same non-leaking shape as get_opportunity."""
    application = (
        client.table("applications")
        .select(_APPLICATION_COLUMNS)
        .eq("id", str(application_id))
        .eq("opportunity_id", str(opportunity_id))
        .maybe_single()
        .execute()
    )
    if application is None or not application.data:
        return None
    app_row = application.data

    requirements = opportunity_service.get_requirements(client, opportunity_id)
    student_scores = assessment_service.get_student_skill_scores(service_client, app_row["student_id"])
    summary = compute_alignment(requirements, student_scores)

    profile = (
        client.table("profiles")
        .select("full_name, username")
        .eq("id", app_row["student_id"])
        .maybe_single()
        .execute()
    )
    profile_data = profile.data if profile is not None else None

    return {
        "id": app_row["id"],
        "student_id": app_row["student_id"],
        "student_name": (profile_data or {}).get("full_name") or (profile_data or {}).get("username"),
        "status": app_row["status"],
        "cover_note": app_row["cover_note"],
        "overall_match_score": summary.overall_score,
        "created_at": app_row["created_at"],
        "updated_at": app_row["updated_at"],
        "skills": summary.results,
    }


def get_student_match(
    client: Client, student_id: str, opportunity_id: UUID
) -> tuple[Decimal, list]:
    """The authenticated student's own match against one opportunity --
    both the requirements and the student's own skill evidence are read
    through the caller's own user-scoped client (RLS permits both: the
    opportunity's requirements once PUBLISHED, and a student's own
    assessment_attempts always), so no service-role client is needed
    here at all, unlike list_opportunity_applicants above."""
    requirements = opportunity_service.get_requirements(client, opportunity_id)
    student_scores = assessment_service.get_student_skill_scores(client, student_id)
    summary = compute_alignment(requirements, student_scores)
    return summary.overall_score, summary.results
