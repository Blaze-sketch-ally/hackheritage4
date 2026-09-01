"""Regression guard for the product decision recorded in
database/migrations/027_forbid_industry_record_deletes.sql and
database/migrations/028_forbid_internship_job_deletes.sql:

    HARD DELETE MUST NOT BE POSSIBLE FOR INDUSTRY RECORDS.

Independent halves are checked, none of which needs a live database
(consistent with the rest of this suite -- see the note in
test_industry_collaborations.py: "RLS is the real access-control
boundary ... not independently re-verified against a live database
here"):

1. Application layer -- no Industry resource service ever issues a
   `.delete(` against its own *record* table. Removal is always a
   status transition (ARCHIVED for the postings; CANCELLED / COMPLETED
   / REJECTED for collaborations). The internship/job services DO
   delete their `*_skills` child rows -- that is the legitimate
   skill-list replacement path and must stay.

2. Migration layer -- 027 (industry_projects / industry_training /
   industry_workshops / industry_mentorship / industry_collaborations)
   and 028 (internships / jobs) replace every `for all` owner-management
   policy on those record tables with scoped SELECT / INSERT / UPDATE
   policies and leave NO delete-capable policy, so RLS denies DELETE
   for every `authenticated` caller. internship_skills / job_skills are
   deliberately left `for all`.

This file is the only place these assertions live; the per-resource
test files (test_industry_projects.py, test_internships.py, ...) are
unchanged.
"""

import inspect
from pathlib import Path

from app.services import (
    industry_collaboration_service,
    industry_mentorship_service,
    industry_project_service,
    industry_training_service,
    industry_workshop_service,
    internship_service,
    job_service,
)

# repo_root/backend/tests/this_file.py -> parents[2] == repo root
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
MIGRATION_027 = MIGRATIONS_DIR / "027_forbid_industry_record_deletes.sql"
MIGRATION_028 = MIGRATIONS_DIR / "028_forbid_internship_job_deletes.sql"

# record table -> the `for all` owner policy name its original migration created
OWNER_MANAGE_POLICIES_027 = {
    "industry_projects": "Industry can manage their own projects",
    "industry_training": "Industry can manage their own training",
    "industry_workshops": "Industry can manage their own workshops",
    "industry_mentorship": "Industry can manage their own mentorship opportunities",
    "industry_collaborations": "Industry can manage their own collaborations",
}
OWNER_MANAGE_POLICIES_028 = {
    "internships": "Industry can manage their own internships",
    "jobs": "Industry can manage their own jobs",
}

# Phase 10 services that must never issue ANY `.delete(` (single-table
# resources: no child rows to replace).
PHASE10_SERVICES = {
    "industry_projects": industry_project_service,
    "industry_training": industry_training_service,
    "industry_workshops": industry_workshop_service,
    "industry_mentorship": industry_mentorship_service,
    "industry_collaborations": industry_collaboration_service,
}

# service module -> its own record table (which must never be deleted,
# even though the service is allowed to delete its *_skills child rows).
RECORD_TABLE_FOR_SERVICE = {
    internship_service: "internships",
    job_service: "jobs",
}

OWNERSHIP_PREDICATE = "auth.uid() = industry_id and public.is_industry(auth.uid())"


def _sql_without_comments(path: Path) -> str:
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )


# ============================================================
# 1. Application layer
# ============================================================


def test_phase10_services_never_issue_any_delete():
    offenders = [
        name for name, module in PHASE10_SERVICES.items() if ".delete(" in inspect.getsource(module)
    ]
    assert not offenders, (
        "These Phase 10 Industry resource services issue a hard delete, which the "
        f"027 migration and the documented status-only lifecycle forbid: {offenders}"
    )


def test_internship_and_job_services_never_delete_their_own_record_table():
    """The internship/job services may delete *_skills child rows, but
    must never delete an `internships` / `jobs` row itself."""
    for module, table in RECORD_TABLE_FOR_SERVICE.items():
        source = inspect.getsource(module)
        assert f'table("{table}").delete(' not in source, (
            f"{module.__name__} must never hard-delete a {table} row -- the lifecycle "
            "is status-only (archive), and migration 028 removes the DELETE privilege."
        )


def test_internship_and_job_services_still_replace_skills_via_delete():
    """The legitimate skill-list replacement path must remain: each
    service deletes its *_skills child rows and re-inserts them."""
    internship_src = inspect.getsource(internship_service)
    job_src = inspect.getsource(job_service)
    assert 'table("internship_skills").delete()' in internship_src, (
        "internship_service._replace_skills must keep deleting internship_skills rows"
    )
    assert 'table("job_skills").delete()' in job_src, (
        "job_service._replace_skills must keep deleting job_skills rows"
    )


