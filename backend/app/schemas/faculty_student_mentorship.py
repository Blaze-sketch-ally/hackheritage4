"""Pydantic schemas for Faculty <-> Student mentorship (Phase F4.2,
`faculty_student_mentorships`, 040_faculty_student_mentorships.sql).

Deliberately distinct from FacultyEngagementResponse (Industry/
Institution <-> Faculty) -- a mentorship is a separate relationship with
a different pair of participants and a different lifecycle. Never merge
the two.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.portfolio import AchievementResponse, CertificationResponse, ProjectResponse

MentorshipStatus = Literal[
    "REQUESTED", "ACCEPTED", "ACTIVE", "DECLINED", "WITHDRAWN", "COMPLETED", "ENDED"
]

# The subset of transitions a caller may ever request via the API --
# anything else is rejected by the database trigger regardless of what
# reaches this schema (see guard_faculty_student_mentorship()).
MentorshipStatusUpdate = Literal["ACCEPTED", "DECLINED", "WITHDRAWN", "ACTIVE", "COMPLETED", "ENDED"]


class FacultyStudentMentorshipResponse(BaseModel):
    id: str
    faculty_id: str
    student_id: str
    requested_by: str
    status: MentorshipStatus
    focus_area: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FacultyStudentMentorshipListResponse(BaseModel):
    mentorships: list[FacultyStudentMentorshipResponse]


class CreateMentorshipRequest(BaseModel):
    """POST body for both /faculty/mentorships (Faculty requesting a
    student) and /student/mentorships (Student requesting a faculty
    member). `target_id` is generic because which side is "self" is
    always derived from the caller's own authenticated role -- never
    client-supplied. There is no directory/browse endpoint behind this;
    the caller must already know the other party's id (out of scope for
    this phase -- see the F4.2 report's Deferred section)."""

    model_config = ConfigDict(extra="forbid")

    target_id: str
    focus_area: str | None = Field(default=None, max_length=2000)


class UpdateMentorshipStatusRequest(BaseModel):
    """PATCH .../mentorships/{id}/status body. Participant identity is
    never accepted here -- immutable, derived at creation only."""

    model_config = ConfigDict(extra="forbid")

    status: MentorshipStatusUpdate


class MentorshipNoteResponse(BaseModel):
    id: str
    mentorship_id: str
    faculty_id: str
    note: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpsertMentorshipNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=5000)


# ---- The authorized mentee data bundle (GET /faculty/mentorships/{id}/student) ----
# Assembled entirely from tables the approved visibility matrix names --
# never assessment_answers, never applications, never internship/training
# records. See 040's own header for the exact RLS policies backing this.


class MenteeAcademicProfileResponse(BaseModel):
    """Mirrors the subset of student_profiles a mentor may see -- academic
    fields only. Personal/contact fields (phone, date_of_birth, gender,
    location) are deliberately never selected here, on top of RLS, as an
    additional API-layer minimisation."""

    institution_name: str | None = None
    department: str | None = None
    degree: str | None = None
    graduation_year: int | None = None
    cgpa: float | None = None
    percentage: float | None = None
    career_goals: str | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)


class MenteeSkillResponse(BaseModel):
    skill_id: str
    proficiency_level: str
    proficiency_score: float | None = None
    is_verified: bool


class MenteeAssessmentAttemptResponse(BaseModel):
    """Results/scores only -- mirrors assessment_attempts' own columns.
    No answer text exists on this table; this schema cannot leak one."""

    id: str
    assessment_id: str
    status: str
    score: float | None = None
    total_marks: float | None = None
    percentage: float | None = None
    submitted_at: datetime | None = None


class MenteeProfileBundleResponse(BaseModel):
    mentorship_id: str
    student_id: str
    full_name: str | None = None
    email: str | None = None
    username: str | None = None
    academic_profile: MenteeAcademicProfileResponse | None = None
    skills: list[MenteeSkillResponse]
    assessment_attempts: list[MenteeAssessmentAttemptResponse]
    projects: list[ProjectResponse]
    certifications: list[CertificationResponse]
    achievements: list[AchievementResponse]


# ---- Admin oversight (admin_list_faculty_student_mentorships RPC) ----
# Deliberately narrower than FacultyStudentMentorshipResponse: no
# focus_area, and this is never joined with faculty_mentorship_notes.


class AdminMentorshipResponse(BaseModel):
    id: str
    faculty_id: str
    student_id: str
    status: MentorshipStatus
    requested_by: str
    start_date: date | None = None
    end_date: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminMentorshipListResponse(BaseModel):
    mentorships: list[AdminMentorshipResponse]
