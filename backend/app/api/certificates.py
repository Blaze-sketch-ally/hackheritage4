"""PUBLIC certificate verification (Phase 7 internship, Phase J4 job training).

No authentication. Calls ONLY the SECURITY DEFINER verifier functions
public.verify_internship_certificate
(database/migrations/051_workspace_submissions_completion.sql) and
public.verify_job_training_certificate
(database/migrations/053_job_training_completion.sql) -- each with a
pinned empty search_path and granted to `anon` -- never a direct SELECT
against a certificate / completion / profile / internship_workspace /
application table. Each function is the safety boundary: it returns
exactly its declared public columns and nothing else -- no email, no
UUIDs, no submission / stipend / completion detail.

Uses app.core.security.build_anon_client() -- the anon-key client with no
user session, matching the `anon` grant on the functions. Never
service_role: these routes need no bypass of RLS, only the one function
call every anonymous caller is already permitted to make.
"""

import re

from fastapi import APIRouter, HTTPException, status

from app.core.security import build_anon_client
from app.schemas.internship_completion import PublicCertificateResponse
from app.schemas.job_training_completion import PublicJobTrainingCertificateResponse

router = APIRouter(prefix="/certificates", tags=["certificates"])

# AIC-INT-{YYYY}-{13 base32 chars} (public.generate_internship_certificate_number, 051).
_NUMBER_PATTERN = r"^AIC-INT-\d{4}-[A-Z2-7]{13}$"
# AIC-JOB-{YYYY}-{13 base32 chars} (public.generate_job_training_certificate_number, 053).
_JOB_NUMBER_PATTERN = r"^AIC-JOB-\d{4}-[A-Z2-7]{13}$"


@router.get("/verify/{certificate_number}", response_model=PublicCertificateResponse)
def verify_certificate(certificate_number: str) -> PublicCertificateResponse:
    """Look up a certificate by its public number. No auth required.
    422 for a number that isn't even the right shape (AIC-INT-YYYY-...);
    404 for a well-formed number that doesn't resolve to a certificate."""
    if not re.match(_NUMBER_PATTERN, certificate_number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That doesn't look like a valid certificate number.",
        )

    client = build_anon_client()
    try:
        response = client.rpc(
            "verify_internship_certificate", {"p_number": certificate_number}
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify this certificate. Please try again.",
        ) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found."
        )
    return PublicCertificateResponse(**rows[0])


@router.get(
    "/verify-job-training/{certificate_number}",
    response_model=PublicJobTrainingCertificateResponse,
)
def verify_job_training_certificate(
    certificate_number: str,
) -> PublicJobTrainingCertificateResponse:
    """Look up a JOB TRAINING certificate by its public number. No auth
    required. 422 for a number that isn't the right shape
    (AIC-JOB-YYYY-...); 404 for a well-formed number that doesn't resolve.
    Calls ONLY public.verify_job_training_certificate -- a separate route
    from the internship verifier because the response shape differs
    (job_title + program_title, not a single title)."""
    if not re.match(_JOB_NUMBER_PATTERN, certificate_number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That doesn't look like a valid certificate number.",
        )

    client = build_anon_client()
    try:
        response = client.rpc(
            "verify_job_training_certificate", {"p_number": certificate_number}
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify this certificate. Please try again.",
        ) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found."
        )
    return PublicJobTrainingCertificateResponse(**rows[0])
