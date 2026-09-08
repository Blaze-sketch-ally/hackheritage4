"""Schema guard for PHASE J1 of the Job Training domain
(database/migrations/040_job_training.sql).

Same convention as tests/test_internship_workspace_schema.py /
tests/test_learning_schema.py: this suite has no live database, so every
DB-level guarantee is asserted by reading the migration SQL. J1 is
DATABASE ONLY -- there is no router / service / schema for Job Training
yet (later phases), so these tests assert nothing about app code.

Business rule under guard:
    JOB       + SELECTED  -> a job_training_enrollment may be created.
    JOB       + any other status -> rejected at the database.
    INTERNSHIP + any status (SELECTED included) -> rejected at the database.
Training is EXCLUSIVE to selected JOB candidates.
"""

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
M040 = MIGRATIONS_DIR / "040_job_training.sql"

PROGRAM_TABLES = (
    "job_programs",
    "job_program_modules",
    "job_program_items",
    "job_program_skills",
    "job_program_assignments",
)
ENROLLMENT_TABLES = ("job_training_enrollments",)
ALL_NEW_TABLES = PROGRAM_TABLES + ENROLLMENT_TABLES

# Objects guaranteed present from migrations 001-039 / the Supabase base.
_PREEXISTING_TABLES = {
    "profiles", "skills", "skill_categories", "student_skills", "internships",
    "internship_skills", "jobs", "job_skills", "applications", "interviews",
    "industry_profiles", "student_profiles", "student_notifications",
}
_PREEXISTING_FUNCS = {"set_updated_at", "is_student", "is_industry"}


