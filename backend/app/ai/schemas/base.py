"""Generic Phase-1 response schemas for the AI subsystem.

Deliberately generic and provider/agent-agnostic -- nothing here is
shaped for a specific future agent (no SkillGapAgentResponse,
CourseAgentResponse, etc.). Those belong to the phase that implements
that agent, built on top of AIResponseEnvelope below, not inside this
module.
"""

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel

ResultT = TypeVar("ResultT", bound=BaseModel)


class AIProvider(str, Enum):
    GROQ = "groq"


class AIErrorDetail(BaseModel):
    """A client-safe description of an AI-subsystem failure. `code` is
    one of the class names in app.ai.exceptions (e.g. "AIProviderError")
    -- never a raw provider message, stack trace, or the API key."""

    code: str
    message: str


class AIResponseMeta(BaseModel):
    """Provider/model metadata attached to a successful AI response."""

    provider: AIProvider = AIProvider.GROQ
    model: str


class AIResponseEnvelope(BaseModel, Generic[ResultT]):
    """A uniform wrapper future agents can return.

    Exactly one of `result` / `error` is meaningful at a time: on
    success, `success=True`, `meta` and `result` are populated and
    `error` is None; on failure, `success=False`, `error` is populated
    and `meta`/`result` are None. Callers should branch on `success`,
    not on which of `result`/`error` happens to be set.
    """

    success: bool
    meta: AIResponseMeta | None = None
    result: ResultT | None = None
    error: AIErrorDetail | None = None


class AIHealthResponse(BaseModel):
    """GET /api/v1/ai/health -- whether the AI subsystem is configured.
    Reports configuration state only; never includes the API key or
    calls Groq (see app.api.ai's module docstring for why)."""

    configured: bool
    provider: AIProvider = AIProvider.GROQ
    model: str
