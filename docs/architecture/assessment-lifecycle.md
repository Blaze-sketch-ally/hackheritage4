# Assessment Lifecycle Contract

This is the contract future phases must follow. It exists because Phase 1K
introduced the one distinction the whole assessment system now depends on:

> **Configuration determines what can happen. An attempt records what
> actually happened. Historical records are never reconstructed from
> today's configuration.**

Concretely: the question bank and the blueprint are *configuration* — they
describe what's currently possible. `assessment_attempt_questions` is a
*fact* — a permanent record of what was actually selected for one specific
student's one specific attempt, at the moment they started it. Nothing
downstream of attempt creation (scoring, results) ever re-derives its
question population from current configuration again. This is not a style
preference; Phase 1K's own real-Supabase verification found and fixed
several bugs that were all, at root, some code path forgetting this
distinction (see the Phase 1K development and hardening reports for the
full account).

| Concept | Role |
|---|---|
| Question bank (`assessment_questions`) | Current configuration |
| Question `is_active` state | Governs eligibility for **future** attempt generation only |
| Blueprint (`assessment_blueprint_rules`) | Generation rule, applies to attempts created *after* it's set |
| Attempt question set (`assessment_attempt_questions`) | Historical realization — fixed at creation, permanent |
| An existing attempt (once created) | Independent historical state — never re-reads configuration again |

## The chain

```
Assessment                  (container: title, difficulty, skill_id)
    ↓
Question Bank                (assessment_questions — shared, multi-setter)
    ↓ peer review
Approved Pool                 (review_status = APPROVED, is_active = true,
                                scoring_method = OBJECTIVE)
    ↓
Blueprint                     (assessment_blueprint_rules — difficulty → count)
    ↓ create_assessment_attempt() — ONE atomic transaction
Persisted Attempt Question Set (assessment_attempt_questions — immutable)
    ↓
Student UI                    (GET /attempts/{id}/questions — reads ONLY
                                the persisted set, never the live pool)
    ↓
Answers                       (assessment_answers, scoped to attempt_id)
    ↓
Submission                    (completeness checked against the persisted
                                set, not the live pool)
    ↓ score_assessment_attempt() — ONE atomic transaction
Score                         (computed once, over the persisted set)
    ↓
Results                       (GET /attempts/{id}/result — reconstructed
                                from assessment_answers, never re-derived
                                from current question-bank state)
```

## Stage-by-stage ownership

| Stage | Owning table | Owning API | Owning service | Security boundary | Mutable? | Historical? |
|---|---|---|---|---|---|---|
| Assessment | `assessments` | `GET /assessments`, `GET /assessments/{id}` | `assessment_service` | RLS: readable by student or faculty; writable only by `service_role` (no assessment-CRUD API exists) | Yes, by `service_role` only | Referenced by history, not itself historical |
| Question bank | `assessment_questions`, `..._options`, `..._answers` | `app/api/questions.py` | `question_bank_service` | RLS: any faculty may read any question; only the creator may write a non-approved question; only a *different* faculty member may transition PENDING → APPROVED/REJECTED, via `review_question()` | Content mutable only pre-approval; `is_active` always togglable | No — represents current state, not a historical fact |
| Blueprint | `assessment_blueprint_rules` | `GET`/`PUT /assessments/{id}/blueprint` | `question_bank_service` | RLS: readable by anyone authenticated; writable by any faculty | Fully mutable, any time | No — a rule, not a record of what happened |
| Attempt | `assessment_attempts` | `POST /assessments/{id}/attempts` | `assessment_service` | Created only via `create_assessment_attempt()` (service-role RPC); student can never supply `student_id`/`status`/score fields | `status`/`submitted_at` change through defined transitions only; score fields are trigger-protected | **Yes** |
| Persisted question set | `assessment_attempt_questions` | `GET /attempts/{id}/questions` | `assessment_service` | Written exactly once, inside `create_assessment_attempt()`. No `UPDATE`/`DELETE` policy exists for any role. | **No — immutable from the moment it's written** | **Yes** |
| Answers | `assessment_answers` | `POST /attempts/{id}/answers` | `assessment_service` | RLS scopes to the attempt's own student; only while `status = IN_PROGRESS` | Mutable until submission | **Yes** |
| Score | `assessment_attempts.score/total_marks/percentage` | `POST /attempts/{id}/score` | `assessment_service` (via `score_assessment_attempt()`) | Computed once, only by the trusted RPC; `prevent_self_attempt_scoring` trigger blocks any other write | Write-once | **Yes** |
| Results | (reconstructed) | `GET /attempts/{id}/result` | `assessment_service` | Reconstructed from `assessment_answers`, never from live `assessment_questions` state | N/A — a view, not stored | **Yes**, by construction |

