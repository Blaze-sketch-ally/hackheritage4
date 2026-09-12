"""Career AI Chat (Phase 7) -- server-owned chat facts and a
deliberately flat, ref-only LLM contract, exactly the same boundary as
every earlier phase's *LLMOutput schema.

Groq NEVER queries the database, never invents a job/course/video/
score/verification state, and never sees more than the bounded,
already-grounded facts the router selected for the classified intent.
`ChatLLMOutput` (extra="forbid") is the ENTIRE surface Groq can affect:
a short message string and a list of bare refs into data the server
already built. Every card in the response is reconstructed server-side
from the SAME specialist objects every other AI route already trusts
(skill_gap_agent / course_recommendation_agent /
youtube_recommendation_agent / opportunity_recommendation_agent) --
never from LLM text.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

_MAX_MESSAGE = 1500
_MAX_HISTORY = 6

# ============================================================
# Request
# ============================================================


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=_MAX_MESSAGE)


class CareerChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE)
    history: list[ChatMessage] = Field(default_factory=list, max_length=_MAX_HISTORY)


# ============================================================
# Intent
# ============================================================


# Plain string constants, not a real Enum -- `ChatIntentValue` (the
# Literal below) is what gives Pydantic its closed set; these exist so
# guardrails/career_chat.py's keyword table and chat/career_chat.py's
# dispatch table can reference intents without a `.value` indirection.
SKILL_GAP = "SKILL_GAP"
LEARNING = "LEARNING"
YOUTUBE_LEARNING = "YOUTUBE_LEARNING"
JOB = "JOB"
INTERNSHIP = "INTERNSHIP"
OPPORTUNITY = "OPPORTUNITY"
ASSESSMENT = "ASSESSMENT"
CAREER_PLAN = "CAREER_PLAN"
READINESS = "READINESS"
GENERAL_CAREER = "GENERAL_CAREER"

ChatIntentValue = Literal[
    "SKILL_GAP",
    "LEARNING",
    "YOUTUBE_LEARNING",
    "JOB",
    "INTERNSHIP",
    "OPPORTUNITY",
    "ASSESSMENT",
    "CAREER_PLAN",
    "READINESS",
    "GENERAL_CAREER",
]


class IntentClassification(BaseModel):
    """The ONLY thing the fallback classifier call may return -- a
    single closed-vocabulary field. There is no channel here for the
    model to return prose, a tool call, or anything else."""

    model_config = ConfigDict(extra="forbid")
    intent: ChatIntentValue


# ============================================================
# Cards -- every field source-owned, reconstructed server-side only
# ============================================================


class SkillCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["SKILL"] = "SKILL"
    skill_id: str
    skill_name: str
    current_level: str | None = None
    target_level: str | None = None
    status: str | None = None
    priority: str | None = None
    importance: str | None = None
    reason: str | None = None


class CourseCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["COURSE"] = "COURSE"
    candidate_id: str
    title: str
    provider: str | None = None
    url: str
    level: str | None = None
    duration_text: str | None = None
    skill_name: str | None = None
    reason: str | None = None


class YouTubeVideoCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["YOUTUBE_VIDEO"] = "YOUTUBE_VIDEO"
    video_id: str
    title: str
    channel_title: str
    thumbnail_url: str | None = None
    watch_url: str
    duration_text: str | None = None
    view_count: int | None = None
    published_at: str | None = None
    skill_name: str | None = None
    reason: str | None = None


class OpportunityCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["OPPORTUNITY"] = "OPPORTUNITY"
    opportunity_id: str
    opportunity_type: str
    title: str
    company: str | None = None
    match_score: int | None = None
    match_band: str | None = None
    matched_count: int | None = None
    gap_count: int | None = None
    detail_url: str
    reason: str | None = None


class AssessmentCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["ASSESSMENT"] = "ASSESSMENT"
    skill_id: str
    skill_name: str
    action: str
    note: str
    cta_url: str = "/student/skill-gap"


class CareerActionCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["CAREER_ACTION"] = "CAREER_ACTION"
    label: str
    url: str


ChatCard = Annotated[
    SkillCard | CourseCard | YouTubeVideoCard | OpportunityCard | AssessmentCard | CareerActionCard,
    Field(discriminator="type"),
]


class SuggestedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    url: str


# ============================================================
# LLM boundary
# ============================================================


class ChatInputCard(BaseModel):
    """One bounded, already-truncated fact Groq is allowed to see and
    reference -- `detail` is a short, source-derived descriptor (e.g.
    "Beginner -> Intermediate, CORE priority"), never free LLM text."""

    ref: str
    kind: str
    title: str
    detail: str | None = None


class ChatHistoryTurn(BaseModel):
    role: str
    content: str


class ChatAgentInput(BaseModel):
    """Never contains student_id, email, or any field not already on
    ChatInputCard/ChatHistoryTurn -- built fresh per request from the
    router's OWN grounded specialist call, never from history."""

    user_message: str
    intent: str
    grounded_cards: list[ChatInputCard]
    recent_history: list[ChatHistoryTurn]


class ChatLLMOutput(BaseModel):
    """No free metadata survives: a short message plus bare refs into
    already-grounded cards. Even a malicious model cannot introduce a
    URL, score, title, or fact that was not already server-selected."""

    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=800)
    mentioned_refs: list[str] = Field(default_factory=list, max_length=8)


# ============================================================
# Response
# ============================================================


class CareerChatMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["groq"] = "groq"
    model: str
    ai_available: bool = False
    intent: ChatIntentValue
    intent_source: Literal["KEYWORD", "AI_CLASSIFIER", "DEFAULT"] = "KEYWORD"


class CareerChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    intent: ChatIntentValue
    cards: list[ChatCard] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    meta: CareerChatMeta
    disclaimer: str = (
        "Career AI explanations are advisory. Every fact shown (scores, matches, "
        "verification, course/video/opportunity details) comes directly from your "
        "canonical data -- the assistant only helps explain and navigate it."
    )