def _raw(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """SQL with comment-only lines stripped (keeps trailing inline code)."""
    return "\n".join(
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("--")
    )


M040_RAW = _raw(M040)
M040_C = _code(M040)
M040_L = M040_C.lower()


def _table_block(sql: str, table: str) -> str:
    head = f"create table if not exists {table}"
    assert head in sql, f"missing: {head}"
    return sql.split(head, 1)[1].split(");", 1)[0]


def _check_set(sql: str, column: str) -> set[str]:
    """The value set of a `check (<column> in ('A', 'B', ...))` clause."""
    m = re.search(
        rf"check\s*\(\s*{re.escape(column)}\s+in\s*\(([^)]*)\)\s*\)",
        sql, re.DOTALL | re.IGNORECASE,
    )
    assert m, f"no CHECK clause found for column {column!r}"
    return {v.strip().strip("'\"") for v in m.group(1).replace("\n", " ").split(",") if v.strip()}


def _index_of(needle: str) -> int:
    i = M040_C.find(needle)
    assert i != -1, f"not found in 040: {needle!r}"
    return i


def _created_before(needle_a: str, needle_b: str) -> bool:
    return _index_of(needle_a) < _index_of(needle_b)


def _fn_signature(name: str) -> str:
    after = M040_C.split(f"create or replace function public.{name}", 1)[1]
    return after.split("$$", 1)[0]


def _fn_body(name: str) -> str:
    after = M040_C.split(f"create or replace function public.{name}", 1)[1]
    return after.split("$$", 2)[1]


# ============================================================
# 1. Existence, numbering, historical integrity
# ============================================================


def test_migration_040_exists():
    assert M040.is_file(), f"expected {M040} to exist"


def test_migration_numbering_stays_contiguous_and_unique():
    numbers = sorted(int(p.name[:3]) for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert len(numbers) == len(set(numbers)), f"duplicate migration numbers: {numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap in numbering: {numbers}"
    assert 40 in numbers
    # 041 (Job Training completion) is the J4 tip; nothing after it yet.
    assert numbers[-1] in (40, 41), f"unexpected migration tip: {numbers[-1]}"


def test_no_historical_migration_was_modified_by_j1():
    """J1 adds exactly one migration file and edits none of 001-039."""
    for anchor, marker in (
        ("020_applications.sql", "create table applications"),
        ("019_jobs.sql", "create table if not exists jobs"),
        ("033_learning_resources.sql", "create table if not exists learning_resources"),
        ("035_student_notifications.sql", "create table if not exists student_notifications"),
        ("037_internship_program.sql", "create table if not exists internship_programs"),
        ("038_internship_workspace.sql", "create table if not exists internship_workspaces"),
        ("039_workspace_submissions_completion.sql", "create table if not exists workspace_submissions"),
    ):
        assert marker in _raw(MIGRATIONS_DIR / anchor)


def test_j1_is_additive_and_non_destructive():
    assert "drop table" not in M040_L, "040 must not drop a table"
    assert "truncate" not in M040_L, "040 must not truncate"
    for line in M040_L.splitlines():
        s = line.strip()
        if s.startswith("drop ") and "execute format(" not in s:
            assert s.startswith(("drop policy if exists", "drop trigger if exists")), (
                f"040: unexpected drop statement: {s!r}"
            )


def test_j1_does_not_touch_the_frozen_existing_tables():
    """The only ALTER TABLE on a pre-existing table is the additive
    student_notifications CHECK widening."""
    assert "alter table public.student_notifications" in M040_L
    frozen = (
        "applications", "jobs", "internships", "profiles", "skills", "student_skills",
        "assessments", "learning_resources", "learning_resource_skills",
        "student_learning_progress", "industry_training", "applications_legacy",
        "internship_programs", "program_modules", "module_items", "program_skills",
        "program_assignments", "internship_workspaces", "workspace_skill_selections",
        "workspace_submissions", "submission_reviews", "internship_completions",
        "internship_certificates", "stipend_disbursements",
    )
    for t in frozen:
        assert f"alter table {t} " not in M040_L, f"040 must not alter {t}"
        assert f"alter table public.{t} " not in M040_L, f"040 must not alter public.{t}"
        assert f"create table if not exists {t}" not in M040_L, f"040 must not (re)create {t}"


def test_j1_does_not_add_a_new_application_status():
    assert "alter table applications" not in M040_L
    assert "alter table public.applications" not in M040_L
    # 040 only ever READS applications.status, never widens/edits its CHECK.
    assert "status in ('applied'" not in M040_L
    assert "add constraint applications" not in M040_L


def test_shared_helpers_are_reused_not_redefined():
    for fn in ("set_updated_at", "is_student", "is_industry"):
        assert f"create or replace function public.{fn}" not in M040_C
    assert "execute procedure public.set_updated_at()" in M040_C
    assert "public.is_student(auth.uid())" in M040_C
    assert "public.is_industry(auth.uid())" in M040_C


def test_j1_never_references_student_skills_or_verification():
    assert "student_skills" not in M040_L, "040 must not reference student_skills"
    assert "is_verified" not in M040_L, "040 must not touch skill verification"
    assert "score_assessment_attempt" not in M040_L
    # training completion is NOT skill evidence
    assert "student_learning_progress" not in M040_L


def test_j1_does_not_repurpose_student_learning_or_industry_training():
    for other in ("learning_resources", "student_learning_progress", "industry_training"):
        assert f"references {other}" not in M040_L
        assert f"from public.{other}" not in M040_L
        assert f"join public.{other}" not in M040_L


# ============================================================
# 2. Tables exist, RLS enabled
# ============================================================


def test_all_six_tables_are_created():
    for t in ALL_NEW_TABLES:
        assert f"create table if not exists {t}" in M040_L, f"missing table {t}"


def test_rls_enabled_on_every_new_table():
    for t in ALL_NEW_TABLES:
        assert f"alter table {t} enable row level security" in M040_L, f"RLS not enabled on {t}"


def test_no_new_table_has_a_delete_policy():
    for t in ALL_NEW_TABLES:
        assert f"on {t} for delete" not in M040_L, f"{t} must not allow hard delete"


# ============================================================
# 3. job_programs: 1:1 with a JOB, no internship_id
# ============================================================


def test_job_program_is_strictly_one_per_job():
    block = _table_block(M040_L, "job_programs")
    assert "job_id uuid not null references jobs (id) on delete cascade" in block
    assert "constraint job_programs_one_per_job unique (job_id)" in block


def test_job_program_has_no_internship_reference_anywhere_in_the_migration():
    assert "internship_id" not in M040_L, "040 must have NO internship_id column"
    assert "references internships" not in M040_L
    assert "internship_programs" not in M040_L
    # a job program is structurally impossible to attach to an internship
    block = _table_block(M040_L, "job_programs")
    assert "internship" not in block


def test_job_program_status_lifecycle_values():
    assert _check_set(_table_block(M040_C, "job_programs"), "status") == {
        "DRAFT", "PUBLISHED", "ARCHIVED"
    }


def test_job_program_has_required_conceptual_fields_and_timestamps():
    block = _table_block(M040_L, "job_programs")
    for col in ("id uuid primary key default gen_random_uuid()", "title text not null",
                "summary text", "published_at timestamptz",
                "created_at timestamptz not null default now()",
                "updated_at timestamptz not null default now()"):
        assert col in block, f"job_programs missing {col!r}"


def test_job_program_does_not_store_industry_id():
    # ownership derives THROUGH jobs.industry_id -- one source of truth
    block = _table_block(M040_L, "job_programs")
    assert "industry_id" not in block


# ============================================================
# 4. owns_job_program(): ownership through the job
# ============================================================


def test_owns_job_program_helper_is_defined_after_its_table():
    # the exact failure the 037 live push hit: a `language sql` helper
    # created before its table.
    assert _created_before(
        "create table if not exists job_programs",
        "create or replace function public.owns_job_program",
    ), "owns_job_program() must be created AFTER job_programs"


def test_owns_job_program_resolves_through_job_ownership():
    sig = _fn_signature("owns_job_program")
    body = _fn_body("owns_job_program")
    assert "language\n  sql" in sig or "language sql" in sig
    assert "security definer" in sig
    assert "set search_path = ''" in sig
    assert "stable" in sig
    assert "join public.jobs j on j.id = prog.job_id" in body
    assert "j.industry_id = auth.uid()" in body
    assert "public.is_industry(auth.uid())" in body
    assert "j.status" not in body, "ownership must not depend on the posting status"


def test_owns_job_program_is_locked_down_then_granted_to_authenticated():
    assert "revoke all on function public.owns_job_program(uuid) from public" in M040_C
    assert "revoke all on function public.owns_job_program(uuid) from anon" in M040_C
    assert "grant execute on function public.owns_job_program(uuid) to authenticated" in M040_C


# ============================================================
# 5. Program content model (mirrors the internship program tables)
# ============================================================


def test_job_program_modules_shape():
    block = _table_block(M040_L, "job_program_modules")
    assert "program_id uuid not null references job_programs (id) on delete cascade" in block
    assert "order_index int not null default 0 check (order_index >= 0)" in block
    assert "is_published boolean not null default false" in block
    assert "job_program_modules_program_id_idx" in M040_L


def test_job_program_items_are_one_normalized_table_with_a_type_check():
    block = _table_block(M040_C, "job_program_items")
    assert "module_id uuid not null references job_program_modules (id) on delete cascade" in block.lower()
    assert _check_set(block, "item_type") == {"VIDEO", "PDF", "LINK", "TEXT"}
    assert "job_program_items_content_matches_type" in block
    assert "job_program_items_module_id_idx" in M040_L


def test_job_program_skills_reference_canonical_catalog_with_required_optional():
    block = _table_block(M040_C, "job_program_skills")
    bl = block.lower()
    assert "program_id uuid not null references job_programs (id) on delete cascade" in bl
    assert "skill_id uuid not null references skills (id) on delete restrict" in bl
    assert _check_set(block, "requirement") == {"REQUIRED", "OPTIONAL"}
    assert "unique (program_id, skill_id)" in bl
    assert "job_program_skills_skill_id_idx" in M040_L
    # mutable child content -> `for all` owner policy (replaceable set)
    assert "on job_program_skills for all" in M040_L


def test_job_program_assignments_is_one_table_not_three():
    for forbidden in ("create table if not exists job_assignments",
                      "create table if not exists job_quizzes",
                      "create table if not exists job_projects"):
        assert forbidden not in M040_L
    block = _table_block(M040_C, "job_program_assignments")
    assert _check_set(block, "assignment_type") == {"ASSIGNMENT", "QUIZ", "PROJECT"}
    assert _check_set(block, "submission_kind") == {"LINK", "REPO", "FILE", "TEXT", "MIXED"}
    bl = block.lower()
    for col in ("is_required", "is_published", "linked_skill_id", "order_index",
                "due_offset_days", "repo_required", "live_url_expected"):
        assert col in bl, f"job_program_assignments missing {col}"
    assert "linked_skill_id uuid references skills (id) on delete set null" in bl
    assert "job_program_assignments_repo_kind_consistent" in block


def test_job_program_assignment_program_id_is_derived_by_a_before_trigger():
    assert "create or replace function public.set_job_program_assignment_program_id" in M040_C
    assert "before insert or update on job_program_assignments" in M040_C
    body = _fn_body("set_job_program_assignment_program_id")
    assert "from public.job_program_modules m" in body
    assert "new.program_id := v_program_id" in body
    sig = _fn_signature("set_job_program_assignment_program_id")
    assert "security definer" in sig and "set search_path = ''" in sig


def test_program_record_tables_have_only_select_insert_update_policies():
    for t in ("job_programs", "job_program_modules", "job_program_items",
              "job_program_assignments"):
        assert f"on {t} for delete" not in M040_L, f"{t} must not allow delete"
        assert f"on {t} for all" not in M040_L, f"{t} must not have a `for all` policy"
        for verb in ("select", "insert", "update"):
            assert f"on {t} for {verb}" in M040_L, f"{t} needs a `for {verb}` policy"


# ============================================================
# 6. Enrollment: identity, uniqueness, derivation
# ============================================================


def test_enrollment_is_one_per_application_and_keyed_to_the_application():
    block = _table_block(M040_L, "job_training_enrollments")
    assert "application_id uuid not null references applications (id) on delete cascade" in block
    assert "student_id uuid not null references profiles (id) on delete cascade" in block
    assert "industry_id uuid not null references profiles (id) on delete restrict" in block
    assert "job_id uuid not null references jobs (id) on delete restrict" in block
    assert "constraint job_training_enrollments_one_per_application unique (application_id)" in block


def test_enrollment_status_uses_the_minimum_lifecycle():
    assert _check_set(_table_block(M040_C, "job_training_enrollments"), "enrollment_status") == {
        "ACTIVE", "COMPLETED", "REVOKED"
    }
    # no student opt-in step was invented
    assert "ACCEPTED" not in M040_C
    assert "DECLINED" not in M040_C
    assert "PENDING_ACCEPTANCE" not in M040_C


def test_enrollment_paired_field_constraints():
    block = _table_block(M040_L, "job_training_enrollments")
    assert "job_training_enrollments_completed_at_requires_completed" in block
    assert "job_training_enrollments_revoked_fields_require_revoked" in block


def test_enrollment_derivation_trigger_exists_and_is_before_insert():
    assert "create or replace function public.set_job_training_enrollment_derived_ids" in M040_C
    assert "before insert on job_training_enrollments" in M040_C
    sig = _fn_signature("set_job_training_enrollment_derived_ids")
    assert "security definer" in sig and "set search_path = ''" in sig


def test_enrollment_derivation_reads_all_three_ids_from_the_application():
    body = _fn_body("set_job_training_enrollment_derived_ids")
    assert "from public.applications a" in body
    assert "a.student_id" in body and "a.industry_id" in body and "a.job_id" in body
    for assign in ("new.student_id  := v_student_id",
                   "new.industry_id := v_industry_id",
                   "new.job_id      := v_job_id"):
        assert assign in body, f"missing derived assignment: {assign!r}"


def test_enrollment_indexes():
    assert "job_training_enrollments_student_status_idx" in M040_L
    assert "job_training_enrollments_industry_status_idx" in M040_L
    assert "job_training_enrollments_job_id_idx" in M040_L


# ============================================================
# 7. THE ABSOLUTE GATE -- JOB + SELECTED only
# ============================================================


def test_gate_requires_opportunity_type_job():
    body = _fn_body("set_job_training_enrollment_derived_ids")
    assert "v_opportunity_type <> 'JOB'" in body
    assert "v_job_id is null" in body
    assert "can only be created for a JOB application" in body


def test_gate_requires_status_selected():
    body = _fn_body("set_job_training_enrollment_derived_ids")
    assert "v_app_status <> 'SELECTED'" in body
    assert "can only be created for a SELECTED application" in body


def test_gate_rejects_every_non_selected_job_status_by_construction():
    """The trigger allows ONLY status == 'SELECTED'. Every other value the
    applications CHECK permits is therefore rejected -- assert the guard is
    an exact-equality check, not a set membership that could leak a value."""
    body = _fn_body("set_job_training_enrollment_derived_ids")
    assert "v_app_status <> 'SELECTED'" in body
    for leaked in ("APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED",
                   "REJECTED", "WITHDRAWN"):
        assert f"'{leaked}'" not in body, (
            f"the gate must not enumerate {leaked!r} -- only 'SELECTED' is allowed"
        )


def test_gate_rejects_internship_applications_even_when_selected():
    """opportunity_type must be 'JOB'. A SELECTED INTERNSHIP application
    fails the `v_opportunity_type <> 'JOB'` branch before status is even
    considered."""
    body = _fn_body("set_job_training_enrollment_derived_ids")
    assert "v_opportunity_type <> 'JOB'" in body
    # the JOB check is written before/independent of any internship notion
    assert "internship" not in body.lower()


def test_gate_is_a_database_trigger_not_only_a_backend_check():
    # the gate lives in a BEFORE INSERT trigger function on the table
    assert "before insert on job_training_enrollments" in M040_C
    assert "raise exception" in _fn_body("set_job_training_enrollment_derived_ids")


# ============================================================
# 8. Enrollment identity integrity
# ============================================================


def test_enrollment_identity_freeze_trigger_pins_every_identity_column():
    assert "create or replace function public.prevent_job_training_enrollment_identity_change" in M040_C
    assert "before update on job_training_enrollments" in M040_C
    body = _fn_body("prevent_job_training_enrollment_identity_change")
    for col in ("application_id", "student_id", "industry_id", "job_id"):
        assert f"new.{col} is distinct from old.{col}" in body, f"{col} not frozen"
    assert "current_setting('role', true) = 'service_role'" in body


def test_enrollment_transition_trigger_documents_and_enforces_the_lifecycle():
    assert "create or replace function public.enforce_job_training_enrollment_transitions" in M040_C
    body = _fn_body("enforce_job_training_enrollment_transitions")
    assert "current_setting('role', true) = 'service_role'" in body
    # a student can never change the status
    assert "auth.uid() = old.student_id" in body
    # REVOKED is terminal; COMPLETED -> only REVOKED
    assert "old.enrollment_status = 'REVOKED'" in body
    assert "old.enrollment_status = 'COMPLETED'" in body
    assert "new.enrollment_status <> 'REVOKED'" in body


def test_enrollment_has_no_student_update_or_delete_policy():
    block = M040_L.split("alter table job_training_enrollments enable row level security", 1)[1]
    assert "on job_training_enrollments for delete" not in block
    for student_write in ("students can update", "students can respond", "students can manage",
                          "students can accept", "students can decline"):
        assert student_write not in block, f"student must not: {student_write}"
    assert "students can view their own job training enrollment" in block


def test_enrollment_industry_policies_are_scoped_to_the_owner():
    block = M040_L.split("alter table job_training_enrollments enable row level security", 1)[1]
    for verb in ("select", "insert", "update"):
        assert f"on job_training_enrollments for {verb}" in block
    assert block.count("auth.uid() = industry_id and public.is_industry(auth.uid())") >= 3


# ============================================================
# 9. student_can_access_job_program(): the student read gate
# ============================================================


def test_student_access_helper_is_defined_after_both_tables_it_reads():
    assert _created_before(
        "create table if not exists job_programs",
        "create or replace function public.student_can_access_job_program",
    )
    assert _created_before(
        "create table if not exists job_training_enrollments",
        "create or replace function public.student_can_access_job_program",
    )


def test_student_access_helper_requires_student_enrollment_and_published():
    sig = _fn_signature("student_can_access_job_program")
    body = _fn_body("student_can_access_job_program").lower()
    assert "security definer" in sig
    assert "set search_path = ''" in sig
    assert "stable" in sig
    assert "join public.job_training_enrollments e on e.job_id = prog.job_id" in body
    assert "prog.status = 'published'" in body
    assert "e.student_id = auth.uid()" in body
    assert "public.is_student(auth.uid())" in body
    assert "e.enrollment_status <> 'revoked'" in body


def test_student_access_helper_never_depends_on_jobs_status():
    body = _fn_body("student_can_access_job_program").lower()
    assert "j.status" not in body
    assert "'closed'" not in body
    assert "'archived'" not in body
    # closed/archived posting must NOT revoke a selected student's access
    assert "prog.status = 'published'" in body  # only the PROGRAM's status matters


def test_student_access_helper_is_locked_down_then_granted_to_authenticated():
    assert "revoke all on function public.student_can_access_job_program(uuid) from public" in M040_C
    assert "revoke all on function public.student_can_access_job_program(uuid) from anon" in M040_C
    assert (
        "grant execute on function public.student_can_access_job_program(uuid) to authenticated"
        in M040_C
    )


def test_student_content_policies_use_the_helper_and_require_published():
    for t in PROGRAM_TABLES:
        assert f"on {t} for select" in M040_L, f"040 must add a student SELECT policy on {t}"
    assert "public.student_can_access_job_program" in M040_C
    assert "job_program_modules.is_published = true" in M040_C
    assert "job_program_items.is_published = true" in M040_C
    assert "job_program_assignments.is_published = true" in M040_C


# ============================================================
# 10. RLS isolation: no broad policies
# ============================================================


def test_no_new_policy_uses_using_true():
    # `using (true)` / `with check (true)` are forbidden -- there is no
    # public-read requirement anywhere in this migration.
    assert "using (true)" not in M040_L
    assert "with check (true)" not in M040_L
    assert "for select\n  to authenticated\n  using (true)" not in M040_L


def test_every_policy_targets_authenticated_only():
    # no `to anon` / `to public` policy anywhere -- Job Training is never
    # a public-read surface.
    assert "for select\n  to anon" not in M040_L
    assert " to public" not in M040_L.replace("from public", "").replace("public.", "")
    assert "to anon, authenticated" not in M040_L


def test_industry_content_policies_route_through_owns_job_program():
    # every industry-side content policy must be scoped by owns_job_program
    for t in ("job_program_modules", "job_program_items", "job_program_skills",
              "job_program_assignments"):
        section = M040_L.split(f"alter table {t} enable row level security", 1)[1]
        section = section.split("-- ====", 1)[0]
        assert "public.owns_job_program(" in section, f"{t} policies must use owns_job_program"


# ============================================================
# 11. Ordering / dependency correctness (mandatory)
# ============================================================


def test_language_sql_helpers_only_reference_already_created_tables():
    """`language sql` bodies are validated at CREATE time
    (check_function_bodies), so every table they read must be created
    earlier in the file. `language plpgsql` bodies may forward-reference."""
    created: set[str] = set()
    chunks = re.split(
        r"(create table if not exists \w+|create or replace function public\.\w+)", M040_C
    )
    idx = 0
    while idx < len(chunks):
        marker = chunks[idx]
        tm = re.match(r"create table if not exists (\w+)", marker)
        fm = re.match(r"create or replace function public\.(\w+)", marker)
        if tm:
            created.add(tm.group(1))
        elif fm:
            body = chunks[idx + 1] if idx + 1 < len(chunks) else ""
            head = body.split("$$", 1)[0]
            if re.search(r"\blanguage\s+sql\b", head, re.IGNORECASE):
                refs = set(re.findall(r"(?:from|join)\s+public\.(\w+)", body, re.IGNORECASE))
                unknown = refs - created - _PREEXISTING_TABLES
                assert not unknown, (
                    f"language-sql helper public.{fm.group(1)} references table(s) "
                    f"not yet created: {sorted(unknown)}"
                )
        idx += 1


def test_every_function_is_created_before_it_is_referenced_by_a_policy_or_trigger():
    for fn in ("owns_job_program", "student_can_access_job_program",
               "set_job_program_assignment_program_id",
               "set_job_training_enrollment_derived_ids",
               "prevent_job_training_enrollment_identity_change",
               "enforce_job_training_enrollment_transitions"):
        define_at = M040_C.find(f"create or replace function public.{fn}")
        assert define_at != -1, f"{fn} not defined"
        # every CALL site (execute procedure / policy predicate) must come
        # after the definition -- the `revoke`/`grant` lines and the
        # definition header are not calls (they lack a trailing `(`arg`)`).
        call_pattern = re.compile(
            rf"(execute procedure public\.{fn}\(|"
            rf"(?:using|with check)\s*\(\s*public\.{fn}\(|"
            rf"join public\.{fn}\()"
        )
        for m in call_pattern.finditer(M040_C):
            assert m.start() > define_at, f"{fn} is used before it is defined"


def test_rls_is_enabled_before_any_policy_on_each_table():
    for t in ALL_NEW_TABLES:
        enable_at = M040_C.lower().find(f"alter table {t} enable row level security")
        assert enable_at != -1, f"RLS not enabled on {t}"
        first_policy = M040_C.lower().find(f' on {t} for ')
        assert first_policy == -1 or first_policy > enable_at, (
            f"a policy on {t} appears before RLS is enabled"
        )


def test_triggers_are_created_after_their_table_and_function():
    for trig, tbl, fn in (
        ("job_programs_set_updated_at", "job_programs", "set_updated_at"),
        ("job_program_assignments_set_program_id", "job_program_assignments",
         "set_job_program_assignment_program_id"),
        ("job_training_enrollments_set_derived_ids", "job_training_enrollments",
         "set_job_training_enrollment_derived_ids"),
        ("job_training_enrollments_prevent_identity_change", "job_training_enrollments",
         "prevent_job_training_enrollment_identity_change"),
        ("job_training_enrollments_enforce_transitions", "job_training_enrollments",
         "enforce_job_training_enrollment_transitions"),
    ):
        trig_at = M040_C.find(f"create trigger {trig}")
        assert trig_at != -1, f"missing trigger {trig}"
        assert M040_C.find(f"create table if not exists {tbl}") < trig_at
        if fn != "set_updated_at":  # set_updated_at is pre-existing (012)
            assert M040_C.find(f"create or replace function public.{fn}") < trig_at


def test_all_trigger_typed_functions_revoke_from_public():
    for fn in ("set_job_program_assignment_program_id",
               "set_job_training_enrollment_derived_ids",
               "prevent_job_training_enrollment_identity_change",
               "enforce_job_training_enrollment_transitions"):
        assert f"revoke all on function public.{fn}() from public" in M040_C


def test_helper_functions_have_pinned_empty_search_path():
    for fn in ("owns_job_program", "student_can_access_job_program",
               "set_job_program_assignment_program_id",
               "set_job_training_enrollment_derived_ids",
               "prevent_job_training_enrollment_identity_change",
               "enforce_job_training_enrollment_transitions"):
        assert "set search_path = ''" in _fn_signature(fn), f"{fn} lacks a pinned search_path"
        assert "security definer" in _fn_signature(fn), f"{fn} is not SECURITY DEFINER"


# ============================================================
# 12. student_notifications CHECK widening: additive only
# ============================================================


def test_notification_type_widening_keeps_every_original_value_and_adds_job_training():
    m = re.search(
        r"add constraint student_notifications_type_check\s*\n\s*check \(type in \(([^)]*)\)\)",
        M040_C, re.DOTALL,
    )
    assert m, "widened type CHECK not found"
    values = {v.strip().strip("'") for v in m.group(1).replace("\n", " ").split(",") if v.strip()}
    assert values == {
        "APPLICATION_STATUS", "INTERVIEW", "ASSESSMENT", "LEARNING",
        "MENTORSHIP", "EVENT", "SYSTEM", "INTERNSHIP", "JOB_TRAINING",
    }


def test_notification_related_entity_widening_keeps_every_original_value():
    m = re.search(
        r"add constraint student_notifications_related_entity_type_check\s*\n\s*"
        r"check \(related_entity_type in \(([^)]*)\)\)",
        M040_C, re.DOTALL,
    )
    assert m, "widened related_entity_type CHECK not found"
    values = {v.strip().strip("'") for v in m.group(1).replace("\n", " ").split(",") if v.strip()}
    assert values == {
        "APPLICATION", "INTERVIEW", "ASSESSMENT", "LEARNING_RESOURCE",
        "MENTORSHIP", "EVENT", "INTERNSHIP_WORKSPACE", "JOB_TRAINING_ENROLLMENT",
    }


def test_notification_widening_resolves_the_constraint_name_defensively():
    assert M040_C.count("do $$") >= 2
    assert "array_length(con.conkey, 1) = 1" in M040_C
    assert "att.attname = 'type'" in M040_C
    assert "att.attname = 'related_entity_type'" in M040_C
    # the 2-column *_paired check is never named / dropped
    assert "student_notifications_related_entity_paired" not in M040_C


def test_notification_table_is_not_recreated_or_bare_altered():
    assert "create table if not exists student_notifications" not in M040_L
    assert "alter table public.student_notifications\n  drop constraint" not in M040_L
    assert "alter table student_notifications drop constraint" not in M040_L
    # the only two add-constraint statements in the file are the widenings
    added = re.findall(r"add constraint (\w+)", M040_C)
    assert set(added) == {
        "student_notifications_type_check",
        "student_notifications_related_entity_type_check",
    }, added


def test_no_notification_producer_is_wired_in_j1():
    # J1 is DB-only: no producer, no emit_* call, no service-role insert
    assert "emit_" not in M040_L
    assert "notification_producer" not in M040_L
    assert "insert into student_notifications" not in M040_L
    assert "insert into public.student_notifications" not in M040_L


# ============================================================
# 13. Malformed / invalid-state guards
# ============================================================


def test_migration_has_no_obvious_sql_syntax_smells():
    # balanced dollar-quote blocks
    assert M040_RAW.count("$$") % 2 == 0, "unbalanced $$ dollar-quote blocks"
    # every `create table if not exists` block is closed with `);`
    for t in ALL_NEW_TABLES:
        block = _table_block(M040_RAW, t)
        assert block.count("(") >= block.count(")") - 1  # rough balance inside the block
    # no accidental reference to the internship helper
    assert "student_can_access_program(" not in M040_C
    assert "owns_internship_program(" not in M040_C


def test_enrollment_cannot_be_created_for_a_missing_application():
    body = _fn_body("set_job_training_enrollment_derived_ids")
    assert "Referenced application does not exist." in body
    assert "23503" in body


def test_completed_and_revoked_columns_cannot_be_set_on_an_active_row():
    block = _table_block(M040_C, "job_training_enrollments")
    assert "completed_at is null or enrollment_status = 'COMPLETED'" in block
    assert "revoked_at is null and revoke_reason is null) or enrollment_status = 'REVOKED'" in block


def test_j1_migration_stays_pure_schema_no_app_logic_embedded():
    """Scope guard: the J1 DELIVERABLE is the migration + this schema
    suite. Later phases (J2 industry authoring, J3 student API +
    provisioning) add the app code that reads/writes this schema -- those
    are checked by their own suites, not here. What this test still
    guarantees is that migration 040 itself contains no application logic
    (no HTTP, no Python service imports, no provisioning code path)."""
    for smell in ("fastapi", "APIRouter", "require_student", "require_industry",
                  "build_user_client", "def provision_for_selection"):
        assert smell not in M040_C, f"040 migration must not embed app code: {smell!r}"
    # the migration and this schema suite are the J1 artifacts
    assert M040.is_file()
