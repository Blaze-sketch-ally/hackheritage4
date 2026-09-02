"""Shared test helpers: mock a Supabase-authenticated request without any
live Supabase project or real token.
"""

from contextlib import ExitStack, contextmanager
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

    `role` is any value profiles.role can hold ("STUDENT", "INDUSTRY",
    "FACULTY", "INSTITUTION", "ADMIN") or None for a user who hasn't
    finished onboarding; the role guards (require_student / require_industry
    / ...) then accept or 403 the request accordingly.

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

    # Every route module that imports build_user_client for its own use
    # needs its own name binding patched (see the docstring above). The
    # list is built here and entered through an ExitStack rather than a
    # parenthesised `with` -- CPython caps statically nested blocks at 20,
    # and the flat `with (...)` form still counts each context as a block.
    route_modules = (
        "analytics",
        "applications",
        "assessments",
        "interviews",
        "attempts",
        "industry",
        "industry_collaborations",
        "industry_mentorship_opportunities",
        "industry_projects",
        "industry_trainings",
        "industry_workshops",
        "internships",
        "jobs",
        "skills",
        "skill_gap",
        "student_events",
        "student_learning",
        "student_mentorship",
        "student_notifications",
        "student_opportunities",
        "student_portfolio",
        "student_recommendations",
    )
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.core.dependencies.verify_access_token",
                return_value=mock_supabase_user(user_id),
            )
        )
        stack.enter_context(
            patch("app.core.dependencies.build_user_client", return_value=client)
        )
        for module in route_modules:
            stack.enter_context(
                patch(f"app.api.{module}.build_user_client", return_value=client)
            )
        # The S8 notification producer is the one service-role touch reachable
        # from an authorized (Industry) request. Stub it so no test ever
        # constructs a real service-role client or attempts a live write --
        # matching the per-test `patch("app.api.assessments.get_supabase", ...)`
        # convention. A test that wants to assert on the producer patches
        # `emit_application_status_change` itself.
        stack.enter_context(
            patch("app.services.notification_producer.get_supabase", return_value=MagicMock())
        )
        yield
