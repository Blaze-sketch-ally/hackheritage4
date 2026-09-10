-- Migration: 082_job_training_completion
-- Purpose: PHASE J4 of the Job Training architecture -- COMPLETION,
-- industry VERIFICATION, PASS-only CERTIFICATE issuance, and the public
-- certificate-verification function.
--
-- ============================================================
-- Where this sits in the approved architecture
-- ============================================================
-- J1 (081_job_training.sql) delivered job_programs + content + the
-- job_training_enrollments instance (one per SELECTED job application,
-- gated by set_job_training_enrollment_derived_ids). J2 added industry
-- authoring, J3 added student consumption + provisioning on the SELECTED
-- transition, J5 added the student frontend.
--
-- J4 (this migration) adds the END of the lifecycle, mirroring the
-- Internship Workspace completion/certificate design
-- (062_workspace_submissions_completion.sql) and adapting it:
--   1. job_training_completions   -- explicit industry verification, one
--                                    per enrollment, NEVER automatic.
--   2. job_training_certificates  -- 1:1 with a PASSED completion;
--                                    immutable, self-contained JSONB
--                                    snapshot; server-generated unique
--                                    number in a distinct namespace
--                                    (AIC-JOB-{YYYY}-...).
--   3. public.verify_job_training_certificate(text) -- SECURITY DEFINER,
--                                    exposes ONLY public verification
--                                    fields, granted to anon.
--   4. Two enrollment-ownership RLS helpers (052 shipped none).
--
-- ============================================================
-- What is DELIBERATELY DIFFERENT from the internship analog
-- ============================================================
-- * Single completion_status field: PENDING / PASSED / FAILED. The
--   internship model splits this into completion_status
--   ('REQUIREMENTS_MET','COMPLETED') + outcome ('PASS','FAIL'); Job
--   Training has no submission/review system yet, so there is no
--   computed "requirements met" pre-state to represent -- one field is
--   the cleaner, consistent model, and no unnecessary status is added.
-- * The completion row DENORMALIZES student_id / industry_id / job_id /
--   program_id (the internship completion carries only workspace_id). All
--   four are derived from the enrollment lineage by a BEFORE-INSERT
--   trigger and frozen -- never trusted from client input. This follows
--   the 020 / 050 / 052 "derive-and-freeze" precedent.
-- * Certificate namespace is AIC-JOB-* (vs AIC-INT-*), so a job training
--   certificate number can never be confused with an internship one.
--
-- ============================================================
-- Relationship to the existing schema (nothing existing is modified)
-- ============================================================
-- * job_training_completions.enrollment_id -> job_training_enrollments(id)
--   ON DELETE CASCADE (052). Enrollments are never hard-deleted, so this
--   CASCADE only fires on a service_role / GDPR path.
-- * The completion's derivation trigger REQUIRES: the enrollment exists,
--   is NOT REVOKED, its application is opportunity_type = 'JOB' AND
--   status = 'SELECTED', and the job has an authored job_program. Any of
--   these failing raises -- so an internship, a non-selected job, a
--   revoked enrollment, or a program-less job can never receive a
--   completion, not even via a direct REST insert.
-- * job_training_certificates.completion_id -> job_training_completions(id)
--   ON DELETE RESTRICT. Certificates are permanent.
-- * NOTHING here references or writes student_skills, is_verified,
--   score_assessment_attempt, or any assessment table. A verified
--   completion and an issued certificate are job-training EVIDENCE only --
--   they never create a student_skill, change proficiency, or mark a
--   skill verified. That boundary (015_assessment_verification.sql) is
--   untouched.
-- * NO application status is introduced. The application stays SELECTED.
-- * NO student_notifications change -- 052 already widened its CHECKs to
--   allow type 'JOB_TRAINING' and related_entity_type
--   'JOB_TRAINING_ENROLLMENT'. This migration ASSUMES 052 has run (it is
--   lower-numbered, so a forward replay guarantees that).
--
-- ============================================================
-- Conventions reused (001-052)
-- ============================================================
-- * uuid PK default gen_random_uuid(); created_at / updated_at timestamptz
--   not null default now(); public.set_updated_at() trigger (012), reused
--   never redefined.
-- * Enum-like columns -> CHECK value lists, never a Postgres enum type.
-- * public.is_student(uuid) / public.is_industry(uuid) (012/013/017).
-- * SECURITY DEFINER + set search_path = '' on every helper and trigger
--   function; defensive `revoke all ... from public` on the trigger-typed
--   ones; `revoke ... from public, anon` + `grant execute ... to
--   authenticated` on the two boolean RLS helpers.
-- * Record tables: explicit per-command SELECT / INSERT / UPDATE policies,
--   NO DELETE policy (020/027/028/030/049/050/051/052 precedent).
-- * Certificate number generation: RFC 4648 base32 of 8 CSPRNG bytes via
--   md5(gen_random_uuid()...) + get_byte() + numeric -- no pgcrypto, no
--   gen_random_bytes, no bit-string cast. Exact copy of 051's approach,
--   only the prefix changes.
-- * Idempotent in shape: create table / index if not exists;
--   drop policy/trigger if exists + create; create or replace function.
--   Forward-only, additive: no DROP TABLE, no TRUNCATE, no destructive
--   ALTER, no change to any existing table/policy/trigger/function.
--
-- No seed data.
--
-- ============================================================
-- Object creation order (dependency-correct)
-- ============================================================
--   1. industry_owns_job_training_enrollment()   -- language sql; reads
--      student_owns_job_training_enrollment()        job_training_enrollments (052)
--   2. job_training_completions          (table + indexes)
--   3. set_job_training_completion_derived_ids()  -- plpgsql BEFORE INSERT
--      set_job_training_completion_verifier()      -- plpgsql BEFORE INSERT OR UPDATE
--      + triggers + set_updated_at trigger
--   4. RLS enable + policies on job_training_completions (use the helpers)
--   5. job_training_certificates         (table + indexes)
--   6. generate_job_training_certificate_number()  -- plpgsql; no table refs
--   7. set_job_training_certificate_derived_ids()  -- plpgsql BEFORE INSERT;
--                                          reads job_training_completions (2),
--                                          job_training_enrollments (052),
--                                          job_programs (052)
--      prevent_job_training_certificate_tamper()   -- plpgsql BEFORE UPDATE
--      + triggers + set_updated_at trigger
--   8. RLS enable + policies on job_training_certificates
--   9. public.verify_job_training_certificate()    -- language sql; reads
--                                          job_training_certificates (5) +
--                                          profiles / industry_profiles /
--                                          jobs / job_programs. Grants last.
-- Every `language sql` body is created AFTER every table it reads; every
-- policy is created AFTER its table's RLS is enabled and after any
-- function it references.

