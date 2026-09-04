"""PUBLIC certificate verification (Phase 7).

No authentication. Calls ONLY public.verify_internship_certificate(text)
(database/migrations/039_workspace_submissions_completion.sql) -- a
SECURITY DEFINER function with a pinned empty search_path, granted to
`anon` -- never a direct SELECT against internship_certificates,
internship_completions, profiles, internship_workspaces or applications.
The function itself is the safety boundary: it returns exactly
(certificate_number, student_name, company_name, title, issued_at,
status) and nothing else -- no email, no UUIDs, no submission or stipend
data.

Uses app.core.security.build_anon_client() -- the anon-key client with no
user session, matching the `anon` grant on the function. Never
service_role: this route needs no bypass of RLS, only the one function
call every anonymous caller is already permitted to make.
"""

import re

from fastapi import APIRouter, HTTPException, status

from app.core.security import build_anon_client
from app.schemas.internship_completion import PublicCertificateResponse

router = APIRouter(prefix="/certificates", tags=["certificates"])

# AIC-INT-{YYYY}-{13 base32 chars} (public.generate_internship_certificate_number, 039).
_NUMBER_PATTERN = r"^AIC-INT-\d{4}-[A-Z2-7]{13}$"


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
