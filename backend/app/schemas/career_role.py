"""Pydantic schemas for the Career Role / Skill Gap API (Phase 1L).

Mirrors database/migrations/022_career_roles_skill_gap.sql exactly -- no
invented columns. Decimal fields (required_level, student_score, gap,
weight, overall_score) serialize as JSON STRINGS, exactly like every
other Decimal field in this project (see schemas/assessment.py's own
docstring) -- never parse them into a JS number client-side for further
arithmetic; the backend (app.services.skill_alignment_service) is the
sole source of these values.

No endpoint, service, or alignment-calculation logic lives here --
schemas only.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel

# ============================================================
# Enums -- mirrors app.services.skill_alignment_service.AlignmentStatus
# ============================================================


class AlignmentStatus(str, Enum):
    STRONG = "STRONG"
    GAP = "GAP"
    NOT_ASSESSED = "NOT_ASSESSED"


# ============================================================
# career_roles
# ============================================================


class CareerRoleResponse(BaseModel):
    """Mirrors `career_roles`."""

    id: UUID
    title: str
    description: str | None
    category: str | None
    created_at: datetime
    updated_at: datetime


class CareerRoleListResponse(BaseModel):
    career_roles: list[CareerRoleResponse]


# ============================================================
# Skill gap
# ============================================================


class SkillGapSkillResponse(BaseModel):
    """One required skill's alignment result -- mirrors
    app.services.skill_alignment_service.SkillAlignmentResult field for
    field."""

    skill_id: UUID
    skill_name: str
    required_level: Decimal
    student_score: Decimal
    gap: Decimal
    weight: Decimal
    status: AlignmentStatus


class SkillGapResponse(BaseModel):
    """The full skill-gap comparison for the authenticated student against
    one career role. Never constructed with another student's data --
    student_score values here are always derived from the CALLER's own
    completed attempts (app.services.assessment_service.
    get_student_skill_scores), never a client-supplied student_id."""

    career_role: CareerRoleResponse
    overall_score: Decimal
    skills: list[SkillGapSkillResponse]
