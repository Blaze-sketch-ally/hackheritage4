"""Pydantic schemas for the Student "My Institution" portal
(backend/app/api/student_institution.py, /student/institution...,
database/migrations/047_student_institution_visibility.sql).

PHASE 12. There is no new institution-relationship table. This module
reads the SAME entities every other part of the platform already reads:

  - `student_profiles.institution_id`         -- the verified link itself,
                                                   set ONLY by the existing
                                                   institution_link_requests
                                                   approval trigger (038)
  - `institution_profiles`                     -- institution identity
  - `departments`                              -- the student's own
                                                   department's name
  - `placement_drives`                         -- institution-run drives
  - `institution_internships` + `internships`  -- institution-curated
                                                   internships
  - `institution_events`                       -- institution-organized
                                                   events
  - `applications`                             -- the student's own
                                                   applications (unchanged
                                                   table, unchanged
                                                   opportunity_type)

"Curated" internships means exactly what it means in the Institution
module (institution_internships.status = 'ACTIVE') -- never every
PUBLISHED internship on the platform. Eligibility for a placement drive
reuses institution_placement_service.compute_eligibility verbatim --
there is no second eligibility engine here. Events carry NO
registration/attendance data because none exists anywhere in this
schema -- `is_relevant_to_me` is descriptive audience-targeting metadata
(institution_events.target_department_ids/target_batches), never a
participation record.
"""

from pydantic import BaseModel

# ---- identity ----


class StudentInstitutionIdentity(BaseModel):
    id: str
    institution_name: str | None
    institution_type: str | None
    location: str | None
    website_url: str | None


class StudentInstitutionProfile(BaseModel):
    department_id: str | None
    department: str | None
    batch: int | None
    cgpa: float | None
    verified_at: str | None
    """When the link request that connected this student was approved --
    from institution_link_requests.updated_at, not a second flag."""


# ---- KPIs ----


class StudentInstitutionKpis(BaseModel):
    placement_drives: int
    internships: int
    events: int
    active_applications: int


# ---- placement drives ----


class StudentPlacementDriveRow(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    application_deadline: str | None
    drive_date: str | None
    mode: str | None
    venue: str | None
    company_name: str | None
    job_id: str
    is_eligible: bool
    eligibility_reasons: list[str]
    already_applied: bool
    application_status: str | None


# ---- internships ----


class StudentCuratedInternshipRow(BaseModel):
    id: str
    title: str
    description: str | None
    company_name: str | None
    work_mode: str | None
    duration_months: int | None
    stipend_amount: float | None
    stipend_currency: str | None
    application_deadline: str | None
    start_date: str | None
    eligibility_criteria: str | None
    already_applied: bool
    application_status: str | None


# ---- events ----


class StudentInstitutionEventRow(BaseModel):
    id: str
    title: str
    description: str | None
    event_type: str
    mode: str | None
    venue: str | None
    start_at: str | None
    end_at: str | None
    company_name: str | None
    is_relevant_to_me: bool
    """True when the event targets no specific department/batch (open to
    everyone) or explicitly targets this student's own department/batch.
    Descriptive only -- there is no registration/attendance record."""


# ---- activity ----


class StudentActivityItem(BaseModel):
    type: str
    """One of: INSTITUTION_VERIFIED, INTERNSHIP_APPLIED, PLACEMENT_APPLIED, SELECTED."""
    label: str
    occurred_at: str


# ---- envelope ----


class StudentInstitutionResponse(BaseModel):
    linked: bool
    """False when student_profiles.institution_id is currently null --
    every section below is then empty, never fabricated."""
    institution: StudentInstitutionIdentity | None
    profile: StudentInstitutionProfile | None
    kpis: StudentInstitutionKpis
    placement_drives: list[StudentPlacementDriveRow]
    internships: list[StudentCuratedInternshipRow]
    events: list[StudentInstitutionEventRow]
    activity: list[StudentActivityItem]

    curation_note: str
    eligibility_note: str
    registration_note: str
