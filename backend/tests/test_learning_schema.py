"""Schema guard for the Phase 6A Student Learning database foundation
(database/migrations/033_learning_resources.sql +
database/seed/learning_resources.sql).

Same convention as tests/test_industry_record_no_hard_delete.py and
tests/test_role_and_skill_integrity.py: this suite has no live database,
so the DB-level guarantees are asserted by reading the migration SQL, and
the seed is checked for scope, not executed.

Phase 6A is DATABASE ONLY -- there is no FastAPI router / service / schema
for Learning yet (that is Phase 6B). These tests therefore assert nothing
about app code.
"""

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
SEED_DIR = Path(__file__).resolve().parents[2] / "database" / "seed"
MIGRATION_033 = MIGRATIONS_DIR / "033_learning_resources.sql"
SEED_033 = SEED_DIR / "learning_resources.sql"

LEARNING_TABLES = (
    "learning_resources",
    "learning_resource_skills",
    "student_learning_progress",
)


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sql_without_comments(path: Path) -> str:
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )


# ============================================================
# 1-4. Existence, numbering, tables
# ============================================================


def test_migration_033_exists():
    assert MIGRATION_033.is_file(), f"expected {MIGRATION_033} to exist"


def test_migration_numbering_stays_contiguous_unique_and_033_is_highest():
    numbers = sorted(int(p.name[:3]) for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert len(numbers) == len(set(numbers)), f"duplicate migration numbers: {numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap in migration numbering: {numbers}"
    assert 33 in numbers
    assert numbers[-1] == 33, "033 must currently be the highest-numbered migration"


def test_migration_033_does_not_reuse_a_historical_number_or_rename_anything():
    names = {p.name for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")}
    assert "033_learning_resources.sql" in names
    # 007_learning.sql (the original placeholder) is left exactly as-is,
    # not superseded in place.
    assert "007_learning.sql" in names
    assert "Not implemented yet" in _sql(MIGRATIONS_DIR / "007_learning.sql")
    # anchor historical files still present, unrenamed
    for anchor in ("003_skills.sql", "016_skill_gap.sql", "032_profile_role_immutability.sql"):
        assert anchor in names


def test_migration_033_creates_all_three_tables():
    sql = _sql_without_comments(MIGRATION_033).lower()
    for table in LEARNING_TABLES:
        assert f"create table if not exists {table}" in sql, f"033 must create {table}"


# ============================================================
# 5. learning_resources core fields
# ============================================================


def test_learning_resources_core_fields_and_constraints():
    sql = _sql_without_comments(MIGRATION_033)
    block = sql.split("create table if not exists learning_resources", 1)[1].split(");", 1)[0]
    assert "id uuid primary key default gen_random_uuid()" in block
    assert "title text not null" in block
    assert "url text not null" in block
    assert "description text" in block
    assert "provider text" in block
    assert "resource_type text not null check (resource_type in ('COURSE', 'ARTICLE', 'VIDEO', 'OTHER'))" in block
    assert "difficulty text check (difficulty in ('Beginner', 'Intermediate', 'Advanced', 'Expert'))" in block
    assert "estimated_minutes int check (estimated_minutes is null or estimated_minutes > 0)" in block
    assert "is_active boolean not null default true" in block
    assert "created_at timestamptz not null default now()" in block
    assert "updated_at timestamptz not null default now()" in block


# ============================================================
# 6-9. FKs and UNIQUE constraints
# ============================================================


def test_learning_resource_skills_references_learning_resources_and_skills_only():
    sql = _sql_without_comments(MIGRATION_033)
    block = sql.split("create table if not exists learning_resource_skills", 1)[1].split(");", 1)[0]
    assert "resource_id uuid not null references learning_resources (id) on delete cascade" in block
    assert "skill_id uuid not null references skills (id) on delete restrict" in block
    assert "target_level text check (target_level in ('Beginner', 'Intermediate', 'Advanced', 'Expert'))" in block
    # the mapping references the canonical skills catalog -- NOT student_skills / job_roles / career_roles
    assert "references student_skills" not in block
    assert "references job_roles" not in block
    assert "references career_roles" not in block


def test_student_learning_progress_references_profiles_and_learning_resources():
    sql = _sql_without_comments(MIGRATION_033)
    block = sql.split("create table if not exists student_learning_progress", 1)[1].split(");", 1)[0]
    assert "student_id uuid not null references profiles (id) on delete cascade" in block
    assert "resource_id uuid not null references learning_resources (id) on delete cascade" in block
    # progress is NOT skill evidence
    for forbidden in ("score", "skill_level", "is_verified", "verified_at", "assessment_id", "student_skill_id"):
        assert forbidden not in block, f"student_learning_progress must not have a {forbidden} column"


def test_unique_constraints_exist():
    sql = _sql_without_comments(MIGRATION_033)
    assert "unique (resource_id, skill_id)" in sql, "learning_resource_skills needs UNIQUE(resource_id, skill_id)"
    assert "unique (student_id, resource_id)" in sql, "student_learning_progress needs UNIQUE(student_id, resource_id)"


# ============================================================
# 10. progress status enum values
# ============================================================


def test_progress_status_check_has_the_three_mvp_values():
    sql = _sql_without_comments(MIGRATION_033)
    m = re.search(r"status text not null default 'SAVED' check \(status in \(([^)]*)\)\)", sql)
    assert m, "student_learning_progress.status CHECK not found in the expected shape"
    values = {v.strip().strip("'") for v in m.group(1).split(",")}
    assert values == {"SAVED", "IN_PROGRESS", "COMPLETED"}


def test_progress_completed_at_requires_completed_status():
    sql = _sql_without_comments(MIGRATION_033)
    assert "check (completed_at is null or status = 'COMPLETED')" in sql


# ============================================================
# 11-13. RLS
# ============================================================


def test_rls_enabled_on_all_three_tables():
    sql = _sql_without_comments(MIGRATION_033).lower()
    for table in LEARNING_TABLES:
        assert f"alter table {table} enable row level security" in sql, f"RLS must be enabled on {table}"


def test_catalog_tables_have_a_select_only_authenticated_policy_and_no_write_policy():
    sql = _sql_without_comments(MIGRATION_033)
    for table in ("learning_resources", "learning_resource_skills"):
        assert f"on {table} for select" in sql, f"{table} must have a SELECT policy"
        for verb in ("insert", "update", "delete"):
            assert f"on {table} for {verb}" not in sql, (
                f"{table} is a curated catalog -- it must not have a `for {verb}` policy for authenticated"
            )
        assert f"on {table} for all" not in sql
    # active-only exposure
    assert "using (is_active = true)" in sql
    assert "and r.is_active = true" in sql


def test_student_progress_policies_are_owner_only_and_role_guarded():
    sql = _sql_without_comments(MIGRATION_033)
    for verb in ("select", "insert", "update"):
        assert f"on student_learning_progress for {verb}" in sql, (
            f"student_learning_progress must have a `for {verb}` policy"
        )
    # no DELETE for the MVP
    assert "on student_learning_progress for delete" not in sql
    assert "on student_learning_progress for all" not in sql
    # ownership predicate, exact shape used by student_skills / student_target_job_role
    predicate = "auth.uid() = student_id and public.is_student(auth.uid())"
    # SELECT using + INSERT with check + UPDATE using + UPDATE with check == 4
    assert sql.count(predicate) == 4, (
        "every student_learning_progress policy must carry the owner+role predicate"
    )


# ============================================================
# 14-16. Isolation / safety
# ============================================================


def test_migration_033_does_not_reference_forbidden_tables():
    sql = _sql_without_comments(MIGRATION_033).lower()
    for forbidden in (
        "student_skills",
        "career_roles",
        "career_role_skill_requirements",
        "opportunities",
        "opportunity_skill_requirements",
        "industry_training",
        "job_roles",
        "job_role_skills",
        "assessments",
        "assessment_attempts",
        "portfolio_projects",
        "portfolio_certifications",
    ):
        assert forbidden not in sql, f"033 must not reference {forbidden}"


def test_migration_033_has_no_destructive_statements():
    sql = _sql_without_comments(MIGRATION_033).lower()
    assert "drop table" not in sql
    assert "truncate" not in sql
    # only DROPs allowed are the idempotent trigger/policy guards
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("drop "):
            assert s.startswith(("drop trigger if exists", "drop policy if exists")), (
                f"unexpected drop statement in 033: {s!r}"
            )
    # additive: it does not ALTER any pre-existing table (its own new
    # tables are created, never altered).
    for existing in ("profiles", "skills", "student_profiles"):
        assert f"alter table {existing} " not in sql, f"033 must not ALTER {existing}"


def test_migration_033_reuses_set_updated_at_without_redefining_it():
    sql = _sql_without_comments(MIGRATION_033)
    assert "execute procedure public.set_updated_at()" in sql
    assert "create or replace function public.set_updated_at" not in sql, (
        "set_updated_at() is defined in 012_student_profiles.sql -- 033 must reuse, not redefine it"
    )
    # idempotent trigger creation
    assert "drop trigger if exists learning_resources_set_updated_at on learning_resources" in sql
    assert "drop trigger if exists student_learning_progress_set_updated_at on student_learning_progress" in sql


def test_no_historical_migration_was_modified_by_this_phase():
    """007_learning.sql stays the placeholder it always was; 033 is the
    only file this phase adds to database/migrations/."""
    seven = _sql(MIGRATIONS_DIR / "007_learning.sql")
    assert "schema defined when the Learning feature is built" in seven
    assert "create table" not in seven.lower()


# ============================================================
# 17. Seed scope
# ============================================================


def test_seed_file_exists_and_targets_only_the_learning_schema():
    assert SEED_033.is_file(), f"expected {SEED_033} to exist"
    sql = _sql_without_comments(SEED_033).lower()
    assert "insert into learning_resources" in sql
    assert "insert into learning_resource_skills" in sql
    # resolves skills by NAME against the existing catalog -- no invented UUIDs
    assert "from skills where lower(name) = lower(" in sql
    assert "gen_random_uuid()" not in sql  # no hardcoded / generated resource ids in the seed
    # does not seed student-owned or unrelated data
    for forbidden in (
        "student_learning_progress",
        "student_skills",
        "job_roles",
        "career_roles",
        "assessments",
        "profiles",
    ):
        assert f"insert into {forbidden}" not in sql, f"seed must not write {forbidden}"
    # idempotent
    assert "on conflict do nothing" in sql


def test_seed_has_a_reasonable_number_of_resources():
    sql = _sql_without_comments(SEED_033)
    resources_block = sql.split("insert into learning_resources", 1)[1].split("on conflict", 1)[0]
    # each resource row is a "( ... 'COURSE'|'ARTICLE'|'VIDEO'|'OTHER' ... )" tuple
    row_count = len(re.findall(r"'(?:COURSE|ARTICLE|VIDEO|OTHER)'", resources_block))
    assert 15 <= row_count <= 30, f"expected ~15-20 curated resources, found {row_count}"
