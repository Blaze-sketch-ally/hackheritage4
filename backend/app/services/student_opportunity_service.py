"""Business logic for the STUDENT side of opportunity discovery and
applications.

Every function takes an already-built *user-scoped* Supabase client
(app.core.security.build_user_client) -- RLS is the real access-control
boundary and nothing here uses service_role.

What RLS already guarantees for a STUDENT caller, and this module relies
on rather than re-implements:

* `internships` / `jobs`: "Authenticated users can view published
  internships/jobs" -- a student only ever sees `status = 'PUBLISHED'`
  rows. A DRAFT/CLOSED/ARCHIVED posting is invisible (reads return no
  row -> callers 404).
* `internship_skills` / `job_skills`: visible only for a PUBLISHED
  parent posting.
* `industry_profiles`: "Authenticated users can view industry profiles"
  -- company display info only, never `profiles`.
* `applications`: "Students can view their own applications" (select) and
  "Students can apply to published opportunities" (insert, with a
  WITH CHECK that re-verifies `auth.uid() = student_id`, `is_student`,
  and the referenced posting actually being PUBLISHED). `industry_id` is
  filled by the `applications_set_industry_id` BEFORE-INSERT trigger --
  this module never sends it.

The student-facing opportunity id is ``internship_<uuid>`` /
``job_<uuid>`` so the source table is always unambiguous even if a raw
internship UUID ever equals a raw job UUID.
"""

from postgrest.exceptions import APIError
from supabase import Client

from app.services import match_service

_INTERNSHIP_PREFIX = "internship_"
_JOB_PREFIX = "job_"

# Columns selected from each posting table for the detail view. The list
# view uses a narrower subset (see _SUMMARY_COLUMNS).
_INTERNSHIP_COLUMNS = (
    "id, industry_id, title, description, location, work_mode, duration_months, "
    "stipend_amount, stipend_currency, openings, eligibility_criteria, "
    "application_deadline, start_date, status, created_at, "
    "internship_skills(skill_id, required_level, importance, "
    "skill:skills(name, category:skill_categories(name)))"
)
_JOB_COLUMNS = (
    "id, industry_id, title, description, location, work_mode, employment_type, "
    "salary_min, salary_max, salary_currency, experience_min_years, openings, "
    "eligibility_criteria, application_deadline, status, created_at, "
    "job_skills(skill_id, required_level, importance, "
    "skill:skills(name, category:skill_categories(name)))"
)
_SUMMARY_COLUMNS = (
    "id, industry_id, title, description, location, work_mode, "
    "application_deadline, status, created_at"
)


class InvalidOpportunityIdError(Exception):
    """The supplied student-facing opportunity id is not a well-formed
    ``internship_<uuid>`` / ``job_<uuid>`` string."""


class DuplicateApplicationError(Exception):
    """The student has already applied to this posting -- the DB's partial
    unique index (applications_unique_student_internship_idx /
    applications_unique_student_job_idx) rejected the insert."""


class OpportunityNotPublishedError(Exception):
    """The referenced posting exists but is not visible to the student
    (not PUBLISHED) -- the insert's RLS WITH CHECK rejected it."""


class ApplicationNotWithdrawableError(Exception):
    """The student's own application is in a status that can no longer be
    withdrawn: SELECTED (offer in hand -- declining is the Internship
    Workspace's job), REJECTED (industry decision, terminal), or already
    WITHDRAWN."""

    def __init__(self, current_status: str) -> None:
        self.current_status = current_status
        super().__init__(
            f"An application at '{current_status}' can no longer be withdrawn."
        )


# Active candidate stages a student may still pull out of. Mirrors the
# intent of application_service._STATUS_TRANSITIONS on the Industry side --
# SELECTED / REJECTED / WITHDRAWN carry no student-initiated transition.
WITHDRAWABLE_STATUSES = frozenset(
    {"APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED"}
)


