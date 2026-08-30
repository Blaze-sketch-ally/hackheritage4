from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    """Server-side Supabase client using the service role key.

    This client BYPASSES ROW LEVEL SECURITY entirely -- it is not scoped to
    any user and is not subject to RLS policies. Never expose this key to
    the frontend, and never use this client for ordinary user-scoped reads
    or writes (listing/creating/reading a student's own data). For those,
    use `build_user_client(access_token)` from `app.core.security` instead,
    which preserves RLS.

    Reserve this client for explicitly authorized, privileged server-side
    operations only -- e.g. Phase 1 assessment scoring/submission, where
    RLS itself structurally blocks every non-service-role caller from
    writing scores. Every such use must independently verify ownership in
    Python first (never rely on service_role's bypass as an authorization
    check).
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