-- ============================================================
-- 1. Enrollment-ownership RLS helpers
-- ============================================================
-- 052 shipped owns_job_program / student_can_access_job_program (keyed on
-- program_id) but no enrollment-keyed helper. These two mirror
-- student_owns_workspace / industry_owns_workspace (050). SECURITY
-- DEFINER + pinned empty search_path + STABLE.

create or replace function public.industry_owns_job_training_enrollment(p_enrollment_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.job_training_enrollments e
    where e.id = p_enrollment_id
      and e.industry_id = auth.uid()
      and public.is_industry(auth.uid())
  );
$$;

revoke all on function public.industry_owns_job_training_enrollment(uuid) from public;
revoke all on function public.industry_owns_job_training_enrollment(uuid) from anon;
grant execute on function public.industry_owns_job_training_enrollment(uuid) to authenticated;

create or replace function public.student_owns_job_training_enrollment(p_enrollment_id uuid)
returns boolean
language sql
security definer
set search_path = ''
stable
as $$
  select exists (
    select 1
    from public.job_training_enrollments e
    where e.id = p_enrollment_id
      and e.student_id = auth.uid()
      and public.is_student(auth.uid())
  );
$$;

revoke all on function public.student_owns_job_training_enrollment(uuid) from public;
revoke all on function public.student_owns_job_training_enrollment(uuid) from anon;
grant execute on function public.student_owns_job_training_enrollment(uuid) to authenticated;

