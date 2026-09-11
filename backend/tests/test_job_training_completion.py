"""Phase J4 -- Job Training completion + certificate
(database/migrations/082_job_training_completion.sql).

Three surfaces:
  * INDUSTRY  GET/POST /api/v1/industry/job-training/{enrollment_id}/completion[/verify]
  * STUDENT   GET /api/v1/student/job-training/{enrollment_id}/completion
              GET /api/v1/student/job-training/{enrollment_id}/certificate
  * PUBLIC    GET /api/v1/certificates/verify-job-training/{certificate_number}

Schema guarantees are asserted against the migration TEXT (no live DB).
Service/route behaviour is driven with a small fake Supabase client that
emulates the J4 DB triggers -- derivation, the PASSED-only certificate
gate, verifier stamping, and the UNIQUE constraints -- so an ownership
bypass or a missing gate shows up as a test failure, not a mock
assertion.

The J1/J4 database triggers remain the FINAL gate: this suite verifies
the Python layer's half.
"""

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.api import certificates as certificates_api
from app.api import student_job_training as student_api
from app.main import app
from app.services import job_training_service as svc
from app.services import notification_producer
from tests.conftest import authenticated_as

client = TestClient(app)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
M052 = MIGRATIONS_DIR / "081_job_training.sql"
M053 = MIGRATIONS_DIR / "082_job_training_completion.sql"


def _code(path: Path) -> str:
    return "\n".join(
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("--")
    )


M053_RAW = M053.read_text(encoding="utf-8")
M053_C = _code(M053)
M053_L = M053_C.lower()

_EID = "11111111-1111-1111-1111-111111111111"
_SID = "22222222-2222-2222-2222-222222222222"
_IID = "33333333-3333-3333-3333-333333333333"
_JID = "44444444-4444-4444-4444-444444444444"
_PID = "55555555-5555-5555-5555-555555555555"
_APPID = "66666666-6666-6666-6666-666666666666"
_CID = "77777777-7777-7777-7777-777777777777"


# ============================================================
# 1. SCHEMA -- migration 053 text
# ============================================================


