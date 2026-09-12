"""StudentCareerContext -- the normalized, read-only data model future
career agents will consume (Phase 2).

This is deliberately a COMPOSITION of the project's existing, already-
authoritative response schemas (app.schemas.assessment/skill_gap/
student_portfolio/student_learning/student_opportunity/
student_recommendation) -- never a re-derivation of their fields. Every
number/status/score here is copied verbatim from the same deterministic
services every existing student-facing endpoint already uses (see
app.ai.context and app.ai.tools). No field here is LLM-authored.

Sections are independent, typed models (StudentBasicInfo,
AssessmentSummary, SkillGapSection, PortfolioSection,
ApplicationHistorySummary) precisely so a future specialist agent can be
handed only the one or two sections it actually needs, instead of the
whole context -- see app.ai.tools for the per-section accessors.

Deliberately excluded (not "sensitive/unnecessary fields" per the Phase 2
brief): phone, date_of_birth, gender, location, cgpa, percentage,
department -- none of these are needed for skill-gap/course/opportunity
reasoning, and several are meaningful PII beyond what a career-advice
agent requires. `career_goals` / `preferred_roles` / `preferred_locations`
are kept because they are directly career-relevant self-reported intent.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.assessment import AttemptHistoryItemResponse
from app.schemas.skill_gap import (
    AnalysisMode,
    SkillGapJobRoleResponse,
    SkillGapPersonalResponse,
    TargetJobRoleResponse,
)
from app.schemas.student_learning import StudentLearningProgressItem
from app.schemas.student_opportunity import StudentApplicationResponse
from app.schemas.student_portfolio import (
    AchievementResponse,
    CertificationResponse,
    ProjectResponse,
)
from app.schemas.student_recommendation import RecommendedOpportunity

# Caps applied when building recent_attempts / recent_applications --
# context-size hygiene for a future agent's prompt budget, not a data
# limitation (the full history is still reachable through the existing
# GET /attempts and GET /student/applications endpoints).
_RECENT_ATTEMPTS_LIMIT = 10
_RECENT_APPLICATIONS_LIMIT = 10


class StudentBasicInfo(BaseModel):
    """Minimal, career-relevant identity + academic info. See the module
    docstring for what is deliberately excluded and why."""

    student_id: str
    full_name: str | None = None
    email: str | None = None
    degree: str | None = None
    graduation_year: int | None = None
    institution_name: str | None = None
    career_goals: str | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)


class StudentSkillSummary(BaseModel):
    """One of the student's own `student_skills` rows. `is_verified` /
    `verified_at` are copied as-is from the DB -- see
    003_skills.sql / 031_verified_skill_proficiency_integrity.sql for why
    those columns can only ever be trusted, never recomputed here."""

    skill_id: str
    skill_name: str
    category_name: str | None = None
    proficiency_level: str
    is_verified: bool
    verified_at: str | None = None


class AssessmentSummary(BaseModel):
    """Aggregate counts + recent history, all derived from the caller's
    own `assessment_attempts` rows (app.services.assessment_service) --
    no score/percentage/verification value here is recomputed; each is
    read back exactly as score_assessment_attempt() (015) already wrote
    it."""

    total_attempts: int
    completed_attempts: int
    passed_attempts: int
    verified_skill_count: int
    recent_attempts: list[AttemptHistoryItemResponse] = Field(default_factory=list)


class SkillGapSection(BaseModel):
    """The current deterministic Skill Gap output
    (app.services.skill_gap_service), verbatim -- exactly one of
    job_role_analysis / personal_analysis is populated, matching `mode`.
    Never recomputed differently than GET /api/v1/skill-gap itself."""

    mode: AnalysisMode
    job_role_analysis: SkillGapJobRoleResponse | None = None
    personal_analysis: SkillGapPersonalResponse | None = None


class PortfolioSection(BaseModel):
    """A direct mirror of app.services.student_portfolio_service's own
    read-only portfolio aggregate -- evidence only, no proficiency/
    verification signal (see that module's own schema docstring)."""

    projects: list[ProjectResponse] = Field(default_factory=list)
    certifications: list[CertificationResponse] = Field(default_factory=list)
    achievements: list[AchievementResponse] = Field(default_factory=list)


class ApplicationHistorySummary(BaseModel):
    """Aggregate counts + recent history over the caller's own
    `applications` rows (app.services.student_opportunity_service).
    `match_score`, where present on an item, is whatever
    match_service.compute_match last cached -- never recomputed here."""

    total_applications: int
    by_status: dict[str, int] = Field(default_factory=dict)
    recent_applications: list[StudentApplicationResponse] = Field(default_factory=list)


class StudentCareerContext(BaseModel):
    """The full normalized context for one student. Built by
    app.ai.context.build_student_career_context -- never by an LLM, and
    never containing anything an LLM (or another student) wrote. Every
    section defaults to an empty/None value when the student has no data
    there yet; an incomplete profile is a normal state, not a build
    failure (see the module docstring on app.ai.context)."""

    student_id: str
    generated_at: datetime

    basic_info: StudentBasicInfo
    target_job_role: TargetJobRoleResponse | None = None
    skills: list[StudentSkillSummary] = Field(default_factory=list)
    assessment_summary: AssessmentSummary
    skill_gap: SkillGapSection
    portfolio: PortfolioSection
    learning_progress: list[StudentLearningProgressItem] = Field(default_factory=list)
    application_history: ApplicationHistorySummary
    recommended_opportunities: list[RecommendedOpportunity] = Field(default_factory=list)
