"""Business logic for the Portfolio API (Phase 1N).

Every function here takes an already-constructed, user-scoped Supabase
client (app.core.security.build_user_client) -- RLS
(025_portfolio_projects_and_certifications.sql) is the real enforcement
for ownership and cross-role (industry applicant) visibility; this
module's own checks are defense in depth, matching every other service
module in this project. No service-role usage anywhere in this file --
unlike application_service.list_opportunity_applicants (which needs
another student's assessment_attempts, a table RLS never grants industry
access to), RLS alone already grants an industry account read access to
a legitimate applicant's portfolio directly, so no privileged read is
ever required here.

get_student_portfolio() is deliberately the ONE function used both by a
student reading their own portfolio (GET /portfolio) and by an industry
account reading an applicant's portfolio (GET /applications/{id}/
portfolio, in app/api/applications.py) -- RLS alone decides what each
caller may see; this module never branches on caller role itself.
"""

from uuid import UUID

from supabase import Client

_PROJECT_COLUMNS = (
    "id, student_id, title, description, technologies, project_url, github_url, created_at, updated_at"
)
_CERTIFICATION_COLUMNS = (
    "id, student_id, name, issuer, issue_date, credential_url, created_at, updated_at"
)


# ============================================================
# portfolio_projects
# ============================================================


def list_projects(client: Client, student_id: str) -> list[dict]:
    """The given student's own projects -- RLS ("Students can view their
    own projects" / "Industry can view projects of their own
    applicants") already scopes this to whoever the caller legitimately
    is; the explicit .eq("student_id", ...) here is defense in depth,
    matching the pattern used throughout this project."""
    response = (
        client.table("portfolio_projects")
        .select(_PROJECT_COLUMNS)
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_project(client: Client, project_id: UUID) -> dict | None:
    """One project, or None if it doesn't exist / isn't visible to the
    caller. Callers must turn None into a 404."""
    response = (
        client.table("portfolio_projects")
        .select(_PROJECT_COLUMNS)
        .eq("id", str(project_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def create_project(client: Client, student_id: str, payload: dict) -> dict:
    """student_id is always the authenticated caller's own id, never
    client-supplied (ProjectCreateRequest has no such field). RLS's own
    INSERT policy ("...auth.uid() = student_id and is_student(...)") is
    the real enforcement; this function's shape is defense in depth."""
    response = (
        client.table("portfolio_projects").insert({**payload, "student_id": student_id}).execute()
    )
    return response.data[0]


def update_project(client: Client, project_id: UUID, payload: dict) -> dict | None:
    """Partial update. Ownership (and the impossibility of reassigning
    student_id) is enforced entirely by RLS's symmetric USING/WITH CHECK
    -- see the migration's own header comment. Returns None if the row
    doesn't exist or isn't owned by the caller."""
    response = (
        client.table("portfolio_projects").update(payload).eq("id", str(project_id)).execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def delete_project(client: Client, project_id: UUID) -> bool:
    """True if a row was actually deleted -- False means it didn't exist
    or wasn't owned by the caller (RLS matches zero rows either way, not
    an error), which the caller must turn into a 404."""
    response = client.table("portfolio_projects").delete().eq("id", str(project_id)).execute()
    return bool(response.data)


# ============================================================
# portfolio_certifications
# ============================================================


def list_certifications(client: Client, student_id: str) -> list[dict]:
    response = (
        client.table("portfolio_certifications")
        .select(_CERTIFICATION_COLUMNS)
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_certification(client: Client, certification_id: UUID) -> dict | None:
    response = (
        client.table("portfolio_certifications")
        .select(_CERTIFICATION_COLUMNS)
        .eq("id", str(certification_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def create_certification(client: Client, student_id: str, payload: dict) -> dict:
    response = (
        client.table("portfolio_certifications")
        .insert({**payload, "student_id": student_id})
        .execute()
    )
    return response.data[0]


def update_certification(client: Client, certification_id: UUID, payload: dict) -> dict | None:
    response = (
        client.table("portfolio_certifications")
        .update(payload)
        .eq("id", str(certification_id))
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def delete_certification(client: Client, certification_id: UUID) -> bool:
    response = (
        client.table("portfolio_certifications").delete().eq("id", str(certification_id)).execute()
    )
    return bool(response.data)


# ============================================================
# Combined view
# ============================================================


def get_student_portfolio(client: Client, student_id: str) -> dict:
    """Both sections together -- used by GET /portfolio (student, own
    id) and GET /applications/{id}/portfolio (industry, an applicant's
    id, after app/api/applications.py has already proven the
    application/opportunity ownership chain via
    application_service.get_application()). RLS is what actually decides
    whether either read returns anything: an industry caller with no
    legitimate application relationship to this student_id gets back
    empty lists here, not an error -- same "RLS silently returns nothing
    for an unowned relationship" shape used throughout this project."""
    return {
        "student_id": student_id,
        "projects": list_projects(client, student_id),
        "certifications": list_certifications(client, student_id),
    }
