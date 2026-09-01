"""Pydantic schemas for Industry collaborations.

Field names and constraints match database/migrations/026_industry_collaborations.sql
exactly (`industry_collaborations`). This is NOT a posting entity like
industry_project/industry_training/industry_workshop/industry_mentorship
(022-025) -- it is a bilateral academia-industry collaboration
proposal/relationship between an INDUSTRY account (initiator) and a
FACULTY or INSTITUTION account (recipient), with its own lifecycle:
DRAFT -> SENT -> ACCEPTED/REJECTED -> ACTIVE -> COMPLETED/CANCELLED.

Named `industry_collaboration` (not `collaboration`/`collaborations`) to
avoid colliding with the still-unimplemented, ambiguous generic stubs
(backend/app/api/collaborations.py, backend/app/schemas/collaboration.py)
and with 009_collaboration.sql's own broader, unimplemented scope.

Ownership (`industry_id`) and lifecycle (`status`) are never accepted from
the client -- `industry_id` is always the authenticated caller, and
`status` only changes through the explicit lifecycle endpoints.
`recipient_type` is never accepted from the client either -- it is
derived server-side (by a database trigger) from the referenced
recipient's real `profiles.role`. `extra="forbid"` on the write models is
what structurally rejects an attempt to smuggle any of these in.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CollaborationStatus = Literal[
    "DRAFT", "SENT", "ACCEPTED", "REJECTED", "ACTIVE", "COMPLETED", "CANCELLED"
]
RecipientType = Literal["FACULTY", "INSTITUTION"]

COLLABORATION_STATUSES: tuple[str, ...] = (
    "DRAFT",
    "SENT",
    "ACCEPTED",
    "REJECTED",
    "ACTIVE",
    "COMPLETED",
    "CANCELLED",
)
RECIPIENT_TYPES: tuple[str, ...] = ("FACULTY", "INSTITUTION")


class CollaborationCreate(BaseModel):
    """POST /api/v1/collaborations. Always created as DRAFT -- there is no
    `status` field here, and no `industry_id`. `recipient_id` must be the
    id of an existing FACULTY or INSTITUTION profile (typically obtained
    via GET /collaborations/recipients/resolve first) -- the database
    trigger rejects anything else and derives `recipient_type` itself, so
    there is no `recipient_type` field here either."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    recipient_id: UUID


class CollaborationUpdate(BaseModel):
    """PUT /api/v1/collaborations/{id}. Partial: only the fields actually
    sent are changed. Only permitted while the collaboration is still
    DRAFT -- the service layer rejects this once sent. `recipient_id` is
    immutable after creation (not editable here, ever) and `status`
    cannot be changed here."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)


class IndustryCollaboration(BaseModel):
    id: str
    industry_id: str
    recipient_id: str
    recipient_type: str
    title: str
    description: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    # Display identity of each party, resolved server-side via the
    # collaboration_counterparty_names() function (migration 029) -- the
    # read-side counterpart of the recipient resolver. `industry_name` is
    # the initiator's company_name (profiles.full_name fallback);
    # `recipient_name` is the FACULTY/INSTITUTION account's full_name.
    # Null when migration 029 has not been applied yet, or (rarely) when a
    # party has no name on file -- the UI falls back to the recipient-type
    # label. Never accepted from the client; not stored on the table.
    industry_name: str | None = None
    recipient_name: str | None = None


class CollaborationListResponse(BaseModel):
    collaborations: list[IndustryCollaboration]


class RecipientResolution(BaseModel):
    """GET /api/v1/collaborations/recipients/resolve response. Deliberately
    minimal -- id, role, full_name only. No email/phone/other profile
    fields, and only ever populated for a FACULTY or INSTITUTION match."""

    id: str
    role: str
    full_name: str | None = None
