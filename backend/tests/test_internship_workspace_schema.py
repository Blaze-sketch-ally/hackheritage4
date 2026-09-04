"""Schema guard for PHASE 1 of the Internship Workspace domain
(database/migrations/037_internship_program.sql,
038_internship_workspace.sql, 039_workspace_submissions_completion.sql).

Same convention as tests/test_learning_schema.py /
tests/test_industry_record_no_hard_delete.py /
tests/test_role_and_skill_integrity.py: this suite has no live database,
so every DB-level guarantee is asserted by reading the migration SQL.
Phase 1 is DATABASE ONLY -- there is no router / service / schema for the
Internship Workspace yet (later phases), so these tests assert nothing
about app code.
"""

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
M037 = MIGRATIONS_DIR / "037_internship_program.sql"
M038 = MIGRATIONS_DIR / "038_internship_workspace.sql"
M039 = MIGRATIONS_DIR / "039_workspace_submissions_completion.sql"

PROGRAM_TABLES = (
    "internship_programs",
    "program_modules",
    "module_items",
    "program_skills",
    "program_assignments",
)
WORKSPACE_TABLES = (
    "internship_workspaces",
    "workspace_skill_selections",
)
SUBMISSION_TABLES = (
    "workspace_submissions",
    "submission_reviews",
    "internship_completions",
    "internship_certificates",
    "stipend_disbursements",
)
ALL_NEW_TABLES = PROGRAM_TABLES + WORKSPACE_TABLES + SUBMISSION_TABLES


def _raw(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """SQL with comment-only lines stripped (keeps trailing inline code)."""
    return "\n".join(
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("--")
    )


M037_C = _code(M037)
M038_C = _code(M038)
M039_C = _code(M039)
M037_L = M037_C.lower()
M038_L = M038_C.lower()
M039_L = M039_C.lower()
ALL_C = f"{M037_C}\n{M038_C}\n{M039_C}"
ALL_L = ALL_C.lower()


def _table_block(sql: str, table: str) -> str:
    head = f"create table if not exists {table}"
    assert head in sql, f"missing: {head}"
    return sql.split(head, 1)[1].split(");", 1)[0]


def _check_set(sql: str, column: str) -> set[str]:
    """The value set of a `check (<column> in ('A', 'B', ...))` clause,
    tolerant of whitespace/newlines, returned in the SQL's own case."""
    m = re.search(
        rf"check\s*\(\s*{re.escape(column)}\s+in\s*\(([^)]*)\)\s*\)",
        sql, re.DOTALL | re.IGNORECASE,
    )
    assert m, f"no CHECK clause found for column {column!r}"
    return {v.strip().strip("'\"") for v in m.group(1).replace("\n", " ").split(",") if v.strip()}


# ============================================================
# 0. Migration-order / dependency correctness
# ============================================================
# `language sql` function bodies are validated at CREATE time
# (check_function_bodies), so every table a `language sql` helper's body
# references must be created earlier in the migration stream. `language
# plpgsql` bodies are not name-resolved until first execution, so they may
# forward-reference. FK targets, policy targets, trigger targets and
# `execute procedure` functions must all pre-exist.

# Objects guaranteed present from migrations 001-036 / the Supabase base.
_PREEXISTING_TABLES = {
    "profiles", "skills", "skill_categories", "student_skills", "internships",
    "internship_skills", "jobs", "job_skills", "applications", "interviews",
    "industry_profiles", "student_profiles", "student_notifications",
}
_PREEXISTING_FUNCS = {"set_updated_at", "is_student", "is_industry"}


def _created_before(sql: str, needle_a: str, needle_b: str) -> bool:
    ia, ib = sql.find(needle_a), sql.find(needle_b)
    return ia != -1 and ib != -1 and ia < ib


def test_owns_internship_program_helper_is_defined_after_its_table():
    # the exact failure this phase's live push hit: a `language sql` helper
    # created before internship_programs.
    assert _created_before(
        M037_C,
        "create table if not exists internship_programs",
        "create or replace function public.owns_internship_program",
    ), "owns_internship_program() must be created AFTER internship_programs"


def test_every_language_sql_helper_body_only_references_existing_tables():
    created: set[str] = set()
    for sql in (M037_C, M038_C, M039_C):
        # walk statements in order
        chunks = re.split(r"(create table if not exists \w+|create or replace function public\.\w+)", sql)
        # re.split keeps the delimiters as separate list items
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
                        f"language-sql helper public.{fm.group(1)} references "
                        f"table(s) not yet created: {sorted(unknown)}"
                    )
            idx += 1


