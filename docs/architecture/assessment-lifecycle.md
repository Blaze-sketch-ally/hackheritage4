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
- A completed attempt's `assessment_id`, `started_at`, and `submitted_at`
  are immutable, and an existing answer's `attempt_id`/`question_id` can
  never be reassigned — added in
  `023_role_and_attempt_integrity_hardening.sql` after a full-project
  audit found these were unguarded (reassignment/rewrite was never a
  legitimate operation, just previously unblocked). The existing
  submission flow (`mark_attempt_submitted()`, which legitimately sets
  `submitted_at` once while still `IN_PROGRESS`) is unaffected — the new
  check only locks a row once `status = 'COMPLETED'`.

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
  **Update (post-Phase-1L architecture audit):** the same forward-reference
  problem also applies to `public.is_student(uuid)` — `003_skills.sql`'s
  `student_skills` policies and `004_assessments.sql`'s `assessment_attempts`/
  `assessment_question_answers` policies all call it, but it isn't *defined*
  until `012_student_profiles.sql` either. A second, independent instance of
  the same class of gap, not a new one — same status (pre-existing, not
  blocking, not fixed here for the same reason).
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

## Skill Evidence Boundary (Phase 1L)

Phase 1L (skill-gap analysis / career roles) is a **read-only analysis
layer over assessment history** — it extends this chain, it does not
change it. Three concepts, three different roles:

| Concept | Role | Owning table |
|---|---|---|
| Career role requirements | Current configuration | `career_role_skill_requirements` (service_role-seeded, like `assessments`/`skills`) |
| A student's assessed skill evidence | Derived from historical fact, computed fresh on every read | **No new table** — `app.services.assessment_service.get_student_skill_scores()` reads directly from `assessment_attempts`/`assessments` |
| `student_skills` (003_skills.sql) | A *different* concept: self-reported, unverified proficiency a student typed in themselves | Deliberately untouched by Phase 1L, in either direction |

**Hard architectural decision, made explicitly, not by default:** Phase
1L does not create a `student_skill_levels` table, and does not sync
into the pre-existing `student_skills` table either — even though
004_assessments.sql's own closing comment once described a hypothetical
future sync from completed attempts into `student_skills`. That sync was
never built, and building it now would mean writing to (or immediately
after) the trusted scoring path — exactly the kind of change to Phase
1K's existing scoring model Phase 1L is scoped not to make. Instead, skill
evidence is computed on demand: the best `percentage` across a student's
own `COMPLETED` `assessment_attempts`, joined through
`assessments.skill_id`, keyed by skill. Skill evidence uses the same 0–100
scale as `assessment_attempts.percentage` — a career role's
`required_level` is directly comparable to it without any translation.

The deterministic comparison itself (`app.services.
skill_alignment_service.compute_alignment()`) is written generic over its
inputs, not career-role-specific, precisely so a future opportunity-
matching feature can reuse the identical algorithm against a different
requirements source without duplicating it — see that module's own
docstring.

## Opportunity Matching Boundary (Phase 1M)

Phase 1M (opportunities / jobs / internships / applications) is the
"future opportunity-matching feature" the section above anticipated —
it reuses `app.services.skill_alignment_service.compute_alignment()`
**unmodified**, against a second requirements source
(`opportunity_skill_requirements` instead of
`career_role_skill_requirements`), and the same
`get_student_skill_scores()` evidence read Phase 1L established. No
matching logic is duplicated; no new algorithm exists.

**Unified domain, not two:** jobs and internships are one table,
`opportunities`, distinguished only by `opportunity_type` (`JOB` |
`INTERNSHIP`). There is no separate business logic, schema, or service
per type anywhere in the backend — the frontend's Jobs/Internships pages
are thin, type-locked views over the same list/detail/apply components.

**Configuration vs. historical record**, extended one level further than
Phase 1L:

| Concept | Role | Owning table |
|---|---|---|
| An opportunity posting | Current configuration (industry-owned, DRAFT/PUBLISHED/CLOSED) | `opportunities` |
| Its skill requirements | Current configuration — **mutable only while DRAFT**; frozen the moment the posting is first PUBLISHED | `opportunity_skill_requirements` |
| A student's application | A historical event — the fact that a student applied, and what happened next | `applications` |
| A match score (student ⇄ opportunity) | Always a **current derived view**, computed fresh on every read from live requirements + live assessment evidence — **never stored, never snapshotted onto the application** | not a table — `opportunity_service`/`application_service` compute it on demand |

