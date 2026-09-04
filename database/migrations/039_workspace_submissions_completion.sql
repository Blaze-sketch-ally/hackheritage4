-- Migration: 039_workspace_submissions_completion
-- Purpose: PHASE 1 (database foundation) of the approved post-selection
-- Internship Workspace architecture -- SUBMISSIONS, REVIEWS, COMPLETION,
-- CERTIFICATE, STIPEND, plus the public certificate-verification function
-- and the additive widening of the student_notifications CHECKs.
--
-- ============================================================
-- What this delivers
-- ============================================================
-- 1. workspace_submissions    -- append-only submission attempts
-- 2. submission_reviews       -- append-only industry review decisions
--                                (the source of truth; the submission's
--                                submission_status is a denormalized cache)
-- 3. internship_completions   -- explicit industry completion verification
--                                (NEVER automatic); 1:1 with a workspace
-- 4. internship_certificates  -- 1:1 with a PASSED completion; immutable,
--                                self-contained JSONB snapshot; server-
--                                generated unique number
-- 5. stipend_disbursements    -- record-keeping only, 1 per workspace,
--                                RELEASED / CANCELLED terminal
-- 6. public.verify_internship_certificate(text) -- SECURITY DEFINER,
--                                exposes ONLY public verification fields
-- 7. student_notifications CHECK widening -- + 'INTERNSHIP' type and
--                                'INTERNSHIP_WORKSPACE' related_entity_type
--
-- ============================================================
-- Progress is COMPUTED, not stored
-- ============================================================
-- There is deliberately NO progress column anywhere. "In scope" required
-- assignments are: published AND is_required AND (linked_skill_id IS NULL
-- OR linked to a REQUIRED program skill OR linked to a skill the student
-- selected in workspace_skill_selections). Progress = accepted-required /
-- in-scope-required. Optional assignments never gate completion. The
-- helper that serves this is an application-layer concern (later phase);
-- no database function is required for integrity here.
--
-- ============================================================
-- Skill-verification boundary
-- ============================================================
-- Nothing here reads or writes student_skills. An accepted submission, a
-- completed internship and an issued certificate are internship EVIDENCE
-- only -- they never create a student_skill, change proficiency, or mark a
-- skill verified. score_assessment_attempt() (015) stays the sole writer
-- of student_skills verification state.
--
-- ============================================================
-- Conventions reused (001-038)
-- ============================================================
-- * uuid PK; created_at/updated_at; public.set_updated_at() (012).
-- * CHECK value lists, never enum types.
-- * public.student_owns_workspace / public.industry_owns_workspace (038)
--   for every child table's RLS.
-- * Derived-id BEFORE INSERT triggers (020/030 pattern); service_role
--   steps aside in every guard; SECURITY DEFINER + set search_path = ''.
-- * Every table is a record: explicit SELECT / INSERT / UPDATE policies,
--   NO DELETE policy. submission_reviews additionally has NO UPDATE policy
--   (a correction is a new review row).
-- * Idempotent in shape; forward-only; additive. The one existing-schema
--   change is the student_notifications CHECK widening at the end --
--   additive to the allowed value sets, so no existing row can violate the
--   widened constraints.

-- ============================================================
-- 1. workspace_submissions -- append-only attempts
-- ============================================================

create table if not exists workspace_submissions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references internship_workspaces (id) on delete cascade,
  assignment_id uuid not null references program_assignments (id) on delete restrict,

  -- Assigned server-side by set_workspace_submission_attempt_number: 1 for
  -- the first attempt, max+1 thereafter. A resubmission is a NEW row --
  -- never an update of the prior one, never a 'RESUBMITTED' status.
  attempt_number int not null check (attempt_number >= 1),

  submission_status text not null default 'SUBMITTED' check (
    submission_status in ('SUBMITTED', 'UNDER_REVIEW', 'REVISION_REQUESTED', 'ACCEPTED', 'REJECTED')
  ),

  repo_url text,
  live_url text,
  attachment_url text,
  notes text,

  submitted_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint workspace_submissions_unique_attempt unique (workspace_id, assignment_id, attempt_number)
);

create index if not exists workspace_submissions_workspace_id_idx on workspace_submissions (workspace_id);
create index if not exists workspace_submissions_assignment_id_idx on workspace_submissions (assignment_id);
create index if not exists workspace_submissions_latest_idx
  on workspace_submissions (workspace_id, assignment_id, attempt_number desc);