def test_workspace_child_policies_come_after_the_ownership_helpers():
    # 038: student_owns_workspace / industry_owns_workspace must be defined
    # before any policy that calls them.
    for helper in ("student_owns_workspace", "industry_owns_workspace",
                   "student_can_access_program"):
        assert _created_before(
            M038_C,
            f"create or replace function public.{helper}",
            f"public.{helper}(",
        ) or M038_C.count(f"public.{helper}(") == 1, (
            f"{helper} is used before it is defined in 038"
        )
    # and the helpers themselves come after the workspace table they read
    assert _created_before(
        M038_C,
        "create table if not exists internship_workspaces",
        "create or replace function public.student_owns_workspace",
    )


def test_verify_function_is_defined_after_the_certificate_table():
    assert _created_before(
        M039_C,
        "create table if not exists internship_certificates",
        "create or replace function public.verify_internship_certificate",
    )


# ============================================================
# 1. Existence, numbering, historical integrity
# ============================================================


def test_all_three_migrations_exist():
    for p in (M037, M038, M039):
        assert p.is_file(), f"expected {p} to exist"


def test_migration_numbering_stays_contiguous_and_unique():
    numbers = sorted(int(p.name[:3]) for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert len(numbers) == len(set(numbers)), f"duplicate migration numbers: {numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap in numbering: {numbers}"
    assert {37, 38, 39}.issubset(set(numbers))


def test_no_historical_migration_was_modified():
    """Phase 1 adds exactly three files and edits none of 001-036."""
    names = {p.name for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")}
    for anchor, marker in (
        ("018_internships.sql", "create table if not exists internships"),
        ("020_applications.sql", "create table applications"),
        ("035_student_notifications.sql", "create table if not exists student_notifications"),
        ("003_skills.sql", "create table if not exists skills"),
        ("015_assessment_verification.sql", "score_assessment_attempt"),
    ):
        assert anchor in names
        assert marker in _raw(MIGRATIONS_DIR / anchor)
    assert "not implemented yet" in _raw(MIGRATIONS_DIR / "007_learning.sql").lower()


def test_phase1_migrations_are_additive_and_non_destructive():
    for name, sql in (("037", M037_L), ("038", M038_L), ("039", M039_L)):
        assert "drop table" not in sql, f"{name} must not drop a table"
        assert "truncate" not in sql, f"{name} must not truncate"
        for line in sql.splitlines():
            s = line.strip()
            if s.startswith("drop ") and "execute format(" not in s:
                assert s.startswith(("drop policy if exists", "drop trigger if exists")), (
                    f"{name}: unexpected drop statement: {s!r}"
                )
    # The ONLY alter-table on a pre-existing table is the additive
    # student_notifications CHECK widening, isolated in 039.
    assert "alter table public.student_notifications" in M039_L
    for existing in ("applications", "internships", "profiles", "skills", "student_skills",
                     "assessments", "learning_resources", "industry_training"):
        assert f"alter table {existing} " not in ALL_L
        assert f"alter table public.{existing} " not in ALL_L


def test_shared_helpers_are_reused_not_redefined():
    for sql in (M037_C, M038_C, M039_C):
        assert "create or replace function public.set_updated_at" not in sql
        assert "create or replace function public.is_student" not in sql
        assert "create or replace function public.is_industry" not in sql
    assert "execute procedure public.set_updated_at()" in M037_C
    assert "public.is_student(auth.uid())" in M038_C
    assert "public.is_industry(auth.uid())" in M037_C


# ============================================================
# 2. Tables exist, RLS enabled
# ============================================================


def test_all_twelve_tables_are_created():
    for t in PROGRAM_TABLES:
        assert f"create table if not exists {t}" in M037_L
    for t in WORKSPACE_TABLES:
        assert f"create table if not exists {t}" in M038_L
    for t in SUBMISSION_TABLES:
        assert f"create table if not exists {t}" in M039_L


def test_rls_enabled_on_every_new_table():
    for t in PROGRAM_TABLES:
        assert f"alter table {t} enable row level security" in M037_L
    for t in WORKSPACE_TABLES:
        assert f"alter table {t} enable row level security" in M038_L
    for t in SUBMISSION_TABLES:
        assert f"alter table {t} enable row level security" in M039_L


# ============================================================
# 3. Approved architecture: program is 1:1 with internship
# ============================================================


def test_internship_program_is_strictly_one_per_internship():
    block = _table_block(M037_L, "internship_programs")
    assert "internship_id uuid not null references internships (id) on delete cascade" in block
    assert "unique (internship_id)" in block


def test_program_status_lifecycle_values():
    assert _check_set(_table_block(M037_C, "internship_programs"), "status") == {
        "DRAFT", "PUBLISHED", "ARCHIVED"
    }


def test_program_does_not_duplicate_recruitment_fields():
    block = _table_block(M037_L, "internship_programs")
    for recruitment_only in ("stipend_amount", "openings", "application_deadline", "industry_id"):
        assert recruitment_only not in block, (
            f"internship_programs must not copy internships.{recruitment_only}"
        )


# ============================================================
# 4. Program content model
# ============================================================


def test_module_items_are_one_normalized_table_with_a_type_check():
    block = _table_block(M037_C, "module_items")
    assert "module_id uuid not null references program_modules (id) on delete cascade" in block.lower()
    assert _check_set(block, "item_type") == {"VIDEO", "PDF", "LINK", "TEXT"}
    assert "module_items_content_matches_type" in block


def test_program_skills_reference_canonical_catalog_with_required_optional():
    block = _table_block(M037_C, "program_skills")
    bl = block.lower()
    assert "program_id uuid not null references internship_programs (id) on delete cascade" in bl
    assert "skill_id uuid not null references skills (id) on delete restrict" in bl
    assert _check_set(block, "requirement") == {"REQUIRED", "OPTIONAL"}
    assert "unique (program_id, skill_id)" in bl


def test_program_assignments_is_one_table_not_three():
    for forbidden in ("create table if not exists assignments",
                      "create table if not exists quizzes",
                      "create table if not exists projects"):
        assert forbidden not in ALL_L
    assert _check_set(_table_block(M037_C, "program_assignments"), "assignment_type") == {
        "ASSIGNMENT", "QUIZ", "PROJECT"
    }


def test_program_assignments_supports_project_and_quiz_fields():
    block = _table_block(M037_C, "program_assignments")
    bl = block.lower()
    for col in ("is_required", "is_published", "linked_skill_id", "order_index",
                "due_offset_days", "submission_kind", "repo_required", "live_url_expected"):
        assert col in bl, f"program_assignments missing {col}"
    assert _check_set(block, "submission_kind") == {"LINK", "REPO", "FILE", "TEXT", "MIXED"}
    assert "program_assignments_repo_kind_consistent" in block
    assert "linked_skill_id uuid references skills (id) on delete set null" in bl
    assert "set_program_assignment_program_id" in M037_C


# ============================================================
# 5. Program RLS: industry ownership through the internship
# ============================================================


def test_program_ownership_resolves_through_internship_ownership():
    assert "create or replace function public.owns_internship_program" in M037_C
    assert "join public.internships intr on intr.id = prog.internship_id" in M037_C
    assert "intr.industry_id = auth.uid()" in M037_C
    assert "public.is_industry(auth.uid())" in M037_C


def test_program_record_tables_have_no_delete_or_all_policy():
    for t in ("internship_programs", "program_modules", "module_items", "program_assignments"):
        assert f"on {t} for delete" not in M037_L, f"{t} must not allow hard delete"
        assert f"on {t} for all" not in M037_L, f"{t} must not have a `for all` policy"
        for verb in ("select", "insert", "update"):
            assert f"on {t} for {verb}" in M037_L, f"{t} needs a `for {verb}` policy"


def test_program_skills_is_a_replaceable_child_table():
    # matches internship_skills: `for all` owner policy so _replace_skills can DELETE+INSERT
    assert "on program_skills for all" in M037_L


def test_students_do_not_get_program_policies_in_037():
    assert "student_can_access_program" not in M037_C
    assert '"students can' not in M037_L


# ============================================================
# 6. Workspace: identity, uniqueness, lifecycle
# ============================================================


def test_workspace_is_one_per_application_and_keyed_correctly():
    block = _table_block(M038_L, "internship_workspaces")
    assert "application_id uuid not null references applications (id) on delete cascade" in block
    assert "student_id uuid not null references profiles (id) on delete cascade" in block
    assert "industry_id uuid not null references profiles (id) on delete restrict" in block
    assert "internship_id uuid not null references internships (id) on delete restrict" in block
    assert "unique (application_id)" in block


def test_workspace_work_mode_snapshot_is_remote_or_hybrid_only():
    assert _check_set(_table_block(M038_C, "internship_workspaces"), "work_mode") == {
        "REMOTE", "HYBRID"
    }


def test_workspace_status_uses_the_approved_lifecycle():
    assert _check_set(_table_block(M038_C, "internship_workspaces"), "workspace_status") == {
        "PENDING_ACCEPTANCE", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "DECLINED", "RESCINDED"
    }


def test_no_new_application_status_and_no_internship_offers_table():
    assert "internship_offers" not in ALL_L
    # applications is never altered and its status CHECK is never touched
    assert "alter table applications" not in ALL_L
    assert "alter table public.applications" not in ALL_L
    # the only re-added CHECK constraints in the whole phase are the two
    # student_notifications widenings
    added = re.findall(r"add constraint (\w+)", ALL_C)
    assert set(added) == {
        "student_notifications_type_check",
        "student_notifications_related_entity_type_check",
    }, added


def test_workspace_identity_and_transition_guards_exist():
    assert "create or replace function public.set_workspace_derived_ids" in M038_C
    assert "create or replace function public.prevent_workspace_identity_change" in M038_C
    assert "create or replace function public.enforce_workspace_status_transitions" in M038_C
    assert "v_app_status <> 'SELECTED'" in M038_C
    assert "v_work_mode not in ('REMOTE', 'HYBRID')" in M038_C
    for col in ("application_id", "student_id", "industry_id", "internship_id", "work_mode"):
        assert f"new.{col} is distinct from old.{col}" in M038_C
    assert "current_setting('role', true) = 'service_role'" in M038_C
    assert "new.workspace_status in ('ACCEPTED', 'DECLINED')" in M038_C


def test_workspace_has_no_delete_policy():
    assert "on internship_workspaces for delete" not in M038_L
    assert "on internship_workspaces for all" not in M038_L
    for verb in ("select", "insert", "update"):
        assert f"on internship_workspaces for {verb}" in M038_L


# ============================================================
# 7. Workspace RLS: isolation, and NOT dependent on internships.status
# ============================================================


def test_workspace_rls_never_depends_on_internship_published_status():
    body = M038_C.split("function public.student_can_access_program", 1)[1].split("$$", 2)[1].lower()
    assert "w.student_id = auth.uid()" in body
    assert "w.workspace_status not in ('declined', 'rescinded')" in body
    assert "prog.status = 'published'" in body
    # never gates on the internship posting's own status
    assert "'closed'" not in body
    assert "'archived'" not in body
    assert "i.status" not in body and "intr.status" not in body


def test_workspace_child_isolation_uses_ownership_helpers():
    assert "create or replace function public.student_owns_workspace" in M038_C
    assert "create or replace function public.industry_owns_workspace" in M038_C
    assert "w.student_id = auth.uid()" in M038_C
    assert "w.industry_id = auth.uid()" in M038_C


def test_student_program_content_policies_are_added_in_038_and_require_published():
    for t in ("internship_programs", "program_modules", "module_items",
              "program_assignments", "program_skills"):
        assert f"on {t} for select" in M038_L, f"038 must add a student SELECT policy on {t}"
    assert "program_modules.is_published = true" in M038_C
    assert "module_items.is_published = true" in M038_C
    assert "program_assignments.is_published = true" in M038_C
    assert "public.student_can_access_program" in M038_C


# ============================================================
# 8. Skill selection does NOT touch student_skills verification
# ============================================================


def test_phase1_never_references_student_skills_or_verification():
    for name, sql in (("037", M037_L), ("038", M038_L), ("039", M039_L)):
        assert "student_skills" not in sql, f"{name} must not reference student_skills"
        assert "is_verified" not in sql, f"{name} must not touch skill verification"
        assert "score_assessment_attempt" not in sql
        assert "prevent_self_skill_verification" not in sql


def test_workspace_skill_selections_shape_and_uniqueness():
    block = _table_block(M038_L, "workspace_skill_selections")
    assert "workspace_id uuid not null references internship_workspaces (id) on delete cascade" in block
    assert "skill_id uuid not null references skills (id) on delete restrict" in block
    assert "unique (workspace_id, skill_id)" in block
    assert "on workspace_skill_selections for update" not in M038_L
    assert "on workspace_skill_selections for delete" in M038_L
    assert "ps.requirement = 'OPTIONAL'" in M038_C


# ============================================================
# 9. Work-mode protection trigger (in 038, where internship_workspaces exists)
# ============================================================


def test_workmode_protection_trigger_blocks_only_the_orphaning_transition():
    assert "create or replace function public.prevent_ineligible_workmode_change" in M038_C
    assert "before update on internships" in M038_C
    body = M038_C.split("function public.prevent_ineligible_workmode_change", 1)[1].split("$$", 2)[1]
    assert "old.work_mode in ('REMOTE', 'HYBRID')" in body
    assert "new.work_mode not in ('REMOTE', 'HYBRID')" in body
    assert "w.workspace_status not in ('DECLINED', 'RESCINDED')" in body
    assert "current_setting('role', true) = 'service_role'" in body


# ============================================================
# 10. Submissions: append-only, constrained statuses
# ============================================================


def test_submissions_are_append_only_with_attempt_numbers():
    block = _table_block(M039_C, "workspace_submissions")
    bl = block.lower()
    assert "attempt_number int not null check (attempt_number >= 1)" in bl
    assert "unique (workspace_id, assignment_id, attempt_number)" in bl
    assert _check_set(block, "submission_status") == {
        "SUBMITTED", "UNDER_REVIEW", "REVISION_REQUESTED", "ACCEPTED", "REJECTED"
    }
    assert "RESUBMITTED" not in M039_C
    assert "'DRAFT'" not in block
    assert "create or replace function public.prevent_workspace_submission_content_change" in M039_C
    assert "a submission is append-only" in M039_L
    assert "on workspace_submissions for delete" not in M039_L


def test_submission_attempt_number_is_server_assigned():
    assert "create or replace function public.set_workspace_submission_attempt_number" in M039_C
    assert "coalesce(max(s.attempt_number), 0) + 1" in M039_C
    assert "v_prev_status not in ('REVISION_REQUESTED', 'REJECTED')" in M039_C


def test_submission_reviews_are_the_source_of_truth_and_immutable():
    block = _table_block(M039_C, "submission_reviews")
    bl = block.lower()
    assert "submission_id uuid not null references workspace_submissions (id) on delete cascade" in bl
    assert "reviewer_id uuid not null references profiles (id) on delete restrict" in bl
    assert _check_set(block, "verdict") == {"ACCEPTED", "REVISION_REQUESTED", "REJECTED"}
    assert "new.reviewer_id := auth.uid()" in M039_C
    assert "on submission_reviews for update" not in M039_L
    assert "on submission_reviews for delete" not in M039_L
    assert "on submission_reviews for select" in M039_L
    assert "on submission_reviews for insert" in M039_L


def test_phase6_needs_no_new_migration_submission_reviews_already_has_the_columns():
    """The Phase 6 review flow (verdict + feedback + score, append-only, one
    row per decision, reviewer forced to auth.uid()) is fully served by the
    submission_reviews table + trigger + RLS already in migration 039. No
    new migration exists, and 039 itself is untouched."""
    block = _table_block(M039_C, "submission_reviews").lower()
    assert "feedback text" in block
    assert "score numeric(6, 2) check (score is null or score >= 0)" in block
    # the industry insert policy is scoped to the internship owner
    assert "public.industry_owns_workspace(s.workspace_id)" in M039_C
    # no Phase 6 migration was added (040+ does not exist)
    later = [int(p.name[:3]) for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql") if int(p.name[:3]) >= 40]
    assert later == [], f"unexpected post-039 migration(s): {later}"


# ============================================================
# 11. Completion: explicit verification, never automatic
# ============================================================


def test_completion_is_one_per_workspace_and_needs_explicit_verification():
    block = _table_block(M039_C, "internship_completions")
    bl = block.lower()
    assert "workspace_id uuid not null references internship_workspaces (id) on delete cascade" in bl
    assert "unique (workspace_id)" in bl
    assert _check_set(block, "completion_status") == {"REQUIREMENTS_MET", "COMPLETED"}
    assert _check_set(block, "outcome") == {"PASS", "FAIL"}
    assert "internship_completions_completed_requires_verification" in block
    assert "new.verified_by := auth.uid()" in M039_C


# ============================================================
# 12. Certificate: 1:1, immutable, self-contained, server number
# ============================================================


def test_certificate_is_one_to_one_with_a_passed_completion():
    block = _table_block(M039_C, "internship_certificates")
    bl = block.lower()
    assert "completion_id uuid not null references internship_completions (id) on delete restrict" in bl
    assert "unique (completion_id)" in bl
    assert "certificate_number text not null" in bl
    assert "unique (certificate_number)" in bl
    assert "details jsonb not null default '{}'::jsonb" in bl
    assert "pdf_url text" in bl
    assert "a certificate can only be issued for a passed internship completion" in M039_L


def test_certificate_number_format_is_server_generated():
    assert "create or replace function public.generate_internship_certificate_number" in M039_C
    assert "'AIC-INT-' || to_char(now(), 'YYYY') || '-'" in M039_C
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" in M039_C
    assert "for v_i in 1..13 loop" in M039_C
    assert "gen_random_bytes" not in M039_C
    assert "revoke all on function public.generate_internship_certificate_number() from authenticated" in M039_C


def test_certificate_is_immutable_except_pdf_and_revocation():
    assert "create or replace function public.prevent_internship_certificate_tamper" in M039_C
    for frozen in ("completion_id", "certificate_number", "issued_at", "details",
                   "student_id", "industry_id", "internship_id"):
        assert f"new.{frozen} is distinct from old.{frozen}" in M039_C
    assert "on internship_certificates for delete" not in M039_L


# ============================================================
# 13. Certificate verification function: safe public projection only
# ============================================================


def test_verify_function_is_security_definer_with_pinned_search_path():
    after = M039_C.split("create or replace function public.verify_internship_certificate", 1)[1]
    signature = after.split("$$", 1)[0]
    body = after.split("$$", 2)[1]
    assert "security definer" in signature
    assert "set search_path = ''" in signature
    cols = re.search(r"returns table \(([^)]*)\)", signature, re.DOTALL).group(1)
    returned = {ln.strip().split()[0] for ln in cols.strip().splitlines() if ln.strip()}
    assert returned == {"certificate_number", "student_name", "company_name",
                        "title", "issued_at", "status"}
    # Only the SELECT projection (between `select` and `from`) is returned to
    # the caller -- JOIN ON clauses may reference private keys internally.
    projection = body.lower().split("select", 1)[1].split("from public.internship_certificates", 1)[0]
    for leak in ("email", "avatar_url", "c.id", "c.student_id", "c.industry_id",
                 "c.workspace_id", "c.internship_id", "c.completion_id",
                 "application_id", "stipend", "submission", "c.notes"):
        assert leak not in projection, f"verify_internship_certificate returns {leak!r}"
    # and it never touches the private per-student tables at all
    for private in ("workspace_submissions", "submission_reviews",
                    "stipend_disbursements", "internship_completions"):
        assert private not in body.lower()


def test_verify_function_is_granted_to_anon_for_public_verification():
    assert "revoke all on function public.verify_internship_certificate(text) from public" in M039_C
    assert ("grant execute on function public.verify_internship_certificate(text) "
            "to anon, authenticated") in M039_C
    # no table-level anon/public policy on internship_certificates
    cert_rls = M039_L.split("alter table internship_certificates enable row level security", 1)[1]
    cert_rls = cert_rls.split("stipend_disbursements", 1)[0]
    assert "to anon" not in cert_rls
    assert "to public" not in cert_rls


# ============================================================
# 14. Stipend: record-keeping, terminal states, student read-only
# ============================================================


def test_stipend_is_one_per_workspace_with_a_terminal_lifecycle():
    block = _table_block(M039_C, "stipend_disbursements")
    bl = block.lower()
    assert "workspace_id uuid not null references internship_workspaces (id) on delete cascade" in bl
    assert "unique (workspace_id)" in bl
    assert _check_set(block, "disbursement_status") == {"PENDING", "APPROVED", "RELEASED", "CANCELLED"}
    assert "a released or cancelled stipend record cannot change state" in M039_L
    assert "old.disbursement_status in ('RELEASED', 'CANCELLED')" in M039_C


def test_stipend_student_is_read_only():
    block = M039_L.split("alter table stipend_disbursements enable row level security", 1)[1]
    block = block.split("public certificate verification", 1)[0]
    assert "students can view their own stipend record" in block
    for student_write in ("students can create", "students can update", "students can add",
                          "students can manage", "students can release"):
        assert student_write not in block, f"student must not: {student_write}"


# ============================================================
# 15. student_notifications CHECK widening: additive only
# ============================================================


def test_notification_type_widening_keeps_every_original_value():
    m = re.search(
        r"add constraint student_notifications_type_check\s*\n\s*check \(type in \(([^)]*)\)\)",
        M039_C, re.DOTALL,
    )
    assert m, "widened type CHECK not found"
    values = {v.strip().strip("'") for v in m.group(1).replace("\n", " ").split(",") if v.strip()}
    assert values == {
        "APPLICATION_STATUS", "INTERVIEW", "ASSESSMENT", "LEARNING",
        "MENTORSHIP", "EVENT", "SYSTEM", "INTERNSHIP",
    }


def test_notification_related_entity_widening_keeps_every_original_value():
    m = re.search(
        r"add constraint student_notifications_related_entity_type_check\s*\n\s*"
        r"check \(related_entity_type in \(([^)]*)\)\)",
        M039_C, re.DOTALL,
    )
    assert m, "widened related_entity_type CHECK not found"
    values = {v.strip().strip("'") for v in m.group(1).replace("\n", " ").split(",") if v.strip()}
    assert values == {
        "APPLICATION", "INTERVIEW", "ASSESSMENT", "LEARNING_RESOURCE",
        "MENTORSHIP", "EVENT", "INTERNSHIP_WORKSPACE",
    }


def test_notification_widening_resolves_the_constraint_name_defensively():
    assert M039_C.count("do $$") >= 2
    assert "array_length(con.conkey, 1) = 1" in M039_C
    assert "att.attname = 'type'" in M039_C
    assert "att.attname = 'related_entity_type'" in M039_C
    # the 2-column *_paired check is never named / dropped
    assert "student_notifications_related_entity_paired" not in M039_C


def test_notification_table_is_not_recreated():
    tail = M039_L.split("student_notifications", 1)[1]
    assert "create table" not in tail
    # the constraint swap only ever happens inside a guarded DO block via
    # `execute format(... drop constraint %i ...)` -- never a bare top-level
    # `alter table ... drop constraint`
    assert "alter table public.student_notifications\n  drop constraint" not in M039_L
    assert "alter table student_notifications drop constraint" not in M039_L
