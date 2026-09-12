"""Exceptions for the AI subsystem.

Every message on these is already written to be safe to show a caller
(no provider stack trace, no request/response body, no API key) -- but
callers at the API boundary (app.api.ai, and future agent routers)
should still prefer a generic HTTPException detail over `str(exc)`,
matching every other router in this project (see app.main's own
unhandled-exception handler for the same convention).
"""


class AIError(Exception):
    """Base class for every AI-subsystem error."""


class AIConfigurationError(AIError):
    """The AI subsystem is not configured (e.g. GROQ_API_KEY is unset)."""


class AIProviderError(AIError):
    """Groq itself failed: a connection/timeout/rate-limit/5xx error that
    persisted after every retry, or a 4xx request Groq rejected outright
    (never retried -- see app.ai.client)."""


class AIResponseError(AIError):
    """Groq responded successfully but the content was empty or unusable."""


class AIStructuredOutputError(AIError):
    """The response could not be parsed as JSON, or did not match the
    expected Pydantic schema."""