That last row is a deliberate, explicit choice: an application does not
freeze the match score at apply-time. If a student completes a new
assessment after applying, the score a reviewer sees updates
automatically — matching is a *live judgment aid*, not part of the
historical record. The historical record is only ever: did this student
apply, and what is the application's current status.

**Requirement immutability enforcement:** the RLS policy on
`opportunity_skill_requirements` permits INSERT/UPDATE/DELETE only while
the parent `opportunities.status = 'DRAFT'`. This is what makes "match is
always derived, no snapshot needed" actually true — once published, the
comparison basis for every existing/future applicant is guaranteed
stable, without needing to copy it anywhere.

**RLS ownership pattern**, the same join-through-ownership-chain
established in `020_student_view_own_attempt_questions.sql` and reused by
Phase 1L, applied twice more here: `opportunity_skill_requirements`'
SELECT policy joins through `opportunity_id`; `applications`' industry
SELECT/UPDATE policies join through `opportunity_id` to prove the
opportunity belongs to the caller. A third, narrower instance was added
directly to `profiles`: an industry account may `SELECT` the profile of a
student **only** if a real `applications` row proves that student
applied to one of that industry's opportunities — the first case in this
project of one role reading another named individual's profile, gated
entirely by a real relationship rather than role membership alone.

**Applicant match scores cross a service-role boundary, narrowly:**
`opportunity_service.list_opportunity_applicants()` first proves
ownership using the caller's own RLS-scoped client (an unowned
opportunity's applicant query returns empty before any privileged read
happens), then uses a service-role client only to read each
already-proven-legitimate applicant's own assessment evidence and compute
their score — the same class of narrow, justified trust as Phase 1K's
`create_attempt`/`score_attempt`. Only the computed aggregate score
crosses back out; raw assessment answers/evidence are never exposed to
an industry account.

## Portfolio Boundary — Phase 1N

Phase 1N (the digital portfolio) adds a **fourth** kind of evidence,
alongside the three the chain above already distinguishes:

| Concept | Role | Owning table |
|---|---|---|
| `student_skills` (003_skills.sql) | Self-reported, unverified | `student_skills` |
| Assessment evidence | Objectively derived, system-scored | `assessment_attempts`/`assessments` |
| Career role / opportunity requirements | Current configuration | `career_role_skill_requirements` / `opportunity_skill_requirements` |
| **Portfolio (Phase 1N)** | **Student-presented work/context — authored by the student, never scored** | `portfolio_projects` / `portfolio_certifications` |

Portfolio content is deliberately inert with respect to every other
system in the chain: a project's `technologies` array is never resolved
to a `skill_id` and never written into `student_skills`; portfolio rows
are never read by `assessment_service`, `skill_alignment_service`, or
either matching path (`opportunity_service.get_student_match` /
`application_service.list_opportunity_applicants` /
`get_applicant_detail`). **Portfolio does not influence matching** — a
student's `overall_score` against an opportunity, and the status of an
existing `applications` row, are both provably unchanged by adding or
removing a portfolio project (verified live, not just asserted — see
`tests/integration/test_portfolio_live.py`'s
`test_portfolio_changes_never_affect_match_or_application`). Portfolio
is context a reviewer sees *alongside* the match, never an input to it.

**Authorization chain**, the third instance of the join-through-
ownership-chain pattern this document already tracks (Phase 1M's
applicant-profile policy was the first):

```
industry (auth.uid()) → owns opportunity → student applied
  (applications.student_id) → industry may SELECT that student's
  portfolio_projects/portfolio_certifications rows
```

**No service-role access anywhere in this domain** — a deliberate
contrast with Phase 1M's applicant match-score path (which genuinely
needs `service_role` because RLS correctly has no cross-student
`assessment_attempts` visibility policy for any role). Portfolio
visibility is instead granted directly by RLS to a legitimate industry
applicant-reviewer, because there is no equivalent sensitivity concern —
so `GET /applications/{id}/portfolio` proves ownership via
`application_service.get_application()`'s own RLS-scoped read, then
re-reads the target student's portfolio through that *same*
caller-scoped client; the portfolio table's own SELECT policy is what
actually authorizes that second read, independently.

