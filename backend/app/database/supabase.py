from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    """Server-side Supabase client using the service role key.

    Never expose this key to the frontend — only used from the backend.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
