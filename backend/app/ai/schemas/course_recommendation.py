"""Server-owned course facts and a deliberately flat, ref-only LLM contract."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.schemas.base import AIResponseMeta
from app.ai.schemas.youtube_learning import YouTubeRecommendation
from app.schemas.skill_gap import AnalysisMode


class CourseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate_id: str = Field(min_length=1, max_length=300)
    source_type: Literal["INTERNAL", "EXTERNAL"]
    provider: str | None = Field(default=None, max_length=300)
    title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=1, max_length=2048)
    description: str | None = Field(default=None, max_length=4000)
    skill_ids: list[str] = Field(min_length=1, max_length=50)
    skill_names: list[str] = Field(default_factory=list, max_length=50)
    level: str | None = None
    duration_text: str | None = None
    price_text: str | None = None
    rating: float | None = Field(default=None, ge=0)
    certificate_available: bool | None = None
    external_course_id: str | None = None
    metadata_source: str = Field(min_length=1, max_length=300)

    @field_validator("url")
    @classmethod
    def safe_link(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Course URL must be an HTTP(S) source link.")
        return value


class CourseSkill(BaseModel):
    ref: str
    skill_id: str
    skill_name: str
    status: str | None = None
    priority: str | None = None
    importance: str | None = None
    current_level: str | None = None
    target_level: str | None = None
    reason: str | None = None


class CourseCanonical(BaseModel):
    mode: AnalysisMode
    target_role: str | None = None
    skills_considered: list[CourseSkill] = Field(default_factory=list)


class CourseInputSkill(BaseModel):
    ref: str
    name: str
    status: str | None
    priority: str | None
    importance: str | None
    current_level: str | None
    target_level: str | None


class CourseInputCandidate(BaseModel):
    ref: str
    title: str
    description: str | None
    level: str | None
    skill_refs: list[str]


class CourseRecommendationAgentInput(BaseModel):
    target_role: str | None
    top_skill_gaps: list[CourseInputSkill]
    course_candidates: list[CourseInputCandidate]


class CourseLLMOutput(BaseModel):
    """No free prose survives: notes select server-checked rationale codes.

    This is stronger than a prompt prohibition: even a malicious model cannot
    introduce a URL, certificate claim, or completion claim into an explanation.
    """

    model_config = ConfigDict(extra="forbid")
    recommended_course_refs: list[str] = Field(max_length=12)
    recommendation_notes: list[str] = Field(
        max_length=12, description="C1 -> G1: SKILL_MATCH or LEVEL_MATCH or FOUNDATION"
    )
    learning_order: list[str] = Field(
        max_length=12, description="Bare selected C refs in study order"
    )


class CourseRecommendation(BaseModel):
    course: CourseCandidate
    for_skill: CourseSkill
    reason: str
    rank: int


class CoursePlanStep(BaseModel):
    order: int
    candidate_id: str
    skill_id: str
    instruction: str = "Review this resource and use it for focused practice."


class CourseResponseMeta(AIResponseMeta):
    ai_ranking_available: bool = False
    ranking_status: Literal["AI", "DETERMINISTIC", "NO_GAPS", "NO_COURSES"]
    external_discovery_available: bool = False
    external_discovery_status: Literal["AVAILABLE", "CONFIGURATION_REQUIRED", "FAILED"]
    internal_discovery_available: bool = True
    message: str | None = None
    # YouTube (Phase 4.7) is a fully additive, independent channel --
    # see app.ai.agents.youtube_recommendation_agent. Its own
    # unavailability never touches ranking_status/external_discovery_*
    # above, which describe the course pipeline only.
    youtube_available: bool = False
    youtube_ai_ranking_available: bool = False
    youtube_status: Literal[
        "AVAILABLE", "CONFIGURATION_REQUIRED", "QUOTA_EXCEEDED", "TEMPORARILY_UNAVAILABLE", "FAILED"
    ] = "CONFIGURATION_REQUIRED"


class CourseRecommendationResponse(BaseModel):
    canonical: CourseCanonical
    recommendations: list[CourseRecommendation] = Field(default_factory=list)
    learning_plan: list[CoursePlanStep] = Field(default_factory=list)
    # Additive sibling list, never merged into `recommendations` -- a
    # YouTube video is not a CourseCandidate (see
    # app.ai.schemas.youtube_learning.YouTubeVideoCandidate's own
    # docstring on why mixing the two would be misleading metadata).
    youtube_videos: list[YouTubeRecommendation] = Field(default_factory=list)
    meta: CourseResponseMeta
    disclaimer: str = (
        "Course facts come from the catalog or discovery source. Ranking is advisory; "
        "a recommendation does not establish course completion or skill verification."
    )
