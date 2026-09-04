"""Pydantic schemas for Phase 7 -- internship completion + certificate
(database/migrations/039_workspace_submissions_completion.sql:
`internship_completions`, `internship_certificates`,
`public.verify_internship_certificate`).

Completion "requirements met" is ALWAYS computed live from
program_assignments.is_required + is_published and workspace_submissions
(an ACCEPTED attempt) -- it is never stored as authoritative state. The
only thing this phase persists is the industry's explicit verification
(`internship_completions`, one row per workspace) and the certificate it
produces (`internship_certificates`, one row per completion, immutable
snapshot). `certificate_number` / `reviewer` / `verified_by` /
`student_id` / `industry_id` are always server-derived -- never accepted
from a client.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# internship_completions.outcome CHECK (039).
CompletionOutcome = Literal["PASS", "FAIL"]


class OutstandingRequirement(BaseModel):
    """One unmet REQUIRED + published program_assignment -- the student has
    no ACCEPTED submission for it yet."""

    kind: Literal["ASSIGNMENT"] = "ASSIGNMENT"
    id: str
    title: str


class CertificateSkill(BaseModel):
    skill_id: str
    skill_name: str


class CertificateInfo(BaseModel):
    """The frozen public snapshot (internship_certificates.details), plus
    the record's own immutable fields. Never a live join -- the snapshot
    is captured once, at issuance."""

    certificate_number: str
    student_name: str | None = None
    company_name: str | None = None
    internship_title: str | None = None
    issued_at: str | None = None
    skills: list[CertificateSkill] = []
    revoked: bool = False


class CompletionSummary(BaseModel):
    """Answers: how many required assignments, how many are done, what's
    outstanding, has industry verified, and is a certificate available.
    `completed_count` / `required_count` / `outstanding` are ALWAYS
    computed live -- never read back from a stored column."""

    workspace_id: str
    required_count: int
    completed_count: int
    requirements_met: bool
    outstanding: list[OutstandingRequirement] = []
    industry_verified: bool
    result: CompletionOutcome | None = None
    verified_at: str | None = None
    certificate: CertificateInfo | None = None


class VerifyCompletionRequest(BaseModel):
    """POST .../completion/verify body. `industry_id` / `verified_by` /
    `outcome` / `workspace_id` are never accepted -- all server-derived."""

    model_config = ConfigDict(extra="forbid")

    summary: str | None = Field(default=None, max_length=4000)


# ---- public verification (public.verify_internship_certificate) ----


class PublicCertificateResponse(BaseModel):
    """Exactly the columns public.verify_internship_certificate(text)
    returns -- no email, no UUIDs, no submission/stipend data."""

    certificate_number: str
    student_name: str | None = None
    company_name: str | None = None
    title: str | None = None
    issued_at: str | None = None
    status: Literal["VALID", "REVOKED"]