-- BEFORE INSERT: assign attempt_number; enforce that the workspace is
-- active, the assignment belongs to this workspace's program and is
-- published, and a resubmission only follows a REVISION_REQUESTED /
-- REJECTED prior attempt.
create or replace function public.set_workspace_submission_attempt_number()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_status text;
  v_prev_status text;
  v_next int;
begin
  select w.workspace_status into v_status
  from public.internship_workspaces w
  where w.id = new.workspace_id;

  if v_status is null then
    raise exception 'Referenced internship workspace does not exist.' using errcode = '23503';
  end if;
  if v_status not in ('ACCEPTED', 'IN_PROGRESS') then
    raise exception 'Submissions are only accepted while the internship workspace is active.'
      using errcode = '42501';
  end if;

  if not exists (
    select 1
    from public.program_assignments a
    join public.internship_programs prog on prog.id = a.program_id
    join public.internship_workspaces w on w.internship_id = prog.internship_id
    where a.id = new.assignment_id
      and w.id = new.workspace_id
      and a.is_published = true
  ) then
    raise exception 'This assignment is not part of your internship workspace.'
      using errcode = '42501';
  end if;

  select coalesce(max(s.attempt_number), 0) + 1 into v_next
  from public.workspace_submissions s
  where s.workspace_id = new.workspace_id
    and s.assignment_id = new.assignment_id;

  if v_next > 1 then
    select s.submission_status into v_prev_status
    from public.workspace_submissions s
    where s.workspace_id = new.workspace_id
      and s.assignment_id = new.assignment_id
    order by s.attempt_number desc
    limit 1;

    if v_prev_status not in ('REVISION_REQUESTED', 'REJECTED') then
      raise exception 'You can only resubmit after a revision has been requested.'
        using errcode = '42501';
    end if;
  end if;

  new.attempt_number := v_next;
  return new;
end;
$$;

revoke all on function public.set_workspace_submission_attempt_number() from public;

drop trigger if exists workspace_submissions_set_attempt_number on workspace_submissions;
create trigger workspace_submissions_set_attempt_number
  before insert on workspace_submissions
  for each row
  execute procedure public.set_workspace_submission_attempt_number();

-- BEFORE UPDATE: a submission is append-only. Only submission_status (the
-- denormalized review cache) may change; every content and identity field
-- is frozen. Resubmit as a new attempt instead.
create or replace function public.prevent_workspace_submission_content_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.id is distinct from old.id
    or new.workspace_id is distinct from old.workspace_id
    or new.assignment_id is distinct from old.assignment_id
    or new.attempt_number is distinct from old.attempt_number
    or new.repo_url is distinct from old.repo_url
    or new.live_url is distinct from old.live_url
    or new.attachment_url is distinct from old.attachment_url
    or new.notes is distinct from old.notes
    or new.submitted_at is distinct from old.submitted_at
    or new.created_at is distinct from old.created_at
  then
    raise exception 'A submission is append-only -- only its review status may change. Resubmit as a new attempt instead.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_workspace_submission_content_change() from public;

drop trigger if exists workspace_submissions_prevent_content_change on workspace_submissions;
create trigger workspace_submissions_prevent_content_change
  before update on workspace_submissions
  for each row
  execute procedure public.prevent_workspace_submission_content_change();

drop trigger if exists workspace_submissions_set_updated_at on workspace_submissions;
create trigger workspace_submissions_set_updated_at
  before update on workspace_submissions
  for each row
  execute procedure public.set_updated_at();

alter table workspace_submissions enable row level security;

drop policy if exists "Students can view their own submissions" on workspace_submissions;
create policy "Students can view their own submissions"
  on workspace_submissions for select
  to authenticated
  using (public.student_owns_workspace(workspace_submissions.workspace_id));

drop policy if exists "Students can submit to their own workspace" on workspace_submissions;
create policy "Students can submit to their own workspace"
  on workspace_submissions for insert
  to authenticated
  with check (public.student_owns_workspace(workspace_submissions.workspace_id));

drop policy if exists "Industry can view submissions for their own internships" on workspace_submissions;
create policy "Industry can view submissions for their own internships"
  on workspace_submissions for select
  to authenticated
  using (public.industry_owns_workspace(workspace_submissions.workspace_id));

