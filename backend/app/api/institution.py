"""API routes for Institution.

The institution's own profile (GET/PUT /institution/profile), the
dashboard overview (GET /institution/overview), and the Student Directory
(GET /institution/students, GET /institution/students/{id}). The bilateral
student-linking workflow (resolve/create/approve/reject/unlink) lives in
its own router, app.api.institution_link_requests -- same split as
industry.py (own profile) vs industry_collaborations.py (bilateral
relationship).

Every route is guarded by require_institution() and run through
build_user_client(current_user.access_token) -- never get_supabase() /
service_role -- so every underlying read/write is RLS-scoped:
student-level dashboard data is limited to students linked to this
institution (student_profiles.institution_id = current_user.id),
enforced by database/migrations/037_institution_tenancy.sql, not by this
route. `institution_id` is always current_user.id; it is never read from
the request.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.dependencies import CurrentUser, require_institution
from app.core.security import build_user_client
from app.schemas.institution import (
    InstitutionOverviewResponse,
    InstitutionProfileResponse,
    InstitutionProfileUpdate,
)
from app.schemas.institution_analytics import InstitutionAnalyticsResponse
from app.schemas.institution_department import (
    AssignDepartmentRequest,
    DepartmentCreate,
    DepartmentDetailResponse,
    DepartmentListResponse,
    DepartmentSummary,
    DepartmentUpdate,
)
from app.schemas.institution_event import (
    EventDetail,
    EventListResponse,
    EventOverviewResponse,
    InstitutionEventCreate,
    InstitutionEventStatusUpdate,
    InstitutionEventUpdate,
)
from app.schemas.institution_industry import (
    CompanyOptionListResponse,
    IndustryPartnerDetail,
    IndustryPartnerListResponse,
    IndustryPartnerMetricsResponse,
    IndustryPartnerRelationshipCreate,
    IndustryPartnerRelationshipResponse,
    IndustryPartnerRelationshipUpdate,
)
from app.schemas.institution_industry_connection import (
    IndustryConnectionCreate,
    IndustryConnectionListResponse,
    IndustryConnectionRow,
    IndustryConnectionUpdate,
)
from app.schemas.institution_internship import (
    AvailableInternshipListResponse,
    InstitutionInternshipDetail,
    InstitutionInternshipListResponse,
    InstitutionInternshipOverviewResponse,
    InternshipAssociationResponse,
)
from app.schemas.institution_placement import (
    AvailableJobListResponse,
    DriveApplicantsResponse,
    DriveStudentsResponse,
    PlacementDriveCreate,
    PlacementDriveDetail,
    PlacementDriveListResponse,
    PlacementDriveStatusUpdate,
    PlacementDriveUpdate,
    PlacementOverviewResponse,
)
from app.schemas.institution_reports import InstitutionReportResponse, ReportType
from app.schemas.institution_skill_gap import SkillGapDetailResponse, SkillGapListResponse
from app.schemas.institution_student import (
    InternshipStatus,
    PlacementStatus,
    StudentDetailResponse,
    StudentListResponse,
)
from app.services import (
    institution_analytics_service,
    institution_department_service,
    institution_event_service,
    institution_industry_connection_service,
    institution_industry_service,
    institution_internship_service,
    institution_placement_service,
    institution_reports_service,
    institution_service,
    institution_skill_gap_service,
    institution_student_service,
)
from app.services.institution_placement_service import CrossInstitutionEligibilityError

router = APIRouter(prefix="/institution", tags=["institution"])

_SORT_FIELDS = ("name", "cgpa", "department", "placement_status")


@router.get("/profile", response_model=InstitutionProfileResponse)
def get_institution_profile(
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionProfileResponse:
    """The caller's own institution profile.

    `institution_profiles` is a lazy 1:1 row -- a brand-new INSTITUTION
    account has none yet. That is not a 404: this returns 200 with `id`
    set and every other field null, so the frontend can render a clean
    "start your institution profile" state.
    """
    client = build_user_client(current_user.access_token)
    try:
        row = institution_service.get_profile(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your institution profile.",
        ) from exc

    if row is None:
        return InstitutionProfileResponse(id=current_user.id)
    return InstitutionProfileResponse(**row)


@router.put("/profile", response_model=InstitutionProfileResponse)
def update_institution_profile(
    body: InstitutionProfileUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionProfileResponse:
    """Create (first save) or replace the caller's own institution
    profile. The row id is forced to current_user.id inside the service;
    nothing from `body` can change which row is written. RLS re-checks
    ownership and the INSTITUTION role on both the INSERT and UPDATE
    paths."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_service.upsert_profile(client, current_user.id, body.model_dump())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save your institution profile.",
        ) from exc

    return InstitutionProfileResponse(**row)


