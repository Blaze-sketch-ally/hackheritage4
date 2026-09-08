"""Pydantic schemas for PHASE J4 -- Job Training completion + certificate
(database/migrations/041_job_training_completion.sql:
`job_training_completions`, `job_training_certificates`,
`public.verify_job_training_certificate`).

Job Training completion is NEVER computed / automatic: it is exactly the
industry's explicit verification (`job_training_completions`, one row per
enrollment) plus the certificate it produces when the outcome is PASS
(`job_training_certificates`, one row per completion, immutable
snapshot). `certificate_number` / `verified_by` / `student_id` /
`industry_id` / `job_id` / `program_id` are ALWAYS server-derived --
never accepted from a client.

Mirrors app.schemas.internship_completion, adapted: a single
`completion_status` (PENDING / PASSED / FAILED) instead of the
internship's completion_status + outcome pair, and job_title +
program_title exposed distinctly in the public certificate.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# job_training_completions.completion_status CHECK (041).
JobTrainingCompletionStatus = Literal["PENDING", "PASSED", "FAILED"]
# The industry's decision, as sent to the verify endpoint. 'PASS' -> the
# row becomes PASSED and a certificate is issued; 'FAIL' -> FAILED, no
# certificate.
VerifyOutcome = Literal["PASS", "FAIL"]


class JobTrainingCertificateInfo(BaseModel):
    """The frozen public snapshot (job_training_certificates.details) plus
    the record's own immutable fields. Never a live join -- the snapshot
    is captured once, at issuance."""

    certificate_number: str
    student_name: str | None = None
    company_name: str | None = None
    job_title: str | None = None
    program_title: str | None = None
    issued_at: str | None = None
    revoked: bool = False


class JobTrainingCompletionSummary(BaseModel):
    """The completion state for one enrollment: has the industry verified,
    what was the outcome, when, and is a certificate available. Nothing
    here is a computed progress percentage -- Job Training has no
    submission/review system, so completion is purely the industry's
    explicit sign-off."""

    enrollment_id: str
    completion_status: JobTrainingCompletionStatus
    industry_verified: bool
    verified_at: str | None = None
    verification_notes: str | None = None
    completed_at: str | None = None
    certificate: JobTrainingCertificateInfo | None = None


class VerifyJobTrainingCompletionRequest(BaseModel):
    """POST .../completion/verify body. `industry_id` / `verified_by` /
    `enrollment_id` / `certificate_number` are never accepted -- all
    server-derived. `outcome` is the industry's decision; `notes` is
    optional free text kept on the completion record."""

    model_config = ConfigDict(extra="forbid")

    outcome: VerifyOutcome
    notes: str | None = Field(default=None, max_length=4000)


# ---- public verification (public.verify_job_training_certificate) ----


class PublicJobTrainingCertificateResponse(BaseModel):
    """Exactly the columns public.verify_job_training_certificate(text)
    returns -- no email, no UUIDs, no completion / verification detail."""

    certificate_number: str
    student_name: str | None = None
    company_name: str | None = None
    job_title: str | None = None
    program_title: str | None = None
    issued_at: str | None = None
    status: Literal["VALID", "REVOKED"]
