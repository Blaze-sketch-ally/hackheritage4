"""Shared test helpers: mock a Supabase-authenticated request without any
live Supabase project or real token.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch


def mock_supabase_user(user_id: str = "student-1", email: str = "student@example.com"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


def mock_client_with_role(role: str | None):
    """A fake Supabase client whose profiles.role lookup returns `role`."""
    mock_table = MagicMock()
    mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        {"role": role} if role is not None else None
    )
    mock_client = MagicMock()
    mock_client.table.return_value = mock_table
    return mock_client


@contextmanager
def authenticated_as(role: str | None, user_id: str = "student-1"):
    """Patch the auth dependency chain so a request behaves as if a real
    user with the given app role successfully authenticated -- no live
    Supabase project, real token, or backend/.env required.

    build_user_client has two separate name bindings that both need
    patching: app.core.dependencies imports it for the profile-role lookup
    inside get_current_user(), and each route module (e.g.
    app.api.assessments) imports it separately to build the client handed
    to the service layer. Patching only the former lets get_current_user()
    succeed while a route's own unmocked call still tries to construct a
    real Supabase client via settings.supabase_url/supabase_anon_key --
    which only works where backend/.env happens to have real values (e.g.
    a local dev machine), and raises SupabaseException("supabase_url is
    required") anywhere it doesn't (CI). Add further `app.api.<module>`
    patches here as new route modules import build_user_client.
    """
    client = mock_client_with_role(role)
    with (
        patch(
            "app.core.dependencies.verify_access_token",
            return_value=mock_supabase_user(user_id),
        ),
        patch("app.core.dependencies.build_user_client", return_value=client),
        patch("app.api.assessments.build_user_client", return_value=client),
    ):
        yield