**Reassignment protection needs no bespoke trigger.** Every other
cross-role-owned table in this project (`applications`, `opportunities`)
needed an explicit immutability trigger because the party permitted to
write isn't always the row's own identity column. Portfolio rows are
different: the owner (`auth.uid() = student_id`) is the same identity
permitted to write, so RLS's own symmetric `USING`/`WITH CHECK` on
`UPDATE` blocks `student_id` reassignment for free — the new row fails
`WITH CHECK` the moment `student_id` no longer equals the caller's own
`auth.uid()`. See
`025_portfolio_projects_and_certifications.sql`'s own header comment.

## Evaluation Boundary — Phase F8.1

Phase F8 (Evaluation & Rubrics) adds the human-evaluation layer this
chain's own header comment always left open: `scoring_method` has allowed
`AI_EVALUATED` since `004_assessments.sql`, but nothing before F8
implemented what happens to a question marked that way. F8.1
(`045_evaluation_foundation.sql`) is the **database-only foundation** —
no API, no frontend, and it does not change objective scoring or grant
Faculty any new visibility into student answers. F8.2 (a dedicated
security phase) owns the actual `assessment_answers` RLS change; F8.4
owns integrating a finalized human score into `assessment_attempts.score`.

| Concept | Role | Owning table |
|---|---|---|
| An evaluator assignment | A historical fact — who was authorized to evaluate one exact `(attempt_id, question_id)`, and when | `evaluator_assignments` |
| A rubric | Current configuration, until a `FINALIZED` evaluation uses it — then usage-locked (see below) | `rubrics` / `rubric_criteria` |
| An evaluation (current state) | Mutable while not `FINALIZED`; immutable once `FINALIZED` | `evaluations` |
| An evaluation's history | Append-only — every transition, permanently | `evaluation_history` |

**Grain, chosen deliberately, not by default:** an assignment scopes
exactly `(evaluator, attempt_id, question_id)` — the same composite
primary key `assessment_attempt_questions` already uses, referenced via a
two-column foreign key rather than a bare `attempt_id`. Scoping at the
whole-attempt level would hand an evaluator every question in an attempt,
including ones nothing assigned them to; this grain is what lets a future
`assessment_answers` RLS policy (F8.2) join through the assignment and
grant nothing broader than what was actually assigned.

**Append-only history, not F7's latest-state model.** F7 (Review
Governance) deliberately stores only the current reviewer/note, reasoning
that nothing asks "show me every past review." F8 makes the opposite
choice for the identical-shaped problem, because a finalized evaluation
is a real, high-stakes number a student's outcome depends on:
`evaluations` is the current record (mirroring `assessment_answers`' own
"mutable while in progress, trigger-locked once it matters" shape), and
`evaluation_history` is a second, append-only table recording every
transition — the exact same two-table pattern
`faculty_assessment_permissions` + `faculty_assessment_permission_audit`
(`027_faculty_assessment_permissions.sql`) already established for
capability grants, reused here for a new domain rather than invented.

**Finalization is server-forced, not merely validated** —
`submitted_at`/`finalized_at`/`finalized_by` are always overwritten by
the trigger the moment their status is entered, regardless of what a
client sends. This is stricter than `044_question_review_governance.sql`'s
own `reviewed_by` (which only rejects a *mismatched* client value, rather
than ignoring it outright) — a corrected, stronger version of that same
lesson, applied here because a score is higher-stakes than a review note.

**Rubric immutability is usage-triggered, not versioned.** Once any
`FINALIZED` evaluation references a rubric, that rubric's (and its
criteria's) name/description/marks become immutable — the same pattern
`prevent_unauthorized_question_review()`'s `APPROVED` branch already uses
for question content, applied to rubrics rather than a new
version-chain/copy-on-use system.

**Mentor ≠ evaluator, unchanged.** F8.1 adds zero policies to `profiles`,
`student_profiles`, or either mentorship table — a mentor's visibility
(Phase F4.2, above) is exactly what it was before this phase, and an
evaluator's own new visibility is scoped to `evaluator_assignments` and
`evaluations` only, never to `assessment_answers` (still F8.2's
concern, not opened here).

