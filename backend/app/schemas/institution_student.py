"""Pydantic schemas for the Institution Student Directory
(backend/app/api/institution.py, GET /institution/students,
GET /institution/students/{student_id}).

Every field here is backed by a real column or a real, already-derived
value -- nothing is fabricated. In particular:
  - `placement_status` reuses the EXACT same three-bucket definition as
    the Institution Dashboard (institution_service._placement_buckets):
    PLACED (>=1 SELECTED application), APPLYING (>=1 application, none
    SELECTED), NOT_PARTICIPATING (no applications at all). The dashboard
    and this directory must never define "placed" differently -- see
    institution_student_service.py's own docstring.
  - `internship_status` is the same three-bucket logic narrowed to
    opportunity_type = 'INTERNSHIP' only.
  - There is no `eligible` field anywhere here -- same reasoning as
    InstitutionOverviewResponse.eligibility_note (no eligibility data
    model exists in this schema).
  - No email, phone, or any other sensitive profile field is exposed --
    see institution_student_service.py and migration 039's own comments.
"""

from typing import Literal

from pydantic import BaseModel

PlacementStatus = Literal["PLACED", "APPLYING", "NOT_PARTICIPATING"]
InternshipStatus = Literal["SELECTED", "APPLYING", "NONE"]


class StudentSkillSummary(BaseModel):
    skill_name: str
    proficiency_level: str
    is_verified: bool


class StudentSummary(BaseModel):
    """One row in the Student Directory list."""

    id: str
    full_name: str | None
    username: str | None
    avatar_url: str | None
    # institution_link_requests.id for this student's current APPROVED
    # link -- lets the frontend call the existing unlink endpoint
    # (POST /institution-links/{id}/unlink, migration 038) directly from
    # the directory/detail views without a second lookup. None only in
    # the (should-never-happen) case where a student_profiles row has
    # institution_id set but no matching APPROVED request is found.
    link_request_id: str | None
    # None means "Unassigned" -- see database/migrations/
    # 040_institution_departments.sql. `department` is the resolved
    # display name ("Unassigned" when department_id is None), NOT the
    # student's own free-text student_profiles.department value anymore.
    department_id: str | None
    department: str
    # student_profiles.graduation_year -- displayed as "Batch".
    batch: int | None
    cgpa: float | None
    percentage: float | None
    placement_status: PlacementStatus
    internship_status: InternshipStatus
    # Up to 5 skills, highest-proficiency first -- not the full list (see
    # get_student_detail for that). Matches the dashboard's own
    # top-skills cap philosophy (institution_service._TOP_SKILLS_LIMIT).
    top_skills: list[str]
    # Same algorithm as frontend/lib/student/profile.ts's
    # getProfileCompletion -- ported here so the institution-visible
    # figure and the student's own never silently drift apart. See
    # institution_student_service._profile_completion.
    profile_completion: int


class StudentListSummary(BaseModel):
    """Roster-wide counts (before search/filter/pagination is applied) --
    reuses the exact same `_placement_buckets` computation as the
    Institution Dashboard (institution_service.compute_institution_overview),
    so these summary cards and the Dashboard's own KPIs can never disagree
    for the same institution."""

    total_students: int
    placed: int
    unplaced: int
    no_applications: int
    internship_selected: int


class DepartmentOption(BaseModel):
    """One of the institution's real departments (id + display name) --
    NOT a free-text value. Includes inactive departments too, so a
    student historically assigned to a since-deactivated department can
    still be found via this filter (Part 12/23 of this phase: inactive
    departments must not disappear from historical student data)."""

    id: str
    name: str


class StudentListFilters(BaseModel):
    """Distinct values available across the institution's FULL linked
    roster (not just the current page) -- lets the frontend populate
    filter dropdowns without a second round trip or guessing options
    from one page's worth of rows. "Unassigned" is not listed here (it's
    a fixed, well-known filter value the frontend already knows about,
    not a real department row) -- pass `department=unassigned` to filter
    for it."""

    departments: list[DepartmentOption]
    batches: list[int]


class StudentListResponse(BaseModel):
    students: list[StudentSummary]
    total: int
    page: int
    page_size: int
    filters: StudentListFilters
    summary: StudentListSummary


class StudentProjectSummary(BaseModel):
    id: str
    title: str
    description: str | None
    project_url: str | None
    repo_url: str | None
    is_ongoing: bool
    skills: list[str]


class StudentCertificationSummary(BaseModel):
    id: str
    name: str
    issuing_organization: str | None
    issue_date: str | None
    credential_url: str | None


class StudentAchievementSummary(BaseModel):
    id: str
    title: str
    description: str | None
    achievement_date: str | None
    issuing_organization: str | None


class StudentApplicationSummary(BaseModel):
    id: str
    opportunity_type: str  # "INTERNSHIP" | "JOB"
    opportunity_title: str | None
    company_name: str | None
    status: str
    applied_at: str | None


class StudentAssessmentSummary(BaseModel):
    assessment_title: str | None
    skill_name: str | None
    status: str
    percentage: float | None
    submitted_at: str | None


class StudentInterviewSummary(BaseModel):
    """Deliberately excludes `notes` (industry-private preparation notes,
    030_industry_interviews.sql's own comment: "never exposed to any
    other role") -- see institution_student_service.py."""

    id: str
    opportunity_title: str | None
    scheduled_at: str
    mode: str
    status: str


class StudentDetailResponse(BaseModel):
    id: str
    full_name: str | None
    username: str | None
    avatar_url: str | None
    # See StudentSummary.link_request_id's own docstring.
    link_request_id: str | None

    # ---- academics ----
    department_id: str | None
    department: str
    # The free-text value from the student's OWN /student/profile page --
    # informational only, shown so the institution can decide which real
    # department to assign; never the authoritative value itself.
    self_reported_department: str | None
    batch: int | None
    degree: str | None
    cgpa: float | None
    percentage: float | None
    profile_completion: int

    # ---- skills ----
    skills: list[StudentSkillSummary]

    # ---- portfolio (read-only; no new schema, existing student_* tables) ----
    projects: list[StudentProjectSummary]
    certifications: list[StudentCertificationSummary]
    achievements: list[StudentAchievementSummary]

    # ---- applications / placement / internships ----
    applications: list[StudentApplicationSummary]
    placement_status: PlacementStatus
    internship_status: InternshipStatus

    # ---- assessments ----
    assessments_completed: int
    average_assessment_percentage: float | None
    assessments: list[StudentAssessmentSummary]

    # ---- interviews ----
    interviews: list[StudentInterviewSummary]

    # Always present -- explains what is NOT shown and why (no resume
    # storage, no GitHub/LinkedIn field, no eligibility/backlog data).
    notes: list[str]