@router.get("/overview", response_model=InstitutionOverviewResponse)
def get_institution_overview(
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionOverviewResponse:
    """Every dashboard metric for the authenticated Institution account in
    a single response. An institution with no linked students gets an
    honest all-zeros student section, not an error and not fabricated
    data."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_service.compute_institution_overview(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load the institution overview. Please try again.",
        ) from exc
    return InstitutionOverviewResponse(**data)


@router.get("/analytics", response_model=InstitutionAnalyticsResponse)
def get_institution_analytics(
    department_id: str | None = Query(default=None, description="'unassigned' matches students with no department."),
    batch: int | None = Query(default=None, description="student_profiles.graduation_year"),
    date_from: str | None = Query(default=None, description="ISO date (YYYY-MM-DD), inclusive."),
    date_to: str | None = Query(default=None, description="ISO date (YYYY-MM-DD), inclusive."),
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionAnalyticsResponse:
    """The Institution Analytics workspace: every metric described in
    Phase 6, aggregated server-side from the caller's own linked students
    and their real application/skill/assessment/interview/placement-drive
    records. See institution_analytics_service's own docstring for
    exactly which existing calculations this reuses (never re-derives)
    and which sections respect the department/batch/date filters."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_analytics_service.compute_institution_analytics(
            client,
            current_user.id,
            department_id=department_id,
            batch=batch,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load analytics. Please try again.",
        ) from exc
    return InstitutionAnalyticsResponse(**data)


@router.get("/students", response_model=StudentListResponse)
def list_institution_students(
    search: str | None = Query(default=None, description="Matches name or username."),
    department: str | None = Query(default=None),
    batch: int | None = Query(default=None, description="student_profiles.graduation_year"),
    cgpa_min: float | None = Query(default=None, ge=0, le=10),
    cgpa_max: float | None = Query(default=None, ge=0, le=10),
    placement_status: PlacementStatus | None = Query(default=None),
    internship_status: InternshipStatus | None = Query(default=None),
    skill: str | None = Query(default=None, description="Substring match on skill name."),
    sort_by: str = Query(default="name"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_institution),
) -> StudentListResponse:
    """The Student Directory: every student LINKED to the authenticated
    institution (student_profiles.institution_id = current_user.id), never
    a client-supplied institution id. Filters/sort/pagination are applied
    server-side -- see institution_student_service's own docstring for
    why this is a full-roster-then-filter design, not a DB-side paginated
    query."""
    if sort_by not in _SORT_FIELDS:
        sort_by = "name"
    client = build_user_client(current_user.access_token)
    try:
        data = institution_student_service.list_students(
            client,
            current_user.id,
            search=search,
            department=department,
            batch=batch,
            cgpa_min=cgpa_min,
            cgpa_max=cgpa_max,
            placement_status=placement_status,
            internship_status=internship_status,
            skill=skill,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your students. Please try again.",
        ) from exc
    return StudentListResponse(**data)


