"""Business logic for the Institution Departments module
(backend/app/api/institution.py, /institution/departments...,
database/migrations/040_institution_departments.sql).

Same shape as every other institution service module: every function
takes an already-built *user-scoped* Supabase client and RLS is the real
access-control boundary -- nothing here uses service_role. Student/
placement counts reuse `_placement_buckets` from institution_service.py
(the Dashboard's own module) -- this file never defines a second notion
of "placed", per this phase's own consistency requirement (PART 18).
"""

from supabase import Client

from app.services.institution_service import _percentage, _placement_buckets, fetch_departments

_DEPARTMENT_COLUMNS = "id, name, code, description, is_active, created_at, updated_at"


class DuplicateDepartmentError(Exception):
    """A department with the same (case-insensitive) name or code already
    exists for this institution -- matches
    departments_institution_name_lower_idx /
    departments_institution_code_lower_idx (040)."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"A department with that {field} already exists.")


class CrossInstitutionAssignmentError(Exception):
    """The department (or the student) does not belong to the calling
    institution -- Part 6/14 of this phase's own task: a student may
    never reference another institution's department."""


def _fetch_student_ids_and_department(client: Client, institution_id: str) -> list[dict]:
    resp = (
        client.table("student_profiles")
        .select("id, department_id")
        .eq("institution_id", institution_id)
        .execute()
    )
    return list(resp.data or [])


def _fetch_applications_for(client: Client, student_ids: list[str]) -> list[dict]:
    if not student_ids:
        return []
    resp = (
        client.table("applications")
        .select("id, student_id, status, opportunity_type")
        .in_("student_id", student_ids)
        .execute()
    )
    return list(resp.data or [])


def _internship_selected_ids(applications: list[dict]) -> set[str]:
    return {
        a["student_id"]
        for a in applications
        if a.get("opportunity_type") == "INTERNSHIP" and a.get("status") == "SELECTED"
    }


def _department_stats(
    department_id: str,
    students: list[dict],
    placed: set[str],
    unplaced_active: set[str],
    not_participating: set[str],
    internship_selected: set[str],
) -> dict:
    dept_student_ids = {s["id"] for s in students if s.get("department_id") == department_id}
    total = len(dept_student_ids)
    placed_count = len(dept_student_ids & placed)
    return {
        "student_count": total,
        "placed_count": placed_count,
        "unplaced_count": len(dept_student_ids & unplaced_active),
        "no_applications_count": len(dept_student_ids & not_participating),
        "placement_rate": _percentage(placed_count, total),
        "internship_selected_count": len(dept_student_ids & internship_selected),
    }


def _compute_all_stats(client: Client, institution_id: str) -> dict[str, dict]:
    """One pass over the institution's students/applications, stats for
    EVERY department at once -- avoids re-fetching per department (no
    N+1 across list_departments' rows)."""
    students = _fetch_student_ids_and_department(client, institution_id)
    student_ids = [s["id"] for s in students]
    applications = _fetch_applications_for(client, student_ids)
    placed, unplaced_active, not_participating = _placement_buckets(student_ids, applications)
    internship_selected = _internship_selected_ids(applications)

    department_ids = {s["department_id"] for s in students if s.get("department_id")}
    return {
        dept_id: _department_stats(dept_id, students, placed, unplaced_active, not_participating, internship_selected)
        for dept_id in department_ids
    }


_EMPTY_STATS = {
    "student_count": 0,
    "placed_count": 0,
    "unplaced_count": 0,
    "no_applications_count": 0,
    "placement_rate": None,
    "internship_selected_count": 0,
}


def list_departments(client: Client, institution_id: str) -> list[dict]:
    departments = fetch_departments(client, institution_id)
    stats = _compute_all_stats(client, institution_id)
    return [{**d, **stats.get(d["id"], _EMPTY_STATS)} for d in departments]