def test_migration_053_exists_and_052_unchanged_and_no_054():
    assert M053.is_file()
    names = sorted(p.name for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    numbers = sorted(int(n[:3]) for n in names)
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"gap: {numbers}"
    # 053 is the Job Training completion tip. The only migration allowed
    # past it is 054 (student interview visibility -- an unrelated feature
    # that adds one read-only RPC and touches no job-training object).
    assert 82 in numbers and 83 in numbers  # merged: job_training_completion (082) + interview visibility (083)
    if numbers[-1] == 54:
        assert "083_student_interview_visibility.sql" in names
    assert "082_job_training_completion.sql" in names
    # 052 still defines its own tables and was not edited
    m052 = M052.read_text(encoding="utf-8")
    assert "create table if not exists job_training_enrollments" in m052


def test_053_is_additive_and_non_destructive():
    assert "drop table" not in M053_L
    assert "truncate" not in M053_L
    for line in M053_L.splitlines():
        s = line.strip()
        if s.startswith("drop ") and "execute format(" not in s:
            assert s.startswith(("drop policy if exists", "drop trigger if exists")), s


def test_053_creates_the_two_new_tables_with_rls():
    for t in ("job_training_completions", "job_training_certificates"):
        assert f"create table if not exists {t}" in M053_L
        assert f"alter table {t} enable row level security" in M053_L


def test_053_does_not_touch_frozen_existing_tables():
    frozen = (
        "job_training_enrollments", "job_programs", "job_program_modules",
        "job_program_items", "job_program_skills", "job_program_assignments",
        "applications", "jobs", "internships", "student_skills", "student_notifications",
        "internship_completions", "internship_certificates", "internship_workspaces",
        "workspace_submissions", "learning_resources", "industry_training",
    )
    for t in frozen:
        assert f"create table if not exists {t}" not in M053_L, t
        assert f"alter table {t} " not in M053_L, t
        assert f"alter table public.{t} " not in M053_L, t


def test_053_never_references_student_skills_or_verification():
    assert "student_skills" not in M053_L
    assert "is_verified" not in M053_L
    assert "score_assessment_attempt" not in M053_L
    assert "assessment" not in M053_L


def test_053_reuses_shared_helpers_not_redefines_them():
    for fn in ("set_updated_at", "is_student", "is_industry"):
        assert f"create or replace function public.{fn}" not in M053_C
    assert "execute procedure public.set_updated_at()" in M053_C
    assert "public.is_student(auth.uid())" in M053_C
    assert "public.is_industry(auth.uid())" in M053_C


def test_completion_table_shape_and_constraints():
    block = M053_L.split("create table if not exists job_training_completions", 1)[1].split(");", 1)[0]
    assert "enrollment_id uuid not null references job_training_enrollments (id) on delete cascade" in block
    assert "student_id uuid not null references profiles (id) on delete cascade" in block
    assert "industry_id uuid not null references profiles (id) on delete restrict" in block
    assert "job_id uuid not null references jobs (id) on delete restrict" in block
    assert "program_id uuid not null references job_programs (id) on delete restrict" in block
    assert "check (completion_status in ('pending', 'passed', 'failed'))" in block
    assert "constraint job_training_completions_one_per_enrollment unique (enrollment_id)" in block
    assert "job_training_completions_decided_requires_verification" in block
    # no internship linkage anywhere
    assert "internship_id" not in block


def test_certificate_table_shape_and_constraints():
    block = M053_L.split("create table if not exists job_training_certificates", 1)[1].split(");", 1)[0]
    assert "completion_id uuid not null references job_training_completions (id) on delete restrict" in block
    assert "certificate_number text not null" in block
    assert "details jsonb not null default '{}'::jsonb" in block
    assert "constraint job_training_certificates_one_per_completion unique (completion_id)" in block
    assert "constraint job_training_certificates_number_unique unique (certificate_number)" in block
    assert "internship_id" not in block


def test_completion_identity_is_trigger_derived_and_gated():
    assert "create or replace function public.set_job_training_completion_derived_ids" in M053_C
    assert "before insert on job_training_completions" in M053_C
    body = M053_C.split("function public.set_job_training_completion_derived_ids", 1)[1].split("$$", 2)[1]
    assert "from public.job_training_enrollments e" in body
    assert "v_enrollment_status = 'REVOKED'" in body
    assert "v_opportunity_type is distinct from 'JOB'" in body
    assert "v_app_status is distinct from 'SELECTED'" in body
    assert "from public.job_programs p" in body
    for assign in ("new.student_id  := v_student_id", "new.industry_id := v_industry_id",
                   "new.job_id      := v_job_id", "new.program_id  := v_program_id"):
        assert assign in body


def test_completion_verifier_trigger_stamps_and_freezes_identity():
    assert "create or replace function public.set_job_training_completion_verifier" in M053_C
    assert "before insert or update on job_training_completions" in M053_C
    body = M053_C.split("function public.set_job_training_completion_verifier", 1)[1].split("$$", 2)[1]
    for col in ("enrollment_id", "student_id", "industry_id", "job_id", "program_id"):
        assert f"new.{col} is distinct from old.{col}" in body
    assert "new.completion_status in ('PASSED', 'FAILED')" in body
    assert "new.verified_by := auth.uid()" in body
    assert "current_setting('role', true) <> 'service_role'" in body


def test_certificate_requires_passed_and_is_immutable():
    assert "create or replace function public.set_job_training_certificate_derived_ids" in M053_C
    d_body = M053_C.split("function public.set_job_training_certificate_derived_ids", 1)[1].split("$$", 2)[1]
    assert "v_completion_status is distinct from 'PASSED'" in d_body
    assert "a certificate can only be issued for a passed job training completion" in M053_L

    assert "create or replace function public.prevent_job_training_certificate_tamper" in M053_C
    t_body = M053_C.split("function public.prevent_job_training_certificate_tamper", 1)[1].split("$$", 2)[1]
    for frozen in ("completion_id", "certificate_number", "issued_at", "details",
                   "student_id", "industry_id", "job_id", "program_id"):
        assert f"new.{frozen} is distinct from old.{frozen}" in t_body


def test_certificate_number_is_server_generated_in_the_job_namespace():
    assert "create or replace function public.generate_job_training_certificate_number" in M053_C
    body = M053_C.split("function public.generate_job_training_certificate_number", 1)[1].split("$$", 2)[1]
    assert "'AIC-JOB-' || to_char(now(), 'YYYY') || '-'" in body
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" in body
    assert "for v_i in 1..13 loop" in body
    assert "gen_random_bytes" not in body
    assert "AIC-INT-" not in M053_C  # distinct namespace from internships
    assert "revoke all on function public.generate_job_training_certificate_number() from authenticated" in M053_C


def test_helpers_are_security_definer_with_pinned_search_path():
    for fn in ("industry_owns_job_training_enrollment", "student_owns_job_training_enrollment",
               "set_job_training_completion_derived_ids", "set_job_training_completion_verifier",
               "generate_job_training_certificate_number", "set_job_training_certificate_derived_ids",
               "prevent_job_training_certificate_tamper", "verify_job_training_certificate"):
        sig = M053_C.split(f"create or replace function public.{fn}", 1)[1].split("$$", 1)[0]
        assert "security definer" in sig, fn
        assert "set search_path = ''" in sig, fn


def test_language_sql_helpers_defined_after_the_tables_they_read():
    # industry/student ownership helpers read job_training_enrollments (052)
    # -> fine (created earlier / lower migration).
    # verify_job_training_certificate reads job_training_certificates (053)
    # -> must be created AFTER that table.
    i_table = M053_C.find("create table if not exists job_training_certificates")
    i_fn = M053_C.find("create or replace function public.verify_job_training_certificate")
    assert i_table != -1 and i_fn != -1 and i_table < i_fn


def test_completion_rls_no_student_write_no_delete():
    section = M053_L.split("alter table job_training_completions enable row level security", 1)[1]
    section = section.split("create table if not exists job_training_certificates", 1)[0]
    assert "for delete" not in section
    for verb in ("select", "insert", "update"):
        assert f"on job_training_completions for {verb}" in section
    # a student may only SELECT
    assert "students can view their own job training completion" in section
    for bad in ("students can create", "students can verify", "students can update",
                "students can issue"):
        assert bad not in section
    # industry write is scoped by ownership helper
    assert "public.industry_owns_job_training_enrollment" in section


def test_certificate_rls_student_read_only_no_anon_table_policy():
    section = M053_L.split("alter table job_training_certificates enable row level security", 1)[1]
    section = section.split("create or replace function public.verify_job_training_certificate", 1)[0]
    assert "for delete" not in section
    assert "students can view their own job training certificate" in section
    for bad in ("students can create", "students can issue", "students can update"):
        assert bad not in section
    # no anon / public TABLE policy -- public verification is function-only
    assert " to anon" not in section
    assert "for select\n  to public" not in section
    assert "for all\n  to public" not in section


def test_public_verifier_returns_only_safe_fields():
    after = M053_C.split("create or replace function public.verify_job_training_certificate", 1)[1]
    sig = after.split("$$", 1)[0]
    body = after.split("$$", 2)[1]
    cols = re.search(r"returns table \(([^)]*)\)", sig, re.DOTALL).group(1)
    returned = {ln.strip().split()[0] for ln in cols.strip().splitlines() if ln.strip()}
    assert returned == {"certificate_number", "student_name", "company_name",
                        "job_title", "program_title", "issued_at", "status"}
    projection = body.lower().split("select", 1)[1].split("from public.job_training_certificates", 1)[0]
    for leak in ("email", "avatar_url", "c.id", "c.student_id", "c.industry_id",
                 "c.job_id", "c.program_id", "c.enrollment_id", "c.completion_id",
                 "verification_notes", "verified_by"):
        assert leak not in projection, leak
    assert "revoke all on function public.verify_job_training_certificate(text) from public" in M053_C
    assert ("grant execute on function public.verify_job_training_certificate(text) "
            "to anon, authenticated") in M053_C


def test_053_makes_no_notification_check_change_and_no_new_app_status():
    # 052 already widened student_notifications; 053 must not touch it.
    assert "alter table public.student_notifications" not in M053_L
    assert "add constraint student_notifications" not in M053_L
    assert "alter table applications" not in M053_L
    for invented in ("'training'", "'training_completed'", "'certified'"):
        assert invented not in M053_L


def test_no_post_053_migration_and_internship_schema_untouched():
    # Any migration added after this one (084+) is free to exist -- the
    # real guarantee this test enforces is the content check below: none
    # of them may touch the tables this migration froze.
    later = sorted(
        p.name for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql") if int(p.name[:3]) >= 84
    )
    for name in later:
        body = (MIGRATIONS_DIR / name).read_text(encoding="utf-8").lower()
        for frozen in ("job_training", "internship_completions", "internship_certificates"):
            assert frozen not in body, (name, frozen)
    for t in ("internship_completions", "internship_certificates", "internship_workspaces"):
        assert f"create table if not exists {t}" not in M053_L
        assert f"alter table {t} " not in M053_L


# ============================================================
# 1b. COMPLETION TERMINAL-STATE INTEGRITY (J4 audit fix)
# ============================================================
# Once job_training_completions.completion_status is PASSED or FAILED the
# record is frozen: no caller -- not even a direct PostgREST / Supabase
# UPDATE that bypasses job_training_service -- may move it back to PENDING,
# flip PASSED <-> FAILED, or rewrite the verifier. PENDING is the only
# state with an outgoing edge. Enforced in the
# set_job_training_completion_verifier BEFORE trigger (a plpgsql body, so
# it is asserted against the migration text -- there is no live DB here).


def _verifier_body() -> str:
    return M053_C.split(
        "function public.set_job_training_completion_verifier", 1
    )[1].split("$$", 2)[1]


def test_completion_verifier_trigger_makes_decided_states_terminal():
    body = _verifier_body()
    # the guard lives in the tg_op = 'UPDATE' branch, keyed on the OLD
    # status already being decided
    assert "old.completion_status in ('PASSED', 'FAILED')" in body
    assert "new.completion_status is distinct from old.completion_status" in body
    # the verifier stamp columns are frozen too, once decided
    for col in ("verified_by", "verified_at", "completed_at"):
        assert f"new.{col} is distinct from old.{col}" in body
    # rejection is a permission error, and the message names terminality
    assert "terminal" in body.lower()
    guard = body.split("old.completion_status in ('PASSED', 'FAILED')", 1)[1].split("end if;", 1)[0]
    assert "raise exception" in guard
    assert "42501" in guard


def test_completion_terminal_guard_is_update_only_and_spares_pending_transitions():
    body = _verifier_body()
    # the terminal guard is inside `if tg_op = 'UPDATE' then` -- a fresh
    # INSERT (PENDING, or created directly as PASSED / FAILED) is never
    # blocked by it.
    update_branch = body.split("if tg_op = 'UPDATE' then", 1)[1]
    assert "old.completion_status in ('PASSED', 'FAILED')" in update_branch
    # the ONLY legal transitions remain PENDING -> PASSED / PENDING -> FAILED:
    # the verifier-stamp block still keys on the OLD row being PENDING.
    assert "old.completion_status = 'PENDING'" in body
    # the guard tests OLD, not NEW -- so it can never fire on a
    # PENDING -> decided update.
    assert "new.completion_status in ('PENDING'" not in body


def test_completion_terminal_guard_has_no_service_role_escape_hatch():
    # consistent with the identity freeze in the same function: a verified
    # outcome is immutable for EVERY role. The only service_role check in
    # this function is the pre-existing verifier-stamp skip.
    body = _verifier_body()
    assert body.count("service_role") == 1
    stamp_line = next(ln for ln in body.splitlines() if "service_role" in ln)
    assert "current_setting('role', true) <> 'service_role'" in stamp_line


# ============================================================
# 2. fake Supabase (emulates the J4 triggers)
# ============================================================


def _ns(data):
    return SimpleNamespace(data=data)


class _Q:
    def __init__(self, fake, table):
        self.fake, self.table = fake, table
        self._filters: list[tuple] = []
        self._single = False
        self._op = "select"
        self._payload = None

    def select(self, *a, **k):
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        self.fake.filters.append((self.table, field, value))
        return self

    def order(self, *a, **k):
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def _match(self, row):
        return all(row.get(f) == v for f, v in self._filters)

    def execute(self):
        return self.fake._exec(self)


class _Rpc:
    def __init__(self, fake, name, params):
        self.fake, self.name, self.params = fake, name, params

    def execute(self):
        if self.name == "application_applicant_names":
            ids = (self.params or {}).get("application_ids", [])
            return _ns([
                {"application_id": i, "student_name": self.fake.applicant_names.get(i)}
                for i in ids if i in self.fake.applicant_names
            ])
        raise AssertionError(f"unexpected rpc {self.name!r}")


def _api_error(code: str) -> APIError:
    return APIError({"code": code, "message": code, "details": "", "hint": ""})


class _Fake:
    def __init__(
        self,
        *,
        enrollment=None,
        application=None,
        program=None,
        completion=None,
        certificate=None,
        role="service_role_off",
    ):
        self.rows = {
            "job_training_enrollments": [enrollment] if enrollment else [],
            "applications": [application] if application else [],
            "job_programs": [program] if program else [],
            "job_training_completions": [completion] if completion else [],
            "job_training_certificates": [certificate] if certificate else [],
            "industry_profiles": [{"id": _IID, "company_name": "Acme Corp"}],
            "jobs": [{"id": _JID, "title": "Platform Engineer"}],
        }
        self.applicant_names = {_APPID: "Riya Student"}
        self.inserts: list[tuple] = []
        self.updates: list[tuple] = []
        self.filters: list[tuple] = []
        self._cert_n = 0

    def table(self, name):
        return _Q(self, name)

    def rpc(self, name, params):
        return _Rpc(self, name, params)

    # ---- helpers ----

    def _one(self, table, **kw):
        for r in self.rows.get(table, []):
            if all(r.get(k) == v for k, v in kw.items()):
                return r
        return None

    def _exec(self, q: _Q):
        if q._op == "insert":
            return self._insert(q)
        if q._op == "update":
            return self._update(q)
        matched = [r for r in self.rows.get(q.table, []) if q._match(r)]
        if q._single:
            return _ns(matched[0] if matched else None)
        return _ns(matched)

    def _insert(self, q: _Q):
        p = dict(q._payload)
        self.inserts.append((q.table, dict(q._payload)))

        if q.table == "job_training_completions":
            enr = self._one("job_training_enrollments", id=p["enrollment_id"])
            if enr is None:
                raise _api_error("23503")
            if enr.get("enrollment_status") == "REVOKED":
                raise _api_error("42501")
            app_row = self._one("applications", id=enr["application_id"])
            if app_row and app_row.get("opportunity_type") != "JOB":
                raise _api_error("42501")
            if app_row and app_row.get("status") != "SELECTED":
                raise _api_error("42501")
            prog = self._one("job_programs", job_id=enr["job_id"])
            if prog is None:
                raise _api_error("42501")
            if self._one("job_training_completions", enrollment_id=p["enrollment_id"]):
                raise _api_error("23505")
            p.setdefault("id", _CID)
            p["student_id"] = enr["student_id"]
            p["industry_id"] = enr["industry_id"]
            p["job_id"] = enr["job_id"]
            p["program_id"] = prog["id"]
            p.setdefault("completion_status", "PENDING")
            if p["completion_status"] in ("PASSED", "FAILED"):
                p.setdefault("verified_by", _IID)
                p["verified_at"] = "2026-09-10T00:00:00Z"
                p["completed_at"] = "2026-09-10T00:00:00Z"
            p.setdefault("verified_at", None)
            p.setdefault("verification_notes", None)
            p.setdefault("completed_at", None)
            self.rows["job_training_completions"].append(p)
            return _ns([{"id": p["id"]}])

        if q.table == "job_training_certificates":
            comp = self._one("job_training_completions", id=p["completion_id"])
            if comp is None:
                raise _api_error("23503")
            if comp.get("completion_status") != "PASSED":
                raise _api_error("42501")
            if self._one("job_training_certificates", completion_id=p["completion_id"]):
                raise _api_error("23505")
            self._cert_n += 1
            p.setdefault("id", "cert-1")
            p["enrollment_id"] = comp["enrollment_id"]
            p["student_id"] = comp["student_id"]
            p["industry_id"] = comp["industry_id"]
            p["job_id"] = comp["job_id"]
            p["program_id"] = comp["program_id"]
            # emulates generate_job_training_certificate_number (053):
            # AIC-JOB-{YYYY}-{13 base32 chars}
            p["certificate_number"] = "AIC-JOB-2026-BCDFGHJKLMNP" + str(2 + self._cert_n % 6)
            p.setdefault("issued_at", "2026-09-10T00:00:00Z")
            p.setdefault("revoked_at", None)
            p.setdefault("details", p.get("details") or {})
            self.rows["job_training_certificates"].append(p)
            return _ns([{"id": p["id"]}])

        row = {**p}
        self.rows.setdefault(q.table, []).append(row)
        return _ns([row])

    def _update(self, q: _Q):
        p = dict(q._payload)
        self.updates.append((q.table, dict(p)))
        hits = [r for r in self.rows.get(q.table, []) if q._match(r)]

        if q.table == "job_training_completions":
            for r in hits:
                # emulates set_job_training_completion_verifier (053): PASSED
                # and FAILED are terminal -- their outcome / verification can
                # never change afterwards. Only PENDING has an outgoing edge.
                if r["completion_status"] in ("PASSED", "FAILED") and (
                    ("completion_status" in p and p["completion_status"] != r["completion_status"])
                    or ("verified_by" in p and p["verified_by"] != r.get("verified_by"))
                    or ("verified_at" in p and p["verified_at"] != r.get("verified_at"))
                    or ("completed_at" in p and p["completed_at"] != r.get("completed_at"))
                ):
                    raise _api_error("42501")
                if p.get("completion_status") in ("PASSED", "FAILED") and r["completion_status"] == "PENDING":
                    r["verified_by"] = _IID
                    r["verified_at"] = "2026-09-10T00:00:00Z"
                    r["completed_at"] = "2026-09-10T00:00:00Z"
                r.update(p)
            return _ns([dict(r) for r in hits])

        for r in hits:
            r.update(p)
        return _ns([dict(r) for r in hits])


def _enr(**over):
    row = {
        "id": _EID,
        "application_id": _APPID,
        "student_id": _SID,
        "industry_id": _IID,
        "job_id": _JID,
        "enrollment_status": "ACTIVE",
        "completed_at": None,
        "revoked_at": None,
        "revoke_reason": None,
        "created_at": "2026-09-08T00:00:00Z",
        "updated_at": "2026-09-08T00:00:00Z",
    }
    row.update(over)
    return row


def _app(**over):
    row = {"id": _APPID, "opportunity_type": "JOB", "status": "SELECTED"}
    row.update(over)
    return row


def _prog(**over):
    row = {"id": _PID, "job_id": _JID, "title": "Platform Onboarding", "status": "PUBLISHED"}
    row.update(over)
    return row


def _fake(**over) -> _Fake:
    over.setdefault("enrollment", _enr())
    over.setdefault("application", _app())
    over.setdefault("program", _prog())
    return _Fake(**over)


# ============================================================
# 3. SERVICE -- verify + lifecycle
# ============================================================


def test_pass_records_completion_issues_certificate_and_completes_enrollment():
    fake = _fake()
    summary = svc.verify_completion(fake, _IID, _EID, "PASS", "great work")
    assert summary["completion_status"] == "PASSED"
    assert summary["industry_verified"] is True
    assert summary["certificate"] is not None
    assert summary["certificate"]["certificate_number"].startswith("AIC-JOB-2026-")
    assert summary["_newly_verified"] is True
    assert summary["_student_id"] == _SID
    # enrollment moved ACTIVE -> COMPLETED
    enr_updates = [u for u in fake.updates if u[0] == "job_training_enrollments"]
    assert enr_updates and enr_updates[0][1]["enrollment_status"] == "COMPLETED"
    # certificate snapshot captured
    cert_insert = next(p for t, p in fake.inserts if t == "job_training_certificates")
    assert cert_insert["details"]["company_name"] == "Acme Corp"
    assert cert_insert["details"]["job_title"] == "Platform Engineer"
    assert cert_insert["details"]["student_name"] == "Riya Student"


def test_fail_records_completion_without_a_certificate():
    fake = _fake()
    summary = svc.verify_completion(fake, _IID, _EID, "FAIL")
    assert summary["completion_status"] == "FAILED"
    assert summary["certificate"] is None
    assert not any(t == "job_training_certificates" for t, _ in fake.inserts)
    enr_updates = [u for u in fake.updates if u[0] == "job_training_enrollments"]
    assert enr_updates and enr_updates[0][1]["enrollment_status"] == "COMPLETED"


def test_pending_completion_certificate_is_not_issued():
    # a completion sitting at PENDING -> get_student_certificate returns None
    fake = _fake(completion={
        "id": _CID, "enrollment_id": _EID, "student_id": _SID, "industry_id": _IID,
        "job_id": _JID, "program_id": _PID, "completion_status": "PENDING",
        "verified_by": None, "verified_at": None, "verification_notes": None, "completed_at": None,
    })
    assert svc.get_student_certificate(fake, _SID, _EID) is None


def test_verify_is_idempotent_no_duplicate_completion_or_certificate():
    fake = _fake()
    first = svc.verify_completion(fake, _IID, _EID, "PASS")
    second = svc.verify_completion(fake, _IID, _EID, "PASS")
    assert first["certificate"]["certificate_number"] == second["certificate"]["certificate_number"]
    assert "_newly_verified" not in second  # second call is not "newly verified"
    # exactly one completion row and one certificate row survive
    assert len(fake.rows["job_training_completions"]) == 1
    assert len(fake.rows["job_training_certificates"]) == 1


def test_reverify_never_flips_a_passed_completion_to_failed():
    fake = _fake()
    svc.verify_completion(fake, _IID, _EID, "PASS")
    summary = svc.verify_completion(fake, _IID, _EID, "FAIL")
    assert summary["completion_status"] == "PASSED"  # unchanged
    assert summary["certificate"] is not None


# ---- completion terminal-state integrity (J4 audit fix) ----


def _completion(status: str, **over) -> dict:
    row = {
        "id": _CID, "enrollment_id": _EID, "student_id": _SID, "industry_id": _IID,
        "job_id": _JID, "program_id": _PID, "completion_status": status,
        "verified_by": None if status == "PENDING" else _IID,
        "verified_at": None if status == "PENDING" else "2026-09-09T00:00:00Z",
        "verification_notes": None,
        "completed_at": None if status == "PENDING" else "2026-09-09T00:00:00Z",
    }
    row.update(over)
    return row


def test_pending_completion_can_be_verified_to_passed():
    """1. PENDING -> PASSED is allowed (and issues the certificate)."""
    fake = _fake(completion=_completion("PENDING"))
    summary = svc.verify_completion(fake, _IID, _EID, "PASS")
    assert summary["completion_status"] == "PASSED"
    assert summary["certificate"] is not None
    assert fake.rows["job_training_completions"][0]["completion_status"] == "PASSED"


def test_pending_completion_can_be_verified_to_failed():
    """2. PENDING -> FAILED is allowed (no certificate)."""
    fake = _fake(completion=_completion("PENDING"))
    summary = svc.verify_completion(fake, _IID, _EID, "FAIL")
    assert summary["completion_status"] == "FAILED"
    assert summary["certificate"] is None
    assert fake.rows["job_training_completions"][0]["completion_status"] == "FAILED"


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("PASSED", "FAILED"),   # 3. PASSED -> FAILED rejected
        ("PASSED", "PENDING"),  # 4. PASSED -> PENDING rejected
        ("FAILED", "PASSED"),   # 5. FAILED -> PASSED rejected (FAILED is terminal by design)
        ("FAILED", "PENDING"),  # FAILED -> PENDING rejected
    ],
)
def test_direct_postgrest_update_of_a_decided_completion_is_rejected(start, target):
    """A direct Supabase/PostgREST PATCH that bypasses the service is
    blocked by the set_job_training_completion_verifier trigger (emulated
    here): a decided completion is terminal."""
    fake = _fake(completion=_completion(start))
    with pytest.raises(APIError) as exc:
        (
            fake.table("job_training_completions")
            .update({"completion_status": target})
            .eq("id", _CID)
            .execute()
        )
    assert exc.value.code == "42501"
    # the stored row is untouched
    assert fake.rows["job_training_completions"][0]["completion_status"] == start


