"""Business logic for the INDUSTRY side of Participation Programs
(`participation_programs` / `_modules` / `_resources` / `_assignments`,
database/migrations/062_participation_programs.sql).

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- RLS (owns_participation_program)
is the real access-control boundary. Nothing here uses service_role.
Generic by `kind` -- one implementation for PROJECT/TRAINING/WORKSHOP,
never three.
"""

from datetime import UTC, datetime

from supabase import Client

from app.services._participation_common import (
    OPPORTUNITY_FK,
    OPPORTUNITY_TABLE,
    PROGRAM_SELECT,
    opportunity_ref,
)

_MODULE_SELECT = "id, program_id, title, description, sequence_order, is_published, created_at, updated_at"
_RESOURCE_SELECT = (
    "id, program_id, module_id, title, description, resource_type, resource_url, "
    "sequence_order, is_published, created_at"
)
_ASSIGNMENT_SELECT = (
    "id, program_id, module_id, title, description, instructions, due_at, max_score, "
    "is_required, is_published, sequence_order, created_at, updated_at"
)


class OpportunityNotOwnedError(Exception):
    """The caller does not own the referenced project/training/workshop."""


class ProgramAlreadyExistsError(Exception):
    """This opportunity already has a participation program (1:1)."""


def _own_opportunity(client: Client, industry_id: str, kind: str, opportunity_id: str) -> bool:
    table = OPPORTUNITY_TABLE[kind]
    response = (
        client.table(table).select("id").eq("id", opportunity_id).eq("industry_id", industry_id).maybe_single().execute()
    )
    return bool(response.data) if response is not None else False


def get_program(client: Client, industry_id: str, program_id: str) -> dict | None:
    response = client.table("participation_programs").select(PROGRAM_SELECT).eq("id", program_id).maybe_single().execute()
    row = response.data if response is not None else None
    if not row:
        return None
    kind = row["kind"]
    opp_id = row.get(OPPORTUNITY_FK[kind])
    if not _own_opportunity(client, industry_id, kind, opp_id):
        return None
    row["opportunity"] = opportunity_ref(client, kind, opp_id)
    return row