-- ============================================================
-- 2. job_training_completions -- explicit verification, never automatic
-- ============================================================

create table if not exists job_training_completions (
  id uuid primary key default gen_random_uuid(),

  -- One completion per enrollment. A duplicate verify attempt hits this
  -- 23505 and the service treats it as "already verified" (idempotent).
  enrollment_id uuid not null references job_training_enrollments (id) on delete cascade,

  -- Denormalized from the enrollment ( + job_programs ) by
  -- set_job_training_completion_derived_ids, then frozen by
  -- set_job_training_completion_verifier. Deletion strategy mirrors the
  -- job_training_enrollments / internship_certificates precedent:
  -- student_id CASCADE, the rest RESTRICT (completion history survives an
  -- industry / job / program removal attempt -- 027/028 block those anyway).
  student_id uuid not null references profiles (id) on delete cascade,
  industry_id uuid not null references profiles (id) on delete restrict,
  job_id uuid not null references jobs (id) on delete restrict,
  program_id uuid not null references job_programs (id) on delete restrict,

  -- PENDING = created, awaiting the industry's decision.
  -- PASSED / FAILED = the industry has explicitly verified with that
  -- outcome. Both are terminal -- a completion is a record. The
  -- set_job_training_completion_verifier BEFORE trigger enforces that
  -- terminality against direct PostgREST updates: once decided, the
  -- status / verifier can never change (PENDING is the ONLY state with
  -- an outgoing edge).
  completion_status text not null default 'PENDING'
    check (completion_status in ('PENDING', 'PASSED', 'FAILED')),

  verified_by uuid references profiles (id) on delete restrict,
  verified_at timestamptz,
  verification_notes text,

  -- Set alongside PASSED / FAILED -- the moment the training engagement
  -- was signed off, pass or fail.
  completed_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint job_training_completions_one_per_enrollment unique (enrollment_id),
  -- A decided completion must carry its verifier + timestamps.
  constraint job_training_completions_decided_requires_verification check (
    completion_status = 'PENDING'
    or (verified_by is not null and verified_at is not null and completed_at is not null)
  )
);

create index if not exists job_training_completions_student_id_idx
  on job_training_completions (student_id);
create index if not exists job_training_completions_industry_status_idx
  on job_training_completions (industry_id, completion_status);
create index if not exists job_training_completions_program_id_idx
  on job_training_completions (program_id);

-- ---- derivation + guards ----

-- BEFORE INSERT: derive student_id / industry_id / job_id / program_id
-- from the enrollment lineage, and enforce every eligibility rule. Any
-- client-supplied value for those four ids is overwritten.
create or replace function public.set_job_training_completion_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_student_id uuid;
  v_industry_id uuid;
  v_job_id uuid;
  v_application_id uuid;
  v_enrollment_status text;
  v_program_id uuid;
  v_opportunity_type text;
  v_app_status text;
begin
  select e.student_id, e.industry_id, e.job_id, e.application_id, e.enrollment_status
    into v_student_id, v_industry_id, v_job_id, v_application_id, v_enrollment_status
  from public.job_training_enrollments e
  where e.id = new.enrollment_id;

  if v_student_id is null then
    raise exception 'Referenced job training enrollment does not exist.' using errcode = '23503';
  end if;

  -- A revoked enrollment can never be completed.
  if v_enrollment_status = 'REVOKED' then
    raise exception 'A revoked job training enrollment cannot be completed.'
      using errcode = '42501';
  end if;

  -- Defence in depth against the application ever not being a SELECTED
  -- job (SELECTED is terminal in the pipeline, and the J1 enrollment
  -- trigger already gated JOB + SELECTED at enrollment creation -- this
  -- re-checks it so the completion gate stands on its own).
  select a.opportunity_type, a.status
    into v_opportunity_type, v_app_status
  from public.applications a
  where a.id = v_application_id;

  if v_opportunity_type is distinct from 'JOB' then
    raise exception 'A job training completion is only for a JOB application.'
      using errcode = '42501';
  end if;
  if v_app_status is distinct from 'SELECTED' then
    raise exception 'A job training completion is only for a SELECTED application.'
      using errcode = '42501';
  end if;

  -- The job must have an authored program -- you cannot complete training
  -- that was never built.
  select p.id into v_program_id
  from public.job_programs p
  where p.job_id = v_job_id;

  if v_program_id is null then
    raise exception 'This job has no training program -- there is nothing to complete.'
      using errcode = '42501';
  end if;

  new.student_id  := v_student_id;
  new.industry_id := v_industry_id;
  new.job_id      := v_job_id;
  new.program_id  := v_program_id;
  return new;