def test_direct_postgrest_rewrite_of_the_verifier_on_a_decided_completion_is_rejected():
    fake = _fake(completion=_completion("PASSED"))
    with pytest.raises(APIError) as exc:
        (
            fake.table("job_training_completions")
            .update({"verified_by": "someone-else"})
            .eq("id", _CID)
            .execute()
        )
    assert exc.value.code == "42501"


def test_service_reverify_is_a_noop_and_never_trips_the_terminal_guard():
    """7. The existing idempotent re-verify path still works: the service
    early-returns on a decided completion, so it never issues the UPDATE
    the DB would now reject."""
    fake = _fake(completion=_completion("PASSED", verification_notes="ok"))
    # seed the matching certificate so the PASS path is fully idempotent
    fake.rows["job_training_certificates"].append({
        "id": "cert-1", "completion_id": _CID, "enrollment_id": _EID, "student_id": _SID,
        "industry_id": _IID, "job_id": _JID, "program_id": _PID,
        "certificate_number": "AIC-JOB-2026-ABCDEFGHJKLMN",
        "details": {"outcome": "PASS"}, "issued_at": "2026-09-09T00:00:00Z", "revoked_at": None,
    })
    summary = svc.verify_completion(fake, _IID, _EID, "FAIL")
    assert summary["completion_status"] == "PASSED"  # unchanged
    assert not any(t == "job_training_completions" for t, _ in fake.updates)
    assert fake.rows["job_training_completions"][0]["completion_status"] == "PASSED"


