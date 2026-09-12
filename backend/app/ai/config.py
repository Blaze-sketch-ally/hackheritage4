"""Centralized configuration for the AI subsystem (Groq).

Mirrors the shape of app.core.config.Settings (pydantic-settings
BaseSettings + a module-level singleton), but stays its own settings
object, scoped to the AI subsystem only -- so later agent phases never
need to touch app.core.config or grow the app-wide Settings with
AI-specific knobs.

Every value has a safe default except the API key, which defaults to ""
(unconfigured) -- see `is_configured`. Nothing here is ever logged or
returned in an API response; see app.api.ai.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""

    # Must be a model Groq is CURRENTLY serving -- this roster changes
    # over time (models get deprecated/replaced), so verify against
    # https://console.groq.com/docs/models or `client.models.list()`
    # before changing this. Verified live 2026-09-12: openai/gpt-oss-20b
    # is currently available and supports JSON mode (see app.ai.client's
    # `json_mode`); llama-3.3-70b-versatile (the original Phase 1 choice)
    # returned a 404 model_not_found and was replaced for that reason.
    groq_model: str = "openai/gpt-oss-20b"

    # Per-request timeout, seconds. Passed straight to the Groq SDK client.
    groq_timeout_seconds: float = 30.0

    # Number of ADDITIONAL attempts after the first, for transient
    # failures only (see app.ai.client._RETRYABLE_EXCEPTIONS). 0 disables
    # retrying entirely. Kept small and finite -- never unbounded.
    groq_max_retries: int = 2

    groq_temperature: float = 0.2
    groq_max_tokens: int = 1024

    @property
    def is_configured(self) -> bool:
        """Whether a usable API key is present. Never True for an empty
        or whitespace-only value."""
        return bool(self.groq_api_key.strip())


ai_settings = AISettings()


class YouTubeSettings(BaseSettings):
    """Optional external video-learning provider (Phase 4.7). Kept as its
    own settings object for the same reason as AISettings above -- the
    Course Recommendation Agent (and the separate YouTube Learning
    Agent) must work with zero configuration here -- see
    app.ai.tools.youtube_learning.get_youtube_provider.

    The YouTube Data API v3 uses simple API-key authentication (no
    OAuth) -- see https://developers.google.com/youtube/v3/getting-started.
    Nothing here is ever logged or returned in an API response -- see
    app.ai.tools.youtube_learning.

    (Phase 4.6's Microsoft Learn integration was removed: it was never
    configured and is no longer part of the active external
    recommendation path. Only InternalLearningResourceProvider and the
    generic, still-unconfigured CourseDiscoveryProvider external seam
    remain in app.ai.tools.course_discovery.)
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    youtube_api_key: str = ""

    # Per-request timeout, seconds, for both search.list and videos.list.
    youtube_timeout_seconds: float = 8.0

    # Raw search.list maxResults per skill query -- bounded, never the
    # full result set (see app.ai.tools.youtube_learning's own quota
    # notes). The number of GOOD candidates kept per skill after
    # enrichment/filtering is a separate, smaller constant in that
    # module -- this only bounds the initial search.
    youtube_max_results_per_skill: int = 5

    # In-process search-result cache TTL, seconds. Shared across every
    # student searching the same skill/level -- see
    # app.ai.tools.youtube_learning's cache docstring for why this is
    # safe (only public YouTube search results are cached, never
    # student identity/profile/skill-gap data).
    youtube_cache_ttl_seconds: int = 21600

    @property
    def is_configured(self) -> bool:
        """Whether a usable API key is present. Never True for an empty
        or whitespace-only value."""
        return bool(self.youtube_api_key.strip())


youtube_settings = YouTubeSettings()
