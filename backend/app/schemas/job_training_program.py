"""Pydantic schemas for INDUSTRY Job Training program authoring
(database/migrations/052_job_training.sql).

PHASE J2 scope: an industry account authors exactly one job_program for
one of its JOB postings -- program metadata, ordered modules, learning
items, program skills, and gradable assignments -- and publishes /
unpublishes it. The student-facing consumption of a PUBLISHED program is
a LATER phase and has no schema here.

J2 NEVER touches job_training_enrollments: there is no student API, no
enrollment provisioning, no completion / certificate / progress /
notification code. Student access stays gated by
public.student_can_access_job_program (a non-revoked enrollment AND a
PUBLISHED program) -- and J2 creates no enrollments, so publishing a
program grants nobody access on its own.

Ownership is never accepted in a request: every endpoint derives the
industry from the token (require_industry -> current_user.id) and RLS
(052_job_training.sql, via public.owns_job_program + the job-ownership
predicate) is the real access-control boundary. Shape mirrors
app.schemas.internship_program (the internship-program authoring analog).
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# database/migrations/052_job_training.sql -- CHECK value lists
JobProgramStatus = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
SkillRequirement = Literal["REQUIRED", "OPTIONAL"]
JobProgramItemType = Literal["VIDEO", "PDF", "LINK", "TEXT"]
AssignmentType = Literal["ASSIGNMENT", "QUIZ", "PROJECT"]
SubmissionKind = Literal["LINK", "REPO", "FILE", "TEXT", "MIXED"]


# ============================================================
# responses
# ============================================================


class ProgramJobRef(BaseModel):
    id: str
    title: str
    status: str


class JobProgramMeta(BaseModel):
    id: str
    job_id: str
    title: str
    summary: str | None = None
    estimated_weeks: int | None = None
    status: str
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class JobProgramItemResponse(BaseModel):
    id: str
    module_id: str
    title: str
    item_type: str
    content_url: str | None = None
    content_text: str | None = None
    order_index: int
    is_published: bool


class JobProgramAssignmentResponse(BaseModel):
    id: str
    module_id: str
    program_id: str
    title: str
    description: str | None = None
    instructions: str | None = None
    assignment_type: str
    is_required: bool
    is_published: bool
    order_index: int
    due_offset_days: int | None = None
    submission_kind: str
    repo_required: bool
    live_url_expected: bool
    max_score: float | None = None
    linked_skill_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class JobProgramModuleResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    order_index: int
    is_published: bool
    items: list[JobProgramItemResponse] = []
    assignments: list[JobProgramAssignmentResponse] = []


class JobProgramSkillResponse(BaseModel):
    skill_id: str
    skill_name: str
    requirement: str  # REQUIRED | OPTIONAL


class AvailableSkill(BaseModel):
    """One of the job's recruitment skills (job_skills, 019) -- offered to
    the authoring UI as a suggestion list. It is NOT a hard limit: a Job
    Training program may also train skills outside the screening set (J1's
    job_program_skills.skill_id references the canonical `skills` catalog,
    not job_skills)."""

    skill_id: str
    skill_name: str
    required_level: str | None = None
    importance: str | None = None


class JobProgramBundle(BaseModel):
    """Everything the authoring UI needs in one payload. `program` is null
    when the industry hasn't created one yet (the job is still resolvable
    and `available_skills` is still populated)."""

    job: ProgramJobRef
    program: JobProgramMeta | None = None
    modules: list[JobProgramModuleResponse] = []
    skills: list[JobProgramSkillResponse] = []
    available_skills: list[AvailableSkill] = []


# ============================================================
# request bodies (all extra="forbid")
# ============================================================


class JobProgramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    estimated_weeks: int | None = Field(default=None, ge=1, le=52)


class JobProgramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    estimated_weeks: int | None = Field(default=None, ge=1, le=52)


class JobProgramModuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    is_published: bool = True


class JobProgramModuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    is_published: bool | None = None


class JobProgramItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    item_type: JobProgramItemType
    content_url: str | None = Field(default=None, max_length=2000)
    content_text: str | None = Field(default=None, max_length=20000)
    is_published: bool = True


class JobProgramItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    item_type: JobProgramItemType | None = None
    content_url: str | None = Field(default=None, max_length=2000)
    content_text: str | None = Field(default=None, max_length=20000)
    is_published: bool | None = None


class ReorderRequest(BaseModel):
    """The full set of child ids in the desired order. Must contain
    exactly the current children -- no additions or omissions."""

    model_config = ConfigDict(extra="forbid")

    ordered_ids: list[UUID] = Field(min_length=1, max_length=200)


class JobProgramSkillInput(BaseModel):
    skill_id: UUID
    requirement: SkillRequirement = "REQUIRED"


class JobProgramSkillsUpdate(BaseModel):
    """Replace-set the program's skills. Every skill_id must be a real
    skill in the canonical `skills` catalog."""

    model_config = ConfigDict(extra="forbid")

    skills: list[JobProgramSkillInput] = Field(default_factory=list, max_length=50)


class JobAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    instructions: str | None = Field(default=None, max_length=20000)
    assignment_type: AssignmentType = "ASSIGNMENT"
    is_required: bool = True
    is_published: bool = True
    due_offset_days: int | None = Field(default=None, ge=0, le=3650)
    submission_kind: SubmissionKind = "LINK"
    repo_required: bool = False
    live_url_expected: bool = False
    max_score: float | None = Field(default=None, gt=0, le=10000)
    linked_skill_id: UUID | None = None


class JobAssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    instructions: str | None = Field(default=None, max_length=20000)
    assignment_type: AssignmentType | None = None
    is_required: bool | None = None
    is_published: bool | None = None
    due_offset_days: int | None = Field(default=None, ge=0, le=3650)
    submission_kind: SubmissionKind | None = None
    repo_required: bool | None = None
    live_url_expected: bool | None = None
    max_score: float | None = Field(default=None, gt=0, le=10000)
    linked_skill_id: UUID | None = None
