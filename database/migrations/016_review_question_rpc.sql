-- Migration: 016_review_question_rpc
-- Purpose: fixes a real bug found during Phase 1K real-Supabase QA
-- verification -- approving/rejecting another setter's PENDING question
-- through the plain RLS-gated UPDATE path (015's "Faculty can update
-- their own or review pending questions" policy) reliably failed with
-- Postgres's own generic "new row violates row-level security policy"
-- error the moment review_status actually changed away from PENDING,
-- even though the policy's own with_check (`is_faculty(auth.uid())`)
-- has no dependency on review_status at all and is_faculty(auth.uid())
-- was independently confirmed true for the reviewing user. Empirically
-- isolated with three live tests against the real database: (1) a true
-- no-op update (review_status: PENDING -> PENDING) succeeded, (2)
-- changing is_active only (review_status untouched) correctly failed
-- with the prevent_unauthorized_question_review TRIGGER's own message
-- ("Reviewers may only change review_status."), and (3) the real
-- transition (PENDING -> APPROVED) failed with Postgres's native RLS
-- message instead of ever reaching the trigger's logic at all -- proving
-- the rejection happens at the policy-evaluation layer specifically when
-- review_status changes, not in application logic or the trigger.
--
-- Rather than keep chasing the exact RLS mechanics of a two-permissive-
-- policy UPDATE with an OR'd USING clause, this migration moves the
-- approve/reject transition to a SECURITY DEFINER RPC -- the same
-- trusted-operation pattern already used for score_assessment_attempt()
-- and create_assessment_attempt() (014, 015), which sidesteps RLS's
-- UPDATE-policy evaluation for its own internal write entirely. Unlike
-- those two functions, this one is granted directly to `authenticated`
-- (not restricted to service_role) -- its OWN internal is_faculty/
-- ownership/pending checks are the complete security boundary for this
-- one operation, the same pattern already used for
-- get_email_for_identifier (001_profiles.sql), just for a write instead
-- of a read. The backend still calls it through the ordinary user-scoped
-- client (build_user_client), never service_role -- see
-- app.services.question_bank_service.set_review_status.
--
-- The prevent_unauthorized_question_review trigger (015) is UNCHANGED
-- and still fires for this RPC's internal UPDATE (BEFORE UPDATE triggers
-- fire regardless of caller privilege) -- it remains the real,
-- independent enforcement of "only review_status may change" and "only
-- APPROVED/REJECTED reachable this way, never by the row's own creator."
-- This RPC's own checks are additional defense in depth, not a
-- replacement for the trigger.
--
-- The plain UPDATE path (015's PATCH .../questions/{id} route) still
-- exists, still uses the same RLS policy + trigger as before, and is
-- UNCHANGED by this migration -- it remains correct for a question's own
-- creator editing their own non-approved content or resubmitting
-- (review_status -> PENDING only), which was never the transition that
-- exhibited this bug. Only the reviewer-approves/rejects-someone-elses-
-- question transition moves to this RPC.

create or replace function public.review_question(
  p_question_id uuid,
  p_decision text
)
returns public.assessment_questions
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_question public.assessment_questions;
begin
  if p_decision not in ('APPROVED', 'REJECTED') then
    raise exception 'Invalid review decision: %.', p_decision using errcode = '22023';
  end if;

  if not public.is_faculty(auth.uid()) then
    raise exception 'This action requires the FACULTY role.' using errcode = '42501';
  end if;

  select *
  into v_question
  from public.assessment_questions
  where id = p_question_id
  for update;

  if not found then
    raise exception 'Question not found.' using errcode = 'P0002';
  end if;

  if v_question.created_by = auth.uid() then
    raise exception 'Cannot review your own question.' using errcode = '42501';
  end if;

  if v_question.review_status <> 'PENDING' then
    raise exception 'Question is not pending review.' using errcode = '55000';
  end if;

  -- Fires prevent_unauthorized_question_review same as any other UPDATE
  -- to this table -- see header comment. That trigger independently
  -- re-confirms "only review_status changed" and "caller is not the
  -- creator," so this function's own checks above are defense in depth,
  -- not the sole enforcement.
  update public.assessment_questions
  set review_status = p_decision
  where id = p_question_id
  returning * into v_question;

  return v_question;
end;
$$;

revoke all on function public.review_question(uuid, text) from public;
revoke all on function public.review_question(uuid, text) from anon;
grant execute on function public.review_question(uuid, text) to authenticated;
