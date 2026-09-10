"""Pydantic schemas for the Institution Departments module
(backend/app/api/institution.py, /institution/departments...).

Field names match database/migrations/040_institution_departments.sql
exactly. Student/placement counts reuse the EXACT SAME
`_placement_buckets` computation as the Institution Dashboard and Student
Directory (imported from institution_service in
institution_department_service.py) -- this schema never defines a second
notion of "placed".
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _blank_to_none(data: object) -> object:
    if not isinstance(data, dict):
        return data
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        cleaned[key] = value
    return cleaned


class DepartmentCreate(BaseModel):
    """POST /api/v1/institution/departments. `institution_id` is never
    accepted here -- always the authenticated caller."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        return _blank_to_none(data)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Department name cannot be blank.")
        return value


class DepartmentUpdate(BaseModel):
    """PUT /api/v1/institution/departments/{id}. Partial: only fields
    actually sent are changed. `is_active` is how a department is
    deactivated/reactivated -- there is no delete endpoint."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data: object) -> object:
        # is_active is a bool, not a string -- _blank_to_none only
        # touches str values, so this is safe to share.
        return _blank_to_none(data)


class DepartmentSummary(BaseModel):
    """One row in the department list, or the base of the detail
    response. Every count is scoped to students LINKED to this
    institution (student_profiles.institution_id) AND assigned to this
    department (student_profiles.department_id) -- never platform-wide,
    never another institution's students."""

    id: str
    name: str
    code: str | None
    description: str | None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None

    student_count: int
    placed_count: int
    unplaced_count: int
    no_applications_count: int
    # None when student_count == 0 -- never a fabricated 0%.
    placement_rate: float | None
    internship_selected_count: int


class DepartmentListResponse(BaseModel):
    departments: list[DepartmentSummary]


class DepartmentDetailResponse(DepartmentSummary):
    pass


class AssignDepartmentRequest(BaseModel):
    """PATCH /api/v1/institution/students/{student_id}/department.
    `department_id: null` unassigns the student (sets department_id back
    to NULL) -- a deliberate, explicit action, not an omission."""

    model_config = ConfigDict(extra="forbid")

    department_id: str | None = None