**Assignment creation is `service_role`-only in F8.1, deliberately not
`is_admin()`-gated** even though `is_admin()`
(`035_admin_faculty_permission_management.sql`) already gates the
closely analogous `admin_grant_assessment_capability()`. Who the real
governance actor for evaluator assignment should be is an open decision
this phase does not resolve — see that migration's own header comment.

## Evaluator Answer Access — Phase F8.2

F8.2 (`046_evaluator_answer_access.sql`) is the first migration in this
project's history to grant any Faculty role read access to
`assessment_answers` beyond the mentor's existing summary-only policy
(`assessment_attempts.score/percentage`, no answer content, Phase F4.2
above). Implemented exactly as audited and approved — read access only,
no write policy anywhere in this migration.

**The full authorization chain, every link required:**

```
auth.uid()
  → is_faculty(auth.uid())                                          (015)
  → has_assessment_capability(auth.uid(), 'assessment_evaluator')   (027, checked LIVE on every query --
                                                                       SUSPENDED/EXPIRED/REVOKED removes
                                                                       access on the very next request,
                                                                       automatically)
  → an ACTIVE evaluator_assignments row for the EXACT
    (attempt_id, question_id) being read                            (045)
  → assessment_answers / assessment_attempts row visible
```

A capability alone is never sufficient — the explicitly rejected shape
(`has_assessment_capability(...) → SELECT assessment_answers`, with no
assignment check) would have exposed every student's answer to every
evaluator. `has_active_evaluator_assignment(p_attempt_id, p_question_id)`
is the one new helper (`SECURITY DEFINER`, `search_path=''`, derives the
evaluator's identity from `auth.uid()` only — never a caller-supplied
parameter, which would otherwise let one evaluator probe another's
assignments).

**Approved decisions this migration encodes:**
- **Co-evaluation is allowed.** Multiple different evaluators may hold
  simultaneous `ACTIVE` assignments to the same `(attempt_id,
  question_id)` — every policy scopes strictly to `auth.uid()`'s own
  assignment row, so revoking one co-evaluator's access never affects
  another's (verified live).
- **Student identity is visible** to the assigned evaluator via
  `assessment_attempts.student_id` on an attempt they are actually
  assigned to — but no policy was added to `profiles` of any kind; an
  evaluator learns a uuid, not a browsable profile.
- **No answer-key access.** `assessment_question_answers` remains exactly
  as protected as before this migration, for every role — the rubric
  (F8.1) is the authoritative grading criteria for human evaluation.
- **No `assessment_attempt_questions` access** — nothing an evaluator
  needs is missing without it (their own assignment already carries
  `attempt_id`/`question_id`, and `assessment_answers` carries both
  directly).
- **Rubric/rubric criteria visibility** is scoped to only the rubric
  actually attached to the reading evaluator's own evaluation — never a
  blanket "any evaluator reads any rubric" grant.
- **Mentor contributes nothing to evaluator authorization** — verified
  live for the mixed case (one Faculty account holding both `faculty_mentor`
  and `assessment_evaluator`, with an active mentorship *and* an active
  evaluator assignment for the same student): answer visibility appears
  only once the evaluator assignment exists, never from the mentorship
  alone.

**What F8.2 deliberately does not do:** no FastAPI route, no service, no
frontend — `require_assessment_evaluator` (existing) is left for F8.3 to
combine with an assignment-specific check at the service layer, the same
"RLS is the real boundary, the backend re-verifies as defense in depth"
pattern this project already uses in `attempts.py`'s `get_attempt_result`.
No change to `create_assessment_attempt()`/`score_assessment_attempt()` —
final score integration remains F8.4's concern.

## What is explicitly *not* documented here

Assessment CRUD (creating a new assessment itself is `service_role`-only,
no API exists), admin-role workflows, and institution flows are all out
of scope for this document — none of them exist yet. Industry flows are
now partially in scope as of Phase 1M (opportunity posting, requirements,
applicant review — see above); everything else industry-facing (offer
letters, interview scheduling, analytics) remains out of scope.