@router.get("/students/{student_id}", response_model=StudentDetailResponse)
def get_institution_student(
    student_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> StudentDetailResponse:
    """One student LINKED to the authenticated institution. A student id
    that doesn't exist, or that belongs to a different institution (or no
    institution at all), is a 404 either way -- indistinguishable, so no
    cross-institution existence is ever leaked."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_student_service.get_student_detail(client, current_user.id, str(student_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this student. Please try again.",
        ) from exc
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return StudentDetailResponse(**data)


# ============================================================
# Departments (database/migrations/040_institution_departments.sql)
# ============================================================


def _department_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")


@router.get("/departments", response_model=DepartmentListResponse)
def list_institution_departments(
    current_user: CurrentUser = Depends(require_institution),
) -> DepartmentListResponse:
    """Every department belonging to the authenticated institution (any
    status -- deactivated departments are never hidden, since existing
    student assignments and historical placement data must remain
    visible). Search/status filtering happens client-side over this
    small list -- see Part 12 of this phase's own task ("keep this
    simple")."""
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_department_service.list_departments(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your departments. Please try again.",
        ) from exc
    return DepartmentListResponse(departments=[DepartmentSummary(**r) for r in rows])


@router.get("/departments/{department_id}", response_model=DepartmentDetailResponse)
def get_institution_department(
    department_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> DepartmentDetailResponse:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_department_service.get_department(client, current_user.id, str(department_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this department. Please try again.",
        ) from exc
    if row is None:
        raise _department_not_found()
    return DepartmentDetailResponse(**row)


@router.post("/departments", response_model=DepartmentDetailResponse, status_code=status.HTTP_201_CREATED)
def create_institution_department(
    body: DepartmentCreate,
    current_user: CurrentUser = Depends(require_institution),
) -> DepartmentDetailResponse:
    """`institution_id` is always current_user.id -- never accepted from
    the request body (DepartmentCreate has no such field, and
    extra="forbid" rejects any attempt to smuggle one in)."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_department_service.create_department(client, current_user.id, body.model_dump())
    except institution_department_service.DuplicateDepartmentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create the department. Please try again.",
        ) from exc
    return DepartmentDetailResponse(**row)


@router.put("/departments/{department_id}", response_model=DepartmentDetailResponse)
def update_institution_department(
    department_id: UUID,
    body: DepartmentUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> DepartmentDetailResponse:
    """Partial update -- only fields the client actually sent are
    changed (`exclude_unset=True`). `is_active=false` is how a department
    is deactivated; there is no delete endpoint (Part 10 of this phase:
    prefer soft deactivation, never destroy historical student/placement
    data)."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_department_service.update_department(
            client, current_user.id, str(department_id), body.model_dump(exclude_unset=True)
        )
    except institution_department_service.DuplicateDepartmentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the department. Please try again.",
        ) from exc
    if row is None:
        raise _department_not_found()
    return DepartmentDetailResponse(**row)


@router.patch("/students/{student_id}/department", response_model=StudentDetailResponse)
def assign_student_department(
    student_id: UUID,
    body: AssignDepartmentRequest,
    current_user: CurrentUser = Depends(require_institution),
) -> StudentDetailResponse:
    """Assigns (or, when department_id is null, clears) the department
    for one of the institution's own linked students. Both the student
    and the department must belong to the calling institution -- enforced
    server-side (institution_department_service.assign_student_department),
    never trusted from the frontend's own dropdown contents. Returns the
    student's full detail payload so the frontend can refresh in place."""
    client = build_user_client(current_user.access_token)
    try:
        institution_department_service.assign_student_department(
            client, current_user.id, str(student_id), body.department_id
        )
        data = institution_student_service.get_student_detail(client, current_user.id, str(student_id))
    except institution_department_service.CrossInstitutionAssignmentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update this student's department. Please try again.",
        ) from exc
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return StudentDetailResponse(**data)


# ============================================================
# Skill Gap Analysis (database/migrations/048_institution_skill_gap.sql)
#
# APPLICATION-scoped, not an institution-wide dashboard: for one of the
# institution's own linked students' applications, how their recorded
# skills compare to what the internship/job actually requires. Reuses the
# existing `applications` / `internship_skills` / `job_skills` /
# `student_skills` tables and the exact same deterministic
# match_service.compute_match Industry's own skill match already uses --
# see institution_skill_gap_service.py's own docstring.
# ============================================================


def _skill_gap_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")


@router.get("/skill-gaps", response_model=SkillGapListResponse)
def list_skill_gap_applications(
    search: str | None = Query(default=None, description="Matches student, opportunity, or company."),
    opportunity_type: str | None = Query(default=None, description="INTERNSHIP or JOB."),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_institution),
) -> SkillGapListResponse:
    """Every application by one of the institution's own linked students --
    from any application flow (marketplace, curated internship, placement
    drive) -- with its deterministic skill match already computed."""
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_skill_gap_service.list_skill_gap_applications(
            client,
            current_user.id,
            search=search,
            opportunity_type=opportunity_type,
            status_filter=status_filter,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load skill gap data. Please try again.",
        ) from exc
    return SkillGapListResponse(applications=rows)