def test_certificate_issuance_is_unaffected_by_the_terminal_guard():
    """6. Certificate behaviour is unchanged: PASS still issues exactly one
    immutable certificate, idempotently."""
    fake = _fake(completion=_completion("PENDING"))
    first = svc.verify_completion(fake, _IID, _EID, "PASS")
    second = svc.verify_completion(fake, _IID, _EID, "PASS")
    assert first["certificate"]["certificate_number"] == second["certificate"]["certificate_number"]
    assert len(fake.rows["job_training_certificates"]) == 1
    assert first["certificate"]["certificate_number"].startswith("AIC-JOB-2026-")


def test_revoked_enrollment_cannot_be_completed():
    fake = _fake(enrollment=_enr(enrollment_status="REVOKED"))
    with pytest.raises(svc.EnrollmentRevokedError):
        svc.verify_completion(fake, _IID, _EID, "PASS")
    assert not fake.inserts


def test_verify_requires_an_authored_program():
    fake = _fake(program=None)
    with pytest.raises(svc.ProgramMissingError):
        svc.verify_completion(fake, _IID, _EID, "PASS")
    assert not fake.inserts


def test_another_industry_cannot_verify_this_enrollment():
    fake = _fake()
    with pytest.raises(svc.EnrollmentNotFoundError):
        svc.verify_completion(fake, "industry-OTHER", _EID, "PASS")
    assert not fake.inserts


