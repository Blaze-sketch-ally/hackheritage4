"""Tests for the AI foundation (Phase 1): AISettings, GroqClient, and the
structured-output layer.

No live Groq credentials or network access anywhere in this file --
GroqClient._create_completion (the one method that reaches the network)
is mocked in every test. `time.sleep` is also patched during retry tests
so they run instantly rather than actually waiting out the backoff.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from groq import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.client import GroqClient, build_strict_json_schema
from app.ai.config import AISettings
from app.ai.exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIResponseError,
    AIStructuredOutputError,
)

_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _mock_completion(content: str) -> MagicMock:
    """A MagicMock shaped like a groq ChatCompletion response, exposing
    only the `.choices[0].message.content` path the client reads."""
    response = MagicMock()
    response.choices[0].message.content = content
    return response


def _configured_client(**overrides) -> GroqClient:
    settings = AISettings(groq_api_key="fake-test-key", **overrides)
    return GroqClient(settings)


def _unconfigured_client() -> GroqClient:
    settings = AISettings(groq_api_key="")
    return GroqClient(settings)


class _EchoResult(BaseModel):
    message: str
    score: int


class _EchoItem(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    note: str | None = None


class _EchoWithNested(BaseModel):
    """A response model with a nested $ref'd model and an optional
    field -- used to test build_strict_json_schema's handling of
    $defs and Optional fields, neither of which _EchoResult exercises."""

    model_config = ConfigDict(extra="forbid")

    title: str
    items: list[_EchoItem] = Field(default_factory=list, max_length=5)


# ============================================================
# Configuration
# ============================================================


def test_is_configured_false_when_key_empty():
    assert _unconfigured_client().is_configured is False


def test_is_configured_true_when_key_present():
    assert _configured_client().is_configured is True


def test_missing_api_key_raises_configuration_error():
    client = _unconfigured_client()
    with pytest.raises(AIConfigurationError):
        client.chat_completion(system="sys", user="hi")


def test_missing_api_key_never_calls_the_network():
    client = _unconfigured_client()
    with (
        patch.object(client, "_create_completion") as mock_create,
        pytest.raises(AIConfigurationError),
    ):
        client.chat_completion(system="sys", user="hi")
    mock_create.assert_not_called()


# ============================================================
# Successful completion
# ============================================================


def test_successful_chat_completion_returns_content():
    client = _configured_client()
    with patch.object(client, "_create_completion", return_value=_mock_completion("hello")):
        result = client.chat_completion(system="sys", user="hi")
    assert result == "hello"


def test_chat_completion_passes_model_and_messages():
    client = _configured_client(groq_model="llama-3.3-70b-versatile")
    with patch.object(
        client, "_create_completion", return_value=_mock_completion("ok")
    ) as mock_create:
        client.chat_completion(system="be nice", user="hello")

    _, kwargs = mock_create.call_args
    assert kwargs["model"] == "llama-3.3-70b-versatile"
    assert kwargs["messages"] == [
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "hello"},
    ]


def test_json_mode_sets_response_format():
    client = _configured_client()
    with patch.object(
        client, "_create_completion", return_value=_mock_completion("{}")
    ) as mock_create:
        client.chat_completion(system="sys", user="hi", json_mode=True)

    _, kwargs = mock_create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}


def test_empty_content_raises_response_error():
    client = _configured_client()
    with (
        patch.object(client, "_create_completion", return_value=_mock_completion("   ")),
        pytest.raises(AIResponseError),
    ):
        client.chat_completion(system="sys", user="hi")


# ============================================================
# Provider failures: retryable vs non-retryable
# ============================================================


def test_non_retryable_failure_raises_immediately_without_retry():
    client = _configured_client(groq_max_retries=2)
    error = BadRequestError(
        "bad request", response=httpx.Response(400, request=_REQUEST), body=None
    )
    with (
        patch.object(client, "_create_completion", side_effect=error) as mock_create,
        pytest.raises(AIProviderError),
    ):
        client.chat_completion(system="sys", user="hi")
    mock_create.assert_called_once()


def test_transient_failure_retries_then_succeeds():
    client = _configured_client(groq_max_retries=2)
    error = APIConnectionError(message="conn error", request=_REQUEST)
    with (
        patch.object(
            client, "_create_completion", side_effect=[error, _mock_completion("recovered")]
        ) as mock_create,
        patch("app.ai.client.time.sleep") as mock_sleep,
    ):
        result = client.chat_completion(system="sys", user="hi")

    assert result == "recovered"
    assert mock_create.call_count == 2
    mock_sleep.assert_called_once()


def test_transient_failure_exhausts_retries_then_raises():
    client = _configured_client(groq_max_retries=2)
    error = RateLimitError(
        "rate limited", response=httpx.Response(429, request=_REQUEST), body=None
    )
    with (
        patch.object(client, "_create_completion", side_effect=error) as mock_create,
        patch("app.ai.client.time.sleep"),
        pytest.raises(AIProviderError),
    ):
        client.chat_completion(system="sys", user="hi")

    # 1 initial attempt + 2 retries = 3 total calls, never more.
    assert mock_create.call_count == 3


def test_zero_retries_means_a_single_attempt():
    client = _configured_client(groq_max_retries=0)
    error = InternalServerError(
        "server error", response=httpx.Response(500, request=_REQUEST), body=None
    )
    with (
        patch.object(client, "_create_completion", side_effect=error) as mock_create,
        pytest.raises(AIProviderError),
    ):
        client.chat_completion(system="sys", user="hi")
    mock_create.assert_called_once()


def test_unexpected_exception_is_wrapped_not_leaked():
    client = _configured_client()
    with (
        patch.object(client, "_create_completion", side_effect=RuntimeError("boom, secret=xyz")),
        pytest.raises(AIProviderError) as exc_info,
    ):
        client.chat_completion(system="sys", user="hi")
    assert "boom" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


# ============================================================
# Structured output: JSON parsing + Pydantic validation
# ============================================================


def test_structured_completion_success():
    client = _configured_client()
    with patch.object(
        client,
        "_create_completion",
        return_value=_mock_completion('{"message": "hi", "score": 5}'),
    ):
        result = client.complete_structured(system="sys", user="hi", response_model=_EchoResult)
    assert isinstance(result, _EchoResult)
    assert result.message == "hi"
    assert result.score == 5


def test_structured_completion_malformed_json_raises():
    client = _configured_client()
    with (
        patch.object(client, "_create_completion", return_value=_mock_completion("not json{{")),
        pytest.raises(AIStructuredOutputError),
    ):
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)


def test_structured_completion_schema_mismatch_raises():
    client = _configured_client()
    # Valid JSON, but missing the required `score` field.
    with (
        patch.object(
            client, "_create_completion", return_value=_mock_completion('{"message": "hi"}')
        ),
        pytest.raises(AIStructuredOutputError),
    ):
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)


def test_structured_completion_wrong_type_raises():
    client = _configured_client()
    with (
        patch.object(
            client,
            "_create_completion",
            return_value=_mock_completion('{"message": "hi", "score": "not-a-number"}'),
        ),
        pytest.raises(AIStructuredOutputError),
    ):
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)


def test_structured_completion_provider_failure_propagates():
    client = _configured_client(groq_max_retries=0)
    error = BadRequestError(
        "bad request", response=httpx.Response(400, request=_REQUEST), body=None
    )
    with (
        patch.object(client, "_create_completion", side_effect=error),
        pytest.raises(AIProviderError),
    ):
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)


def test_pydantic_validation_error_is_real_for_sanity():
    """Sanity check that _EchoResult actually enforces its fields, so the
    schema-mismatch tests above are testing something real."""
    with pytest.raises(ValidationError):
        _EchoResult.model_validate({"message": "hi"})


# ============================================================
# Phase 3.1: schema-constrained structured output
# ============================================================


def test_build_strict_json_schema_forces_additional_properties_false_and_full_required():
    schema = build_strict_json_schema(_EchoResult)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"message", "score"}


def test_build_strict_json_schema_strips_unsupported_keywords_from_root():
    """_EchoItem's own maxLength/minLength constraints are Pydantic-level
    validation, not part of what Groq's strict mode accepts -- they must
    not appear in the schema sent to the provider."""
    schema = build_strict_json_schema(_EchoWithNested)
    assert "maxLength" not in schema["properties"]["items"]
    assert "maxItems" not in schema["properties"]["items"]


def test_build_strict_json_schema_tightens_nested_defs_too():
    """The bug this guards against: $defs are siblings of `properties`,
    referenced via $ref rather than inlined -- a naive single-pass
    transform that only walks `properties` never reaches them."""
    schema = build_strict_json_schema(_EchoWithNested)
    nested = schema["$defs"]["_EchoItem"]
    assert nested["additionalProperties"] is False
    assert set(nested["required"]) == {"label", "note"}
    assert "maxLength" not in nested["properties"]["label"]
    assert "minLength" not in nested["properties"]["label"]


def test_build_strict_json_schema_optional_field_becomes_required_but_nullable():
    """`note: str | None = None` is optional in Python/Pydantic terms,
    but strict mode has no concept of an absent key -- it must appear in
    `required`, with its nullability preserved via the anyOf/null shape
    Pydantic already produces."""
    schema = build_strict_json_schema(_EchoWithNested)
    nested = schema["$defs"]["_EchoItem"]
    assert "note" in nested["required"]
    note_schema = nested["properties"]["note"]
    assert "default" not in note_schema
    types_present = {branch.get("type") for branch in note_schema.get("anyOf", [])}
    assert "null" in types_present


def test_complete_structured_sends_strict_json_schema_response_format():
    client = _configured_client()
    with patch.object(
        client, "_create_completion", return_value=_mock_completion('{"message": "hi", "score": 5}')
    ) as mock_create:
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)

    _, kwargs = mock_create.call_args
    response_format = kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "_EchoResult"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False


def test_chat_completion_falls_back_to_json_object_mode_when_schema_mode_rejected():
    """The configured model (or Groq generally) rejecting the
    schema-constrained request outright (400) must not be a hard
    failure -- one automatic retry with plain json_object mode, then
    succeed."""
    client = _configured_client(groq_max_retries=0)
    schema_rejected = BadRequestError(
        "response_format.json_schema not supported for this model",
        response=httpx.Response(400, request=_REQUEST),
        body=None,
    )
    with patch.object(
        client,
        "_create_completion",
        side_effect=[schema_rejected, _mock_completion('{"message": "hi", "score": 5}')],
    ) as mock_create:
        result = client.complete_structured(system="sys", user="hi", response_model=_EchoResult)

    assert result.message == "hi"
    assert mock_create.call_count == 2
    first_call_format = mock_create.call_args_list[0].kwargs["response_format"]
    second_call_format = mock_create.call_args_list[1].kwargs["response_format"]
    assert first_call_format["type"] == "json_schema"
    assert second_call_format == {"type": "json_object"}


def test_chat_completion_fallback_still_raises_if_json_object_mode_also_fails():
    client = _configured_client(groq_max_retries=0)
    error = BadRequestError(
        "json_schema unsupported", response=httpx.Response(400, request=_REQUEST), body=None
    )
    with (
        patch.object(client, "_create_completion", side_effect=error) as mock_create,
        pytest.raises(AIProviderError),
    ):
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)

    # One attempt in schema mode + one fallback attempt in json_object
    # mode -- bounded, never more.
    assert mock_create.call_count == 2


def test_chat_completion_retry_behavior_unchanged_for_schema_mode():
    """Transient failures still retry up to groq_max_retries times in
    schema mode before any fallback is even considered."""
    client = _configured_client(groq_max_retries=2)
    error = InternalServerError(
        "server error", response=httpx.Response(500, request=_REQUEST), body=None
    )
    with (
        patch.object(client, "_create_completion", side_effect=error) as mock_create,
        patch("app.ai.client.time.sleep"),
        pytest.raises(AIProviderError),
    ):
        client.complete_structured(system="sys", user="hi", response_model=_EchoResult)

    # Exhausted transient failures must never restart in JSON-object mode.
    assert mock_create.call_count == 3


def test_json_mode_flag_still_works_independently_of_response_schema():
    """chat_completion's pre-existing json_mode=True path (used directly
    by any caller not going through complete_structured) is untouched."""
    client = _configured_client()
    with patch.object(
        client, "_create_completion", return_value=_mock_completion("{}")
    ) as mock_create:
        client.chat_completion(system="sys", user="hi", json_mode=True)

    _, kwargs = mock_create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("kind", ["timeout", "rate_limit", "server", "connection"])
def test_exhausted_transient_schema_request_never_falls_back(kind):
    from groq import APITimeoutError
    errors = {
        "timeout": APITimeoutError(request=_REQUEST),
        "rate_limit": RateLimitError("limited", response=httpx.Response(429, request=_REQUEST), body=None),
        "server": InternalServerError("failed", response=httpx.Response(500, request=_REQUEST), body=None),
        "connection": APIConnectionError(request=_REQUEST),
    }
    client = _configured_client(groq_max_retries=2)
    with (patch.object(client, "_create_completion", side_effect=errors[kind]) as create,
          patch("app.ai.client.time.sleep"), pytest.raises(AIProviderError)):
        client.complete_structured(system="s", user="u", response_model=_EchoResult)
    assert create.call_count == 3
    assert all(c.kwargs["response_format"]["type"] == "json_schema" for c in create.call_args_list)


@pytest.mark.parametrize("status_code,message", [(400, "invalid max_tokens"),
                                                 (401, "response_format unauthorized"),
                                                 (404, "json_schema model not found")])
def test_unrelated_or_auth_failure_does_not_fallback(status_code, message):
    from groq import APIStatusError
    error = APIStatusError(message, response=httpx.Response(status_code, request=_REQUEST), body=None)
    client = _configured_client()
    with (patch.object(client, "_create_completion", side_effect=error) as create,
          pytest.raises(AIProviderError)):
        client.complete_structured(system="s", user="u", response_model=_EchoResult)
    create.assert_called_once()