-- Industry UPDATE is limited to the submission_status cache by
-- prevent_workspace_submission_content_change.
drop policy if exists "Industry can update submission status for their own internships" on workspace_submissions;
create policy "Industry can update submission status for their own internships"
  on workspace_submissions for update
  to authenticated
  using (public.industry_owns_workspace(workspace_submissions.workspace_id))
  with check (public.industry_owns_workspace(workspace_submissions.workspace_id));

-- No DELETE policy -- full attempt history is permanent.

-- ============================================================
-- 2. submission_reviews -- append-only, industry source of truth
-- ============================================================

create table if not exists submission_reviews (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references workspace_submissions (id) on delete cascade,
  reviewer_id uuid not null references profiles (id) on delete restrict,

  verdict text not null check (verdict in ('ACCEPTED', 'REVISION_REQUESTED', 'REJECTED')),
  feedback text,
  score numeric(6, 2) check (score is null or score >= 0),

  created_at timestamptz not null default now()
);

create index if not exists submission_reviews_submission_id_idx on submission_reviews (submission_id);

-- BEFORE INSERT: record the reviewer as the caller and verify they own
-- the internship behind the submission's workspace.
create or replace function public.set_submission_review_reviewer()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_industry_id uuid;
begin
  select w.industry_id into v_industry_id
  from public.workspace_submissions s
  join public.internship_workspaces w on w.id = s.workspace_id
  where s.id = new.submission_id;

  if v_industry_id is null then
    raise exception 'Referenced submission does not exist.' using errcode = '23503';
  end if;

  if current_setting('role', true) <> 'service_role' then
    if auth.uid() <> v_industry_id then
      raise exception 'Only the industry that owns this internship can review its submissions.'
        using errcode = '42501';
    end if;
    new.reviewer_id := auth.uid();
  end if;

  return new;
end;
$$;

revoke all on function public.set_submission_review_reviewer() from public;

drop trigger if exists submission_reviews_set_reviewer on submission_reviews;
create trigger submission_reviews_set_reviewer
  before insert on submission_reviews
  for each row
  execute procedure public.set_submission_review_reviewer();

alter table submission_reviews enable row level security;

drop policy if exists "Students can view reviews of their own submissions" on submission_reviews;
create policy "Students can view reviews of their own submissions"
  on submission_reviews for select
  to authenticated
  using (
    exists (
      select 1 from workspace_submissions s
      where s.id = submission_reviews.submission_id
        and public.student_owns_workspace(s.workspace_id)
    )
  );

drop policy if exists "Industry can view reviews for their own internships" on submission_reviews;
create policy "Industry can view reviews for their own internships"
  on submission_reviews for select
  to authenticated
  using (
    exists (
      select 1 from workspace_submissions s
      where s.id = submission_reviews.submission_id
        and public.industry_owns_workspace(s.workspace_id)
    )
  );

drop policy if exists "Industry can add reviews for their own internships" on submission_reviews;
create policy "Industry can add reviews for their own internships"
  on submission_reviews for insert
  to authenticated
  with check (
    exists (
      select 1 from workspace_submissions s
      where s.id = submission_reviews.submission_id
        and public.industry_owns_workspace(s.workspace_id)
    )
  );

-- No UPDATE policy (a correction is a new review row) and no DELETE policy
-- (feedback history is permanent).

-- ============================================================
-- 3. internship_completions -- explicit verification, never automatic
-- ============================================================

create table if not exists internship_completions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references internship_workspaces (id) on delete cascade,
  verified_by uuid references profiles (id) on delete restrict,

  -- REQUIREMENTS_MET is the system-created pre-state (all in-scope
  -- required assignments accepted). COMPLETED is set ONLY by an explicit
  -- industry "verify" action -- computed progress never sets it.
  completion_status text not null default 'REQUIREMENTS_MET'
    check (completion_status in ('REQUIREMENTS_MET', 'COMPLETED')),
  outcome text check (outcome in ('PASS', 'FAIL')),
  summary text,
  verified_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint internship_completions_one_per_workspace unique (workspace_id),
  constraint internship_completions_completed_requires_verification check (
    completion_status <> 'COMPLETED'
    or (outcome is not null and verified_by is not null and verified_at is not null)
  )
);

