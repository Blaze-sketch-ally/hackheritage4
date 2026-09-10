"""Pydantic schemas for the Institution Skill Gap Analysis
(backend/app/api/institution.py, GET /institution/skill-gaps,
GET /institution/skill-gaps/{application_id}).

This is an APPLICATION-SPECIFIC skill gap tool, not an institution-wide
prediction dashboard: for one of the institution's own linked students'
applications, how does that student's recorded `student_skills` compare to
the opportunity's own `internship_skills` / `job_skills` requirements.

The match fields (`score`, `recommendation`, `skill_coverage`,
`matched_skills`, `needs_improvement_skills`, `missing_skills`) are the
EXACT same shape Industry's own ApplicationMatchResponse already uses
(app.schemas.application) -- `MatchSkill` and `MatchRecommendation` are
imported, not redefined, so a client (or a test) can never observe two
different skill-match shapes across roles. `student_skills` reuses
`StudentSkillSummary` from app.schemas.institution_student for the exact
same reason -- the Institution Student Directory already defined "how a
student's skill list is shaped for institution eyes"; this module does not
invent a second one.
"""

from pydantic import BaseModel

from app.schemas.application import MatchRecommendation, MatchSkill, OpportunityType
from app.schemas.institution_student import StudentSkillSummary


class SkillGapApplicationSummary(BaseModel):
    """One row in the Skill Gap Analysis list -- one application by one of
    the institution's own linked students, with its deterministic skill
    match already computed (app.services.match_service.compute_match)."""

    application_id: str
    student_id: str
    full_name: str | None
    username: str | None
    opportunity_type: OpportunityType
    opportunity_title: str | None
    company_name: str | None
    status: str
    applied_at: str | None
    score: int
    recommendation: MatchRecommendation
    skill_coverage: str
    matched_count: int
    needs_improvement_count: int
    missing_count: int


class SkillGapListResponse(BaseModel):
    applications: list[SkillGapApplicationSummary]


class SkillGapDetailResponse(SkillGapApplicationSummary):
    """Everything the list row has, plus the full skill breakdown and the
    student's own complete recorded skill list (not just the skills the
    opportunity happens to require)."""

    required_count: int
    matched_skills: list[MatchSkill]
    needs_improvement_skills: list[MatchSkill]
    missing_skills: list[MatchSkill]
    student_skills: list[StudentSkillSummary]