# ============================================================
# 2. Migration 027 -- Phase 10 Industry record tables
# ============================================================


def test_migration_027_exists():
    assert MIGRATION_027.is_file(), f"expected {MIGRATION_027} to exist"


def test_migration_027_drops_every_for_all_owner_policy():
    sql = MIGRATION_027.read_text(encoding="utf-8")
    for table, policy in OWNER_MANAGE_POLICIES_027.items():
        assert f'drop policy if exists "{policy}" on {table};' in sql, (
            f"027 must drop the `for all` owner policy {policy!r} on {table}"
        )


def test_migration_027_recreates_scoped_select_insert_update_policies():
    sql = MIGRATION_027.read_text(encoding="utf-8")
    for table in OWNER_MANAGE_POLICIES_027:
        for command in ("select", "insert", "update"):
            assert f"on {table} for {command}" in sql, (
                f"027 must define a `for {command}` policy on {table}"
            )
        assert f"on {table} for delete" not in sql, f"027 must not add a DELETE policy on {table}"
        assert f"on {table} for all" not in sql, f"027 must not leave a `for all` policy on {table}"


def test_migration_027_preserves_the_exact_ownership_predicate():
    sql_only = _sql_without_comments(MIGRATION_027)
    # 5 tables x (SELECT using + INSERT with check + UPDATE using + UPDATE with check) = 20
    assert sql_only.count(OWNERSHIP_PREDICATE) == 20, (
        "every scoped policy in 027 must carry the same ownership predicate that "
        "the dropped `for all` policy used, unchanged"
    )


# ============================================================
# 3. Migration 028 -- internships / jobs (Phase 9 posting tables)
# ============================================================


def test_migration_028_exists_in_a_contiguous_migration_sequence():
    """028 is the delete-protection migration for internships / jobs. It
    need not be the highest-numbered migration (later, unrelated
    migrations may follow -- e.g. 029 adds a read-only collaboration
    counterparty-name function), but it must still be present and the
    numbering must stay a gap-free, duplicate-free run so nothing was
    renumbered on top of it."""
    assert MIGRATION_028.is_file(), f"expected {MIGRATION_028} to exist"
    numbers = sorted(int(p.name[:3]) for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert 28 in numbers, "028 must remain in the migration sequence"
    assert len(numbers) == len(set(numbers)), f"duplicate migration numbers: {numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap in migration numbering: {numbers}"


def test_migration_028_drops_the_for_all_owner_policy_on_internships_and_jobs():
    sql = MIGRATION_028.read_text(encoding="utf-8")
    for table, policy in OWNER_MANAGE_POLICIES_028.items():
        assert f'drop policy if exists "{policy}" on {table};' in sql, (
            f"028 must drop the `for all` owner policy {policy!r} on {table}"
        )


def test_migration_028_recreates_scoped_select_insert_update_and_no_delete():
    sql = MIGRATION_028.read_text(encoding="utf-8")
    for table in OWNER_MANAGE_POLICIES_028:
        for command in ("select", "insert", "update"):
            assert f"on {table} for {command}" in sql, (
                f"028 must define a `for {command}` policy on {table}"
            )
        assert f"on {table} for delete" not in sql, f"028 must not add a DELETE policy on {table}"
        assert f"on {table} for all" not in sql, f"028 must not leave a `for all` policy on {table}"


def test_migration_028_preserves_the_exact_ownership_predicate():
    sql_only = _sql_without_comments(MIGRATION_028)
    # 2 tables x (SELECT using + INSERT with check + UPDATE using + UPDATE with check) = 8
    assert sql_only.count(OWNERSHIP_PREDICATE) == 8, (
        "every scoped policy in 028 must carry the same ownership predicate that "
        "the dropped `for all` policy used, unchanged"
    )


def test_migration_028_does_not_touch_the_skills_child_tables():
    """internship_skills / job_skills must be left exactly as 018/019
    defined them -- their owner `for all` policy is required by
    _replace_skills(). (Checked against real SQL, ignoring the `--`
    header, which does name those tables when explaining the exclusion.)"""
    sql_only = _sql_without_comments(MIGRATION_028)
    for child in ("internship_skills", "job_skills"):
        assert f"on {child} " not in sql_only, f"028 must not alter any policy on {child}"
    assert "manage skills" not in sql_only, (
        "028 must not drop or recreate the *_skills 'manage skills' policies"
    )