-- BEFORE INSERT OR UPDATE: workspace_id is immutable; a non-service_role
-- caller crossing into COMPLETED is recorded as the verifier at now().
create or replace function public.set_internship_completion_verifier()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and new.workspace_id is distinct from old.workspace_id then
    raise exception 'Cannot move a completion record to another workspace.' using errcode = '42501';
  end if;

  if current_setting('role', true) <> 'service_role'
     and new.completion_status = 'COMPLETED'
     and (tg_op = 'INSERT' or old.completion_status is distinct from 'COMPLETED')
  then
    new.verified_by := auth.uid();
    if new.verified_at is null then
      new.verified_at := now();
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.set_internship_completion_verifier() from public;

drop trigger if exists internship_completions_set_verifier on internship_completions;
create trigger internship_completions_set_verifier
  before insert or update on internship_completions
  for each row
  execute procedure public.set_internship_completion_verifier();

drop trigger if exists internship_completions_set_updated_at on internship_completions;
create trigger internship_completions_set_updated_at
  before update on internship_completions
  for each row
  execute procedure public.set_updated_at();

alter table internship_completions enable row level security;

drop policy if exists "Students can view their own completion record" on internship_completions;
create policy "Students can view their own completion record"
  on internship_completions for select
  to authenticated
  using (public.student_owns_workspace(internship_completions.workspace_id));

drop policy if exists "Industry can view completion records for their own internships" on internship_completions;
create policy "Industry can view completion records for their own internships"
  on internship_completions for select
  to authenticated
  using (public.industry_owns_workspace(internship_completions.workspace_id));

drop policy if exists "Industry can create completion records for their own internships" on internship_completions;
create policy "Industry can create completion records for their own internships"
  on internship_completions for insert
  to authenticated
  with check (public.industry_owns_workspace(internship_completions.workspace_id));

drop policy if exists "Industry can verify completion for their own internships" on internship_completions;
create policy "Industry can verify completion for their own internships"
  on internship_completions for update
  to authenticated
  using (public.industry_owns_workspace(internship_completions.workspace_id))
  with check (public.industry_owns_workspace(internship_completions.workspace_id));

-- No DELETE policy.

-- ============================================================
-- 4. internship_certificates -- issuer-generated, immutable, 1:1 w/ PASS
-- ============================================================

create table if not exists internship_certificates (
  id uuid primary key default gen_random_uuid(),
  completion_id uuid not null references internship_completions (id) on delete restrict,

  -- Denormalized from the completion -> workspace chain by
  -- set_internship_certificate_derived_ids, then frozen. The certificate
  -- is a historical artifact and must stay correct even if the workspace,
  -- program, internship or profiles change later.
  workspace_id uuid not null references internship_workspaces (id) on delete restrict,
  student_id uuid not null references profiles (id) on delete restrict,
  industry_id uuid not null references profiles (id) on delete restrict,
  internship_id uuid not null references internships (id) on delete restrict,

  -- Server-generated, unique, immutable. Format: AIC-INT-{YYYY}-{base32(8 bytes)}.
  certificate_number text not null,

  -- Self-contained public snapshot: { student_name, company_name, title,
  -- skills, outcome, ... }. Populated by the issuing service (later phase);
  -- verify_internship_certificate() prefers it over live joins.
  details jsonb not null default '{}'::jsonb,

  issued_at timestamptz not null default now(),
  pdf_url text,
  revoked_at timestamptz,
  revoke_reason text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint internship_certificates_one_per_completion unique (completion_id),
  constraint internship_certificates_number_unique unique (certificate_number),
  constraint internship_certificates_revoke_fields_paired
    check ((revoked_at is null) = (revoke_reason is null))
);

create index if not exists internship_certificates_workspace_id_idx on internship_certificates (workspace_id);
create index if not exists internship_certificates_student_id_idx on internship_certificates (student_id);

-- RFC 4648 base32 of 8 CSPRNG bytes, via exact base-32 digit extraction on
-- numeric. No pgcrypto dependency and no bit-string cast: gen_random_uuid()
-- is the CSPRNG, md5() + decode(...,'hex') (both core) give a 16-byte
-- digest, get_byte() (core) reads the first 8 bytes, and numeric holds the
-- 64-bit value exactly (0 .. 2^64-1, always non-negative).
create or replace function public.generate_internship_certificate_number()
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

  -- 8 bytes -> 13 base32 chars (65 bits of capacity; the leading char is
  -- only ever 'A'/'B'). Prepend so the most significant digit comes first.
  for v_i in 1..13 loop
    v_body := substr(v_alphabet, (mod(v_num, 32))::int + 1, 1) || v_body;
    v_num := div(v_num, 32);
  end loop;

  return 'AIC-INT-' || to_char(now(), 'YYYY') || '-' || v_body;
