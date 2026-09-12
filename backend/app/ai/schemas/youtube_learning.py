"""Server-owned YouTube video facts and a deliberately flat, ref-only LLM
contract -- mirrors app.ai.schemas.course_recommendation's own boundary
(CourseCandidate / CourseLLMOutput) but stays a SEPARATE schema on
purpose: a video is not a course, and pretending otherwise would be
misleading metadata (no price/certificate/instructor semantics apply).

This module intentionally does NOT import from
app.ai.schemas.course_recommendation, even though a couple of fields
below (YouTubeSkillRef) mirror CourseSkill/CourseInputSkill -- that
avoids a circular import, since CourseRecommendationResponse embeds
YouTubeRecommendation additively (see that module's own docstring).
"""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

_VIDEO_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"


class YouTubeVideoCandidate(BaseModel):
    """Every field here is source-owned (the YouTube Data API v3
    response); never LLM-authored. `watch_url` is a computed field
    derived only from `video_id` -- it cannot be independently supplied
    or drift from the source-owned ID (see app.ai.tools.youtube_learning
    for why this must never be built from a title/slug)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    video_ref: str = Field(default="", max_length=20)
    video_id: str = Field(min_length=11, max_length=11, pattern=_VIDEO_ID_PATTERN)
    # Populated by the provider with "" (not yet mapped to a canonical
    # skill) and filled in by the calling agent via model_copy() once it
    # is -- see app.ai.tools.youtube_learning._to_candidate and
    # app.ai.tools.youtube_learning.discover_for_skills. Deliberately
    # NOT min_length=1: a video is a real, valid candidate before that
    # mapping happens.
    skill_id: str = Field(default="", max_length=200)
    skill_name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    channel_id: str | None = Field(default=None, max_length=100)
    channel_title: str = Field(min_length=1, max_length=200)
    published_at: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    duration_iso8601: str | None = Field(default=None, max_length=40)
    duration_text: str | None = None
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    source: Literal["YouTube"] = "YouTube"
    resource_type: Literal["VIDEO"] = "VIDEO"
    metadata_source: Literal["YOUTUBE_DATA_API"] = "YOUTUBE_DATA_API"

    @field_validator("thumbnail_url")
    @classmethod
    def https_thumbnail_only(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or any(c.isspace() for c in value):
            raise ValueError("thumbnail_url must be an HTTPS image URL.")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def watch_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


class YouTubeSkillRef(BaseModel):
    """A minimal, independent copy of the canonical skill-gap fields the
    YouTube pipeline needs for display/grounding -- populated from the
    same CourseSkill the caller already selected (see
    app.ai.agents.youtube_recommendation_agent). Kept separate from
    CourseSkill itself only to avoid this module importing from
    app.ai.schemas.course_recommendation (see this module's own
    docstring)."""

    ref: str
    skill_id: str
    skill_name: str
    status: str | None = None
    importance: str | None = None
    target_level: str | None = None


class YouTubeInputVideo(BaseModel):
    ref: str
    title: str
    description: str | None
    channel_title: str
    duration_text: str | None
    skill_refs: list[str]


class YouTubeRecommendationAgentInput(BaseModel):
    top_skill_gaps: list[YouTubeSkillRef]
    video_candidates: list[YouTubeInputVideo]


class YouTubeLLMOutput(BaseModel):
    """No free prose survives: notes select server-checked rationale
    codes. Even a malicious model cannot introduce a video title, URL,
    channel, or statistic into an explanation."""

    model_config = ConfigDict(extra="forbid")
    recommended_video_refs: list[str] = Field(max_length=6)
    recommendation_codes: list[str] = Field(
        max_length=6,
        description="Y1 -> G1: SKILL_GAP_MATCH or LEVEL_MATCH or FOUNDATION or PRACTICAL_TUTORIAL or DEEP_DIVE",
    )
    learning_order: list[str] = Field(max_length=6, description="Bare selected Y refs in study order")


class YouTubeRecommendation(BaseModel):
    video: YouTubeVideoCandidate
    for_skill: YouTubeSkillRef
    reason: str
    rank: int


class YouTubeResponseMeta(BaseModel):
    youtube_available: bool = False
    youtube_ai_ranking_available: bool = False
    youtube_status: Literal[
        "AVAILABLE", "CONFIGURATION_REQUIRED", "QUOTA_EXCEEDED", "TEMPORARILY_UNAVAILABLE", "FAILED"
    ] = "CONFIGURATION_REQUIRED"