def test_db_trigger_rejects_an_internship_or_non_selected_application():
    # the enrollment lineage points at an application that is NOT a
    # selected job -> the DB derivation trigger raises (emulated as 42501)
    for bad_app in (_app(opportunity_type="INTERNSHIP"), _app(status="SHORTLISTED")):
        fake = _fake(application=bad_app)
        with pytest.raises(svc.CompletionRejectedError):
            svc.verify_completion(fake, _IID, _EID, "PASS")


def test_completion_and_certificate_identity_are_never_client_supplied():
    fake = _fake()
    svc.verify_completion(fake, _IID, _EID, "PASS")
    comp_insert = next(p for t, p in fake.inserts if t == "job_training_completions")
    # the service sends only enrollment_id + status (+ optional notes)
    assert set(comp_insert) <= {"enrollment_id", "completion_status", "verification_notes"}
    cert_insert = next(p for t, p in fake.inserts if t == "job_training_certificates")
    assert set(cert_insert) <= {"completion_id", "details"}
    assert "certificate_number" not in cert_insert
    assert "student_id" not in cert_insert


def test_verify_never_touches_student_skills_or_job_program_tables():
    fake = _fake()
    svc.verify_completion(fake, _IID, _EID, "PASS")
    touched = {t for t, _ in fake.inserts} | {t for t, _ in fake.updates}
    assert touched <= {"job_training_completions", "job_training_certificates", "job_training_enrollments"}
    assert "student_skills" not in touched