end;
$$;

revoke all on function public.generate_internship_certificate_number() from public;
revoke all on function public.generate_internship_certificate_number() from anon;
revoke all on function public.generate_internship_certificate_number() from authenticated;

-- BEFORE INSERT: derive the denormalized ids from the completion, require
-- outcome = PASS, and mint the certificate number if not supplied.
create or replace function public.set_internship_certificate_derived_ids()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_workspace_id uuid;
  v_student_id uuid;
  v_industry_id uuid;
  v_internship_id uuid;
  v_outcome text;
begin
  select w.id, w.student_id, w.industry_id, w.internship_id, c.outcome
    into v_workspace_id, v_student_id, v_industry_id, v_internship_id, v_outcome
  from public.internship_completions c
  join public.internship_workspaces w on w.id = c.workspace_id
  where c.id = new.completion_id;

  if v_workspace_id is null then
    raise exception 'Referenced internship completion does not exist.' using errcode = '23503';
  end if;
  if v_outcome is distinct from 'PASS' then
    raise exception 'A certificate can only be issued for a PASSED internship completion.'
      using errcode = '42501';
  end if;

  new.workspace_id  := v_workspace_id;
  new.student_id    := v_student_id;
  new.industry_id   := v_industry_id;
  new.internship_id := v_internship_id;

  if new.certificate_number is null or length(trim(new.certificate_number)) = 0 then
    new.certificate_number := public.generate_internship_certificate_number();
  end if;

  return new;
end;
$$;

revoke all on function public.set_internship_certificate_derived_ids() from public;

drop trigger if exists internship_certificates_set_derived_ids on internship_certificates;
create trigger internship_certificates_set_derived_ids
  before insert on internship_certificates
  for each row
  execute procedure public.set_internship_certificate_derived_ids();

-- BEFORE UPDATE: a certificate is immutable except for pdf_url and its
-- revocation state.
create or replace function public.prevent_internship_certificate_tamper()
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
    or new.workspace_id is distinct from old.workspace_id
    or new.student_id is distinct from old.student_id
    or new.industry_id is distinct from old.industry_id
    or new.internship_id is distinct from old.internship_id
    or new.certificate_number is distinct from old.certificate_number
    or new.issued_at is distinct from old.issued_at
    or new.details is distinct from old.details
    or new.created_at is distinct from old.created_at
  then
    raise exception 'A certificate is immutable except for its document URL and revocation state.'
      using errcode = '42501';
  end if;

  return new;
end;
$$;

revoke all on function public.prevent_internship_certificate_tamper() from public;

drop trigger if exists internship_certificates_prevent_tamper on internship_certificates;
create trigger internship_certificates_prevent_tamper
  before update on internship_certificates
  for each row
  execute procedure public.prevent_internship_certificate_tamper();

drop trigger if exists internship_certificates_set_updated_at on internship_certificates;
create trigger internship_certificates_set_updated_at
  before update on internship_certificates
  for each row
  execute procedure public.set_updated_at();

alter table internship_certificates enable row level security;

drop policy if exists "Students can view their own certificate" on internship_certificates;
create policy "Students can view their own certificate"
  on internship_certificates for select
  to authenticated
  using (auth.uid() = student_id and public.is_student(auth.uid()));

drop policy if exists "Industry can view certificates for their own internships" on internship_certificates;
create policy "Industry can view certificates for their own internships"
  on internship_certificates for select
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can issue certificates for their own internships" on internship_certificates;
create policy "Industry can issue certificates for their own internships"
  on internship_certificates for insert
  to authenticated
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

drop policy if exists "Industry can update certificate document and revocation" on internship_certificates;
create policy "Industry can update certificate document and revocation"
  on internship_certificates for update
  to authenticated
  using (auth.uid() = industry_id and public.is_industry(auth.uid()))
  with check (auth.uid() = industry_id and public.is_industry(auth.uid()));