@router.get("/skill-gaps/{application_id}", response_model=SkillGapDetailResponse)
def get_skill_gap_detail(
    application_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> SkillGapDetailResponse:
    """The full skill-gap breakdown for one application. An application
    id that doesn't exist, or that belongs to a different institution's
    student (or a student not linked to any institution), is a 404 either
    way -- indistinguishable, so no cross-institution existence is ever
    leaked."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_skill_gap_service.get_skill_gap_detail(
            client, current_user.id, str(application_id)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this application's skill gap. Please try again.",
        ) from exc
    if data is None:
        raise _skill_gap_not_found()
    return SkillGapDetailResponse(**data)


# ============================================================
# Placement Drives (database/migrations/041_institution_placement_drives.sql)
#
# Coordinates EXISTING jobs/applications/interviews -- never a parallel
# recruitment system. Industry still owns the job and the hiring
# decision; the Institution only coordinates its own students'
# participation. See institution_placement_service.py's own docstring.
# ============================================================


def _drive_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placement drive not found.")


@router.get("/placements/available-jobs", response_model=AvailableJobListResponse)
def list_available_jobs_for_drive(
    search: str | None = Query(default=None, description="Matches job title or company name."),
    current_user: CurrentUser = Depends(require_institution),
) -> AvailableJobListResponse:
    """Currently PUBLISHED jobs -- platform-wide, not owned by this
    institution -- for the create-drive job picker. Never a duplicate job
    listing system: this is a thin read over the same `jobs` table
    Industry and Student already use."""
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_placement_service.list_available_jobs(client, search=search)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load available jobs. Please try again.",
        ) from exc
    return AvailableJobListResponse(jobs=rows)


@router.get("/placements/overview", response_model=PlacementOverviewResponse)
def get_placement_overview(
    current_user: CurrentUser = Depends(require_institution),
) -> PlacementOverviewResponse:
    """Drive-scoped placement analytics for the authenticated institution
    -- see PlacementOverviewResponse's own docstring for how this relates
    to (and never contradicts) the Institution Dashboard's institution-
    wide numbers."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_placement_service.get_placement_overview(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load placement analytics. Please try again.",
        ) from exc
    return PlacementOverviewResponse(**data)


@router.get("/placements", response_model=PlacementDriveListResponse)
def list_placement_drives(
    search: str | None = Query(default=None, description="Matches drive title, job title, or company."),
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: CurrentUser = Depends(require_institution),
) -> PlacementDriveListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_placement_service.list_drives(
            client, current_user.id, search=search, status=status_filter
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your placement drives. Please try again.",
        ) from exc
    return PlacementDriveListResponse(drives=rows)


@router.post("/placements", response_model=PlacementDriveDetail, status_code=status.HTTP_201_CREATED)
def create_placement_drive(
    body: PlacementDriveCreate,
    current_user: CurrentUser = Depends(require_institution),
) -> PlacementDriveDetail:
    """`institution_id` is always current_user.id -- never accepted from
    the request body. The referenced job must be PUBLISHED right now
    (Part 27) -- a CLOSED/ARCHIVED/DRAFT job cannot become a new drive,
    though an existing drive survives its job later closing."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_placement_service.create_drive(
            client, current_user.id, body.model_dump(mode="json")
        )
    except institution_placement_service.JobNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except institution_placement_service.CrossInstitutionEligibilityError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create the placement drive. Please try again.",
        ) from exc
    return PlacementDriveDetail(**row)


@router.get("/placements/{drive_id}", response_model=PlacementDriveDetail)
def get_placement_drive(
    drive_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> PlacementDriveDetail:
    """Institution A requesting Institution B's drive gets the same 404
    as a nonexistent id -- indistinguishable, since the service's own
    institution_id-scoped lookup returns None either way."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_placement_service.get_drive(client, current_user.id, str(drive_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this placement drive. Please try again.",
        ) from exc
    if row is None:
        raise _drive_not_found()
    return PlacementDriveDetail(**row)


@router.put("/placements/{drive_id}", response_model=PlacementDriveDetail)
def update_placement_drive(
    drive_id: UUID,
    body: PlacementDriveUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> PlacementDriveDetail:
    """Partial update -- only fields the client actually sent are
    changed. `job_id` and `status` are never editable here -- see
    PlacementDriveUpdate's own docstring."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_placement_service.update_drive(
            client, current_user.id, str(drive_id), body.model_dump(mode="json", exclude_unset=True)
        )
    except institution_placement_service.CrossInstitutionEligibilityError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the placement drive. Please try again.",
        ) from exc
    if row is None:
        raise _drive_not_found()
    return PlacementDriveDetail(**row)


@router.patch("/placements/{drive_id}/status", response_model=PlacementDriveDetail)
def update_placement_drive_status(
    drive_id: UUID,
    body: PlacementDriveStatusUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> PlacementDriveDetail:
    """Every lifecycle transition passes through this one validated code
    path (institution_placement_service._VALID_TRANSITIONS) -- never a
    raw status write from the frontend."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_placement_service.update_drive_status(
            client, current_user.id, str(drive_id), body.status
        )
    except institution_placement_service.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the drive status. Please try again.",
        ) from exc
    if row is None:
        raise _drive_not_found()
    return PlacementDriveDetail(**row)