end;
$$;

revoke all on function public.set_job_training_completion_derived_ids() from public;

drop trigger if exists job_training_completions_set_derived_ids on job_training_completions;
create trigger job_training_completions_set_derived_ids
  before insert on job_training_completions
  for each row
  execute procedure public.set_job_training_completion_derived_ids();

-- BEFORE INSERT OR UPDATE: enrollment_id + the derived identity columns
-- are frozen after creation; a non-service_role caller crossing into
-- PASSED / FAILED is recorded as the verifier at now(). Mirrors
-- set_internship_completion_verifier (051).
--
-- TERMINAL-STATE INTEGRITY (J4 audit fix): PASSED and FAILED are BOTH
-- terminal -- a completion is a permanent record of the industry's
-- explicit sign-off. Once a completion carries a decided outcome, its
-- verification status is frozen: no caller may move it back to PENDING,
-- flip PASSED <-> FAILED, or rewrite who verified it / when. Only the
-- PENDING -> PASSED and PENDING -> FAILED transitions are legal, and each
-- happens exactly once. This is enforced HERE, in a BEFORE trigger, so it
-- holds against a direct PostgREST / Supabase UPDATE that bypasses the
-- Python service layer (job_training_service._DECIDED_STATES) -- the RLS
-- UPDATE policy alone would otherwise let the owning industry PATCH
-- completion_status freely. It mirrors the RELEASED / CANCELLED terminal
-- guard on stipend_disbursements (051). No service_role escape hatch --
-- exactly like the identity freeze above it, a verified outcome is
-- immutable for every role; a GDPR erase still CASCADEs the row via
-- enrollment_id / student_id.
create or replace function public.set_job_training_completion_verifier()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    if new.enrollment_id is distinct from old.enrollment_id
      or new.student_id is distinct from old.student_id
      or new.industry_id is distinct from old.industry_id
      or new.job_id is distinct from old.job_id
      or new.program_id is distinct from old.program_id
    then
      raise exception 'Cannot change the enrollment or identity of a job training completion.'
        using errcode = '42501';
    end if;

    if old.completion_status in ('PASSED', 'FAILED')
       and (
         new.completion_status is distinct from old.completion_status
         or new.verified_by is distinct from old.verified_by
         or new.verified_at is distinct from old.verified_at
         or new.completed_at is distinct from old.completed_at
       )
    then
      raise exception 'A verified job training completion is terminal -- its outcome (PASSED / FAILED) and verification cannot be changed.'
        using errcode = '42501';
    end if;
  end if;

  if current_setting('role', true) <> 'service_role'
     and new.completion_status in ('PASSED', 'FAILED')
     and (tg_op = 'INSERT' or old.completion_status = 'PENDING')
  then
    new.verified_by := auth.uid();
    if new.verified_at is null then
      new.verified_at := now();
    end if;
    if new.completed_at is null then
      new.completed_at := now();
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.set_job_training_completion_verifier() from public;

drop trigger if exists job_training_completions_set_verifier on job_training_completions;
create trigger job_training_completions_set_verifier
  before insert or update on job_training_completions
  for each row
  execute procedure public.set_job_training_completion_verifier();

drop trigger if exists job_training_completions_set_updated_at on job_training_completions;
create trigger job_training_completions_set_updated_at
  before update on job_training_completions
  for each row
  execute procedure public.set_updated_at();

-- ---- RLS ----

alter table job_training_completions enable row level security;

drop policy if exists "Students can view their own job training completion" on job_training_completions;
create policy "Students can view their own job training completion"
  on job_training_completions for select
  to authenticated
  using (public.student_owns_job_training_enrollment(job_training_completions.enrollment_id));