# ---- id encoding ----


def encode_opportunity_id(source_type: str, raw_id: str) -> str:
    prefix = _INTERNSHIP_PREFIX if source_type == "INTERNSHIP" else _JOB_PREFIX
    return f"{prefix}{raw_id}"


def decode_opportunity_id(opportunity_id: str) -> tuple[str, str]:
    """``internship_<uuid>`` -> ("INTERNSHIP", "<uuid>"); ``job_<uuid>`` ->
    ("JOB", "<uuid>"). Raises InvalidOpportunityIdError otherwise."""
    if opportunity_id.startswith(_INTERNSHIP_PREFIX):
        raw = opportunity_id[len(_INTERNSHIP_PREFIX):]
        if raw:
            return "INTERNSHIP", raw
    elif opportunity_id.startswith(_JOB_PREFIX):
        raw = opportunity_id[len(_JOB_PREFIX):]
        if raw:
            return "JOB", raw
    raise InvalidOpportunityIdError(opportunity_id)


# ---- industry display info ----


def _fetch_industries(client: Client, industry_ids: list[str]) -> dict[str, dict]:
    """Batch-load company display info for a set of posting owners. Missing
    ids (Industry account with no company profile row yet) simply don't
    appear in the result."""
    ids = sorted({i for i in industry_ids if i})
    if not ids:
        return {}
    response = (
        client.table("industry_profiles")
        .select("id, company_name, industry_sector, logo_url")
        .in_("id", ids)
        .execute()
    )
    return {row["id"]: row for row in (response.data or [])}


def _industry_payload(industry_id: str, industries: dict[str, dict]) -> dict:
    profile = industries.get(industry_id) or {}
    return {
        "id": industry_id,
        "company_name": profile.get("company_name"),
        "industry_sector": profile.get("industry_sector"),
        "logo_url": profile.get("logo_url"),
    }


# ---- normalization ----


def _shape_skills(links: list[dict] | None) -> list[dict]:
    skills = []
    for link in links or []:
        skill = link.get("skill") or {}
        category = skill.get("category") or {}
        skills.append(
            {
                "skill_id": link["skill_id"],
                "skill_name": skill.get("name", ""),
                "category_name": category.get("name"),
                "required_level": link["required_level"],
                "importance": link["importance"],
            }
        )
    skills.sort(key=lambda s: s["skill_name"].lower())
    return skills


def _summary(row: dict, source_type: str, industries: dict[str, dict], *, applied: bool) -> dict:
    return {
        "id": encode_opportunity_id(source_type, row["id"]),
        "source_type": source_type,
        "title": row["title"],
        "description": row["description"],
        "location": row.get("location"),
        "work_mode": row.get("work_mode"),
        "status": row["status"],
        "industry": _industry_payload(row["industry_id"], industries),
        "application_deadline": row.get("application_deadline"),
        "created_at": row.get("created_at"),
        "has_applied": applied,
    }


def _detail(row: dict, source_type: str, industries: dict[str, dict], *, applied: bool) -> dict:
    base = _summary(row, source_type, industries, applied=applied)
    links = row.get("internship_skills") if source_type == "INTERNSHIP" else row.get("job_skills")
    base.update(
        {
            "eligibility_criteria": row.get("eligibility_criteria"),
            "openings": row.get("openings"),
            "duration_months": row.get("duration_months"),
            "stipend_amount": row.get("stipend_amount"),
            "stipend_currency": row.get("stipend_currency"),
            "start_date": row.get("start_date"),
            "employment_type": row.get("employment_type"),
            "salary_min": row.get("salary_min"),
            "salary_max": row.get("salary_max"),
            "salary_currency": row.get("salary_currency"),
            "experience_min_years": row.get("experience_min_years"),
            "skills": _shape_skills(links),
        }
    )
    return base


# ---- browse ----


