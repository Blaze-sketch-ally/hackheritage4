-- Migration: 018_faculty_view_all_questions
-- Purpose: fixes the same class of bug 017 fixed, surfaced again by
-- real-Supabase QA verification -- this time for REJECT rather than
-- APPROVE. 017 widened the three faculty SELECT policies to include
-- APPROVED alongside "own (any status)" and "PENDING (any owner)", which
-- fixed a faculty reviewer losing visibility immediately after approving
-- someone else's question. The identical bug re-appeared for REJECT:
-- rejecting sets review_status to REJECTED, which 017's policy still did
-- not cover for a non-owner, so the reviewing faculty member again lost
-- visibility into the row (and its options/answer key) the moment they
-- rejected it.
--
-- Rather than patch this a third time by also special-casing REJECTED
-- (and risk missing some other transition later), this migration
-- resolves the underlying design question directly: is there any real
-- confidentiality reason review_status should gate a QUESTION's
-- visibility TO OTHER FACULTY at all? No -- PENDING questions are
-- already visible to every faculty member (that's the entire mechanism
-- peer review depends on), and 017 already established that APPROVED
-- content has no confidentiality reason to hide either. REJECTED is no
-- different: it's simply feedback on quality, not sensitive data, and
-- faculty are trusted peers collaborating on one shared bank. WRITE
-- access remains exactly as scoped as before (015/016/017 untouched on
-- that front) -- this migration only ever widens READ access, and only
-- for the FACULTY-facing policies (015's INSERT/UPDATE/DELETE policies
-- on all three tables, review_question(), and the STUDENT-facing SELECT
-- policies gated by is_student() + review_status = 'APPROVED' are all
-- completely unchanged).
--
-- Net result: any FACULTY caller may SELECT any question/its options/its
-- answer key, regardless of review_status or who created it. Ownership
-- and review-status conditions still fully govern every WRITE.

drop policy if exists "Faculty can view their own, pending, or approved questions" on assessment_questions;

create policy "Faculty can view any question"
  on assessment_questions for select
  to authenticated
  using (public.is_faculty(auth.uid()));

drop policy if exists "Faculty can view options for their own, pending, or approved questions" on assessment_question_options;

create policy "Faculty can view options for any question"
  on assessment_question_options for select
  to authenticated
  using (public.is_faculty(auth.uid()));

drop policy if exists "Faculty can view answer keys for their own, pending, or approved questions" on assessment_question_answers;

create policy "Faculty can view answer keys for any question"
  on assessment_question_answers for select
  to authenticated
  using (public.is_faculty(auth.uid()));
