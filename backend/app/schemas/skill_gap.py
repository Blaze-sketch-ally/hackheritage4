"""Pydantic schemas for Skill Gap Analysis, job roles, and the student's
target role.

Mirrors database/migrations/016_skill_gap.sql exactly -- no invented
columns, no invented enum values. Reuses the EXISTING four-value
proficiency scale from student_skills.proficiency_level /
assessments.difficulty (Beginner/Intermediate/Advanced/Expert) -- this
module defines no second, competing proficiency enum.

No LLM, no free-text AI-generated fields anywhere in this module. Every
"reason" string is built from a small set of deterministic templates in
app.services.skill_gap_service, driven entirely by job_role_skills /
skill_relationships / student_skills / assessments data.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.assessment import Difficulty

# ============================================================
# Enums
# ============================================================


class Importance(str, Enum):
    CORE = "CORE"
    IMPORTANT = "IMPORTANT"
    OPTIONAL = "OPTIONAL"


class RelationshipType(str, Enum):
    PREREQUISITE = "PREREQUISITE"
    RELATED = "RELATED"
    NEXT_STEP = "NEXT_STEP"
    COMPLEMENTARY = "COMPLEMENTARY"


class GapStatus(str, Enum):
    MATCHED = "MATCHED"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    MISSING = "MISSING"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalysisMode(str, Enum):
    JOB_ROLE = "JOB_ROLE"
    PERSONAL = "PERSONAL"


# ============================================================
# job_roles / job_role_skills
# ============================================================


class JobRoleResponse(BaseModel):
    """Mirrors `job_roles`. Only ever populated from rows RLS already
    filtered to is_active = true."""

    id: UUID
    name: str
    description: str | None
    category: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobRoleListResponse(BaseModel):
    job_roles: list[JobRoleResponse]


class JobRoleSkillRequirement(BaseModel):
    """Mirrors `job_role_skills`, with the skill's name/category embedded
    for display -- never just a bare skill_id."""

    skill_id: UUID
    skill_name: str
    category_name: str | None
    required_level: Difficulty
    importance: Importance


class JobRoleDetailResponse(BaseModel):
    role: JobRoleResponse
    requirements: list[JobRoleSkillRequirement]


# ============================================================
# student_target_job_role
# ============================================================


class TargetJobRoleResponse(BaseModel):
    """Mirrors `student_target_job_role`, joined with the role itself.
    student_id is deliberately NOT included -- this is always the
    caller's own row, resolved server-side; there is nothing to gain by
    echoing it back."""

    id: UUID
    job_role: JobRoleResponse
    created_at: datetime
    updated_at: datetime


class SetTargetJobRoleRequest(BaseModel):
    """The only field a client may ever supply -- student_id is derived
    from the authenticated session, never accepted here."""

    model_config = ConfigDict(extra="forbid")

    job_role_id: UUID


# ============================================================
# Skill gap analysis
# ============================================================


class SkillGapItem(BaseModel):
    """One required skill's gap status against the target role.

    current_level is the student's DECLARED student_skills.proficiency_level
    (or None if the skill isn't in their active list at all) --
    verification_status is a SEPARATE signal for whether that declared
    level has actually been assessment-verified. These are never mixed
    into one value (see the module/service docstrings for why).
    """

    skill_id: UUID
    skill_name: str
    current_level: Difficulty | None
    required_level: Difficulty
    gap: int
    status: GapStatus
    verification_status: VerificationStatus
    importance: Importance
    priority: Priority
    assessment_available: bool
    assessment_id: UUID | None


class SkillGapSummary(BaseModel):
    matched: int
    needs_improvement: int
    missing: int
    unverified: int


class Recommendation(BaseModel):
    """One deterministic, data-driven recommendation -- never LLM-authored
    free text. `reason` is built from a small fixed set of templates
    (see skill_gap_service.py) parameterized only by real data (skill
    names, levels, relationship type)."""

    skill_id: UUID
    skill_name: str
    reason: str
    current_level: Difficulty | None
    target_level: Difficulty | None
    gap: int | None
    priority: Priority
    relationship_type: RelationshipType | None
    is_missing: bool
    is_verified: bool
    assessment_available: bool
    assessment_id: UUID | None


class SkillGapJobRoleResponse(BaseModel):
    mode: AnalysisMode
    job_role: JobRoleResponse
    readiness_percentage: int
    summary: SkillGapSummary
    skills: list[SkillGapItem]
    recommendations: list[Recommendation]


# ---- Personal (no target role) mode ----


class PersonalSkillCounts(BaseModel):
    total_active_skills: int
    verified_skills: int
    unverified_skills: int
    beginner_skills: int
    intermediate_skills: int
    advanced_skills: int
    expert_skills: int


class ProgressableSkill(BaseModel):
    """One of the student's current skills that has a real assessment
    available at the next level up."""

    skill_id: UUID
    skill_name: str
    current_level: Difficulty
    next_level: Difficulty
    assessment_available: bool
    assessment_id: UUID | None


class PrerequisiteGap(BaseModel):
    """A skill the student is missing that is a documented PREREQUISITE
    (skill_relationships) of one of their recommended next skills."""

    skill_id: UUID
    skill_name: str
    required_for_skill_id: UUID
    required_for_skill_name: str


class SkillGapPersonalResponse(BaseModel):
    mode: AnalysisMode
    counts: PersonalSkillCounts
    progressable_skills: list[ProgressableSkill]
    recommendations: list[Recommendation]
    prerequisite_gaps: list[PrerequisiteGap]
