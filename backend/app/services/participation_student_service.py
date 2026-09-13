"""Read-only STUDENT-side content listings for a Participation Workspace's
program (modules/resources/assignments). RLS (student_has_workspace_for_program,
063) is the real access-control boundary -- these queries rely on it rather
than re-implementing ownership, since a student's own user-scoped client
only ever gets back PUBLISHED rows for a program they hold a workspace in.
"""

from supabase import Client

_MODULE_SELECT = "id, program_id, title, description, sequence_order, is_published, created_at, updated_at"
_RESOURCE_SELECT = (
    "id, program_id, module_id, title, description, resource_type, resource_url, "
    "sequence_order, is_published, created_at"
)
_ASSIGNMENT_SELECT = (
    "id, program_id, module_id, title, description, instructions, due_at, max_score, "
    "is_required, is_published, sequence_order, created_at, updated_at"
)


def list_modules(client: Client, program_id: str) -> list[dict]:
    return (
        client.table("participation_modules").select(_MODULE_SELECT).eq("program_id", program_id).order("sequence_order").execute().data
        or []
    )


def list_resources(client: Client, program_id: str) -> list[dict]:
    return (
        client.table("participation_resources").select(_RESOURCE_SELECT).eq("program_id", program_id).order("sequence_order").execute().data
        or []
    )


def list_assignments(client: Client, program_id: str) -> list[dict]:
    return (
        client.table("participation_assignments").select(_ASSIGNMENT_SELECT).eq("program_id", program_id).order("sequence_order").execute().data
        or []
    )


def list_criteria(client: Client, program_id: str) -> list[dict]:
    return (
        client.table("participation_evaluation_criteria")
        .select("id, program_id, name, description, max_score, weight, sequence_order")
        .eq("program_id", program_id)
        .order("sequence_order")
        .execute()
        .data
        or []
    )
