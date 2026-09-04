"""Pydantic schemas for Phase 8 -- internship stipend record-keeping
(database/migrations/039_workspace_submissions_completion.sql --
stipend_disbursements).

RECORD-KEEPING ONLY. There is no payment gateway, no bank/UPI integration,
and no real money movement anywhere in this module -- "RELEASED" means the
industry has recorded that a disbursement happened, exactly as the
migration's own comment says ("stipend_disbursements -- record-keeping
only"). This is independent of internship_completions /
internship_certificates (Phase 7): a workspace can be PASS + completed
with a stipend still PENDING, or vice versa -- nothing here reads or
writes those tables, and nothing there triggers a stipend transition.

`workspace_id` / `industry_id` / `released_by` / `disbursement_status`
(on create) are never accepted from the client -- every one is derived
from the URL path, the authenticated token, or the server-side state
machine.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# stipend_disbursements.disbursement_status CHECK (039).
StipendStatus = Literal["PENDING", "APPROVED", "RELEASED", "CANCELLED"]


class StipendResponse(BaseModel):
    id: str
    workspace_id: str
    amount: float
    currency: str
    disbursement_status: StipendStatus
    reference: str | None = None
    notes: str | None = None
    released_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StipendSummary(BaseModel):
    """Always 200s for an owned workspace -- `stipend` is null until the
    industry configures one. Mirrors the Phase 7 CompletionSummary shape
    (workspace_id + an optional nested record) for the same reason: "no
    record yet" is a normal, honest state, not a 404."""

    workspace_id: str
    stipend: StipendResponse | None = None


class CreateStipendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(ge=0)
    currency: str = Field(default="INR", min_length=1, max_length=10)
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class UpdateStipendRequest(BaseModel):
    """Only while PENDING (service-enforced -- the DB itself does not lock
    financial fields on APPROVED/RELEASED/CANCELLED, only the status
    column). Partial: only the fields present are changed."""

    model_config = ConfigDict(extra="forbid")

    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=1, max_length=10)
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
