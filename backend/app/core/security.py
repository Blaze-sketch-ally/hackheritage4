"""Supabase access-token verification.

Verification is delegated to Supabase Auth itself (a live GET /auth/v1/user
call, via the SDK's `auth.get_user()`) rather than local JWT signature
checking. This project's Supabase keys are in the newer sb_publishable_ /
sb_secret_ format, which doesn't hand the backend a static shared secret to
verify a JWT signature against locally -- and a live check also catches
revocation/expiry that a local signature check alone would miss.

This module only establishes identity. It does not decide authorization
(role checks) -- see app.core.dependencies.
"""

from supabase import Client, create_client
from supabase_auth.errors import AuthApiError
from supabase_auth.types import User

from app.core.config import settings


class InvalidTokenError(Exception):
    """Raised when a Supabase access token is missing, malformed, expired,
    or otherwise rejected by Supabase Auth."""


def verify_access_token(access_token: str) -> User:
    """Verify a Supabase access token and return the Supabase Auth user it
    belongs to. Raises InvalidTokenError if verification fails."""
    if not access_token:
        raise InvalidTokenError("Missing access token.")

    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    try:
        response = client.auth.get_user(access_token)
    except AuthApiError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if response is None or response.user is None:
        raise InvalidTokenError("Invalid or expired access token.")

    return response.user


def build_user_client(access_token: str) -> Client:
    """A Supabase client scoped to one user's access token.

    Uses the anon key -- never service_role -- so every request made
    through this client is subject to RLS exactly as if it came from the
    user's own browser session.
    """
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client
