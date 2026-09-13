"""Shared constants for the Participation Workspace domain
(app.services.participation_*), keeping the PROJECT/TRAINING/WORKSHOP
table/column mapping in exactly one place so every service function stays
generic-by-kind instead of tripling logic.

Not a public API surface -- imported only by the other participation_*
service modules.
"""

OPPORTUNITY_TABLE = {
    "PROJECT": "industry_projects",
    "TRAINING": "industry_training",
    "WORKSHOP": "industry_workshops",
}
OPPORTUNITY_FK = {"PROJECT": "project_id", "TRAINING": "training_id", "WORKSHOP": "workshop_id"}

APPLICATION_TABLE = {
    "PROJECT": "industry_project_applications",
    "TRAINING": "industry_training_applications",
    "WORKSHOP": "industry_workshop_applications",
}
APPLICATION_FK = {
    "PROJECT": "project_application_id",
    "TRAINING": "training_application_id",
    "WORKSHOP": "workshop_application_id",
}

# Mirrors the CHECK in set_participation_workspace_derived_ids (063) --
# kept here too so the API layer can give a clean, friendly error before
# even attempting the insert.
ELIGIBLE_APPLICATION_STATUSES = {
    "PROJECT": frozenset({"SELECTED", "ACTIVE", "COMPLETED"}),
    "TRAINING": frozenset({"ACCEPTED", "COMPLETED"}),
    "WORKSHOP": frozenset({"ACCEPTED", "COMPLETED"}),
}

PROGRAM_SELECT = (
    "id, kind, project_id, training_id, workshop_id, title, description, "
    "status, published_at, created_at, updated_at"
)

WORKSPACE_SELECT = (
    "id, kind, student_id, industry_id, project_id, training_id, workshop_id, "
    "project_application_id, training_application_id, workshop_application_id, "
    "workspace_status, started_at, completed_at, created_at, updated_at"
)


def opportunity_ref(client, kind: str, opportunity_id: str | None) -> dict | None:
    """id/title/status for whichever opportunity `kind` points at -- used
    to enrich a program/workspace response. None if not found."""
    if not opportunity_id:
        return None
    table = OPPORTUNITY_TABLE[kind]
    response = (
        client.table(table).select("id, title, status").eq("id", opportunity_id).maybe_single().execute()
    )
    row = response.data if response is not None else None
    return dict(row) if row else None