## Invariants (verified, not assumed)

These were each independently confirmed against the real database, not
inferred from reading the code:

- Changing the question bank after an attempt exists **does not** change
  that attempt's question set.
- Changing the blueprint after an attempt exists **does not** change that
  attempt's question set — only attempts created *afterward* see the new
  rule.
- Deactivating a question that's already part of a persisted attempt does
  **not** remove it from that attempt's scoring population; the attempt
  still scores it, still totals its points. A student can still fully see
  and answer a deactivated-but-persisted question's content, in either
  order (deactivated before or after being answered) — migration 020
  widened the student-facing SELECT policies on `assessment_questions`
  and `assessment_question_options` to include "part of one of my own
  attempts," alongside the existing "currently approved and active"
  policy, so the question's content stays visible to its own attempt's
  student regardless of later deactivation. (This same table-level policy
  change also benefits `GET /attempts/{id}/result` — a question
  deactivated after an attempt completes no longer breaks that view
  either, though this was a pre-existing Phase 1I limitation, not
  something Phase 1K introduced.) A `None` embed on either endpoint is
  still treated as a hard failure, never a silently shorter list — after
  020 that should only happen for a genuinely unexpected condition, not
  the ordinary deactivation case.
- **`POST /attempts/{id}/answers` also follows this rule.** `is_active`
  controls eligibility for *future* attempt generation
  (`create_assessment_attempt()`'s own selection query), never the
  membership or answerability of a question already persisted into an
  existing attempt. `save_answer` checks membership in
  `assessment_attempt_questions` (`is_question_in_attempt()`) — never the
  question's current `review_status`/`is_active`/`scoring_method`. A
  question deactivated at any point during an attempt — before or after
  it's answered — remains answerable through that attempt for as long as
  the attempt itself is `IN_PROGRESS`. (Fixed in the Phase 1K
  final-hardening pass; previously, a pre-Phase-1K live-eligibility check
  here — `get_visible_question()` — could leave an in-progress attempt
  permanently unsubmittable if a selected question was deactivated before
  the student got to answer it. See the hardening report for the full
  account.)
- A faculty member can never approve or reject their own question — enforced
  independently by both `review_question()`'s own check and the
  `prevent_unauthorized_question_review` trigger.
- `assessment_attempt_questions` has no write policy for any role — the
  only way a row is ever created is inside `create_assessment_attempt()`.

## Future extension points

Read this before building on top of the assessment system:

- **Retakes.** The uniqueness rule is "one `IN_PROGRESS` attempt per
  student/assessment," not "one attempt ever" — `assessment_attempts` has
  no global uniqueness constraint, only a partial one scoped to
  `IN_PROGRESS`. A retake feature creates a new `assessment_attempts` row
  and a new, independently-randomized `assessment_attempt_questions` set
  through the same `create_assessment_attempt()` path — it does not need
  new schema.
- **Analytics.** Consume `assessment_attempts` / `assessment_attempt_questions`
  / `assessment_answers` as read-only historical data. Analytics code must
  never write to any of these tables, and must never influence
  `score_assessment_attempt()`.
- **AI-assisted authoring.** May suggest metadata (difficulty, topic,
  duplicate/quality warnings) attached to the question-bank workflow. Must
  never determine an answer key, never participate in question selection,
  never influence scoring, and the assessment system must keep working
  exactly as-is if the AI provider is completely unavailable.
- **Adaptive assessment**, if ever built, needs its own explicit
  attempt-question-selection mechanism — it must not bypass
  `assessment_attempt_questions` as the historical record of what a
  student actually saw.
- **Question versioning.** Not implemented, and not needed yet — content
  immutability post-approval already gives historical correctness. If a
  future requirement needs to *edit* approved content while preserving
  what past attempts saw, the extension point is a `question_version`
  table with `assessment_attempt_questions` snapshotting the version, not
  the live question row.

## Migration governance

**Migration files are the source of truth for future schema changes.**
The live database must be periodically reconciled against them, not the
other way around.

- Historical migrations are never rewritten to reflect a later
  correction, even when the live database has drifted from what a file
  describes (this happened three times during Phase 1K — see the
  stabilization report). A correction is always a new, additive migration
  that documents *why* it exists and what it found.
- `014_score_assessment_attempt.sql` in particular must never be edited —
  every Phase 1K change to its logic went through `CREATE OR REPLACE` in
  a later migration instead.
- The intended workflow for any future schema change:

  ```
  schema change → new migration → local/integration validation
      → RLS/RPC validation → application tests → commit
  ```

- **Replayability status, as of Phase 1K:** `003_skills.sql` and
  `004_assessments.sql` both attach triggers calling
  `public.set_updated_at()`, which is only *defined* in the later-numbered
  `012_student_profiles.sql`. A fresh database replaying migrations
  001→021 in strict filename order would fail at 003. This is **pre-existing
  technical debt, not a Phase 1K blocker** — it does not affect the
  already-bootstrapped live database migrations 015–021 were applied to,
  only a hypothetical from-scratch replay. Migrations 015–021 themselves
  have correct internal ordering (each depends only on objects defined in
  004, 012, or an earlier Phase 1K migration) and were verified applying
  cleanly in sequence against the live project. Not fixed here — fixing it
  would mean reordering or renumbering historical files, which the
  migration-governance rule above exists specifically to prevent without
  a deliberate, separate decision to do so.
- No `psql`, Supabase CLI, or direct Postgres connection string exists
  anywhere in this repository or its `.env` files, as of Phase 1K — every
  migration is applied by hand through the Supabase Dashboard SQL Editor.
  This is a known, real limitation (not a design choice) that materially
  slowed every RLS/RPC fix Phase 1K needed. Recommended before the next
  schema-heavy phase, not introduced here to avoid destabilizing the
  current deployment model without a deliberate decision to change it.

## Live-database testing

Mocked backend tests (`backend/tests/*.py`, run by plain `pytest -q`)
cannot prove RLS or `SECURITY DEFINER` RPC correctness — Phase 1K's own
history is the evidence: every real bug it found (a cross-setter RLS
failure, a reviewer-visibility gap, the deactivation-before-answering
gap) passed all 238 mocked tests the entire time it existed. Real
regression coverage for exactly this class of bug now lives in
`backend/tests/integration/` — opt-in only (`RUN_LIVE_INTEGRATION_TESTS=1`),
runs against the real Supabase project and a real running backend, never
touches the database in a normal `pytest -q` / CI run. See that
directory's own `README.md` for the fixture-safety rule (unique run IDs,
exact-ID cleanup, never a bare `LIKE '__QA_%'`) before adding to it.

