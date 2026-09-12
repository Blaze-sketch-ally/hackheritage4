"""Reusable Groq chat-completion client (Phase 1 AI foundation; schema-
constrained structured output added in Phase 3.1).

This is the ONLY module in the codebase allowed to import `groq` or
construct a Groq SDK client. Every future agent must call
`groq_client.chat_completion(...)` / `groq_client.complete_structured(...)`
-- never the raw SDK -- so retry/timeout/error handling and the
"never leak the API key" guarantee live in exactly one place.

Sync, not async: matches the rest of this backend (supabase-py is sync,
every route in app/api/ is a plain `def`, not `async def`) -- a sync
Groq client keeps this the only consistent choice rather than introducing
the one async-only code path in the app.

Retries are bounded and handled explicitly by this class, not the SDK's
own built-in retry mechanism (which is disabled below via max_retries=0
on the SDK client) -- so behavior is one explicit, testable policy
instead of two overlapping ones. Only transient provider-side failures
(connection error, timeout, rate limit, 5xx) are retried, up to
AISettings.groq_max_retries additional attempts with a short capped
backoff between them. A 4xx (bad request, auth, not found,
unprocessable) is a configuration/application error a retry cannot fix,
and is raised immediately -- except the one schema-mode fallback
described on `complete_structured` below.

Phase 3.1 background: `complete_structured` originally used bare
`{"type": "json_object"}` mode, which gives the model no schema at all
beyond what the prompt describes in prose -- live testing during Phase 3
showed this was not reliable (the model invented its own field names).
`complete_structured` now derives a JSON Schema straight from the
supplied `response_model` and asks Groq for schema-CONSTRAINED output
(`{"type": "json_schema", ...}`, OpenAI-compatible structured outputs,
strict mode) -- this is model/agent-agnostic: nothing SkillGap-specific
lives here, any future agent's Pydantic response model benefits
automatically.
"""

import json
import logging
import time

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Groq,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.ai.config import AISettings, ai_settings
from app.ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIResponseError,
    AIStructuredOutputError,
)

logger = logging.getLogger("app.ai")

# Transient, worth retrying. Every one of these is either a network-level
# failure or a provider-side (not caller-side) status code.
_RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)

# Capped exponential backoff between retries, in seconds. Small and
# bounded -- this is a request-time call, not a background job.
_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 4.0

# JSON Schema keywords Groq/OpenAI-style strict structured output does
# NOT support (only a restricted subset of JSON Schema is accepted when
# strict=true -- type/properties/required/additionalProperties/items/
# enum/anyOf/$ref/$defs/description/title). Pydantic's own
# model_json_schema() includes these for documentation/introspection
# purposes; they are stripped from the copy sent to Groq, never from the
# model itself -- response_model.model_validate() (in complete_structured)
# still enforces every one of them after the fact, so nothing here is
# silently unvalidated.
_STRICT_MODE_UNSUPPORTED_KEYWORDS = (
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "format",
    "default",
)


def _tighten_node_for_strict_mode(node: object) -> None:
    """Recursively rewrite one JSON Schema node in place: strip
    unsupported keywords, and -- for every object node -- force
    additionalProperties=false and require every declared property
    (strict mode has no notion of an optional key; a field that is
    conceptually optional keeps its `anyOf: [..., {"type": "null"}]`
    shape from Pydantic and is simply always present, possibly null)."""
    if isinstance(node, list):
        for item in node:
            _tighten_node_for_strict_mode(item)
        return
    if not isinstance(node, dict):
        return

    for keyword in _STRICT_MODE_UNSUPPORTED_KEYWORDS:
        node.pop(keyword, None)

    properties = node.get("properties")
    if isinstance(properties, dict):
        node["additionalProperties"] = False
        node["required"] = list(properties.keys())
        for prop_schema in properties.values():
            _tighten_node_for_strict_mode(prop_schema)

    for keyword in ("anyOf", "oneOf", "allOf"):
        if keyword in node:
            _tighten_node_for_strict_mode(node[keyword])

    if "items" in node:
        _tighten_node_for_strict_mode(node["items"])