drop policy if exists "Industry can view job training completions for their own enrollments" on job_training_completions;
create policy "Industry can view job training completions for their own enrollments"
  on job_training_completions for select
  to authenticated
  using (public.industry_owns_job_training_enrollment(job_training_completions.enrollment_id));

-- industry_id is set by set_job_training_completion_derived_ids (which
-- runs BEFORE this WITH CHECK) from the referenced enrollment, and
-- industry_owns_job_training_enrollment independently confirms the caller
-- owns that enrollment -- so a student can never insert a completion, and
-- an industry can never insert one for another company's enrollment.
drop policy if exists "Industry can create a job training completion for their own enrollment" on job_training_completions;
create policy "Industry can create a job training completion for their own enrollment"
  on job_training_completions for insert
  to authenticated
  with check (
    public.industry_owns_job_training_enrollment(job_training_completions.enrollment_id)
    and auth.uid() = job_training_completions.industry_id
  );

drop policy if exists "Industry can verify job training completions for their own enrollments" on job_training_completions;
create policy "Industry can verify job training completions for their own enrollments"
  on job_training_completions for update
  to authenticated
  using (public.industry_owns_job_training_enrollment(job_training_completions.enrollment_id))
  with check (public.industry_owns_job_training_enrollment(job_training_completions.enrollment_id));

-- No student INSERT / UPDATE / DELETE policy: a student can NEVER create,
-- verify, or edit a completion. No DELETE for any role -- completions are
-- permanent records.

-- ============================================================
-- 3. job_training_certificates -- issuer-generated, immutable, 1:1 w/ PASS
-- ============================================================

create table if not exists job_training_certificates (
  id uuid primary key default gen_random_uuid(),
  completion_id uuid not null references job_training_completions (id) on delete restrict,

  -- Denormalized from the completion -> enrollment chain by
  -- set_job_training_certificate_derived_ids, then frozen. The certificate
  -- is a historical artifact and must stay correct even if the enrollment,
  -- program, job or profiles change later.
  enrollment_id uuid not null references job_training_enrollments (id) on delete restrict,
  student_id uuid not null references profiles (id) on delete restrict,
  industry_id uuid not null references profiles (id) on delete restrict,
  job_id uuid not null references jobs (id) on delete restrict,
  program_id uuid not null references job_programs (id) on delete restrict,

  -- Server-generated, unique, immutable. Format: AIC-JOB-{YYYY}-{base32(8 bytes)}.
  certificate_number text not null,

  -- Self-contained public snapshot: { student_name, company_name,
  -- job_title, program_title, outcome }. Captured ONCE at issuance;
  -- verify_job_training_certificate() prefers it over live joins.
  details jsonb not null default '{}'::jsonb,

  issued_at timestamptz not null default now(),
  pdf_url text,
  revoked_at timestamptz,
  revoke_reason text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint job_training_certificates_one_per_completion unique (completion_id),
  constraint job_training_certificates_number_unique unique (certificate_number),
  constraint job_training_certificates_revoke_fields_paired
    check ((revoked_at is null) = (revoke_reason is null))
);

create index if not exists job_training_certificates_enrollment_id_idx
  on job_training_certificates (enrollment_id);
create index if not exists job_training_certificates_student_id_idx
  on job_training_certificates (student_id);

-- RFC 4648 base32 of 8 CSPRNG bytes -- exact copy of 051's
-- generate_internship_certificate_number, only the 'AIC-JOB-' prefix
-- differs. No pgcrypto dependency and no bit-string cast.
create or replace function public.generate_job_training_certificate_number()
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_alphabet constant text := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  v_digest bytea;
  v_num numeric := 0;
  v_body text := '';
  v_i int;
begin
  v_digest := decode(md5(gen_random_uuid()::text || clock_timestamp()::text), 'hex');
  for v_i in 0..7 loop
    v_num := v_num * 256 + get_byte(v_digest, v_i);
  end loop;

  for v_i in 1..13 loop
    v_body := substr(v_alphabet, (mod(v_num, 32))::int + 1, 1) || v_body;
    v_num := div(v_num, 32);
  end loop;

  return 'AIC-JOB-' || to_char(now(), 'YYYY') || '-' || v_body;