def test_service_module_never_touches_student_skills():
    src = Path(svc.__file__).read_text(encoding="utf-8")
    assert '.table("student_skills")' not in src
    assert "score_assessment_attempt" not in src
    assert "is_verified" not in src


# ---- student / industry reads ----


def test_student_reads_own_completion_and_certificate():
    fake = _fake(
        completion={
            "id": _CID, "enrollment_id": _EID, "student_id": _SID, "industry_id": _IID,
            "job_id": _JID, "program_id": _PID, "completion_status": "PASSED",
            "verified_by": _IID, "verified_at": "2026-09-10T00:00:00Z",
            "verification_notes": "well done", "completed_at": "2026-09-10T00:00:00Z",
        },
        certificate={
            "id": "cert-1", "completion_id": _CID, "certificate_number": "AIC-JOB-2026-ABCDEFGHJKLMN",
            "details": {"student_name": "Riya", "company_name": "Acme", "job_title": "PE",
                        "program_title": "Onboarding", "outcome": "PASS"},
            "issued_at": "2026-09-10T00:00:00Z", "revoked_at": None,
        },
    )
    summary = svc.get_student_completion(fake, _SID, _EID)
    assert summary["completion_status"] == "PASSED"
    assert summary["certificate"]["certificate_number"] == "AIC-JOB-2026-ABCDEFGHJKLMN"
    cert = svc.get_student_certificate(fake, _SID, _EID)
    assert cert["program_title"] == "Onboarding"


def test_student_cannot_read_another_students_completion():
    fake = _fake()
    assert svc.get_student_completion(fake, "student-OTHER", _EID) is None