def build_strict_json_schema(response_model: type[BaseModel]) -> dict[str, object]:
    """Derive a Groq/OpenAI strict-structured-output-compatible JSON
    Schema from a Pydantic model. Generic over any BaseModel -- no
    agent-specific logic. Used by complete_structured(); exposed at
    module level so it can be unit-tested directly."""
    schema = response_model.model_json_schema()
    _tighten_node_for_strict_mode(schema)
    # $defs (nested model definitions, referenced via "$ref" rather than
    # inlined) are siblings of "properties" at the schema root -- the
    # properties-driven recursion above never reaches them, so each one
    # is tightened explicitly here.
    for definition in schema.get("$defs", {}).values():
        _tighten_node_for_strict_mode(definition)
    return schema


def _json_schema_response_format(response_model: type[BaseModel]) -> dict[str, object]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": response_model.__name__,
            "schema": build_strict_json_schema(response_model),
            "strict": True,
        },
    }


def _extract_content(response: object) -> str | None:
    try:
        return response.choices[0].message.content  # type: ignore[union-attr]
    except (AttributeError, IndexError, TypeError):
        return None


class GroqClient:
    """Thin wrapper around the Groq SDK. Holds only its settings and a
    lazily-constructed SDK client -- safe to use as a module-level
    singleton (see `groq_client` below), and safe to construct fresh in
    tests with a custom AISettings."""

    def __init__(self, settings: AISettings | None = None) -> None:
        self._settings = settings or ai_settings
        self._sdk_client: Groq | None = None

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured

    def _get_sdk_client(self) -> Groq:
        if not self._settings.is_configured:
            raise AIConfigurationError(
                "The AI subsystem is not configured: GROQ_API_KEY is not set."
            )
        if self._sdk_client is None:
            self._sdk_client = Groq(
                api_key=self._settings.groq_api_key,
                timeout=self._settings.groq_timeout_seconds,
                # This class owns retrying (see the module docstring) --
                # the SDK's own retries are switched off so the two
                # policies never stack.
                max_retries=0,
            )
        return self._sdk_client

    def _create_completion(self, **kwargs: object) -> object:
        """The one call site that reaches the network. Isolated into its
        own method purely so tests can mock exactly this and nothing
        else (constructing the client itself, request shaping, retrying,
        and content extraction all stay real in a mocked test)."""
        return self._get_sdk_client().chat.completions.create(**kwargs)

    def _execute_with_retries(self, request_kwargs: dict[str, object]) -> object:
        """The bounded retry loop, extracted so it can run twice in one
        chat_completion() call -- once for schema-constrained mode, and
        (only for a schema-related 400/422) once more for the plain
        JSON-mode fallback. See chat_completion's own docstring."""
        attempts = self._settings.groq_max_retries + 1
        response = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._create_completion(**request_kwargs)
                break
            except _RETRYABLE_EXCEPTIONS as exc:
                if attempt < attempts:
                    logger.warning(
                        "Groq request failed (attempt %d/%d), retrying: %s",
                        attempt,
                        attempts,
                        exc.__class__.__name__,
                    )
                    delay = min(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)), _BACKOFF_CAP_SECONDS)
                    time.sleep(delay)
                    continue
                logger.error(
                    "Groq request failed after %d attempt(s): %s", attempts, exc.__class__.__name__
                )
                raise AIProviderError(
                    "The AI provider is temporarily unavailable. Please try again."
                ) from exc
            except AIConfigurationError:
                raise
            except APIStatusError as exc:
                # A non-retryable 4xx (bad request, auth, not found,
                # unprocessable, conflict) -- an application/configuration
                # error, not a transient one. Fail immediately.
                logger.error("Groq rejected the request: %s", exc.__class__.__name__)
                raise AIProviderError("The AI provider rejected this request.") from exc
            except Exception as exc:
                # Last resort: never let an unknown SDK error leak raw.
                logger.error("Unexpected error calling Groq: %s", exc.__class__.__name__)
                raise AIProviderError("The AI provider request failed unexpectedly.") from exc

        return response

    def chat_completion(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        response_schema: type[BaseModel] | None = None,
    ) -> str:
        """One system+user chat completion, returned as its raw text
        content.

        `response_schema`, when given, requests Groq's schema-constrained
        structured output mode for that Pydantic model (see
        build_strict_json_schema) -- takes precedence over `json_mode`.
        If Groq rejects the schema format (schema-related 400/422 -- e.g. the
        configured model doesn't support structured outputs), this
        method automatically retries ONCE more with plain
        `{"type": "json_object"}` mode before giving up, logging a
        warning. This is a bounded (at most one fallback retry cycle), model-
        agnostic degrade-not-fail path -- it never silently swaps which
        model is called, only how strictly the response shape is
        requested from it. `complete_structured` still validates the
        result with Pydantic regardless of which mode ultimately served
        the request, so correctness never depends on this fallback
        firing or not.

        Raises AIConfigurationError (no API key), AIProviderError (Groq
        failed, immediately for a 4xx or after retries for a transient
        failure), or AIResponseError (Groq succeeded but returned empty
        content). Never lets a raw Groq exception, or the API key,
        escape this method.
        """
        if not self._settings.is_configured:
            # Checked here too (not only inside _get_sdk_client), so an
            # unconfigured caller fails before a request is ever built
            # and never reaches _create_completion at all.
            raise AIConfigurationError(
                "The AI subsystem is not configured: GROQ_API_KEY is not set."
            )

        base_kwargs: dict[str, object] = {
            "model": self._settings.groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": (
                temperature if temperature is not None else self._settings.groq_temperature
            ),
            "max_tokens": max_tokens if max_tokens is not None else self._settings.groq_max_tokens,
        }

        if response_schema is not None:
            request_kwargs = {**base_kwargs, "response_format": _json_schema_response_format(response_schema)}
        elif json_mode:
            request_kwargs = {**base_kwargs, "response_format": {"type": "json_object"}}
        else:
            request_kwargs = base_kwargs

        try:
            response = self._execute_with_retries(request_kwargs)
        except AIProviderError as exc:
            cause = exc.__cause__
            # Only a schema-related 400/422 can benefit from changing format.
            # Never restart retries for exhausted transient failures or auth errors.
            schema_rejection = (
                isinstance(cause, APIStatusError)
                and cause.status_code in (400, 422)
                and any(marker in str(cause).lower() for marker in (
                    "json_schema", "response_format", "structured output", "schema"
                ))
            )
            if response_schema is None or not schema_rejection:
                raise
            logger.warning(
                "Groq rejected schema-constrained structured output for model=%s "
                "response_model=%s; retrying once with plain JSON mode.",
                self._settings.groq_model,
                response_schema.__name__,
            )
            fallback_kwargs = {**base_kwargs, "response_format": {"type": "json_object"}}
            response = self._execute_with_retries(fallback_kwargs)

        content = _extract_content(response)
        if not content or not content.strip():
            raise AIResponseError("The AI provider returned an empty response.")
        return content

    def complete_structured(
        self,
        *,
        system: str,
        user: str,
        response_model: type[BaseModel],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> BaseModel:
        """Chat-completion (schema-constrained structured output, with an
        automatic plain-JSON-mode fallback -- see chat_completion) ->
        parsed JSON -> validated `response_model` instance.

        Raises AIStructuredOutputError if the response is not valid JSON
        or does not match the schema -- this never returns a partially
        valid or guessed result. All the `chat_completion` exceptions
        above can also propagate from here unchanged.
        """
        raw = self.chat_completion(
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
            response_schema=response_model,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIStructuredOutputError("The AI provider's response was not valid JSON.") from exc

        try:
            return response_model.model_validate(data)
        except ValidationError as exc:
            raise AIStructuredOutputError(
                "The AI provider's response did not match the expected format."
            ) from exc


# Module-level singleton, matching app.core.config's `settings = Settings()`
# pattern -- future agents import this directly rather than constructing
# their own GroqClient.
groq_client = GroqClient()