def _applied_posting_ids(client: Client, student_id: str) -> tuple[set[str], set[str]]:
    """The internship_id / job_id sets the student has already applied to
    -- used to flag `has_applied` on browse results without a per-row
    query."""
    response = (
        client.table("applications")
        .select("internship_id, job_id")
        .eq("student_id", student_id)
        .execute()
    )
    internships = {r["internship_id"] for r in (response.data or []) if r.get("internship_id")}
    jobs = {r["job_id"] for r in (response.data or []) if r.get("job_id")}
    return internships, jobs


# The only two orderings a student can ask for -- a fixed whitelist, never
# a raw column name. The API layer validates the incoming value against
# the same set (schemas.student_opportunity.OpportunitySort).
_SORTS = ("newest", "deadline")


def _apply_order(query, order_by: str):
    """Apply the DB-side ordering for one posting table's query.

    * ``newest``   -> created_at DESC (the historical default).
    * ``deadline`` -> application_deadline ASC, NULLs LAST -- "closing
      soonest first", postings with no deadline after the dated ones.
    """
    if order_by == "deadline":
        return query.order("application_deadline", desc=False, nullsfirst=False)
    return query.order("created_at", desc=True)


def _sort_shaped(shaped: list[dict], order_by: str) -> None:
    """Re-sort the merged internship+job list in place, matching
    `_apply_order` so a combined (`source_type=None`) request interleaves
    the two DB result sets correctly. `id` is the deterministic tie-break."""
    if order_by == "deadline":
        shaped.sort(
            key=lambda o: (
                o.get("application_deadline") is None,
                o.get("application_deadline") or "",
                o["id"],
            )
        )
    else:
        shaped.sort(key=lambda o: (o.get("created_at") or "", o["id"]), reverse=True)


def list_opportunities(
    client: Client,
    student_id: str,
    *,
    source_type: str | None = None,
    search: str | None = None,
    work_mode: str | None = None,
    order_by: str = "newest",
    min_stipend: int | None = None,
    min_salary: int | None = None,
) -> list[dict]:
    """Published internships and/or jobs, normalized, ordered per
    `order_by`. RLS already restricts every row to `status = 'PUBLISHED'`;
    the explicit `.eq("status", "PUBLISHED")` is defence in depth and is
    ALWAYS applied first -- every filter below only narrows that set.

    Filters (all optional, all narrowing):
    * `search`       -> case-insensitive title match, both tables.
    * `work_mode`    -> exact `work_mode`, both tables.
    * `min_stipend`  -> `stipend_amount >= v`, internships only (NULL
                        stipend is excluded -- intentional).
    * `min_salary`   -> `salary_max >= v`, jobs only (NULL salary excluded).
    """
    want_internships = source_type in (None, "INTERNSHIP")
    want_jobs = source_type in (None, "JOB")
    if order_by not in _SORTS:
        order_by = "newest"

    search_term = search.strip() if search and search.strip() else None

    applied_internships, applied_jobs = _applied_posting_ids(client, student_id)

    rows: list[tuple[dict, str, bool]] = []
    industry_ids: list[str] = []

    if want_internships:
        query = (
            client.table("internships").select(_SUMMARY_COLUMNS).eq("status", "PUBLISHED")
        )
        if search_term:
            query = query.ilike("title", f"%{search_term}%")
        if work_mode:
            query = query.eq("work_mode", work_mode)
        if min_stipend is not None and min_stipend > 0:
            query = query.gte("stipend_amount", min_stipend)
        query = _apply_order(query, order_by)
        for row in query.execute().data or []:
            rows.append((row, "INTERNSHIP", row["id"] in applied_internships))
            industry_ids.append(row["industry_id"])

    if want_jobs:
        query = client.table("jobs").select(_SUMMARY_COLUMNS).eq("status", "PUBLISHED")
        if search_term:
            query = query.ilike("title", f"%{search_term}%")
        if work_mode:
            query = query.eq("work_mode", work_mode)
        if min_salary is not None and min_salary > 0:
            query = query.gte("salary_max", min_salary)
        query = _apply_order(query, order_by)
        for row in query.execute().data or []:
            rows.append((row, "JOB", row["id"] in applied_jobs))
            industry_ids.append(row["industry_id"])

    industries = _fetch_industries(client, industry_ids)

    shaped = [
        _summary(row, kind, industries, applied=applied) for row, kind, applied in rows
    ]
    _sort_shaped(shaped, order_by)
    return shaped