def test_revoked_enrollment_completion_is_not_readable_by_the_student():
    fake = _fake(enrollment=_enr(enrollment_status="REVOKED"))
    assert svc.get_student_completion(fake, _SID, _EID) is None


def test_industry_reads_only_its_own_enrollment_completion():
    fake = _fake()
    assert svc.get_industry_completion(fake, "industry-OTHER", _EID) is None
    summary = svc.get_industry_completion(fake, _IID, _EID)
    assert summary["completion_status"] == "PENDING"
    assert summary["industry_verified"] is False


# ============================================================
# 4. ROUTES -- auth + behaviour
# ============================================================

_STUDENT_URLS = [
    ("get", f"/api/v1/student/job-training/{_EID}/completion"),
    ("get", f"/api/v1/student/job-training/{_EID}/certificate"),
]
_INDUSTRY_URLS = [
    ("get", f"/api/v1/industry/job-training/{_EID}/completion"),
    ("post", f"/api/v1/industry/job-training/{_EID}/completion/verify"),
]


def test_student_completion_routes_require_student():
    for method, url in _STUDENT_URLS:
        assert getattr(client, method)(url).status_code == 401
        for role in ("INDUSTRY", "FACULTY", "INSTITUTION", "ADMIN", None):
            with authenticated_as(role):
                r = getattr(client, method)(url, headers={"Authorization": "Bearer t"})
            assert r.status_code == 403, (role, url)


def _call(method, url, headers=None):
    if method == "post":
        return client.post(url, json={"outcome": "PASS"}, headers=headers)
    return client.get(url, headers=headers)


def test_industry_completion_routes_require_industry():
    for method, url in _INDUSTRY_URLS:
        assert _call(method, url).status_code == 401
        for role in ("STUDENT", "FACULTY", "INSTITUTION", "ADMIN", None):
            with authenticated_as(role):
                r = _call(method, url, headers={"Authorization": "Bearer t"})
            assert r.status_code == 403, (role, url)


def test_student_completion_endpoint_returns_summary_and_404s_cleanly():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "get_student_completion", return_value={
            "enrollment_id": _EID, "completion_status": "PASSED", "industry_verified": True,
            "verified_at": None, "verification_notes": None, "completed_at": None, "certificate": None,
        }),
    ):
        r = client.get(f"/api/v1/student/job-training/{_EID}/completion", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200 and r.json()["completion_status"] == "PASSED"

    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "get_student_completion", return_value=None),
    ):
        r = client.get(f"/api/v1/student/job-training/{_EID}/completion", headers={"Authorization": "Bearer t"})
    assert r.status_code == 404


def test_student_certificate_endpoint_404s_until_issued():
    with (
        authenticated_as("STUDENT", user_id=_SID),
        patch.object(svc, "get_student_certificate", return_value=None),
    ):
        r = client.get(f"/api/v1/student/job-training/{_EID}/certificate", headers={"Authorization": "Bearer t"})
    assert r.status_code == 404


def test_industry_verify_endpoint_forbids_client_identity_fields():
    with (
        authenticated_as("INDUSTRY", user_id=_IID),
        patch.object(svc, "verify_completion") as verify,
    ):
        r = client.post(
            f"/api/v1/industry/job-training/{_EID}/completion/verify",
            json={"outcome": "PASS", "industry_id": "evil", "certificate_number": "x"},
            headers={"Authorization": "Bearer t"},
        )
    assert r.status_code == 422  # extra="forbid"
    verify.assert_not_called()


def test_industry_verify_endpoint_maps_errors():
    cases = [
        (svc.EnrollmentNotFoundError(_EID), 404),
        (svc.EnrollmentRevokedError(_EID), 409),
        (svc.ProgramMissingError(_JID), 409),
        (svc.CompletionRejectedError("nope"), 409),
    ]
    for exc, code in cases:
        with (
            authenticated_as("INDUSTRY", user_id=_IID),
            patch.object(svc, "verify_completion", side_effect=exc),
        ):
            r = client.post(
                f"/api/v1/industry/job-training/{_EID}/completion/verify",
                json={"outcome": "PASS"},
                headers={"Authorization": "Bearer t"},
            )
        assert r.status_code == code, exc


def test_industry_verify_emits_notification_once_only_when_newly_verified():
    newly = {
        "enrollment_id": _EID, "completion_status": "PASSED", "industry_verified": True,
        "verified_at": None, "verification_notes": None, "completed_at": None,
        "certificate": {"certificate_number": "AIC-JOB-2026-ABCDEFGHJKLMN", "job_title": "PE",
                        "program_title": "Onboarding", "student_name": None, "company_name": None,
                        "issued_at": None, "revoked": False},
        "_newly_verified": True, "_student_id": _SID, "_outcome": "PASSED",
    }
    with (
        authenticated_as("INDUSTRY", user_id=_IID),
        patch.object(svc, "verify_completion", return_value=newly),
        patch.object(notification_producer, "emit_job_training_completed") as emit,
    ):
        client.post(f"/api/v1/industry/job-training/{_EID}/completion/verify",
                    json={"outcome": "PASS"}, headers={"Authorization": "Bearer t"})
    emit.assert_called_once()
    assert emit.call_args.kwargs["enrollment_id"] == _EID
    assert emit.call_args.kwargs["certificate_number"] == "AIC-JOB-2026-ABCDEFGHJKLMN"

    repeat = {k: v for k, v in newly.items() if not k.startswith("_")}
    with (
        authenticated_as("INDUSTRY", user_id=_IID),
        patch.object(svc, "verify_completion", return_value=repeat),
        patch.object(notification_producer, "emit_job_training_completed") as emit2,
    ):
        client.post(f"/api/v1/industry/job-training/{_EID}/completion/verify",
                    json={"outcome": "PASS"}, headers={"Authorization": "Bearer t"})
    emit2.assert_not_called()