## Role architecture

Current state, as of Phase 1K:

```
Authentication (Supabase)
    ↓
Profile lookup (profiles.role)
    ↓
Role guard (require_student() / require_faculty() in app.core.dependencies)
    ↓
Role-specific route/layout (frontend: app/student/layout.tsx, app/faculty/layout.tsx)
    ↓
Feature authorization (RLS + trigger, the real boundary either way)
```

`STUDENT` and `FACULTY` are the only roles with a working guard, on both
the backend (`require_student`/`require_faculty`) and the frontend
(`app/student/layout.tsx`/`app/faculty/layout.tsx` both perform a real
server-side role check; `app/admin`, `app/industry`, `app/institution`
layouts remain bare pass-throughs with no auth check at all — acceptable
only because those areas currently render no real content). `ADMIN`,
`INDUSTRY`, and `INSTITUTION` have no capabilities implemented and no
guard function — adding one is a single small function following the
exact shape of `require_faculty()`, not a redesign, whenever a real
feature for one of those roles is actually built. Do not add a guard
speculatively before there's a route that needs it.

## Design checklist for every future assessment-adjacent phase

Before implementing a new feature that touches any part of this chain,
answer these first:

- [ ] Is this current configuration, or historical state?
- [ ] What existing table owns this data?
- [ ] What existing API/service owns this behavior?
- [ ] What role is authorized, and by which existing guard?
- [ ] Does it affect *future* attempts, or does it need to leave *existing*
      attempts alone?
- [ ] Does it need a new migration, or does an existing table already
      cover it?
- [ ] Does it change any RLS policy? If so, has the change been tested
      live, not just against a mock?
- [ ] Does it change scoring or result semantics? If so, has that been
      explicitly approved — never silently?
- [ ] Does a regression test exist for it — mocked, and (if it touches
      RLS/RPC) in `tests/integration/`?

## What is explicitly *not* documented here

Assessment CRUD (creating a new assessment itself is `service_role`-only,
no API exists), admin-role workflows, and industry/institution flows are
all out of scope for this document — none of them exist yet.
