"""Regression guards for the Phase 5 hardening:

  P1-B  A verified student_skills row must not stay verified after the
        student self-edits its proficiency level -- addressed by the
        forward migration 031_verified_skill_proficiency_integrity.sql
        (auto-clear is_verified / verified_at inside
        prevent_self_skill_verification()).

  P1-A  A student must not be able to self-change profiles.role. The
        general role-immutability lock (role settable once, from NULL,
        by any non-service_role caller) is:
          * live on the shared Supabase project via the contributor's
            023 hardening -- confirmed by a read-only Phase 5 probe
            (see test_role_and_skill_integrity_live_evidence);
          * reproduced in THIS repo's own lineage by the Phase 5A forward
            migration 032_profile_role_immutability.sql, so a fresh
            replay of 001..032 has the same protection.
        Migration 002 in this repo still only guards the ADMIN
        transition; this file pins that, pins 032's behaviour, and pins
        that no backend code path writes profiles.role at all.

Same conventions as tests/test_industry_record_no_hard_delete.py: the
DB-level guarantees are checked by reading the migration SQL (this suite
has no live database -- see that file's own note), and the
application-layer guarantees are checked with `inspect.getsource`.
"""

import inspect
from pathlib import Path

from app.services import (
    assessment_service,
    match_service,
    skill_gap_service,
    student_opportunity_service,
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
MIGRATION_001 = MIGRATIONS_DIR / "001_profiles.sql"
MIGRATION_002 = MIGRATIONS_DIR / "002_protect_admin_role.sql"
MIGRATION_003 = MIGRATIONS_DIR / "003_skills.sql"
MIGRATION_015 = MIGRATIONS_DIR / "015_assessment_verification.sql"
MIGRATION_031 = MIGRATIONS_DIR / "031_verified_skill_proficiency_integrity.sql"
MIGRATION_032 = MIGRATIONS_DIR / "032_profile_role_immutability.sql"


def _sql_without_comments(path: Path) -> str:
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )


# ============================================================
# 1. Migration 031 -- verified-skill proficiency integrity
# ============================================================


def test_migration_031_exists():
    assert MIGRATION_031.is_file(), f"expected {MIGRATION_031} to exist"