end;
$$;

revoke all on function public.generate_job_training_certificate_number() from public;
revoke all on function public.generate_job_training_certificate_number() from anon;
revoke all on function public.generate_job_training_certificate_number() from authenticated;

-- BEFORE INSERT: derive the denormalized ids from the completion, require
-- completion_status = 'PASSED', and mint the certificate number if not
-- supplied. Mirrors set_internship_certificate_derived_ids (051).
create or replace function public.set_job_training_certificate_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_enrollment_id uuid;
  v_student_id uuid;
  v_industry_id uuid;
  v_job_id uuid;
  v_program_id uuid;
  v_completion_status text;
begin
  select c.enrollment_id, c.student_id, c.industry_id, c.job_id, c.program_id, c.completion_status
    into v_enrollment_id, v_student_id, v_industry_id, v_job_id, v_program_id, v_completion_status
  from public.job_training_completions c
  where c.id = new.completion_id;

  if v_enrollment_id is null then
    raise exception 'Referenced job training completion does not exist.' using errcode = '23503';
  end if;
  if v_completion_status is distinct from 'PASSED' then
    raise exception 'A certificate can only be issued for a PASSED job training completion.'
      using errcode = '42501';
  end if;

  new.enrollment_id := v_enrollment_id;
  new.student_id    := v_student_id;
  new.industry_id   := v_industry_id;
  new.job_id        := v_job_id;
  new.program_id    := v_program_id;

  if new.certificate_number is null or length(trim(new.certificate_number)) = 0 then
    new.certificate_number := public.generate_job_training_certificate_number();
  end if;

  return new;
end;
$$;

revoke all on function public.set_job_training_certificate_derived_ids() from public;

drop trigger if exists job_training_certificates_set_derived_ids on job_training_certificates;
create trigger job_training_certificates_set_derived_ids
  before insert on job_training_certificates
  for each row
  execute procedure public.set_job_training_certificate_derived_ids();

-- BEFORE UPDATE: a certificate is immutable except for pdf_url and its
-- revocation state. Mirrors prevent_internship_certificate_tamper (051).
create or replace function public.prevent_job_training_certificate_tamper()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.completion_id is distinct from old.completion_id
    or new.enrollment_id is distinct from old.enrollment_id
    or new.student_id is distinct from old.student_id
    or new.industry_id is distinct from old.industry_id
    or new.job_id is distinct from old.job_id
    or new.program_id is distinct from old.program_id
    or new.certificate_number is distinct from old.certificate_number
    or new.issued_at is distinct from old.issued_at
    or new.details is distinct from old.details
    or new.created_at is distinct from old.created_at
  then
    raise exception 'A job training certificate is immutable except for its document URL and revocation state.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_job_training_certificate_tamper() from public;

drop trigger if exists job_training_certificates_prevent_tamper on job_training_certificates;
create trigger job_training_certificates_prevent_tamper
  before update on job_training_certificates
  for each row
  execute procedure public.prevent_job_training_certificate_tamper();

drop trigger if exists job_training_certificates_set_updated_at on job_training_certificates;
create trigger job_training_certificates_set_updated_at
  before update on job_training_certificates
  for each row
  execute procedure public.set_updated_at();

-- ---- RLS ----

alter table job_training_certificates enable row level security;

drop policy if exists "Students can view their own job training certificate" on job_training_certificates;
create policy "Students can view their own job training certificate"
  on job_training_certificates for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view job training certificates for their own jobs" on job_training_certificates;
create policy "Industry can view job training certificates for their own jobs"
  on job_training_certificates for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can issue job training certificates for their own jobs" on job_training_certificates;
create policy "Industry can issue job training certificates for their own jobs"
  on job_training_certificates for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update job training certificate document and revocation" on job_training_certificates;
create policy "Industry can update job training certificate document and revocation"
  on job_training_certificates for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No DELETE policy. No public / anon table policy -- public verification
-- is ONLY via verify_job_training_certificate() below.