@router.get("/placements/{drive_id}/students", response_model=DriveStudentsResponse)
def get_placement_drive_students(
    drive_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> DriveStudentsResponse:
    """Every student LINKED to the authenticated institution, with a
    fully explained eligibility verdict against this drive's criteria --
    cross-institution students can never appear (Part 8)."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_placement_service.get_drive_students(client, current_user.id, str(drive_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load eligible students. Please try again.",
        ) from exc
    if data is None:
        raise _drive_not_found()
    return DriveStudentsResponse(**data)


@router.get("/placements/{drive_id}/applications", response_model=DriveApplicantsResponse)
def get_placement_drive_applications(
    drive_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> DriveApplicantsResponse:
    """Institution students who actually applied to this drive's job,
    with their real application status and (if any) interview -- never a
    fabricated "assessment" stage that doesn't exist in the schema."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_placement_service.get_drive_applicants(client, current_user.id, str(drive_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load applicants. Please try again.",
        ) from exc
    if data is None:
        raise _drive_not_found()
    return DriveApplicantsResponse(**data)


# ============================================================
# Institution-Curated Internships (database/migrations/
# 046_institution_internships.sql)
#
# The canonical internship identity/content remains `internships`
# (018_internships.sql) -- Industry still owns the posting and the
# hiring decision; the Institution only explicitly SELECTS which
# internships it curates (institution_internships), then monitors
# applications/selections for those, exactly like every other
# "coordinate, don't duplicate" institution module. See
# institution_internship_service's own docstring for the full curation
# workflow and the participation estimate's honesty boundaries.
# ============================================================


def _internship_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")


@router.get("/internships/overview", response_model=InstitutionInternshipOverviewResponse)
def get_institution_internship_overview(
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionInternshipOverviewResponse:
    """KPIs, department/company breakdowns, mode/status distributions and
    stipend statistics over this institution's CURATED internships only.
    Placed before /internships/{internship_id} so "overview" is never
    parsed as an id."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_internship_service.compute_internship_overview(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load internship analytics. Please try again.",
        ) from exc
    return InstitutionInternshipOverviewResponse(**data)


@router.get("/internships/available", response_model=AvailableInternshipListResponse)
def list_available_internships(
    search: str | None = Query(default=None, description="Matches internship title or company name."),
    mode: str | None = Query(default=None, description="ONSITE, REMOTE or HYBRID."),
    company_id: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_institution),
) -> AvailableInternshipListResponse:
    """Currently-PUBLISHED internships this institution has NOT yet
    curated -- the browse source for "Add to Institution". Placed before
    /internships/{internship_id} so "available" is never parsed as an id."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_internship_service.list_available_internships(
            client, current_user.id, search=search, mode=mode, company_id=company_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load available internships. Please try again.",
        ) from exc
    return AvailableInternshipListResponse(**data)


@router.get("/internships", response_model=InstitutionInternshipListResponse)
def list_institution_internships(
    search: str | None = Query(default=None, description="Matches internship title or company name."),
    status_filter: str | None = Query(default=None, alias="status"),
    mode: str | None = Query(default=None, description="ONSITE, REMOTE or HYBRID."),
    company_id: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionInternshipListResponse:
    """This institution's own CURATED internship list -- the module's
    default view. Never every platform internship; never another
    institution's curation."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_internship_service.list_internships(
            client, current_user.id, search=search, status=status_filter, mode=mode, company_id=company_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load internships. Please try again.",
        ) from exc
    return InstitutionInternshipListResponse(**data)


@router.post(
    "/internships/{internship_id}/select",
    response_model=InternshipAssociationResponse,
    status_code=status.HTTP_201_CREATED,
)
def select_institution_internship(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> InternshipAssociationResponse:
    """Adds a real, currently-PUBLISHED internship to this institution's
    curated list. `institution_id` is always current_user.id -- never
    accepted from the request. The database's own
    validate_internship_selection trigger (046) is the authoritative
    backstop even if the service-layer visibility check is somehow
    bypassed."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_internship_service.select_internship(client, current_user.id, str(internship_id))
    except institution_internship_service.InternshipNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except institution_internship_service.DuplicateAssociationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not add this internship to your institution. Please try again.",
        ) from exc
    return InternshipAssociationResponse(**row)


