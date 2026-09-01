# Demo data

`industry_demo_seed.py` / `industry_demo.sql` populate the **Industry Portal
demonstration environment**: realistic, clearly-fictional data across every
Industry module, every lifecycle state, and every recipient role, so the
portal can be demoed without looking like an empty dev shell. Everything
else in this directory (`skills.sql`, `job_roles.sql`,
`assessment_catalog_data.py`, …) is unrelated reference/catalog seed data
and is untouched by it.

## Demo accounts

Username / password `DemoAIC!2026xQ7` (unchanged by this seed — do not
rotate):

| Account | Role | Represents |
|---|---|---|
| `technova_demo` | INDUSTRY | TechNova Solutions (DEMO) — AI/software company, Bengaluru |
| `dataforge_demo` | INDUSTRY | DataForge Labs (DEMO) — data engineering/analytics company, Hyderabad |
| `faculty_demo` | FACULTY | Collaboration recipient |
| `institution_demo` | INSTITUTION | Collaboration recipient |
| `student_demo_1` | STUDENT | Demo Student One (DEMO) — frontend/full-stack track |
| `student_demo_2` | STUDENT | Demo Student Two (DEMO) — backend/data-engineering track |

The database also holds real hackathon-participant accounts (test signups,
not demo data). The seed never reads or writes anything outside the six
ids above — every insert is scoped to a hardcoded demo owner/recipient/
student id, verified against the live `profiles` table.

## What's populated (per company, after this seed)

Each of the 6 Industry opportunity modules (internships, jobs, projects,
training, workshops, mentorship):

- **TechNova**: 8 records — 1 Draft, 4 Published, 1 Closed, 2 Archived.
- **DataForge**: 4 records — 1 Draft, 2–3 Published, 0–1 Closed.

Internships and jobs also carry 3–4 required skills each (level +
importance) from the existing skills catalog.

**Collaborations**: TechNova 12 (6 Faculty / 6 Institution, all 7 lifecycle
statuses represented — Draft, Sent, Accepted, Rejected, Active, Completed,
Cancelled); DataForge 2 (1 Sent to Faculty, 1 Active with Institution) so
Industry B also has a collaboration history to demo tenant isolation with.
The Sent collaborations are genuinely actionable — log in as `faculty_demo`
or `institution_demo` to see live Accept/Reject buttons.

**Recruitment**: 10 applications against TechNova postings from
`student_demo_1` / `student_demo_2` — 2 Applied, 2 Under Review, 2
Shortlisted, 2 Interview Scheduled, 1 Selected, 1 Rejected. Dashboard,
Applicants, Shortlisted/Interviews/Selected, and the `/applications`
summary endpoint all read the same rows, so their counts always agree.

**Student skills**: `student_demo_1` gains Machine Learning + FastAPI;
`student_demo_2` gains AWS + Apache Spark (on top of their existing
seeded skills) — additive only, nothing removed.

Every number above is *in addition to* whatever was already in the
database when the seed last ran — see "Idempotency" below.

## How to (re-)apply

```
# from backend/.venv so the `supabase` env vars resolve from backend/.env
python database/seed/industry_demo_seed.py --check    # report only, no writes
python database/seed/industry_demo_seed.py --apply     # idempotent insert
python database/seed/industry_demo_seed.py --emit-sql  # regenerate industry_demo.sql
```

The script talks to Supabase over PostgREST with the service-role key (from
`backend/.env`), so every insert still goes through the real schema — CHECK
constraints, foreign keys, enums, and the BEFORE INSERT triggers
(`set_application_industry_id`, `set_collaboration_recipient_type`,
`set_updated_at`) all fire exactly as they would for a real user action.
Nothing bypasses RLS on the read side; the service-role key is only used
here, never in frontend/backend application code.

`industry_demo.sql` is the same dataset expressed as plain, idempotent SQL
(`insert … select … where not exists (…)`, resolving accounts by username
and skills by name) for anyone who prefers to run it directly against
Supabase (SQL editor or `supabase db`) instead of the Python script. It is
generated from `industry_demo_seed.py --emit-sql` — edit the Python file,
not the `.sql` file, and regenerate.

## Idempotency / re-running safely

Every row is matched on a stable natural key before insert — owner +
title for opportunities and collaborations, the student/posting pair for
applications, student/skill for skills — and only inserted if that key is
absent. Running `--apply` twice in a row is safe: the second run reports
every row as "already present" and writes nothing. This is why re-running
the seed after a browser demo session (someone published a Draft, changed
a status, etc.) will not create duplicates or fight with what a presenter
just did on screen — it only ever adds what's still missing.

## Resetting

There is no scripted reset — the repository's migrations (see
`database/README.md`) forbid hard-deleting Industry records at the
database level (027/028), by design, so "reset" is not a supported
operation here. If a demo session leaves records in an inconvenient
lifecycle state (e.g. a Published posting someone Archived on stage), fix
it forward through the same UI/API actions used to get there — Publish,
Close, etc. — the same as any other Industry account would.

## Scope notes

- This seed is **additive only**. It never updates or deletes an existing
  row (demo or otherwise), including the original ~5-per-module TechNova
  set and 8 collaborations that predate it.
- It does not touch Faculty or Institution *portal* data/implementation —
  only adds collaboration rows addressed to the two recipient accounts,
  through the same `industry_collaborations` table Industry already uses.
- It does not implement Analytics, Global Search, or file uploads, and
  does not create new API routes, schema, or RLS policies.
