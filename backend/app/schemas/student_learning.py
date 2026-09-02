"""Pydantic schemas for the STUDENT Learning API
(database/migrations/033_learning_resources.sql).

Three live tables back this: `learning_resources` (curated catalog,
read-only to students), `learning_resource_skills` (resource -> canonical
`skills` mapping), and `student_learning_progress` (the caller's own
SAVED / IN_PROGRESS / COMPLETED relationship with a resource).

Learning progress is NOT skill evidence: there is no score / skill level /
verification field anywhere here. Completing a resource never touches
`student_skills` and never verifies a skill -- that stays exclusively the
job of the assessment scoring path (015_assessment_verification.sql).

`student_id` is never a field on any request model. It is always
`current_user.id`, derived from the authenticated token by the route.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# database/migrations/033_learning_resources.sql -- CHECK constraints
ResourceType = Literal["COURSE", "ARTICLE", "VIDEO", "OTHER"]
Difficulty = Literal["Beginner", "Intermediate", "Advanced", "Expert"]
ProgressStatus = Literal["SAVED", "IN_PROGRESS", "COMPLETED"]

PROGRESS_STATUSES: tuple[str, ...] = ("SAVED", "IN_PROGRESS", "COMPLETED")


class ResourceSkill(BaseModel):
    """One skill a learning resource helps with, resolved to its catalog
    name. `target_level` is the proficiency level this resource targets
    for that skill (null when the resource is a general intro)."""

    skill_id: str
    skill_name: str
    target_level: str | None = None


class LearningProgress(BaseModel):
    """The authenticated student's own progress on one resource. Embedded
    on a resource response so the browse/detail UI can show a
    "Saved" / "In progress" / "Completed" badge without a second call.
    Always the caller's own -- RLS on `student_learning_progress` and an
    explicit `student_id` filter both scope it."""

    status: str
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None


class LearningResourceSummary(BaseModel):
    """One catalogued resource, normalized for the browse list. Only
    student-facing catalog fields -- no `is_active` (an inactive resource
    is never returned at all), no `created_at`/`updated_at` on the
    resource itself."""

    id: str
    title: str
    description: str | None = None
    url: str
    provider: str | None = None
    resource_type: str
    difficulty: str | None = None
    estimated_minutes: int | None = None
    skills: list[ResourceSkill] = Field(default_factory=list)
    progress: LearningProgress | None = None


class LearningResourceDetail(LearningResourceSummary):
    """The detail response is the same shape as the summary -- a resource
    is small enough that the list already carries everything the detail
    page needs (skills + the caller's progress). Kept as a distinct model
    so a future detail-only field has a home."""


class LearningResourceListResponse(BaseModel):
    resources: list[LearningResourceSummary]


class ProgressResourceRef(BaseModel):
    """The resource a progress row points at, embedded on the "My
    Learning" list. Can be null if the resource has since been
    deactivated -- the progress row itself (the student's history) still
    exists; a student has no RLS path to an inactive resource."""

    id: str
    title: str
    url: str
    provider: str | None = None
    resource_type: str
    difficulty: str | None = None


class StudentLearningProgressItem(BaseModel):
    resource_id: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    resource: ProgressResourceRef | None = None


class StudentLearningProgressListResponse(BaseModel):
    progress: list[StudentLearningProgressItem]


class ProgressUpdateRequest(BaseModel):
    """POST /api/v1/student/learning/resources/{id}/progress body.

    `status` is a restricted Literal, so anything outside
    SAVED / IN_PROGRESS / COMPLETED (e.g. "completed", "DONE", "VERIFIED",
    "PASSED") fails validation with a 422 before any handler runs.
    `extra="forbid"` structurally rejects any attempt to smuggle in
    `student_id`, `created_at`, `updated_at`, `started_at`, `completed_at`,
    `is_verified`, `verified_at`, `score`, `assessment_id`, or
    `student_skill_id` -- every timestamp is server-set, and no
    verification/score concept exists on this path at all.
    """

    model_config = ConfigDict(extra="forbid")

    status: ProgressStatus


class ProgressUpdateResponse(BaseModel):
    resource_id: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


# ---- Skill Gap -> Learning recommendations (Phase 6D) ----


class MatchedGapSkill(BaseModel):
    """One canonical Skill Gap skill (an item of
    ``app.services.skill_gap_service``'s ``recommendations`` list) that a
    recommended learning resource is mapped to via
    ``learning_resource_skills.skill_id``.

    ``reason`` is the Skill Gap engine's own deterministic, server-authored
    text -- surfaced verbatim so the UI can explain *why* the resource is
    recommended. ``priority`` is that engine's HIGH / MEDIUM / LOW tag,
    reused only for ordering -- no relevance score / match percentage is
    invented on this path.
    """

    skill_id: str
    skill_name: str
    reason: str
    priority: str


class LearningRecommendation(BaseModel):
    """One recommended resource plus every current Skill Gap skill it
    covers. A resource mapped to several gap skills appears once here, with
    all of them listed."""

    resource: LearningResourceSummary
    matched_skills: list[MatchedGapSkill]


class LearningRecommendationListResponse(BaseModel):
    """``mode`` mirrors GET /api/v1/skill-gap: ``"JOB_ROLE"`` when the
    student has saved a target role (recommendations come from that role's
    gaps), ``"PERSONAL"`` otherwise (recommendations come from the
    skill-relationship-driven "what to learn next" analysis). The
    recommendation skills themselves are always the canonical engine's
    output -- this endpoint never computes its own."""

    mode: str
    recommendations: list[LearningRecommendation]