@router.patch("/internships/{internship_id}/association", response_model=InternshipAssociationResponse)
def update_institution_internship_association(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> InternshipAssociationResponse:
    """Removes (soft-deactivates) this internship from the institution's
    curated list -- there is no delete endpoint, matching this project's
    deactivate-don't-delete convention. The canonical internship, and any
    other institution's own curation of it, are untouched."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_internship_service.remove_internship(client, current_user.id, str(internship_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update this internship. Please try again.",
        ) from exc
    if row is None:
        raise _internship_not_found()
    return InternshipAssociationResponse(**row)


@router.get("/internships/{internship_id}", response_model=InstitutionInternshipDetail)
def get_institution_internship(
    internship_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionInternshipDetail:
    """One curated internship's full detail plus institution-scoped
    applicant list with a participation estimate. An internship this
    institution never curated is indistinguishable from one that doesn't
    exist."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_internship_service.get_internship_detail(client, current_user.id, str(internship_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this internship. Please try again.",
        ) from exc
    if data is None:
        raise _internship_not_found()
    return InstitutionInternshipDetail(**data)


# ============================================================
# Industry Partners (Phase 8; database/migrations/
# 043_institution_industry_partners.sql)
#
# The canonical company identity is the EXISTING industry_profiles table
# -- no second company entity. institution_industry_partners is a small,
# institution-private relationship TAG on top of it; every activity
# number (jobs/internships/drives/students selected) is computed live
# from the existing applications/placement_drives/industry_collaborations
# tables. See institution_industry_service's own docstring for exactly
# what is reused.
# ============================================================


def _partner_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Industry partner not found.")


@router.get("/industry-partners/metrics", response_model=IndustryPartnerMetricsResponse)
def get_industry_partner_metrics(
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryPartnerMetricsResponse:
    """Placed before /industry-partners/{industry_id} so "metrics" is
    never parsed as a company id."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_industry_service.compute_metrics(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load industry partner metrics. Please try again.",
        ) from exc
    return IndustryPartnerMetricsResponse(**data)


@router.get("/industry-partners/companies", response_model=CompanyOptionListResponse)
def search_industry_partner_companies(
    search: str | None = Query(default=None, description="Matches company name."),
    current_user: CurrentUser = Depends(require_institution),
) -> CompanyOptionListResponse:
    """The add-partner form's company picker -- real companies only
    (industry_profiles), never a free-text name. Placed before
    /industry-partners/{industry_id} so "companies" is never parsed as a
    company id."""
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_industry_service.search_companies(client, search=search)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not search companies. Please try again.",
        ) from exc
    return CompanyOptionListResponse(companies=rows)


@router.get("/industry-partners", response_model=IndustryPartnerListResponse)
def list_industry_partners(
    search: str | None = Query(default=None, description="Matches company name."),
    relationship_type: str | None = Query(default=None),
    relationship_status: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryPartnerListResponse:
    """Every company with either an explicit relationship tag or real
    institution-scoped recruitment/internship/placement-drive/
    collaboration activity -- never another institution's."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_industry_service.list_partners(
            client,
            current_user.id,
            search=search,
            relationship_type=relationship_type,
            relationship_status=relationship_status,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load industry partners. Please try again.",
        ) from exc
    return IndustryPartnerListResponse(**data)


@router.post(
    "/industry-partners", response_model=IndustryPartnerRelationshipResponse, status_code=status.HTTP_201_CREATED
)
def create_industry_partner_relationship(
    body: IndustryPartnerRelationshipCreate,
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryPartnerRelationshipResponse:
    """`institution_id` is always current_user.id -- never accepted from
    the request body. `industry_id` must be a real company; the
    database's own validate_partner_industry_id trigger (043) is the
    authoritative backstop even if this check is somehow bypassed."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_industry_service.create_relationship(client, current_user.id, body.model_dump())
    except institution_industry_service.IndustryProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except institution_industry_service.DuplicateRelationshipError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save this industry partner. Please try again.",
        ) from exc
    return IndustryPartnerRelationshipResponse(**row)


@router.get("/industry-partners/{industry_id}", response_model=IndustryPartnerDetail)
def get_industry_partner(
    industry_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryPartnerDetail:
    """A company outside this institution's activity/relationship union
    is indistinguishable from one that doesn't exist -- same pattern as
    every other institution detail endpoint."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_industry_service.get_partner_detail(client, current_user.id, str(industry_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this industry partner. Please try again.",
        ) from exc
    if data is None:
        raise _partner_not_found()
    return IndustryPartnerDetail(**data)


