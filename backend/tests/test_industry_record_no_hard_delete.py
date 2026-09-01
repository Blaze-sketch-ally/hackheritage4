"""Regression guard for the product decision recorded in
database/migrations/033_forbid_industry_record_deletes.sql (renumbered
from shatrajeet-feature's 027_forbid_industry_record_deletes.sql when the
Industry Portal's projects/training/workshops/mentorship/collaborations
modules were integrated on top of this repo's existing migration
sequence):

    HARD DELETE MUST NOT BE POSSIBLE FOR INDUSTRY RECORDS.

Adapted from the original two-part test (Phase 10 Industry record tables +
Phase 9 internships/jobs): the internships/jobs half is intentionally
dropped here. This repo's own Phase 9 recruitment surface is the unified
`opportunities` / `applications` model (024_opportunities_and_applications.sql),
not shatrajeet-feature's split `internships` / `jobs` tables -- those
tables, their services, and their own delete-lockdown migration
(028_forbid_internship_job_deletes.sql) were excluded entirely as
redundant/conflicting with the schema already in place, so there is
nothing here to test for them.

Independent halves checked, none of which needs a live database
(consistent with the rest of this suite -- see the note in
test_industry_collaborations.py: "RLS is the real access-control
boundary ... not independently re-verified against a live database
here"):

1. Application layer -- no Phase 10 Industry resource service ever
   issues a `.delete(` against its own record table. Removal is always a
   status transition (ARCHIVED for the postings; CANCELLED / COMPLETED /
   REJECTED for collaborations).

2. Migration layer -- 033 (industry_projects / industry_training /
   industry_workshops / industry_mentorship / industry_collaborations)
   replaces every `for all` owner-management policy on those record
   tables with scoped SELECT / INSERT / UPDATE policies and leaves NO
   delete-capable policy, so RLS denies DELETE for every `authenticated`
   caller.

This file is the only place these assertions live; the per-resource test
files (test_industry_projects.py, ...) are unchanged.
"""

import inspect
from pathlib import Path

from app.services import (
    industry_collaboration_service,
    industry_mentorship_service,
    industry_project_service,
    industry_training_service,
    industry_workshop_service,
)

# repo_root/backend/tests/this_file.py -> parents[2] == repo root
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
MIGRATION_033 = MIGRATIONS_DIR / "033_forbid_industry_record_deletes.sql"

# record table -> the `for all` owner policy name its original migration created
OWNER_MANAGE_POLICIES_033 = {
    "industry_projects": "Industry can manage their own projects",
    "industry_training": "Industry can manage their own training",
    "industry_workshops": "Industry can manage their own workshops",
    "industry_mentorship": "Industry can manage their own mentorship opportunities",
    "industry_collaborations": "Industry can manage their own collaborations",
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
        f"033 migration and the documented status-only lifecycle forbid: {offenders}"
    )


# ============================================================
# 2. Migration 033 -- Phase 10 Industry record tables
# ============================================================


def test_migration_033_exists():
    assert MIGRATION_033.is_file(), f"expected {MIGRATION_033} to exist"


def test_migration_033_drops_every_for_all_owner_policy():
    sql = MIGRATION_033.read_text(encoding="utf-8")
    for table, policy in OWNER_MANAGE_POLICIES_033.items():
        assert f'drop policy if exists "{policy}" on {table};' in sql, (
            f"033 must drop the `for all` owner policy {policy!r} on {table}"
        )


def test_migration_033_recreates_scoped_select_insert_update_policies():
    sql = MIGRATION_033.read_text(encoding="utf-8")
    for table in OWNER_MANAGE_POLICIES_033:
        for command in ("select", "insert", "update"):
            assert f"on {table} for {command}" in sql, (
                f"033 must define a `for {command}` policy on {table}"
            )
        assert f"on {table} for delete" not in sql, f"033 must not add a DELETE policy on {table}"
        assert f"on {table} for all" not in sql, f"033 must not leave a `for all` policy on {table}"


def test_migration_033_preserves_the_exact_ownership_predicate():
    sql_only = _sql_without_comments(MIGRATION_033)
    # 5 tables x (SELECT using + INSERT with check + UPDATE using + UPDATE with check) = 20
    assert sql_only.count(OWNERSHIP_PREDICATE) == 20, (
        "every scoped policy in 033 must carry the same ownership predicate that "
        "the dropped `for all` policy used, unchanged"
    )