-- No DELETE policy. No public/anon table policy -- public verification is
-- ONLY via verify_internship_certificate() below.

-- ============================================================
-- 5. stipend_disbursements -- record-keeping only
-- ============================================================

create table if not exists stipend_disbursements (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references internship_workspaces (id) on delete cascade,
  released_by uuid references profiles (id) on delete restrict,

  amount numeric(12, 2) not null check (amount >= 0),
  currency text not null default 'INR',

  disbursement_status text not null default 'PENDING'
    check (disbursement_status in ('PENDING', 'APPROVED', 'RELEASED', 'CANCELLED')),
  reference text,
  notes text,
  released_at timestamptz,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint stipend_disbursements_one_per_workspace unique (workspace_id),
  constraint stipend_disbursements_released_fields check (
    disbursement_status <> 'RELEASED' or (released_at is not null and released_by is not null)
  )
);

-- BEFORE UPDATE: workspace_id immutable; RELEASED and CANCELLED are
-- terminal; a non-service_role caller crossing into RELEASED is recorded
-- as the releaser at now().
create or replace function public.enforce_stipend_disbursement_transitions()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if current_setting('role', true) = 'service_role' then
    return new;
  end if;

  if new.workspace_id is distinct from old.workspace_id then
    raise exception 'Cannot move a stipend record to another workspace.' using errcode = '42501';
  end if;

  if old.disbursement_status in ('RELEASED', 'CANCELLED')
     and new.disbursement_status is distinct from old.disbursement_status
  then
    raise exception 'A released or cancelled stipend record cannot change state.'
      using errcode = '42501';
  end if;

  if new.disbursement_status = 'RELEASED'
     and old.disbursement_status is distinct from 'RELEASED'
  then
    new.released_by := auth.uid();
    if new.released_at is null then
      new.released_at := now();
    end if;
  end if;

  return new;
end;
$$;

revoke all on function public.enforce_stipend_disbursement_transitions() from public;

drop trigger if exists stipend_disbursements_enforce_transitions on stipend_disbursements;
create trigger stipend_disbursements_enforce_transitions
  before update on stipend_disbursements
  for each row
  execute procedure public.enforce_stipend_disbursement_transitions();

drop trigger if exists stipend_disbursements_set_updated_at on stipend_disbursements;
create trigger stipend_disbursements_set_updated_at
  before update on stipend_disbursements
  for each row
  execute procedure public.set_updated_at();

alter table stipend_disbursements enable row level security;

-- Student: READ-ONLY visibility of their own record.
drop policy if exists "Students can view their own stipend record" on stipend_disbursements;
create policy "Students can view their own stipend record"
  on stipend_disbursements for select
  to authenticated
  using (public.student_owns_workspace(stipend_disbursements.workspace_id));

drop policy if exists "Industry can view stipend records for their own internships" on stipend_disbursements;
create policy "Industry can view stipend records for their own internships"
  on stipend_disbursements for select
  to authenticated
  using (public.industry_owns_workspace(stipend_disbursements.workspace_id));

drop policy if exists "Industry can create stipend records for their own internships" on stipend_disbursements;
create policy "Industry can create stipend records for their own internships"
  on stipend_disbursements for insert
  to authenticated
  with check (public.industry_owns_workspace(stipend_disbursements.workspace_id));

drop policy if exists "Industry can update stipend records for their own internships" on stipend_disbursements;
create policy "Industry can update stipend records for their own internships"
  on stipend_disbursements for update
  to authenticated
  using (public.industry_owns_workspace(stipend_disbursements.workspace_id))
  with check (public.industry_owns_workspace(stipend_disbursements.workspace_id));

-- No DELETE policy.

