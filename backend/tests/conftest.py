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
    Supabase call, no real token."""
    with (
        patch(
            "app.core.dependencies.verify_access_token",
            return_value=mock_supabase_user(user_id),
        ),
        patch(
            "app.core.dependencies.build_user_client",
            return_value=mock_client_with_role(role),
        ),
    ):
        yield