def get_department(client: Client, institution_id: str, department_id: str) -> dict | None:
    resp = (
        client.table("departments")
        .select(_DEPARTMENT_COLUMNS)
        .eq("id", department_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    row = resp.data if resp is not None else None
    if not row:
        return None
    stats = _compute_all_stats(client, institution_id)
    return {**row, **stats.get(department_id, _EMPTY_STATS)}


def _check_duplicate(
    client: Client, institution_id: str, *, name: str | None, code: str | None, exclude_id: str | None = None
) -> None:
    if name:
        query = client.table("departments").select("id").eq("institution_id", institution_id).ilike("name", name)
        if exclude_id:
            query = query.neq("id", exclude_id)
        if query.execute().data:
            raise DuplicateDepartmentError("name")
    if code:
        query = client.table("departments").select("id").eq("institution_id", institution_id).ilike("code", code)
        if exclude_id:
            query = query.neq("id", exclude_id)
        if query.execute().data:
            raise DuplicateDepartmentError("code")


def create_department(client: Client, institution_id: str, fields: dict) -> dict:
    _check_duplicate(client, institution_id, name=fields.get("name"), code=fields.get("code"))
    payload = {"institution_id": institution_id, "is_active": True, **fields}
    try:
        response = client.table("departments").insert(payload).execute()
    except Exception as exc:
        raise DuplicateDepartmentError("name or code") from exc
    new_id = response.data[0]["id"]
    row = get_department(client, institution_id, new_id)
    if row is None:
        raise RuntimeError("departments row could not be read back after create.")
    return row


def update_department(client: Client, institution_id: str, department_id: str, fields: dict) -> dict | None:
    existing = get_department(client, institution_id, department_id)
    if existing is None:
        return None

    _check_duplicate(
        client,
        institution_id,
        name=fields.get("name"),
        code=fields.get("code"),
        exclude_id=department_id,
    )
    # `name` is NOT NULL + non-blank at the database level -- a client
    # explicitly clearing it to "" (normalised to None by the schema's
    # blank-to-None validator) is dropped here rather than sent as a
    # NULL update, which the database would otherwise reject as a raw
    # constraint-violation 500 instead of a clean no-op.
    payload = {k: v for k, v in fields.items() if not (k == "name" and v is None)}
    if payload:
        try:
            (
                client.table("departments")
                .update(payload)
                .eq("id", department_id)
                .eq("institution_id", institution_id)
                .execute()
            )
        except Exception as exc:
            raise DuplicateDepartmentError("name or code") from exc

    return get_department(client, institution_id, department_id)


def assign_student_department(
    client: Client, institution_id: str, student_id: str, department_id: str | None
) -> dict:
    """Assigns (or, when department_id is None, clears) a linked
    student's department. Both the student and the department must
    belong to the calling institution -- checked explicitly here, before
    any write, as the clean-error counterpart to the database's own
    validate_student_department_id trigger (040), which would otherwise
    just silently null out an invalid cross-institution assignment."""
    student_resp = (
        client.table("student_profiles")
        .select("id")
        .eq("id", student_id)
        .eq("institution_id", institution_id)
        .maybe_single()
        .execute()
    )
    if not (student_resp and student_resp.data):
        raise CrossInstitutionAssignmentError("Student not found, or not linked to your institution.")

    if department_id is not None:
        dept_resp = (
            client.table("departments")
            .select("id")
            .eq("id", department_id)
            .eq("institution_id", institution_id)
            .maybe_single()
            .execute()
        )
        if not (dept_resp and dept_resp.data):
            raise CrossInstitutionAssignmentError("Department not found, or not owned by your institution.")

    (
        client.table("student_profiles")
        .update({"department_id": department_id})
        .eq("id", student_id)
        .eq("institution_id", institution_id)
        .execute()
    )
    resp = (
        client.table("student_profiles")
        .select("id, department_id")
        .eq("id", student_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp else {"id": student_id, "department_id": department_id}