@router.patch("/industry-partners/{industry_id}/relationship", response_model=IndustryPartnerRelationshipResponse)
def update_industry_partner_relationship(
    industry_id: UUID,
    body: IndustryPartnerRelationshipUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryPartnerRelationshipResponse:
    """Partial update -- only fields the client actually sent are
    changed. Setting relationship_status='INACTIVE' is how a partner is
    "removed" -- there is no delete endpoint (matches this project's
    deactivate-don't-delete convention)."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_industry_service.update_relationship(
            client, current_user.id, str(industry_id), body.model_dump(exclude_unset=True)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update this industry partner. Please try again.",
        ) from exc
    if row is None:
        raise _partner_not_found()
    return IndustryPartnerRelationshipResponse(**row)


# ============================================================
# Industry Connections (Phase 9; database/migrations/
# 044_institution_industry_connections.sql)
#
# The bilateral collaboration PROPOSAL workflow
# (industry_collaborations, backend/app/api/industry_collaborations.py)
# is UNCHANGED by this phase -- the Institution's view of it is already
# served by the shared /api/v1/collaborations/incoming, /accept,
# /reject, and /{id} endpoints (RecipientCollaborationsView /
# lib/industry/collaborations.ts), mounted from
# frontend/app/institution/collaborations/. This section is only the new
# institution-private NAMED CONTACT tracking layer -- see
# institution_industry_connection_service's own docstring.
# ============================================================


def _connection_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Industry connection not found.")


@router.get("/industry-connections", response_model=IndustryConnectionListResponse)
def list_industry_connections(
    search: str | None = Query(default=None, description="Matches company name or contact name."),
    contact_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    industry_id: str | None = Query(default=None, description="Scope to one company (Company Detail integration)."),
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryConnectionListResponse:
    client = build_user_client(current_user.access_token)
    try:
        rows = institution_industry_connection_service.list_connections(
            client,
            current_user.id,
            search=search,
            contact_type=contact_type,
            is_active=is_active,
            industry_id=industry_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load your industry connections. Please try again.",
        ) from exc
    return IndustryConnectionListResponse(connections=rows)


@router.post(
    "/industry-connections", response_model=IndustryConnectionRow, status_code=status.HTTP_201_CREATED
)
def create_industry_connection(
    body: IndustryConnectionCreate,
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryConnectionRow:
    """`institution_id` is always current_user.id -- never accepted from
    the request body. `industry_id` must be a real company; the
    database's own validate_connection_industry_id trigger (044) is the
    authoritative backstop even if this check is somehow bypassed."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_industry_connection_service.create_connection(client, current_user.id, body.model_dump())
    except institution_industry_connection_service.IndustryProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save this industry connection. Please try again.",
        ) from exc
    return IndustryConnectionRow(**row)