-- ============================================================
-- 4. Public certificate verification
-- ============================================================
-- SECURITY DEFINER + pinned empty search_path. Exposes ONLY: the
-- certificate number (echoed), the student's display name, the company
-- name, the job title, the program title, the issue date, and
-- VALID / REVOKED. It exposes NO email, NO profile / application /
-- enrollment / job / program UUID, NO completion or verification detail.
-- Prefers the frozen JSONB snapshot; falls back to live joins for older
-- rows. Granted to anon + authenticated (verification is public by
-- design, exactly like verify_internship_certificate).

create or replace function public.verify_job_training_certificate(p_number text)
returns table (
  certificate_number text,
  student_name text,
  company_name text,
  job_title text,
  program_title text,
  issued_at timestamptz,
  status text
)
language sql
security definer
set search_path = ''
stable
as $$
  select
    c.certificate_number,
    coalesce(c.details ->> 'student_name', sp.full_name)     as student_name,
    coalesce(c.details ->> 'company_name', ip.company_name)  as company_name,
    coalesce(c.details ->> 'job_title', j.title)             as job_title,
    coalesce(c.details ->> 'program_title', prog.title)      as program_title,
    c.issued_at,
    case when c.revoked_at is not null then 'REVOKED' else 'VALID' end as status
  from public.job_training_certificates c
  left join public.profiles sp          on sp.id = c.student_id
  left join public.industry_profiles ip on ip.id = c.industry_id
  left join public.jobs j               on j.id = c.job_id
  left join public.job_programs prog     on prog.id = c.program_id
  where c.certificate_number = p_number;
$$;

revoke all on function public.verify_job_training_certificate(text) from public;
grant execute on function public.verify_job_training_certificate(text) to anon, authenticated;

-- ============================================================
-- Post-conditions (for a live check after `supabase db push`)
-- ============================================================
--   -- 2 new tables, RLS on:
--   select tablename, rowsecurity from pg_tables
--   where schemaname = 'public'
--     and tablename in ('job_training_completions','job_training_certificates');
--
--   -- one completion per enrollment / one certificate per completion:
--   -- a second row for the same enrollment_id / completion_id -> 23505.
--
--   -- the completion gate (as the owning industry, non-service_role):
--   --   * a REVOKED enrollment  -> "... revoked ... cannot be completed."
--   --   * an INTERNSHIP application (impossible via a real enrollment, but
--   --     a forged insert) -> "... only for a JOB application."
--   --   * a job with no job_program -> "... no training program ..."
--
--   -- completion terminal-state integrity (as the owning industry,
--   -- non-service_role, via a direct PostgREST PATCH):
--   --   update job_training_completions set completion_status = 'PENDING'
--   --     where completion_status = 'PASSED'  ->  42501 (terminal).
--   --   update job_training_completions set completion_status = 'FAILED'
--   --     where completion_status = 'PASSED'  ->  42501 (terminal).
--   --   update job_training_completions set completion_status = 'PASSED'
--   --     where completion_status = 'FAILED'  ->  42501 (terminal).
--   --   update job_training_completions set completion_status = 'PASSED'
--   --     where completion_status = 'PENDING' ->  ok (the one legal edge).
--
--   -- certificate requires PASSED:
--   -- insert into job_training_certificates for a PENDING / FAILED
--   -- completion -> "... only be issued for a PASSED ..."
--
--   -- certificate immutability (as the owning industry, non-service_role):
--   -- update job_training_certificates set details = '{}'  ->  42501.
--
--   -- number format + uniqueness:
--   select public.generate_job_training_certificate_number();
--   -- -> 'AIC-JOB-YYYY-XXXXXXXXXXXXX' (13 base32 chars). Two calls differ.
--
--   -- public verification exposes only safe fields:
--   select * from public.verify_job_training_certificate('<number>');
--   -- -> exactly (certificate_number, student_name, company_name,
--   --    job_title, program_title, issued_at, status). No id / email.
--
--   -- student cannot verify:
--   -- as a STUDENT, update job_training_completions set completion_status
--   -- = 'PASSED'  ->  RLS denies (no student UPDATE policy).