def get_program_for_opportunity(client: Client, industry_id: str, kind: str, opportunity_id: str) -> dict | None:
    """The one program for this opportunity, or None -- callers turn None
    into "no program yet" (404), never an error."""
    if not _own_opportunity(client, industry_id, kind, opportunity_id):
        return None
    response = (
        client.table("participation_programs")
        .select(PROGRAM_SELECT)
        .eq(OPPORTUNITY_FK[kind], opportunity_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    row["opportunity"] = opportunity_ref(client, kind, opportunity_id)
    return row


def create_program(client: Client, industry_id: str, data: dict) -> dict:
    kind = data["kind"]
    fk = OPPORTUNITY_FK[kind]
    opportunity_id = data.get(fk)
    if not _own_opportunity(client, industry_id, kind, opportunity_id):
        raise OpportunityNotOwnedError(opportunity_id)

    existing = get_program_for_opportunity(client, industry_id, kind, opportunity_id)
    if existing:
        raise ProgramAlreadyExistsError(opportunity_id)

    payload = {"kind": kind, fk: opportunity_id, "title": data["title"], "description": data.get("description")}
    response = client.table("participation_programs").insert(payload).execute()
    new_id = response.data[0]["id"]
    row = get_program(client, industry_id, new_id)
    if row is None:
        raise RuntimeError("participation program could not be read back after create.")
    return row


def update_program(client: Client, industry_id: str, program_id: str, data: dict) -> dict | None:
    existing = get_program(client, industry_id, program_id)
    if existing is None:
        return None
    payload = {k: v for k, v in data.items() if k in ("title", "description")}
    if payload:
        client.table("participation_programs").update(payload).eq("id", program_id).execute()
    return get_program(client, industry_id, program_id)


def publish_program(client: Client, industry_id: str, program_id: str) -> dict | None:
    existing = get_program(client, industry_id, program_id)
    if existing is None:
        return None
    client.table("participation_programs").update(
        {"status": "PUBLISHED", "published_at": datetime.now(UTC).isoformat()}
    ).eq("id", program_id).execute()
    return get_program(client, industry_id, program_id)


def archive_program(client: Client, industry_id: str, program_id: str) -> dict | None:
    existing = get_program(client, industry_id, program_id)
    if existing is None:
        return None
    client.table("participation_programs").update({"status": "ARCHIVED"}).eq("id", program_id).execute()
    return get_program(client, industry_id, program_id)


# ---- modules ----


def list_modules(client: Client, industry_id: str, program_id: str) -> list[dict] | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    response = (
        client.table("participation_modules").select(_MODULE_SELECT).eq("program_id", program_id).order("sequence_order").execute()
    )
    return response.data or []


def create_module(client: Client, industry_id: str, program_id: str, data: dict) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    payload = {"program_id": program_id, **{k: v for k, v in data.items() if k in ("title", "description", "sequence_order")}}
    response = client.table("participation_modules").insert(payload).execute()
    return response.data[0]


def update_module(client: Client, industry_id: str, program_id: str, module_id: str, data: dict) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    payload = {k: v for k, v in data.items() if k in ("title", "description", "sequence_order")}
    if payload:
        client.table("participation_modules").update(payload).eq("id", module_id).eq("program_id", program_id).execute()
    response = client.table("participation_modules").select(_MODULE_SELECT).eq("id", module_id).maybe_single().execute()
    return response.data if response is not None else None


def set_module_published(client: Client, industry_id: str, program_id: str, module_id: str, published: bool) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    client.table("participation_modules").update({"is_published": published}).eq("id", module_id).eq("program_id", program_id).execute()
    response = client.table("participation_modules").select(_MODULE_SELECT).eq("id", module_id).maybe_single().execute()
    return response.data if response is not None else None


# ---- resources ----


def list_resources(client: Client, industry_id: str, program_id: str) -> list[dict] | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    response = (
        client.table("participation_resources").select(_RESOURCE_SELECT).eq("program_id", program_id).order("sequence_order").execute()
    )
    return response.data or []


def create_resource(client: Client, industry_id: str, program_id: str, data: dict) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    payload = {
        "program_id": program_id,
        **{k: v for k, v in data.items() if k in ("module_id", "title", "description", "resource_type", "resource_url", "sequence_order")},
    }
    response = client.table("participation_resources").insert(payload).execute()
    return response.data[0]


def update_resource(client: Client, industry_id: str, program_id: str, resource_id: str, data: dict) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    payload = {k: v for k, v in data.items() if k in ("title", "description", "resource_url", "sequence_order")}
    if payload:
        client.table("participation_resources").update(payload).eq("id", resource_id).eq("program_id", program_id).execute()
    response = client.table("participation_resources").select(_RESOURCE_SELECT).eq("id", resource_id).maybe_single().execute()
    return response.data if response is not None else None


def set_resource_published(client: Client, industry_id: str, program_id: str, resource_id: str, published: bool) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    client.table("participation_resources").update({"is_published": published}).eq("id", resource_id).eq("program_id", program_id).execute()
    response = client.table("participation_resources").select(_RESOURCE_SELECT).eq("id", resource_id).maybe_single().execute()
    return response.data if response is not None else None


# ---- assignments ----


def list_assignments(client: Client, industry_id: str, program_id: str) -> list[dict] | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    response = (
        client.table("participation_assignments").select(_ASSIGNMENT_SELECT).eq("program_id", program_id).order("sequence_order").execute()
    )
    return response.data or []


def create_assignment(client: Client, industry_id: str, program_id: str, data: dict) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    payload = {
        "program_id": program_id,
        **{
            k: v
            for k, v in data.items()
            if k in ("module_id", "title", "description", "instructions", "due_at", "max_score", "is_required", "sequence_order")
        },
    }
    response = client.table("participation_assignments").insert(payload).execute()
    return response.data[0]


def update_assignment(client: Client, industry_id: str, program_id: str, assignment_id: str, data: dict) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    payload = {
        k: v
        for k, v in data.items()
        if k in ("title", "description", "instructions", "due_at", "max_score", "is_required", "sequence_order")
    }
    if payload:
        client.table("participation_assignments").update(payload).eq("id", assignment_id).eq("program_id", program_id).execute()
    response = client.table("participation_assignments").select(_ASSIGNMENT_SELECT).eq("id", assignment_id).maybe_single().execute()
    return response.data if response is not None else None


def set_assignment_published(client: Client, industry_id: str, program_id: str, assignment_id: str, published: bool) -> dict | None:
    if get_program(client, industry_id, program_id) is None:
        return None
    client.table("participation_assignments").update({"is_published": published}).eq("id", assignment_id).eq("program_id", program_id).execute()
    response = client.table("participation_assignments").select(_ASSIGNMENT_SELECT).eq("id", assignment_id).maybe_single().execute()
    return response.data if response is not None else None