-- ============================================================
-- 6. Public certificate verification
-- ============================================================
-- SECURITY DEFINER + pinned empty search_path. Exposes ONLY: the
-- certificate number (the caller's own input, echoed), the student's
-- display name, the company name, the internship/program title, the issue
-- date, and VALID / REVOKED. It exposes NO email, NO profile/application/
-- workspace/internship UUID, NO submission or stipend data. Prefers the
-- frozen JSONB snapshot; falls back to live joins for older rows.
--
-- Granted to anon + authenticated: verification is public by design
-- (this is the one deliberate difference from
-- application_applicant_names / collaboration_counterparty_names, which
-- are authenticated-only). Enumeration yields only what a certificate is
-- meant to publicly attest.

create or replace function public.verify_internship_certificate(p_number text)
returns table (
  certificate_number text,
  student_name text,
  company_name text,
  title text,
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
    coalesce(c.details ->> 'student_name', sp.full_name)                        as student_name,
    coalesce(c.details ->> 'company_name', ip.company_name)                     as company_name,
    coalesce(c.details ->> 'title', i.title)                                    as title,
    c.issued_at,
    case when c.revoked_at is not null then 'REVOKED' else 'VALID' end          as status
  from public.internship_certificates c
  left join public.profiles sp          on sp.id = c.student_id
  left join public.industry_profiles ip on ip.id = c.industry_id
  left join public.internships i        on i.id = c.internship_id
  where c.certificate_number = p_number;
$$;

revoke all on function public.verify_internship_certificate(text) from public;
grant execute on function public.verify_internship_certificate(text) to anon, authenticated;

-- ============================================================
-- 7. student_notifications CHECK widening (the one existing-schema change)
-- ============================================================
-- Additive to the allowed value sets only: `type` gains 'INTERNSHIP',
-- `related_entity_type` gains 'INTERNSHIP_WORKSPACE'. Every existing row
-- still satisfies the widened constraints -> forward-only, non-destructive.
-- The 035 inline CHECKs are auto-named by Postgres; the DO blocks resolve
-- the real single-column constraint name from the catalog before swapping,
-- so this is correct regardless of that naming.

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.student_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'type';

  if v_name is not null then
    execute format('alter table public.student_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.student_notifications
  add constraint student_notifications_type_check
  check (type in (
    'APPLICATION_STATUS', 'INTERVIEW', 'ASSESSMENT', 'LEARNING',
    'MENTORSHIP', 'EVENT', 'SYSTEM', 'INTERNSHIP'
  ));

do $$
declare
  v_name text;
begin
  select con.conname into v_name
  from pg_constraint con
  join pg_attribute att
    on att.attrelid = con.conrelid and att.attnum = con.conkey[1]
  where con.conrelid = 'public.student_notifications'::regclass
    and con.contype = 'c'
    and array_length(con.conkey, 1) = 1
    and att.attname = 'related_entity_type';

  if v_name is not null then
    execute format('alter table public.student_notifications drop constraint %I', v_name);
  end if;
end $$;

alter table public.student_notifications
  add constraint student_notifications_related_entity_type_check
  check (related_entity_type in (
    'APPLICATION', 'INTERVIEW', 'ASSESSMENT', 'LEARNING_RESOURCE',
    'MENTORSHIP', 'EVENT', 'INTERNSHIP_WORKSPACE'
  ));

-- ============================================================
-- Post-conditions (for a live check after `supabase db push`)
-- ============================================================
--   -- certificate number format + uniqueness:
--   select public.generate_internship_certificate_number();
--   -- -> 'AIC-INT-2026-XXXXXXXXXXXXX' (13 base32 chars). Two calls differ.
--
--   -- verification exposes only safe fields:
--   select * from public.verify_internship_certificate('<number>');
--   -- -> exactly (certificate_number, student_name, company_name, title,
--   --    issued_at, status). No id / email / application_id / workspace_id.
--
--   -- append-only submissions:
--   -- update workspace_submissions set repo_url = '...'  ->  42501.
--   -- update workspace_submissions set submission_status = 'ACCEPTED'  ->  ok (industry).
--
--   -- stipend terminal states:
--   -- update stipend_disbursements set disbursement_status = 'PENDING'
--   --   where disbursement_status = 'RELEASED'  ->  42501.
--
--   -- one certificate per completion / one stipend per workspace:
--   -- a second row for the same completion_id / workspace_id  ->  23505.
--
--   -- notification CHECK widening kept all originals:
--   select pg_get_constraintdef(oid) from pg_constraint
--   where conrelid = 'public.student_notifications'::regclass and contype = 'c';
--   -- -> type list still has APPLICATION_STATUS..SYSTEM, plus INTERNSHIP;
--   --    related_entity_type list still has APPLICATION..EVENT, plus
--   --    INTERNSHIP_WORKSPACE; the *_paired 2-column check is untouched.
--
--   -- existing notification rows still valid:
--   -- (035 ships the table empty; any later rows use the original values,
--   --  all of which remain in the widened sets.)
