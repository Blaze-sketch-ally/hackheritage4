"""Pydantic schemas for the aggregate Student recommendation surface
(Phase S7).

This is a thin ADAPTER/COMPOSER response -- every field is sourced from an
existing canonical system and nothing new is computed:

* `mode` / `target_role`  -- from `skill_recommendation_service`. `mode`
  is always `"AGGREGATE"` and `target_role` is always null: this project
  has no persisted "target role" concept to dispatch on (adopted from a
  collaborator branch and adapted -- see that module's own docstring, and
  app.api.student_learning's identical adaptation for
  /student/learning/recommended).
* assessment items (Phase 3D) -- `assessment_service.list_active_assessments`
  filtered to skills the aggregate Skill Gap flagged as GAP/NOT_ASSESSED,
  excluding assessments the student already has eligible completed
  evidence for (`assessment_service.get_completed_assessment_ids`, the
  same NOT_REQUIRED/COMPLETE eligibility contract as
  `get_student_skill_scores` -- Phase 3A). No new score: ranked by
  priority, then duration, then title.
* opportunity items       -- `student_opportunity_service.list_opportunities`
  for the published internship/job set, ranked by
  `student_opportunity_service.compute_opportunity_match` (which is the
  canonical deterministic `match_service.compute_match` scorer). No
  fabricated "AI" score, probability, or percentage.
* learning items          -- reused verbatim from
  `learning_recommendation_service.get_recommended_resources`
  (`LearningRecommendation` is re-exported from student_learning, not
  redefined).

`match_score` is the canonical `match_service` skill-coverage score
(0-100, weighted by importance and level) -- the same number the Industry
applicant-match and the per-opportunity Student match endpoints already
return. It is NOT a probability of selection / hiring / success, and the
frontend renders the honest "matches N of M skills" count + band rather
than a bare percentage.
"""

from typing import Literal

from pydantic import BaseModel

from app.schemas.student_learning import LearningRecommendation

RecommendationMode = Literal["AGGREGATE"]


class RecommendedTargetRole(BaseModel):
    """The student's saved target role, echoed for UI consistency with
    /student/skill-gap and /student/career. Never set or changed here."""

    id: str
    name: str


class RecommendedAssessment(BaseModel):
    """One active assessment mapped to a skill the aggregate Skill Gap
    flagged as GAP or NOT_ASSESSED, that the student does not already have
    eligible completed evidence for (see module docstring). `reason_type`
    mirrors the underlying app.services.skill_alignment_service.AlignmentStatus
    the gap came from (STRONG is never surfaced here, so only two values
    are possible); `reason`/`priority` are the gap entry's own explanation,
    not a duplicated business rule."""

    id: str
    title: str
    skill_id: str
    skill_name: str
    difficulty: str
    duration_minutes: int | None = None
    reason_type: Literal["SKILL_GAP", "NOT_ASSESSED"]
    reason: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]


class RecommendedOpportunity(BaseModel):
    """One published internship or job the student has NOT already applied
    to, that shares at least one skill with the student's profile.

    `id` keeps the existing student-facing prefixed convention
    (`internship_<uuid>` / `job_<uuid>`) so it round-trips through the
    existing /api/v1/student/opportunities routes unchanged. `detail_path`
    is a server-built fixed-prefix route -- never a free-form string.
    """

    type: Literal["INTERNSHIP", "JOB"]
    id: str
    title: str
    description: str
    company: str | None = None
    location: str | None = None
    work_mode: str | None = None
    detail_path: str

    # All canonical, from match_service.compute_match via
    # student_opportunity_service.compute_opportunity_match:
    match_score: int  # 0-100 skill-coverage score, NOT a probability
    match_band: str  # STRONG / GOOD / PARTIAL / LOW
    matched_skill_count: int
    required_skill_count: int
    relevant_skills: list[str] = []  # names of the required skills the student already has


class StudentRecommendationsResponse(BaseModel):
    mode: RecommendationMode
    target_role: RecommendedTargetRole | None = None
    assessments: list[RecommendedAssessment] = []
    opportunities: list[RecommendedOpportunity] = []
    learning: list[LearningRecommendation] = []
