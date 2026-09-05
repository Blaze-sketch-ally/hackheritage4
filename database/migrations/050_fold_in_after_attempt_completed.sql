-- Migration: 050_fold_in_after_attempt_completed
-- Purpose: Phase F8.4.2.1, Fix A -- closes the one remaining ordering
-- gap the F8.4.2.1 audit identified: an evaluator finalizing an
-- evaluation BEFORE the student's attempt reaches COMPLETED defers
-- fold-in (fold_in_attempt_evaluation() itself requires status =
-- 'COMPLETED', 049_evaluation_status_and_final_score.sql) -- and
-- nothing previously re-invoked it once the attempt later completed.
-- F8.4.2 (faculty_evaluations.update_evaluation_status) already covers
-- the opposite ordering (attempt COMPLETED first, evaluation FINALIZED
-- after) via a route-level trigger. This migration adds the missing
-- direction as a database trigger, so neither ordering depends on the
-- other for the final result to eventually become correct.
--
-- WHY A TRIGGER, NOT AN EDIT TO score_assessment_attempt(): the
-- F8.4.2.1 audit traced every SQL write site across every migration and
-- confirmed score_assessment_attempt() (014/015/048) is the ONLY place
-- that ever sets assessment_attempts.status = 'COMPLETED'. Either an
-- in-function call or an AFTER UPDATE trigger achieves identical
-- same-transaction atomicity (both execute inside the same transaction
-- as the triggering UPDATE; if either raises, the whole transaction --
-- including the attempt's own COMPLETED transition -- rolls back). A
-- trigger is strictly less invasive: it requires zero changes to the
-- already battle-tested 014/015/048 function bodies, and it
-- automatically covers any future code path that might ever set this
-- status, matching this project's own established preference for
-- trigger-enforced invariants (record_evaluation_history,
-- prevent_unauthorized_evaluation_change, both 045_evaluation_
-- foundation.sql) over inline duplication in every writer.
--
-- WHY THIS CANNOT RECURSE: fold_in_attempt_evaluation()'s own body
-- (049) never calls score_assessment_attempt(), never calls any other
-- function, and never writes assessment_attempts.status -- it only
-- reads evaluator_assignments/evaluations/rubrics/assessment_questions
-- and writes evaluation_status/final_score/final_total_marks/
-- final_percentage. The WHEN clause below (new.status = 'COMPLETED' and
-- old.status is distinct from 'COMPLETED') only matches the FIRST
-- transition into COMPLETED; fold-in's own subsequent UPDATE never
-- changes `status`, so old.status stays 'COMPLETED' and the WHEN clause
-- does not re-match -- no re-firing, no loop, no recursion of any kind,
-- direct or indirect.
--
-- WHY THIS CANNOT SELF-DEADLOCK: score_assessment_attempt() already
-- holds `select ... for update` on this exact attempt row from its own
-- first statement, for the life of its transaction.
-- fold_in_attempt_evaluation() independently opens with its own
-- `select ... for update` on the same row -- but a single Postgres
-- transaction never blocks on a row lock it already holds itself, so
-- this nested re-acquisition (via the trigger, within the SAME
-- transaction) succeeds immediately rather than deadlocking.
--
-- WHY OBJECTIVE-ONLY ATTEMPTS ARE UNCHANGED: the trigger fires
-- unconditionally on every COMPLETED transition, but
-- fold_in_attempt_evaluation()'s own v_required_count = 0 branch (no
-- AI_EVALUATED question in the attempt) is a cheap no-op that sets
-- evaluation_status = 'NOT_REQUIRED' -- already the column's own
-- default (049) -- and returns immediately. No change to score/
-- total_marks/percentage, no change to the response an objective-only
-- POST /attempts/{id}/score produces, no new failure mode for the
-- existing, unmodified objective-scoring path.
--
-- SECURITY: the trigger function is SECURITY DEFINER, set search_path
-- = '', owned by the same role that owns fold_in_attempt_evaluation()
-- (both created by this migration's own execution), so it retains the
-- implicit EXECUTE privilege function owners always keep regardless of
-- fold_in_attempt_evaluation()'s existing `revoke all ... from public/
-- anon/authenticated` (049) -- that revocation is unaffected and
-- unchanged by this migration. No new grant to any client-facing role.
-- No new RLS policy. No new client-callable route or RPC is exposed --
-- this trigger fires only as a side effect of the database itself
-- writing assessment_attempts.status = 'COMPLETED', never directly
-- callable by a student, evaluator, or any other authenticated caller.
create or replace function public.fold_in_after_attempt_completed()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform public.fold_in_attempt_evaluation(new.id);
  return new;
end;
$$;

revoke all on function public.fold_in_after_attempt_completed() from public;
revoke all on function public.fold_in_after_attempt_completed() from anon;
revoke all on function public.fold_in_after_attempt_completed() from authenticated;

drop trigger if exists assessment_attempts_fold_in_on_completion on assessment_attempts;

create trigger assessment_attempts_fold_in_on_completion
  after update on assessment_attempts
  for each row
  when (new.status = 'COMPLETED' and old.status is distinct from 'COMPLETED')
  execute procedure public.fold_in_after_attempt_completed();

-- ============================================================
-- NOT DONE HERE (explicitly, per F8.4.2.1's own scope boundary)
-- ============================================================
-- - No edit to 014_score_assessment_attempt.sql, 015_question_bank_
--   random_assessment.sql, or 048_ai_evaluated_attempt_participation.sql.
-- - No change to fold_in_attempt_evaluation() itself (049) -- reused
--   exactly as-is.
-- - No new RLS policy, no new grant to authenticated/anon.
-- - No new FastAPI route -- this trigger is not reachable by any
--   authenticated caller, directly or indirectly.
-- - No reconciliation authority, no moderator/lead activation.
-- - No student-facing exposure of evaluation_status/final_* anywhere.
