"""Auth/token verification helpers.

Verifies a Supabase access token (the same JWT the Next.js frontend
already holds in the student's browser session) against Supabase's own
Auth server and returns the authenticated user's id. This is the ONLY
way any endpoint in this backend learns "who is calling" — no endpoint
ever accepts a student/user id as a request parameter or body field.
"""

from fastapi import HTTPException, status
from supabase import Client


def get_authenticated_user_id(supabase: Client, access_token: str | None) -> str:
    """Verifies `access_token` and returns the authenticated user's id.

    Raises HTTPException(401) if the token is missing, invalid, or expired.
    Uses `auth.get_user()`, which validates the token directly against
    Supabase's Auth server rather than decoding it locally — this avoids
    needing a separate JWT-signing-secret configured in this backend.
    """
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token.")

    try:
        response = supabase.auth.get_user(access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token."
        )

    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authentication token."
        )

    return response.user.id