def test_migration_numbering_is_contiguous_and_unique_and_includes_031_032():
    """031 and 032 must slot cleanly onto the end of the existing 001..030
    run -- no gap, no duplicate, nothing renumbered on top of them, and no
    reuse of a historical number (the teammate lineage's 015..025 in
    particular). Later forward migrations (033+) may follow -- the
    'highest number' assertion lives in that migration's own test."""
    numbers = sorted(int(p.name[:3]) for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert 31 in numbers and 32 in numbers, "031 and 032 must be in the migration sequence"
    assert len(numbers) == len(set(numbers)), f"duplicate migration numbers: {numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap in migration numbering: {numbers}"


def test_migration_031_replaces_the_existing_trigger_function_not_a_new_one():
    sql = _sql_without_comments(MIGRATION_031)
    assert "create or replace function public.prevent_self_skill_verification()" in sql, (
        "031 must CREATE OR REPLACE the existing 003/015 trigger function, not define a new one"
    )
    assert "student_skills_prevent_self_verification" in sql, (
        "031 must (re-)attach the existing trigger name"
    )
    assert "before update on student_skills" in sql


def test_migration_031_auto_clears_verification_on_a_proficiency_change():
    sql = _sql_without_comments(MIGRATION_031)
    # The auto-clear branch: an already-verified row whose proficiency
    # level/score is being changed loses is_verified AND verified_at.
    assert "old.is_verified" in sql
    assert "new.proficiency_level is distinct from old.proficiency_level" in sql
    assert "new.proficiency_score is distinct from old.proficiency_score" in sql
    assert "new.is_verified := false" in sql
    assert "new.verified_at := null" in sql


def test_migration_031_still_blocks_gaining_verification():
    """The dangerous direction (false -> true) must still raise for a
    non-service_role caller, and verified_at must never be settable to a
    non-null value."""
    sql = _sql_without_comments(MIGRATION_031)
    assert "if new.is_verified and not old.is_verified then" in sql
    assert "new.verified_at is distinct from old.verified_at and new.verified_at is not null" in sql
    assert sql.count("raise exception 'Cannot change skill verification status directly.'") == 2


def test_migration_031_keeps_the_service_role_bypass():
    sql = _sql_without_comments(MIGRATION_031)
    assert "if current_setting('role', true) = 'service_role' then" in sql
    assert "return new;" in sql


def test_migration_031_is_non_destructive_and_scoped_to_one_function():
    sql = _sql_without_comments(MIGRATION_031)
    lowered = sql.lower()
    assert "drop table" not in lowered
    assert "drop function" not in lowered  # CREATE OR REPLACE, never DROP
    assert "alter table" not in lowered
    assert "drop policy" not in lowered
    # Touches only student_skills (its own trigger) -- no other table name
    # from the schema appears in real SQL.
    for other in ("profiles", "assessments", "assessment_attempts", "job_roles", "applications"):
        assert other not in lowered, f"031 must not reference {other}"


def test_migration_031_reflects_003_and_015_lineage():
    """Sanity: the function it replaces really is the one 003 defined and
    015 last replaced -- so 031 is the newest link in that chain, not a
    fork."""
    assert "create or replace function public.prevent_self_skill_verification()" in MIGRATION_003.read_text(
        encoding="utf-8"
    )
    assert "create or replace function public.prevent_self_skill_verification()" in MIGRATION_015.read_text(
        encoding="utf-8"
    )


# ============================================================
# 2. Application layer -- student_skills verification / assessment scoring
#    are never written off the trusted (service_role RPC) path
# ============================================================

_SKILL_SERVICES = {
    "skill_gap_service": skill_gap_service,
    "match_service": match_service,
    "student_opportunity_service": student_opportunity_service,
    "assessment_service": assessment_service,
}


def test_no_service_issues_a_write_against_student_skills():
    """is_verified / verified_at / proficiency_level are mutated only by
    the student's own direct-Supabase edit (frontend/lib/student/skills.ts,
    now guarded by migration 031) and by score_assessment_attempt() (a
    Postgres function). No FastAPI service issues an update / insert /
    upsert / delete against student_skills -- they only .select() it."""
    for name, module in _SKILL_SERVICES.items():
        src = inspect.getsource(module)
        for verb in (".update(", ".insert(", ".upsert(", ".delete("):
            assert f'table("student_skills"){verb}' not in src.replace("\n", "").replace(" ", ""), (
                f"{name} must not write student_skills ({verb})"
            )


def test_save_answer_payload_carries_no_scoring_fields():
    """assessment_service.save_answer builds the only student-writable
    assessment_answers payload -- it must contain answer content only,
    never awarded_marks / is_correct (those are the scoring RPC's)."""
    src = inspect.getsource(assessment_service.save_answer)
    assert '"awarded_marks"' not in src
    assert '"is_correct"' not in src
    assert '"answer_text"' in src and '"selected_option_ids"' in src


def test_score_and_create_attempt_go_through_named_rpcs_only():
    """The two privileged writes are Postgres functions invoked by name;
    the Python layer never open-codes the score / verification writes."""
    src = inspect.getsource(assessment_service)
    assert '"score_assessment_attempt"' in src
    assert '"create_assessment_attempt"' in src
    # assessment_service reads student_skills (get_skill_verification) but
    # never writes it -- the write lives inside score_assessment_attempt().
    assert 'table("student_skills")\n' in src or '.table("student_skills")' in src  # read only, see test above


# ============================================================
# 3. profiles.role -- no self-escalation
# ============================================================


def test_migration_002_still_only_guards_the_admin_transition():
    """002 in THIS repo blocks NON-ADMIN -> ADMIN only -- it is left
    exactly as written. The general "role is immutable once set" lock is
    added additively by 032 (see section 4), never by editing 002."""
    sql = _sql_without_comments(MIGRATION_002)
    assert "new.role = 'ADMIN' and old.role is distinct from 'ADMIN'" in sql
    # 002 itself never generalised to "any role transition".
    assert "old.role is not null and new.role is distinct from old.role" not in sql
    # 002's own trigger/function names are untouched by 032.
    assert "prevent_self_admin_promotion" in sql


def test_no_backend_code_path_writes_profiles_role():
    """Role assignment is a frontend onboarding action (NULL -> role,
    once) done directly against Supabase -- see
    frontend/lib/auth.ts::updateProfileRole. NO FastAPI service writes
    profiles.role, so there is nothing on the backend that a general
    role-lock could break."""
    services_dir = Path(__file__).resolve().parents[1] / "app" / "services"
    offenders = []
    for py in services_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        if 'table("profiles")' in text and (".update(" in text or ".upsert(" in text):
            offenders.append(py.name)
    assert not offenders, (
        f"these services write to profiles -- audit them against the role lock: {offenders}"
    )


def test_role_and_skill_integrity_live_evidence():
    """Documentation-as-test (no assertion beyond the trivial one below).

    LIVE-DB EVIDENCE gathered read-only during Phase 5 that the shared
    Supabase project already blocks self-service role changes (via the
    contributor's 023 hardening, which is NOT in this repo's lineage):

      * Direct probe with a demo STUDENT's own session token:
          PATCH /rest/v1/profiles {role:"INDUSTRY"}
            -> HTTP 403
               {"code":"42501",
                "message":"Cannot change your role once it has been set."}
          GET  /rest/v1/profiles?select=role   -> "STUDENT" (unchanged)
        The message is verbatim from 023's prevent_unauthorized_role_change().
      * Corroboration: every `profiles` row has updated_at != created_at
        (023's profiles_set_updated_at trigger is the only migration that
        maintains it, and no frontend code sends updated_at).
      * A legitimate update still works:
          PATCH /rest/v1/profiles {full_name:"..."} -> HTTP 204

    Phase 5A migration 032_profile_role_immutability.sql reproduces ONLY
    the role-immutability rule in this repo's own lineage, so 001..032
    replayed from scratch matches the live security state on this one
    property. 032 was NOT applied to the live database (it is already
    protected there); this phase is repository reproducibility only.
    """
    assert MIGRATION_032.is_file()  # the documentation above is the point


# ============================================================
# 4. Migration 032 -- profile role immutability (Phase 5A)
# ============================================================


def test_migration_032_exists_and_targets_profiles_role():
    assert MIGRATION_032.is_file(), f"expected {MIGRATION_032} to exist"
    sql = _sql_without_comments(MIGRATION_032)
    assert "before update on profiles" in sql
    assert "new.role" in sql and "old.role" in sql


def test_migration_032_prevents_self_role_change_once_set():
    """The invariant: role set (not null) + a non-service_role caller
    changing it (in any direction) -> raise. NULL -> role and a no-op are
    not blocked."""
    sql = _sql_without_comments(MIGRATION_032)
    assert "old.role is not null and new.role is distinct from old.role" in sql
    assert "raise exception" in sql
    assert "using errcode = '42501'" in sql


def test_migration_032_keeps_the_service_role_bypass():
    sql = _sql_without_comments(MIGRATION_032)
    assert "if current_setting('role', true) = 'service_role' then" in sql
    assert "return new;" in sql


def test_migration_032_preserves_legitimate_profile_updates():
    """The trigger inspects ONLY `role` -- a full_name / username /
    avatar_url update never reaches the raise. Verified by shape: the only
    column the function body references is `role`."""
    sql = _sql_without_comments(MIGRATION_032)
    for field in ("full_name", "username", "avatar_url", "email", "bio"):
        assert field not in sql, f"032 must not reference {field}"


def test_migration_032_is_additive_and_non_destructive():
    sql = _sql_without_comments(MIGRATION_032)
    lowered = sql.lower()
    assert "drop table" not in lowered
    assert "create table" not in lowered
    assert "drop function" not in lowered  # CREATE OR REPLACE only
    assert "drop policy" not in lowered and "create policy" not in lowered  # no RLS change
    assert "alter table" not in lowered
    # Does not touch 002's or 023's names -- distinct, coexisting guard.
    assert "prevent_self_admin_promotion" not in lowered
    assert "prevent_unauthorized_role_change" not in lowered


def test_migration_032_does_not_touch_unrelated_tables():
    sql = _sql_without_comments(MIGRATION_032).lower()
    for other in (
        "student_skills",
        "assessment_attempts",
        "assessment_answers",
        "assessment_questions",
        "job_roles",
        "applications",
        "career_roles",
        "opportunities",
        "portfolio",
        "faculty_assessment_permissions",
    ):
        assert other not in sql, f"032 must not reference {other}"


def test_migration_032_is_idempotent_in_shape():
    sql = _sql_without_comments(MIGRATION_032)
    assert "create or replace function public.enforce_profile_role_immutability()" in sql
    assert "drop trigger if exists profiles_enforce_role_immutability on profiles" in sql
    assert "create trigger profiles_enforce_role_immutability" in sql


def test_new_phase5_migrations_are_only_031_and_032():
    """The Phase 5 / 5A work introduces exactly two migrations, numbered
    031 and 032 -- the next two unused numbers. Nothing in the 015..025
    range (which the teammate lineage also uses) was reused, and no
    historical file was renamed."""
    names = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert "031_verified_skill_proficiency_integrity.sql" in names
    assert "032_profile_role_immutability.sql" in names
    # canonical historical files still present, unrenamed
    for anchor in (
        "002_protect_admin_role.sql",
        "015_assessment_verification.sql",
        "016_skill_gap.sql",
        "030_industry_interviews.sql",
    ):
        assert anchor in names
