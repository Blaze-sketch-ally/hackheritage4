-- Migration: 021_attempt_question_id_index
-- Purpose: Phase 1K final release-gate performance check --
-- assessment_attempt_questions has a composite primary key
-- (attempt_id, question_id) and an explicit extra index on attempt_id
-- alone (015), but no index serving lookups by question_id alone.
--
-- Migration 020's two new RLS policies ("Students can view
-- questions/options in their own attempts") both filter
-- assessment_attempt_questions by question_id (`where aq.question_id =
-- assessment_questions.id`) -- and RLS policies are evaluated per row,
-- for every SELECT against assessment_questions/assessment_question_options
-- any authenticated user makes (which now includes the full faculty
-- question-bank listing, per 018). A composite index whose leading
-- column is attempt_id gives little help to a query that filters on the
-- trailing column (question_id) alone -- this adds a dedicated index for
-- exactly that access pattern.
--
-- Pure performance change: no behavior, no security, no RLS/trigger
-- semantics affected. Safe to apply at any time.

create index if not exists assessment_attempt_questions_question_id_idx
  on assessment_attempt_questions (question_id);
