# Frontend ↔ FastAPI Integration

Until the assessment-taking UI (this phase), every built frontend feature
talked to Supabase directly from Next.js — auth, profile, skills. This
document covers the one exception: the Assessment API, which lives in
FastAPI (`backend/app/api/assessments.py`, `attempts.py`) because scoring
requires a trusted, service-role-only Postgres RPC that RLS structurally
forbids the browser from calling. This is the first (and, as of this
phase, only) frontend code that calls FastAPI at all.

## The bridge: `frontend/lib/api.ts`

Every FastAPI call goes through `apiFetch()` (or the `api.get/post/...`
convenience wrapper built on it). It:

1. Reads the current Supabase session via the **browser** Supabase client
   (`lib/supabase/client.ts`) — `getAccessToken()`.
2. Attaches it as `Authorization: Bearer <access_token>`.
3. Sets `Content-Type: application/json` only when a request body is
   actually sent (matters for `POST .../submit` and `.../score`, which
   have no body at all).
4. Parses the JSON response, or throws a typed `ApiError` (carrying the
   HTTP status and a message safe to show a user) for any non-2xx
   response, a network failure, or "no session at all" (401, before any
   request is even sent).

**This module is browser-only.** It must only be imported from Client
Components (`"use client"`). Server Components/Route Handlers that need
Supabase use `lib/supabase/server.ts`'s client instead — that path is
unrelated to this bridge and unchanged by this phase.

There is no second authentication system: the Supabase session is the
only source of identity. FastAPI (`app.core.dependencies`) validates the
token and derives the caller's identity from it; nothing in the frontend
sends a student id, and nothing in the frontend holds
`SUPABASE_SERVICE_ROLE_KEY` — that key exists only in `backend/.env` and
is never referenced by any browser/client-side file.

## Where the actual API calls live

`frontend/lib/student/assessment.ts` is the only place that constructs
Assessment API requests — components call `listAssessments()`,
`createAttempt()`, `saveAnswer()`, `submitAttempt()`, `scoreAttempt()`,
`getAttemptResult()`, etc., never `api.get/post` directly. This mirrors
the existing convention in `lib/student/skills.ts`/`profile.ts` (one
module per feature, exact field-for-field types matching the source).

Types live in `frontend/types/assessment.ts`, mirroring
`backend/app/schemas/assessment.py` exactly. One easy-to-miss fact
worth restating here: `score`, `total_marks`, `percentage`, `points`,
and `awarded_marks` are Pydantic `Decimal` fields, which this API
serializes as **JSON strings** (e.g. `"score": "40.0"`), not numbers.
The frontend types reflect this on purpose — never parse these into a
number to do arithmetic; every scored value is computed once, inside the
trusted PostgreSQL RPC, and the frontend only ever displays what the
backend already computed.

## No attempt-resume endpoint (a real, accepted gap)

There is no `GET /attempts/{attempt_id}` and no "list my answers"
endpoint — only `POST .../answers`, `.../submit`, `.../score`, and the
COMPLETED-only `GET .../result`. If a student reloads mid-attempt, there
is no backend-provided way to rediscover which attempt they were on.

This was a deliberate decision, not an oversight: no backend endpoint,
migration, or resume/retake system was added for it. Instead,
`frontend/lib/student/assessment-session.ts` mirrors the active
`attempt_id` and confirmed-saved answers to `sessionStorage`, keyed by
assessment id, purely so a **same-tab reload during one sitting**
recovers the UI. If that storage is gone (new tab, different device,
cleared storage) and the backend reports an already-in-progress attempt
(`POST .../attempts` → `409`, with no attempt id in the response), the
UI shows an honest "this attempt cannot be recovered from this device"
state with navigation back to the list — it never fabricates an attempt
id and never silently starts a second attempt.

## Testing

This phase also added the project's first frontend test framework
(Vitest + React Testing Library — there was none before). `lib/api.ts`
is unit-tested directly (auth header attachment, no-session handling,
error mapping, token-never-logged); the assessment components and view
are tested with mocked network responses. See `vitest.config.ts` /
`npm test`.