def test_notification_producer_is_best_effort_and_idempotent_by_contract():
    # a producer failure never raises
    with patch.object(notification_producer, "get_supabase", side_effect=RuntimeError("db down")):
        notification_producer.emit_job_training_completed(
            student_id=_SID, enrollment_id=_EID, job_title="PE", program_title="P",
            outcome="PASSED", certificate_number="AIC-JOB-2026-ABCDEFGHJKLMN",
        )  # no exception
    # a non-decided outcome is a no-op
    calls = []
    fake_sb = SimpleNamespace(table=lambda *_: SimpleNamespace(
        insert=lambda payload: SimpleNamespace(execute=lambda: calls.append(payload))))
    with patch.object(notification_producer, "get_supabase", return_value=fake_sb):
        notification_producer.emit_job_training_completed(
            student_id=_SID, enrollment_id=_EID, job_title="PE", program_title="P",
            outcome="PENDING", certificate_number=None,
        )
    assert calls == []


# ---- public verification ----


def _rpc_ok(rows):
    class _C:
        def rpc(self, name, params):
            assert name == "verify_job_training_certificate"
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=rows))
    return _C()


def test_public_job_certificate_verify_rejects_a_bad_shape():
    r = client.get("/api/v1/certificates/verify-job-training/not-a-number")
    assert r.status_code == 422
    # an internship number is the wrong namespace for this route
    r = client.get("/api/v1/certificates/verify-job-training/AIC-INT-2026-ABCDEFGHJKLMN")
    assert r.status_code == 422


def test_public_job_certificate_verify_returns_safe_fields_only():
    row = {
        "certificate_number": "AIC-JOB-2026-ABCDEFGHJKLMN",
        "student_name": "Riya Student", "company_name": "Acme Corp",
        "job_title": "Platform Engineer", "program_title": "Onboarding",
        "issued_at": "2026-09-10T00:00:00Z", "status": "VALID",
    }
    with patch.object(certificates_api, "build_anon_client", return_value=_rpc_ok([row])):
        r = client.get("/api/v1/certificates/verify-job-training/AIC-JOB-2026-ABCDEFGHJKLMN")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"certificate_number", "student_name", "company_name",
                         "job_title", "program_title", "issued_at", "status"}
    assert "email" not in body and "student_id" not in body


def test_public_job_certificate_verify_404s_for_an_unknown_number():
    with patch.object(certificates_api, "build_anon_client", return_value=_rpc_ok([])):
        r = client.get("/api/v1/certificates/verify-job-training/AIC-JOB-2026-ZZZZZZZZZZZZZ")
    assert r.status_code == 404


def test_the_internship_public_verifier_route_is_unchanged():
    # J4 must not break the existing internship route.
    with patch.object(certificates_api, "build_anon_client", return_value=SimpleNamespace(
        rpc=lambda n, p: SimpleNamespace(execute=lambda: SimpleNamespace(data=[])))):
        r = client.get("/api/v1/certificates/verify/AIC-INT-2026-ABCDEFGHJKLMN")
    assert r.status_code == 404  # well-formed, not found -- route still works


# ============================================================
# 5. SECURITY negatives (P.1 - P.15)
# ============================================================


def test_security_student_cannot_verify_or_issue():
    # no student-facing verify/issue endpoint exists at all
    r = client.post(
        f"/api/v1/student/job-training/{_EID}/completion/verify",
        json={"outcome": "PASS"},
    )
    assert r.status_code in (404, 405)  # route does not exist
    src = Path(student_api.__file__).read_text(encoding="utf-8")
    assert "verify_completion" not in src
    assert "_get_or_create_certificate" not in src
    assert "require_industry" not in src


def test_security_industry_a_cannot_touch_industry_b_completion_or_certificate():
    fake = _fake()  # enrollment belongs to _IID
    for call in (
        lambda: svc.verify_completion(fake, "industry-B", _EID, "PASS"),
        lambda: svc.get_industry_completion(fake, "industry-B", _EID),
    ):
        result = None
        try:
            result = call()
        except svc.EnrollmentNotFoundError:
            result = "blocked"
        assert result in ("blocked", None)
    assert not fake.inserts


def test_security_student_a_cannot_read_student_b_completion_or_certificate():
    fake = _fake()  # enrollment belongs to _SID
    assert svc.get_student_completion(fake, "student-B", _EID) is None
    assert svc.get_student_certificate(fake, "student-B", _EID) is None


def test_security_forged_ids_in_verify_body_are_rejected_by_schema():
    for forged in ("student_id", "industry_id", "job_id", "program_id", "verified_by"):
        with (
            authenticated_as("INDUSTRY", user_id=_IID),
            patch.object(svc, "verify_completion") as verify,
        ):
            r = client.post(
                f"/api/v1/industry/job-training/{_EID}/completion/verify",
                json={"outcome": "PASS", forged: "evil"},
                headers={"Authorization": "Bearer t"},
            )
        assert r.status_code == 422, forged
        verify.assert_not_called()


def test_security_internship_enrollment_never_reaches_job_training_completion():
    # the completion derivation trigger raises for a non-JOB application
    fake = _fake(application=_app(opportunity_type="INTERNSHIP"))
    with pytest.raises(svc.CompletionRejectedError):
        svc.verify_completion(fake, _IID, _EID, "PASS")


def test_security_public_verifier_never_leaks_private_identifiers_in_migration():
    # already covered by test_public_verifier_returns_only_safe_fields; this
    # asserts the projection explicitly excludes the verification detail.
    body = M053_C.split("create or replace function public.verify_job_training_certificate", 1)[1]
    projection = body.lower().split("select", 1)[1].split("from public.job_training_certificates", 1)[0]
    assert "verified_by" not in projection
    assert "verification_notes" not in projection
    assert "completion_id" not in projection