@router.get("/industry-connections/{connection_id}", response_model=IndustryConnectionRow)
def get_industry_connection(
    connection_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryConnectionRow:
    client = build_user_client(current_user.access_token)
    try:
        row = institution_industry_connection_service.get_connection(client, current_user.id, str(connection_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this industry connection. Please try again.",
        ) from exc
    if row is None:
        raise _connection_not_found()
    return IndustryConnectionRow(**row)


@router.patch("/industry-connections/{connection_id}", response_model=IndustryConnectionRow)
def update_industry_connection(
    connection_id: UUID,
    body: IndustryConnectionUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> IndustryConnectionRow:
    """Partial update -- only fields the client actually sent are
    changed. Setting is_active=false is how a connection is "removed" --
    there is no delete endpoint."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_industry_connection_service.update_connection(
            client, current_user.id, str(connection_id), body.model_dump(exclude_unset=True)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update this industry connection. Please try again.",
        ) from exc
    if row is None:
        raise _connection_not_found()
    return IndustryConnectionRow(**row)


# ============================================================
# Events (Phase 10; database/migrations/045_institution_events.sql)
#
# `industry_workshops` remains the ONLY entity a company uses to post its
# own event -- untouched by this section. `institution_events` is
# additive, for sessions the INSTITUTION itself organizes. See
# institution_event_service's own docstring for the directory-union rule
# (institution's own events + platform-wide PUBLISHED industry_workshops)
# and why no registration/attendance field exists anywhere here.
# ============================================================


def _event_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")


@router.get("/events/overview", response_model=EventOverviewResponse)
def get_institution_event_overview(
    current_user: CurrentUser = Depends(require_institution),
) -> EventOverviewResponse:
    """Placed before /events/{event_id} so "overview" is never parsed as
    an event id."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_event_service.compute_event_overview(client, current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load event analytics. Please try again.",
        ) from exc
    return EventOverviewResponse(**data)


@router.get("/events", response_model=EventListResponse)
def list_institution_events(
    search: str | None = Query(default=None, description="Matches event title or company name."),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    mode: str | None = Query(default=None, description="ONSITE, REMOTE or HYBRID."),
    industry_id: str | None = Query(default=None, description="Scope to one company (Company Detail integration)."),
    current_user: CurrentUser = Depends(require_institution),
) -> EventListResponse:
    """Every event the institution organizes (any status, including
    drafts) plus every currently-PUBLISHED Industry workshop
    (platform-wide, read-only) -- never another institution's own event."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_event_service.list_events(
            client,
            current_user.id,
            search=search,
            event_type=event_type,
            status=status_filter,
            mode=mode,
            industry_id=industry_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load events. Please try again.",
        ) from exc
    return EventListResponse(**data)


@router.post("/events", response_model=EventDetail, status_code=status.HTTP_201_CREATED)
def create_institution_event(
    body: InstitutionEventCreate,
    current_user: CurrentUser = Depends(require_institution),
) -> EventDetail:
    """`institution_id` is always current_user.id -- never accepted from
    the request body. Always created as DRAFT."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_event_service.create_event(client, current_user.id, body.model_dump(mode="json"))
    except institution_event_service.IndustryProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except CrossInstitutionEligibilityError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create the event. Please try again.",
        ) from exc
    return EventDetail(**row)


@router.get("/events/{event_id}", response_model=EventDetail)
def get_institution_event(
    event_id: UUID,
    current_user: CurrentUser = Depends(require_institution),
) -> EventDetail:
    """An institution-organized event outside the caller's own institution,
    or a non-published/nonexistent workshop, is a 404 either way."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_event_service.get_event_detail(client, current_user.id, str(event_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load this event. Please try again.",
        ) from exc
    if row is None:
        raise _event_not_found()
    return EventDetail(**row)


@router.put("/events/{event_id}", response_model=EventDetail)
def update_institution_event(
    event_id: UUID,
    body: InstitutionEventUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> EventDetail:
    """Partial update -- only fields the client actually sent are
    changed. Only applies to an institution-organized event (never a
    platform-wide Industry workshop, which has no institution write path
    at all -- get_event_detail returning a workshop row here is simply
    treated as "not this institution's event to edit", 404)."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_event_service.update_event(
            client, current_user.id, str(event_id), body.model_dump(mode="json", exclude_unset=True)
        )
    except institution_event_service.IndustryProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except CrossInstitutionEligibilityError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the event. Please try again.",
        ) from exc
    if row is None:
        raise _event_not_found()
    return EventDetail(**row)


@router.patch("/events/{event_id}/status", response_model=EventDetail)
def update_institution_event_status(
    event_id: UUID,
    body: InstitutionEventStatusUpdate,
    current_user: CurrentUser = Depends(require_institution),
) -> EventDetail:
    """Every lifecycle transition passes through this one validated code
    path -- never a raw status write from the frontend."""
    client = build_user_client(current_user.access_token)
    try:
        row = institution_event_service.update_event_status(client, current_user.id, str(event_id), body.status)
    except institution_event_service.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the event status. Please try again.",
        ) from exc
    if row is None:
        raise _event_not_found()
    return EventDetail(**row)


# ============================================================
# Reports (Phase 11) -- NOT a second Analytics module. Every report
# reshapes the output of an EXISTING institution service; see
# institution_reports_service's own docstring for exactly which function
# backs which report. No new table, no new placement/company/department
# definition, no CSV/PDF library (none exists anywhere in this repo).
# ============================================================


@router.get("/reports", response_model=InstitutionReportResponse)
def get_institution_report(
    report_type: ReportType = Query(...),
    department_id: str | None = Query(default=None),
    batch: int | None = Query(default=None),
    company_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    event_type: str | None = Query(default=None),
    collaboration_status: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="ISO date (YYYY-MM-DD), inclusive."),
    date_to: str | None = Query(default=None, description="ISO date (YYYY-MM-DD), inclusive."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    current_user: CurrentUser = Depends(require_institution),
) -> InstitutionReportResponse:
    """One endpoint, one dataset per request -- `report_type` selects
    which of the seven report shapes is populated. `institution_id` is
    always current_user.id; every underlying read is the same
    RLS-scoped, institution-owned query the corresponding module already
    uses, so cross-institution data is excluded/404 exactly as it is
    everywhere else in this project -- never a service_role bypass."""
    client = build_user_client(current_user.access_token)
    try:
        data = institution_reports_service.generate_report(
            client,
            current_user.id,
            report_type=report_type,
            department_id=department_id,
            batch=batch,
            company_id=company_id,
            status=status_filter,
            event_type=event_type,
            collaboration_status=collaboration_status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate this report. Please try again.",
        ) from exc
    return InstitutionReportResponse(**data)