def get_opportunity(client: Client, student_id: str, opportunity_id: str) -> dict | None:
    """One published internship/job, normalized with its required skills,
    or None (callers turn None into a 404). Raises
    InvalidOpportunityIdError for a malformed id."""
    source_type, raw_id = decode_opportunity_id(opportunity_id)

    if source_type == "INTERNSHIP":
        table, columns = "internships", _INTERNSHIP_COLUMNS
    else:
        table, columns = "jobs", _JOB_COLUMNS

    response = (
        client.table(table)
        .select(columns)
        .eq("id", raw_id)
        .eq("status", "PUBLISHED")
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None

    industries = _fetch_industries(client, [row["industry_id"]])
    applied_internships, applied_jobs = _applied_posting_ids(client, student_id)
    applied = raw_id in (applied_internships if source_type == "INTERNSHIP" else applied_jobs)
    return _detail(row, source_type, industries, applied=applied)


# ---- apply ----


def apply_to_opportunity(
    client: Client, student_id: str, opportunity_id: str, cover_note: str | None
) -> dict:
    """Create the existing `applications` row for this student against the
    resolved internship/job. Only `student_id`, `opportunity_type`,
    `internship_id`/`job_id` and `cover_note` are sent -- `industry_id` is
    the trigger's job, `status` defaults to APPLIED, `applied_at` defaults
    to now().

    MUST be called only after get_opportunity() has confirmed the posting
    is visible/published (the route enforces that ordering, mirroring
    app.api.assessments.create_attempt).
    """
    source_type, raw_id = decode_opportunity_id(opportunity_id)

    payload: dict = {
        "student_id": student_id,
        "opportunity_type": source_type,
        "cover_note": (cover_note.strip() or None) if cover_note else None,
    }
    if source_type == "INTERNSHIP":
        payload["internship_id"] = raw_id
    else:
        payload["job_id"] = raw_id

    try:
        response = client.table("applications").insert(payload).execute()
    except APIError as exc:
        if exc.code == "23505":
            raise DuplicateApplicationError(opportunity_id) from exc
        # 42501 = RLS WITH CHECK / trigger rejection (posting not published,
        # not a student, ...). 23503 = posting vanished between the check
        # and the insert.
        if exc.code in ("42501", "23503"):
            raise OpportunityNotPublishedError(opportunity_id) from exc
        raise

    new_id = response.data[0]["id"]
    row = _get_own_application(client, student_id, new_id)
    if row is None:
        raise RuntimeError("application row could not be read back after insert.")
    return row


# ---- my applications ----

_APPLICATION_SELECT = (
    "id, student_id, opportunity_type, internship_id, job_id, status, cover_note, "
    "match_score, applied_at, created_at, updated_at, "
    "internship:internships(id, title, location, work_mode, industry_id), "
    "job:jobs(id, title, location, work_mode, industry_id)"
)

# The student-safe interview columns surfaced on an application. NEVER
# `notes` (Industry-private) / `industry_id` / `student_id` -- the
# public.student_interviews RPC (054) does not return them either.
_INTERVIEW_FIELDS = ("id", "application_id", "scheduled_at", "duration_minutes", "mode", "location", "status")


def _interview_index(client: Client, application_ids: list[str]) -> dict[str, dict]:
    """Map application_id -> its live (SCHEDULED) interview, via ONE call
    to the public.student_interviews SECURITY DEFINER RPC
    (054_student_interview_visibility.sql).

    NOT a nested PostgREST embed: the `interviews -> applications`
    relationship is deliberately not something a read depends on being in
    PostgREST's schema cache (interview_service._opportunity_index and
    institution_student_service both stitch a separate read for the same
    reason). The RPC re-derives `auth.uid() = student_id` +
    `public.is_student(auth.uid())` internally, filters to
    `status = 'SCHEDULED'`, and returns only the student-safe columns.

    Best-effort enrichment, exactly like `_fetch_industries` /
    application_service's applicant names: any failure just leaves
    `interview` as None on every application -- it never turns a
    successful applications read into an error.
    """
    ids = [i for i in dict.fromkeys(application_ids) if i]
    if not ids:
        return {}
    try:
        response = client.rpc("student_interviews", {"application_ids": ids}).execute()
    except Exception:  # noqa: BLE001 -- interview detail is optional enrichment, never fatal
        return {}
    index: dict[str, dict] = {}
    for row in response.data or []:
        # Defence in depth: the RPC already filters to SCHEDULED, but never
        # surface a COMPLETED/CANCELLED row even if that ever changes.
        if row.get("status") != "SCHEDULED":
            continue
        index[row["application_id"]] = {k: row.get(k) for k in _INTERVIEW_FIELDS}
    return index


def _shape_application(
    row: dict, industries: dict[str, dict], interviews: dict[str, dict] | None = None
) -> dict:
    internship = row.pop("internship", None)
    job = row.pop("job", None)
    picked = internship or job
    source_type = "INTERNSHIP" if row["opportunity_type"] == "INTERNSHIP" else "JOB"
    raw_id = row.get("internship_id") or row.get("job_id")

    opportunity = {
        "id": encode_opportunity_id(source_type, raw_id) if raw_id else "",
        "source_type": source_type,
        "title": picked.get("title") if picked else None,
        "location": picked.get("location") if picked else None,
        # Lets the Applications view tell an on-site SELECTED internship
        # (no online workspace) apart from a Remote/Hybrid one.
        "work_mode": picked.get("work_mode") if picked else None,
        "industry": (
            _industry_payload(picked["industry_id"], industries)
            if picked and picked.get("industry_id")
            else None
        ),
    }
    row["opportunity"] = opportunity
    # None when the application has no live interview -- an
    # INTERVIEW_SCHEDULED application can legitimately have none (manual
    # status move, or the interview was cancelled/completed).
    row["interview"] = (interviews or {}).get(row["id"])
    return row


def list_my_applications(client: Client, student_id: str) -> list[dict]:
    """The authenticated student's own applications, newest first. RLS
    ("Students can view their own applications") plus the explicit
    `.eq("student_id", ...)` both scope this to the caller. `status` is
    whatever the owning Industry account last set -- this read always
    reflects the current value."""
    response = (
        client.table("applications")
        .select(_APPLICATION_SELECT)
        .eq("student_id", student_id)
        .order("applied_at", desc=True)
        .execute()
    )
    rows = response.data or []

    industry_ids: list[str] = []
    for row in rows:
        picked = row.get("internship") or row.get("job")
        if picked and picked.get("industry_id"):
            industry_ids.append(picked["industry_id"])
    industries = _fetch_industries(client, industry_ids)
    interviews = _interview_index(client, [row["id"] for row in rows])

    return [_shape_application(row, industries, interviews) for row in rows]


def _get_own_application(client: Client, student_id: str, application_id: str) -> dict | None:
    response = (
        client.table("applications")
        .select(_APPLICATION_SELECT)
        .eq("id", application_id)
        .eq("student_id", student_id)
        .maybe_single()
        .execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    picked = row.get("internship") or row.get("job")
    industries = (
        _fetch_industries(client, [picked["industry_id"]])
        if picked and picked.get("industry_id")
        else {}
    )
    interviews = _interview_index(client, [row["id"]])
    return _shape_application(row, industries, interviews)


def withdraw_application(client: Client, student_id: str, application_id: str) -> dict | None:
    """Move the student's OWN application to WITHDRAWN, if it is still an
    active candidate application.

    Security: `student_id` is always the authenticated caller's id, never a
    request field. Both the read and the write are scoped by an explicit
    `.eq("student_id", student_id)` AND the `applications` student RLS
    policies (`auth.uid() = student_id AND public.is_student(...)`), and the
    `prevent_student_status_override` BEFORE-UPDATE trigger
    (020_applications.sql) independently blocks a student from setting any
    status other than WITHDRAWN. No service_role client is used.

    Returns the updated application (same shape as `apply_to_opportunity` /
    `list_my_applications`), or None when the caller does not own an
    application with that id -- the route turns that into a 404, so another
    student's application is indistinguishable from one that doesn't exist.

    Raises ApplicationNotWithdrawableError (route -> 409) when the current
    status is terminal. An already-WITHDRAWN application is NOT silently
    re-withdrawn: it raises too, matching the Industry side's
    InvalidStatusTransitionError semantics for a no-op transition.

    Scope: touches ONLY `applications.status`. It does not cancel a
    scheduled interview or any downstream object -- consistent with the
    existing INTERVIEW_SCHEDULED -> REJECTED path, which also leaves the
    interview row untouched, and there is no DB trigger cascading
    application status onto `interviews` / workspaces.
    """
    existing = _get_own_application(client, student_id, application_id)
    if existing is None:
        return None

    current = existing["status"]
    if current not in WITHDRAWABLE_STATUSES:
        raise ApplicationNotWithdrawableError(current)

    (
        client.table("applications")
        .update({"status": "WITHDRAWN"})
        .eq("id", application_id)
        .eq("student_id", student_id)
        .execute()
    )
    return _get_own_application(client, student_id, application_id)


# ---- match (advisory) ----


def _posting_required_skills(client: Client, source_type: str, raw_id: str) -> list[dict]:
    if source_type == "INTERNSHIP":
        table, fk = "internship_skills", "internship_id"
    else:
        table, fk = "job_skills", "job_id"
    response = (
        client.table(table)
        .select("skill_id, required_level, importance, skill:skills(name)")
        .eq(fk, raw_id)
        .execute()
    )
    return response.data or []


def _own_skill_levels(client: Client, student_id: str) -> dict[str, dict]:
    response = (
        client.table("student_skills")
        .select("skill_id, proficiency_level, is_verified")
        .eq("student_id", student_id)
        .execute()
    )
    return {row["skill_id"]: row for row in (response.data or [])}


def compute_opportunity_match(client: Client, student_id: str, opportunity_id: str) -> dict:
    """Build the required-skill x own-skill rows and hand them to the
    shared deterministic engine (app.services.match_service.compute_match)
    -- the same scorer the Industry applicant-match endpoint uses. Never
    persisted, never tied to an application. Safe to fail without
    affecting Apply -- the route isolates it."""
    source_type, raw_id = decode_opportunity_id(opportunity_id)

    required = _posting_required_skills(client, source_type, raw_id)
    own = _own_skill_levels(client, student_id)

    rows = []
    for req in required:
        skill_id = req["skill_id"]
        mine = own.get(skill_id)
        skill = req.get("skill") or {}
        rows.append(
            {
                "skill_id": skill_id,
                "skill_name": skill.get("name", ""),
                "required_level": req["required_level"],
                "importance": req["importance"],
                "candidate_has": mine is not None,
                "candidate_level": mine.get("proficiency_level") if mine else None,
                "candidate_verified": bool(mine.get("is_verified")) if mine else False,
            }
        )

    result = match_service.compute_match(opportunity_id, rows)
    result["opportunity_id"] = result.pop("application_id")
    return result
