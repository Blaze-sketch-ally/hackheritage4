<title>AIC Portal — Project Context</title>

> **Read this file first.** It exists so a future Claude Code session (or a
> human) can resume work on AIC Portal without re-explaining the project.
> It was written by inspecting the actual repository, git history, and a
> long series of live tests against the real Supabase project — not
> guessed. Where something is uncertain or unverified, that is stated
> explicitly rather than assumed. **Contains no secrets, keys, or
> credential values anywhere.**

---

## 1. Project Overview

- **Name**: AIC Portal — Academia-Industry Collaboration Portal
- **Purpose**: connects Students, Faculty, Industry, and Institutions
  around a skill-first workflow (per the root `README.md`): Skill
  Assessment → Skill Profile → Skill Gap Analysis → Personalized Learning
  → Digital Portfolio → Internship/Job Matching → Apply → Application
  Tracking → Interview → Selection → Internship Experience → Placement →
  Analytics. **None of that workflow is built yet** — see §12/§14.
- **User roles**: `STUDENT`, `FACULTY`, `INDUSTRY`, `INSTITUTION`, `ADMIN`.
  **`ADMIN` is never publicly selectable** — see §7/§8/§10.
- **Architecture** (intended, per root `README.md`):
  ```
  Browser -> Next.js Frontend -> REST/JSON -> FastAPI Backend -> Supabase PostgreSQL
                                                               -> Supabase Storage
                                                    FastAPI -> LLM / AI API
  ```
  Next.js owns UI/pages/components/client interactions and talks to
  Supabase directly for **auth only**. FastAPI is meant to own business
  logic, AI integration, and analytics later. **In practice, everything
  built so far (all of Authentication + Onboarding) talks to Supabase
  directly from the Next.js frontend — the FastAPI backend has not been
  involved in any feature built to date.** It exists only as an empty
  scaffold (see §2).
- **Current development stage**: Authentication + Role Selection
  foundation is functionally complete and has been live-tested against
  the real Supabase project (with one open discrepancy — see §5). No
  business features (dashboards, profiles, skills, internships, etc.)
  exist beyond static "Coming Soon" placeholders.

---

## 2. Repository Structure

Top level:
```
AIC-Portal (repo root)
├── frontend/     Next.js app — everything built so far lives here
├── backend/      FastAPI scaffold — routers/schemas exist as empty
│                 placeholders, nothing wired up, not used by any
│                 built feature yet
├── database/     SQL migrations (see §7)
├── docs/         This file, plus scaffold-era placeholder docs
├── docker-compose.yml
└── README.md     Root README — describes the scaffold, now stale re:
                  "Status: Environment scaffold only" (auth is built)
```

### `frontend/app/` (Next.js App Router)

Auth/onboarding routes (all real, built this phase):
```
app/(auth)/login/page.tsx
app/(auth)/register/page.tsx
app/(auth)/forgot-password/page.tsx
app/(auth)/reset-password/page.tsx
app/(auth)/verify-email/page.tsx
app/(auth)/onboarding/page.tsx        <- despite the (auth) route group,
                                          this resolves to the public URL
                                          /onboarding (route groups don't
                                          affect the URL)
app/auth/callback/route.ts            <- OAuth + email-link callback
                                          (NOT inside the (auth) group —
                                          real path, must stay /auth/callback)
```
Everything else under `app/` (`admin/`, `faculty/`, `industry/`,
`institution/`, `student/`, `opportunities/`, `collaboration/`, `ai/`) is
**scaffold-era placeholder pages** — each just renders `"<Name> – Coming
Soon"`. They are not built features. Dashboard routes
(`/student/dashboard`, `/faculty/dashboard`, `/industry/dashboard`,
`/institution/dashboard`, `/admin/dashboard`) are the *redirect targets*
for authenticated users with a role — they exist and load, but only show
that placeholder text.

### `frontend/components/`

```
components/auth/            Built this phase — all auth UI
  auth-shell.tsx              shared branded page wrapper (logo, card);
                               takes an optional contentClassName to
                               widen the card (onboarding uses this)
  login-form.tsx              full login form + Google button
  register-form.tsx           full registration form + Google button
  forgot-password-form.tsx    single-step: email -> "check your email"
  reset-password-form.tsx     session-gated new/confirm password form
  verify-email-panel.tsx      "check your inbox" + resend button
  password-input.tsx          reusable show/hide password field
  password-strength.tsx       reusable strength meter + requirement list
  google-button.tsx           "Continue with Google" button (presentational)
  field-error.tsx             inline per-field error text
  form-error.tsx              form-level error banner
  form-success.tsx            form-level success banner

components/onboarding/       Built this phase
  role-selection.tsx           the 4-card role picker + Continue button

components/ui/               shadcn/ui primitives (button, card, dialog,
                              dropdown-menu, input, label, select, table,
                              tabs, tooltip, avatar, badge, progress) —
                              generic, reused throughout auth UI

components/{ai,assessment,common,dashboard,faculty,industry,institution,
             layout,student}/
                              scaffold-era placeholder components, not
                              wired to anything yet
```

### `frontend/lib/`

```
lib/auth.ts             All Supabase Auth *actions* + role/redirect logic.
                         This is the central place for auth business
                         logic — see §5 for exact exports.
lib/constants.ts         USER_ROLES / UserRole (all 5 roles, matches DB
                         CHECK constraint), PUBLIC_ROLES / PublicRole
                         (the 4 self-selectable roles, excludes ADMIN),
                         ROLE_LABELS (title/description shown on the
                         onboarding cards)
lib/validations.ts       Pure client-side validators: isValidEmail,
                         isValidUsername, isValidFullName,
                         getPasswordRequirements, isPasswordValid,
                         getPasswordStrength
lib/utils.ts             cn() — clsx + tailwind-merge helper (shadcn
                         convention)
lib/api.ts               Scaffold-era fetch wrapper for the FastAPI
                         backend — not used by anything built so far
                         (auth talks to Supabase directly, not FastAPI)
lib/supabase/
  client.ts               Browser Supabase client (createBrowserClient)
  server.ts               Server Supabase client for Server
                          Components/Route Handlers (createServerClient,
                          cookie-based)
  middleware.ts            updateSession() — refreshes the session from
                          request cookies and returns { response, user };
                          used by proxy.ts (see §9)
```
**There is exactly one client factory per context (browser/server).
Do not create a second one.**

### `frontend/hooks/`
`use-auth.ts` is real (session/user/loading + signIn/signInWithGoogle/
signOut, wraps `lib/auth.ts`). `use-applications.ts`, `use-assessments.ts`,
`use-internships.ts`, `use-jobs.ts`, `use-recommendations.ts`,
`use-skills.ts`, `use-user.ts` are all scaffold placeholders (return
`null`), unused by anything built.

### `frontend/types/`
`user.ts` has the real `Profile` interface (mirrors the `profiles`
table — see §7). All other files in `types/` (`analytics.ts`,
`application.ts`, etc.) are scaffold placeholders with a single `{ id:
string }` interface each — not used yet.

### `frontend/proxy.ts`
Next.js 16's replacement for `middleware.ts` (the old convention is
deprecated in this Next version — do not recreate `middleware.ts`). See
§9 for what it does.

### `backend/`
FastAPI scaffold: `app/main.py` exposes only `GET /` and `GET /health`.
`app/api/`, `app/schemas/`, `app/services/`, `app/ai/`, `app/database/`,
`app/core/`, `app/utils/` all contain empty placeholder modules from the
initial scaffold. **No backend code has been written or touched during
the Authentication phase.** Do not assume any backend endpoint exists
beyond the two above without checking.

### `database/`
See §7.

---

## 3. Technology Stack

Verified from `frontend/package.json` (do not assume newer/older
versions than this):

- **Next.js**: `16.3.3` (App Router, Turbopack, uses the `proxy.ts`
  convention — `middleware.ts` is deprecated in this version)
- **React**: `19.2.8` / **React DOM**: `19.2.8`
- **TypeScript**: `^5` (devDependency)
- **Supabase**: `@supabase/ssr ^0.12.5`, `@supabase/supabase-js
  ^2.112.4`
- **UI**: Tailwind CSS `^4`, `@base-ui/react ^1.7.0` (shadcn/ui's
  underlying primitive library in this shadcn version — **not**
  Radix), `class-variance-authority`, `clsx`, `tailwind-merge`,
  `tw-animate-css`, icons via `lucide-react ^1.35.0`, charts via
  `recharts ^3.10.1`
- **Package manager**: npm (there is a `package-lock.json`, no
  yarn/pnpm lockfile)
- **Backend**: Python + FastAPI (see `backend/requirements.txt`:
  `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`,
  `python-dotenv`, `supabase`, `httpx`, `pytest`) — scaffold only, not
  used by any built feature
- **Database**: Supabase PostgreSQL
- **Auth provider**: Supabase Auth (email/password + Google OAuth)
- **Deployment config**: `docker-compose.yml` exists at repo root
  (frontend + backend dev containers); root `README.md` mentions Vercel
  (frontend) / Render/Railway (backend) as the intended targets — no
  actual deployment has happened as far as this repo shows.

---

## 4. Environment Variables

**Names only — never write actual values into this file or any other
committed file.**

### Frontend (`frontend/.env.local`, gitignored)
```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_API_URL          (defaults to http://localhost:8000; points at
                              the FastAPI backend, currently unused by auth)
```
Note: Supabase's dashboard now labels the anon key "publishable key" in
newer UI — if you ever see `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` in a
`.env.local`, it must be renamed to `NEXT_PUBLIC_SUPABASE_ANON_KEY` to
match what `lib/supabase/client.ts` / `server.ts` actually read. This
exact mismatch happened once already during this project.

### Backend (`backend/.env`, gitignored)
```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
AI_API_KEY
FRONTEND_URL                 (defaults to http://localhost:3000)
```
**As of the last check, `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
in `backend/.env` were empty** — no admin/service-role credentials have
been available in this environment at any point during the Authentication
phase. The service-role key has never been used anywhere in this
project.

---

## 5. Authentication System — Architecture

Central logic lives in **`frontend/lib/auth.ts`**. Actual exported
functions (verified, not paraphrased):

- `resolveIdentifierToEmail(supabase, identifier)` — if the identifier
  contains `@` returns it as-is; otherwise calls the `get_email_for_identifier`
  Postgres RPC to resolve a username to its email (see §7). Also reused
  by the register form as a pre-submit "is this username taken" check.
- `signInWithIdentifier(supabase, identifier, password)` — resolves the
  identifier then calls `supabase.auth.signInWithPassword`. If resolution
  fails, returns the *same* generic error shape as a wrong password
  (anti-enumeration).
- `signInWithGoogle(supabase, redirectTo)` — calls
  `supabase.auth.signInWithOAuth({ provider: "google", options: {
  redirectTo, queryParams: { prompt: "select_account" } } })`. The
  `prompt: "select_account"` is what forces Google's account chooser to
  appear every time, even with an active Chrome Google session.
- `getPostLoginRedirectPath(role)` — pure function mapping role → path.
  `STUDENT→/student/dashboard`, `FACULTY→/faculty/dashboard`,
  `INDUSTRY→/industry/dashboard`, `INSTITUTION→/institution/dashboard`,
  `ADMIN→/admin/dashboard`, anything else (including `null`) →
  `/onboarding`. **This is the single source of truth for role→route
  mapping — reuse it, don't duplicate the switch elsewhere.**
- `getSafeRedirectPath(path)` — only accepts an internal path (must
  start with `/`, not `//`) — guards the `redirectTo` query param used by
  `proxy.ts` and the `next` param used by the callback route against
  open-redirect.
- `fetchProfileRole(supabase, userId)` — reads `profiles.role` for a
  user.
- `updateProfileRole(supabase, userId, role)` — the onboarding
  role-save call. Typed to accept only `PublicRole` (excludes `ADMIN` at
  the TypeScript level). `.update({ role }).eq("id", userId).select("role").single()`
  — only ever writes the `role` column; `.single()` surfaces a "no rows"
  error if the profile is somehow missing instead of silently no-op'ing.
- `signUpWithEmail(supabase, { email, password, fullName, username,
  emailRedirectTo })` — calls `supabase.auth.signUp` with `full_name`
  and `username` passed through `options.data` (→ `raw_user_meta_data`).
- `syncProfileUsernameFromMetadata(supabase, userId, metadata)` — the
  DB trigger (§7) copies `full_name` into the profile automatically but
  NOT `username`. This function copies `username` from auth metadata
  into the profile, but only once a real session exists (required for
  RLS) and only if the profile doesn't already have a username (never
  overwrites).
- `sendPasswordRecoveryEmail(supabase, email, redirectTo)` — calls
  `supabase.auth.resetPasswordForEmail(email, { redirectTo })`.
- `updatePassword(supabase, password)` — calls
  `supabase.auth.updateUser({ password })`.
- `resendSignupVerificationEmail(supabase, email)` — calls
  `supabase.auth.resend({ type: "signup", email })`.
- `getAuthErrorMessage(error)` — maps raw Supabase error messages to
  safe, generic user-facing strings via a lookup table
  (`FRIENDLY_AUTH_ERRORS`). **Raw Supabase/Postgres errors are never
  shown to users anywhere in this codebase** — every call site routes
  errors through this function (or, for the role-update path
  specifically, a fixed string — see role-selection.tsx).

### Flow: Login (`components/auth/login-form.tsx`)
```
/login
  → user enters "Username or Email" + Password
  → validate (isValidIdentifier, non-empty password)
  → signInWithIdentifier() [resolves username -> email if needed, then
    supabase.auth.signInWithPassword]
  → on success: fetchProfileRole()
  → role present  -> getSafeRedirectPath(?redirectTo) ?? getPostLoginRedirectPath(role)
  → role is null  -> /onboarding
```
Handles: empty fields, invalid format, wrong credentials (generic
message), unverified email (shows a "resend verification" link to
`/verify-email`), network errors — all via `getAuthErrorMessage`.

### Flow: Google OAuth
```
/login (or /register)
  → "Continue with Google" click
  → signInWithGoogle() -> supabase.auth.signInWithOAuth(provider: "google",
    queryParams: { prompt: "select_account" })
  → browser navigates to Supabase's /auth/v1/authorize, then to Google
  → Google's account chooser ALWAYS appears (verified live, multiple times)
  → user selects an account -> Google auth completes
  → redirected back to Supabase -> Supabase redirects to
    {origin}/auth/callback?code=...
  → app/auth/callback/route.ts exchanges the code for a session
  → no `next` param present (Google never sets one) -> role-based redirect
    via getPostLoginRedirectPath(role) -> /onboarding if role is null
```
**Verified live, repeatedly, across several sessions — this flow works.**

### Flow: Registration (`components/auth/register-form.tsx`)
```
/register
  → Full Name, Username, Email, Password, Confirm Password
  → client-side validation (see lib/validations.ts)
  → pre-check: resolveIdentifierToEmail(username) -> if non-null, username
    is taken, block submit before ever calling Supabase Auth
  → signUpWithEmail() -> supabase.auth.signUp({ email, password,
    options: { emailRedirectTo: `${origin}/auth/callback`,
    data: { full_name, username } } })
  → if error -> getAuthErrorMessage() (never raw)
  → if data.session is present -> syncProfileUsernameFromMetadata(),
    fetchProfileRole(), redirect to role's dashboard or /onboarding
  → if data.session is NULL -> redirect to /verify-email?email=... (reuses
    the same page as the resend-verification flow rather than a second
    "check your email" UI)
```

**⚠️ Current intended vs. last-observed behavior — read carefully:**
The project's *intended* configuration is **"Confirm email" = OFF** in
Supabase (Authentication → Providers → Email), so that `signUp()` always
returns a session immediately and the app always takes the
`data.session` branch straight to `/onboarding`, **never** hitting
`/verify-email` for a normal registration. The frontend code was written
specifically to support this (it branches on `data.session`, it doesn't
hardcode either path).

However: in the most recent session, the user reported having turned
"Confirm email" OFF, and a live registration test performed *after* that
change **still returned `data.session === null`** and landed on
`/verify-email`. This was not re-verified again afterward. **Do not
assume this is fixed. Before doing anything else with registration,
re-test it live** (a fresh signup with a new email) to see which branch
actually fires currently, and/or ask the user to re-confirm the dashboard
setting. Do not re-enable email confirmation as a "fix" — the intended
target state is OFF; if it's still requiring confirmation, the dashboard
setting itself needs attention, not the code.

### Flow: Forgot Password / Reset Password
```
/forgot-password
  → single email field
  → sendPasswordRecoveryEmail(supabase, email, `${origin}/auth/callback?next=/reset-password`)
  → generic "Check your email" success state regardless of whether the
    account exists (anti-enumeration)

  [user clicks the link in Supabase's actual reset-password email]

  → GET /auth/callback?code=...&next=/reset-password
  → route exchanges the code for a session
  → `next` is present and safe -> redirect straight to /reset-password
    (skips the normal role-based redirect entirely — a recovery session
    is not a normal sign-in)

/reset-password
  → on mount: checks for an existing session (supabase.auth.getSession())
    + listens for the PASSWORD_RECOVERY auth event
  → no session -> "Your password reset link is invalid or has expired."
    + "Request a new reset link" -> /forgot-password
  → session present -> New Password / Confirm Password form (reuses
    PasswordInput + PasswordStrength), submit disabled until valid+matching
  → updatePassword(supabase, newPassword) -> supabase.auth.updateUser({password})
  → success screen -> "Continue to Login" signs out (ends the recovery
    session) and redirects to /login
```
**This uses Supabase's default password-reset LINK email, not a 6-digit
OTP.** An earlier version of this project attempted a custom OTP-style
UI (6 separate digit boxes, "resend code" cooldown) built around
`supabase.auth.verifyOtp({ type: "recovery" })`, under the mistaken
assumption that Supabase's free email service delivers OTP codes. It was
discovered that Supabase's actual default delivers a clickable link, not
a code readable by a human to type in. **That OTP UI and its supporting
code (`otp-input.tsx`, `email-step.tsx`, `otp-step.tsx`,
`reset-password-step.tsx`, `success-step.tsx`, a
`forgot-password-flow.tsx` orchestrator, plus `verifyPasswordRecoveryOtp`
and `isValidOtp`) were deleted and replaced** with the link-based flow
described above. **Do not reintroduce OTP-based recovery.**

### Sessions / Callback / Protected Routes
See §9 for `proxy.ts` and route protection. Session refresh happens via
`lib/supabase/middleware.ts`'s `updateSession()`, called from `proxy.ts`
on every matched request.

---

## 6. Google OAuth Configuration

**No Client ID/Secret values are recorded here or anywhere in this
repo.**

- Google provider is enabled in the Supabase project (verified live —
  OAuth completes end-to-end).
- The OAuth flow uses Supabase's own `/auth/v1/authorize` and
  `/auth/v1/callback` endpoints (standard Supabase-managed OAuth — no
  manual Google OAuth implementation in this codebase).
- Implementation: `signInWithGoogle()` in `frontend/lib/auth.ts`,
  called from `handleGoogleSignIn()` in both `login-form.tsx` and
  `register-form.tsx`.
- `redirectTo` is always `${window.location.origin}/auth/callback` (no
  `next` param — that's reserved for the recovery flow).
- `queryParams: { prompt: "select_account" }` is what forces Google's
  account chooser every time. **This was added specifically because the
  default behavior silently reused whatever Google account was already
  active in the browser — verified via a dedicated regression task, and
  re-verified live multiple times since. Do not remove `prompt:
  "select_account"`.**
- Local development redirect: `http://localhost:3000/auth/callback` must
  be present in Supabase's Authentication → URL Configuration → Redirect
  URLs (this was configured at some point during development — not
  independently re-verified in this session, but OAuth has worked live
  repeatedly, which implies it's correctly set).
- No production redirect URL configuration exists yet — this project has
  not been deployed.

---

## 7. Database

Two migrations exist in `database/migrations/`. **Both have been
inspected directly (full contents below, summarized) — nothing here is
guessed.**

### `001_profiles.sql`
Creates the `profiles` table:
```sql
create table profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  username text,                          -- nullable; format-checked
  role text check (role in ('STUDENT','FACULTY','INDUSTRY','INSTITUTION','ADMIN')),
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint username_format check (username ~ '^[a-zA-Z0-9_.-]{3,30}$')
);
```
- `profiles_username_lower_idx`: unique index on `lower(username)` —
  case-insensitive uniqueness is the *only* uniqueness constraint on
  username (no separate plain `UNIQUE`).
- RLS **enabled**. Two policies:
  - `"Users can view their own profile"` — `SELECT`, `USING (auth.uid() = id)`
  - `"Users can update their own profile"` — `UPDATE`, `USING (auth.uid()
    = id) WITH CHECK (auth.uid() = id)`
- `handle_new_user()` trigger function (`SECURITY DEFINER`, empty
  `search_path`) fires `AFTER INSERT ON auth.users` and inserts a
  matching `profiles` row, copying `email`, and `full_name`/`avatar_url`
  from `raw_user_meta_data` if present. **`role` is never set here — it
  starts NULL for every new user, Google or email/password alike.**
  `username` is also NOT copied by this trigger (see §5 —
  `syncProfileUsernameFromMetadata` handles that client-side after a
  session exists).
- `get_email_for_identifier(identifier text)` function (`SECURITY
  DEFINER`) — if the identifier contains `@`, returns it unchanged;
  otherwise looks up the email for a username case-insensitively.
  `GRANT EXECUTE` to both `anon` and `authenticated`. This is how the
  login form supports username-based login without ever exposing the
  `profiles` table's `email` column to arbitrary reads.

### `002_protect_admin_role.sql`
**Created specifically to close a privilege-escalation gap**: the
`001` UPDATE policy only checks row ownership (`auth.uid() = id`), not
which *value* `role` is being set to — so any authenticated user could
originally `PATCH` their own profile straight to `role: 'ADMIN'` via the
Supabase REST API, completely bypassing the onboarding UI (the UI only
ever hid `ADMIN` as an option — that was never a real security boundary
on its own).

Adds a `BEFORE UPDATE` trigger, `prevent_self_admin_promotion_trigger`,
calling `prevent_self_admin_promotion()`:
```sql
if current_setting('role', true) = 'service_role' then
  return new;                      -- trusted path steps aside entirely
end if;

if new.role = 'ADMIN' and old.role is distinct from 'ADMIN' then
  raise exception 'Cannot self-assign the ADMIN role.' using errcode = '42501';
end if;
```
- Deliberately **not** a `WITH CHECK (role <> 'ADMIN')` addition to the
  existing policy — that would also permanently block an *already-ADMIN*
  row from ever being updated again (a `WITH CHECK` re-validates the
  entire resulting row on every update, not just the changed column).
  Comparing `OLD.role` vs `NEW.role` avoids that: an `ADMIN -> ADMIN`
  no-op transition (e.g. an admin editing an unrelated field) is
  allowed; only a transition *into* `ADMIN` from anything else
  (including `NULL`) is rejected.
- The `service_role` Postgres role (RLS-bypassing, never used from the
  frontend — see §4/§8) is the only path left able to assign `ADMIN`.
  **No concrete trusted admin-provisioning mechanism has been built
  yet** — this is intentionally left for a later phase.

**Allowed public self-service roles: `STUDENT`, `FACULTY`, `INDUSTRY`,
`INSTITUTION`. `ADMIN` must be assigned through a trusted mechanism —
not built yet.**

No other migrations exist. Do not assume any other tables (no
`assessments`, `internships`, `jobs`, `applications`, etc. tables exist
in the database — those are all still just frontend placeholder pages
with zero backing schema).

---

## 8. RLS / Security Model

- **Row-Level Security is enabled on `profiles`**, with exactly the
  policies described in §7 (view own row, update own row).
- **Role assignment is restricted at the database level**, not just the
  UI — verified live via direct REST calls bypassing the frontend
  entirely (see §11 for the exact test matrix and results).
- **The service-role key has never been used in any frontend code** —
  confirmed by repeated `grep` checks across every task in this phase.
  It also does not currently have a value in `backend/.env` in this
  environment (see §4).
- Passwords are handled exclusively by Supabase Auth
  (`signInWithPassword`, `signUp`, `updateUser`) — **no custom password
  hashing, no password ever stored in the `profiles` table.**
- Raw Supabase/Postgres errors are never shown to users — every call
  site routes through `getAuthErrorMessage()` (auth errors) or a fixed
  friendly string (the role-update path in `role-selection.tsx`).
- No auth tokens, passwords, or OTPs have been logged anywhere in the
  codebase — this was explicitly checked (browser console + localStorage)
  after every live-testing session in this phase.
- Secrets live only in `.env.local` (frontend) / `.env` (backend), both
  gitignored — confirmed via `git check-ignore` and `git ls-files`
  (neither file is tracked) repeatedly across sessions.

### Known, honestly-documented limitations
- **No trusted admin-provisioning mechanism exists yet.** `ADMIN` can
  currently only be assigned via a `service_role`-authenticated request
  (bypassing RLS), and nothing in this app makes such a request. In
  practice this means there is currently no way to create an admin user
  through the app at all — that has to happen via direct database
  access (e.g. the Supabase SQL editor) until a real admin-provisioning
  feature is built.
- **The `ADMIN → ADMIN` no-op case (an existing admin editing their own
  profile) has never been empirically tested** — there is no way to
  create a real `ADMIN` test account without `service_role` access,
  which has been unavailable throughout this phase. The trigger logic
  was verified correct by careful reading, not by a live test of that
  specific case.
- **Username-resolution RPC (`get_email_for_identifier`) has no rate
  limiting of its own.** It's `SECURITY DEFINER` and granted to `anon`,
  so a determined actor could probe it directly to enumerate usernames
  faster than through the UI (the UI itself always shows a generic
  "Invalid username or password" regardless of which step failed).
  Documented as an accepted MVP-level risk, not fixed.
- Registration's "obfuscated existing user" anti-enumeration behavior
  (Supabase's own mechanism — returns a fake-looking user object with an
  empty `identities` array instead of an error, when email confirmation
  is on and the email is already registered) was reasoned about but not
  independently re-verified with confirmation OFF — its exact behavior
  in that mode hasn't been tested.

---

## 9. Routing

Confirmed-existing routes (by file inspection, §2):
```
/login
/register
/forgot-password
/reset-password
/verify-email
/onboarding
/auth/callback        (route handler, not a page)
```
All present.

### `frontend/proxy.ts`
Next.js 16's `middleware.ts` replacement (that convention is deprecated
in this Next version — the file is literally named `proxy.ts` and
exports a `proxy()` function, not `middleware()`). It:
1. Calls `updateSession(request)` (from `lib/supabase/middleware.ts`) to
   refresh the session and get the current `user`.
2. If the request path matches one of `PROTECTED_PREFIXES` — currently
   `["/student", "/faculty", "/industry", "/institution", "/admin",
   "/onboarding"]` — **and there is no authenticated user**, redirects to
   `/login?redirectTo=<original path>`.
3. Otherwise passes the request through.

**Only checks "is there a session at all" — there is no role-based
authorization at the middleware level** (e.g. nothing stops an
authenticated `STUDENT` from directly navigating to `/admin/dashboard` —
that page would just load, showing its placeholder content, since role
gating is not implemented at this layer). This is a known, intentional
scope limit, not an oversight — documented as such in every task in this
phase (§16 "important development rules" explicitly says not to build
full authorization in a task that isn't about that).

`config.matcher` excludes `_next/static`, `_next/image`, `favicon.ico`,
and common image extensions.

---

## 10. Role Selection / Onboarding Flow

`app/(auth)/onboarding/page.tsx` is a **Server Component** (not a client
form directly) — it does the auth/role check server-side before
rendering anything:
```ts
const { data: { user } } = await supabase.auth.getUser();
if (!user) redirect("/login");

const role = await fetchProfileRole(supabase, user.id);
if (role) redirect(getPostLoginRedirectPath(role));

return <AuthShell ...><RoleSelection userId={user.id} /></AuthShell>;
```
So: no session → `/login`. Session + role already set → straight to that
role's dashboard (onboarding is never shown again once a role exists).
Session + role `NULL` → renders the role picker.

`components/onboarding/role-selection.tsx` (client component):
- Renders `PUBLIC_ROLES` (Student, Faculty / Academician, Industry,
  Institution — **never Admin**) as a `role="radiogroup"` of 4 cards,
  full keyboard support (arrow keys move focus + selection, roving
  `tabIndex`, `aria-checked`).
- Continue button disabled until a role is picked.
- On Continue: `updateProfileRole(supabase, userId, selectedRole)` →
  on success, `router.push(getPostLoginRedirectPath(selectedRole))`.
- Any error → fixed friendly message ("Something went wrong while
  setting up your account. Please try again.") — never the raw DB
  error, including the ADMIN-rejection trigger error (which can never
  actually fire from this UI, since `PublicRole` excludes `ADMIN` at the
  type level — the trigger exists for defense against direct API calls,
  not because the UI can trigger it).
- "Not you? Sign out" link at the bottom.

Post-selection dashboards (`/student/dashboard`, `/faculty/dashboard`,
`/industry/dashboard`, `/institution/dashboard`) are **placeholder pages
only** — "`<Role> Dashboard – Coming Soon`". No dashboard functionality
exists.

---

## 11. What Has Been Tested

Only what was actually, live-verified against the real Supabase project
is marked "tested". Anything else is marked accordingly.

| Feature | Status | How tested | Known limitation |
|---|---|---|---|
| Email/password login | **Tested, works** | Live, repeatedly, across many sessions with a real account | — |
| Username-based login | **Tested, works** | Live — `get_email_for_identifier` resolution confirmed via a real login | — |
| Password show/hide toggle | **Tested, works** | Live, visually confirmed (plaintext reveal + icon swap) | — |
| Google OAuth (full flow) | **Tested, works** | Live, multiple times, including after later changes (regression-checked each time) | Only one Google test account available; a truly *fresh* Google user's onboarding path was tested once (landed on `/onboarding`, no role) |
| Google account chooser (`prompt=select_account`) | **Tested, works** | Live — confirmed the chooser screen renders every time, even with an active Chrome session | — |
| Registration (account creation) | **Tested, works** | Live — real Supabase `auth.users` row created each time (multiple fresh test emails via Gmail `+alias`) | See below re: email confirmation |
| Email confirmation behavior | **Unresolved discrepancy** | Live-tested after user reported disabling "Confirm email" — registration still returned no session and went to `/verify-email` | **Needs re-verification** — see §5 warning box |
| Forgot password (send link) | **Tested, works** | Live — real Supabase email-send call succeeded, correct generic "Check your email" UI | Could not click the actual emailed link (no inbox access in this environment) |
| Reset password (update) | **Tested, works** | Live — used an existing authenticated session's own account, real `updateUser()` call, verified via direct DB read that only `role`/password changed, nothing else | The *link-click → session establishment* leg specifically was validated using a pre-existing session found in the browser, not a freshly-clicked email link |
| Session persistence | **Tested, works** | Live — session cookie survives navigation; re-login after sign-out works | — |
| Logout | **Tested, works** | Live — cookie clearing verified, subsequent page loads show signed-out state | — |
| Protected routes (`/student/*` etc. + `/onboarding`) | **Tested, works** | `curl`, repeatedly across sessions — unauthenticated requests get `307` to `/login?redirectTo=...` | No role-based authorization (see §12) |
| Role selection UI (all 4 roles) | **Tested, works** | Live — each of the 4 roles selected via the real UI at least once, each correctly redirected to its dashboard | — |
| Role persistence (DB write) | **Tested, works** | Live — direct authenticated REST reads after each UI-driven update confirmed the exact `role` value written, and that no other column changed | — |
| Admin self-assignment protection | **Tested, works — REJECTED as intended** | Live — direct REST `PATCH` attempts (bypassing the UI) for `NULL→ADMIN`, `STUDENT→ADMIN`, `FACULTY→ADMIN`, `INDUSTRY→ADMIN`, `INSTITUTION→ADMIN` all returned `403`/`42501` | `ADMIN→ADMIN` no-op case untested (see §8 limitations) |
| Invalid role value (`'HACKER'`) | **Tested, works — REJECTED** | Live — `400`/`23514` (pre-existing CHECK constraint), confirmed unaffected by the new trigger | — |
| TypeScript (`tsc --noEmit`) | **Tested, clean** | Run after every task in this phase | — |
| ESLint | **Tested, clean** | Run after every task in this phase | — |
| Production build (`next build`) | **Tested, clean** | Run after every task in this phase — all routes (including `/onboarding`, `/reset-password`, `/auth/callback`) generate successfully | — |

---

## 12. Known Issues / Limitations

- Dashboard routes for all 5 roles are placeholder text only — no real
  dashboard functionality.
- Role-specific profile setup (Student/Faculty/Industry/Institution
  profile fields beyond the shared `profiles` table) is **not
  implemented** — this is the next phase (§15).
- Account settings, notification settings, and privacy/security settings
  are **not implemented** — no pages, no schema.
- Admin management / admin dashboard is **not implemented** — and, per
  §8, there is currently no way to provision an admin account through
  the app at all.
- The FastAPI backend (`backend/`) is an unused scaffold — no
  business-logic endpoint exists.
- No role-based authorization at the middleware or page level beyond
  "is there a session" (§9).
- The email-confirmation-off behavior for registration is unresolved as
  of the last check (§5, §14) — needs a fresh live test before being
  relied upon.
- `ADMIN → ADMIN` no-op profile updates are untested (no way to create a
  real admin account without `service_role` access).

---

## 13. Authentication & User Management Roadmap Status

Based on the original 10-item roadmap for this section of the project:

| # | Item | Status |
|---|---|---|
| 1 | Landing Page | **DONE** (scaffold home page at `/`, not elaborate but functional) |
| 2 | Login | **DONE** — email/username + password, Google OAuth, validation, loading/error states, all live-tested |
| 3 | Register | **DONE** (code-complete, live-tested for account creation) — see the email-confirmation discrepancy in §5/§14, which is a *configuration* question, not a missing feature |
| 4 | Forgot Password | **DONE** — link-based flow, live-tested |
| 5 | Email/Phone Verification | **INTENTIONALLY NOT REQUIRED** — "Confirm email" is meant to be OFF, so verification is a deliberately-skipped step for this project, not an unfinished one. (Its actual current live behavior is unresolved — see §5.) Phone verification was never in scope. |
| 6 | Role Selection | **DONE** — 4 public roles, Admin excluded, DB-level enforcement, live-tested |
| 7 | Profile Setup | **NOT STARTED** — next phase (§15) |
| 8 | Account Settings | **NOT STARTED** |
| 9 | Notification Settings | **NOT STARTED** |
| 10 | Privacy & Security | **NOT STARTED** (beyond the auth-level security work already done — no user-facing privacy/security *settings* page exists) |

---

## 14. Current Development Position

**Where we are now:**
```
Authentication foundation
  → Login (email/username + Google)           DONE
  → Registration                              DONE (email-confirm config unresolved)
  → Password recovery (link-based)             DONE
  → Google OAuth + account chooser             DONE
  → Role selection (Student/Faculty/Industry/Institution)   DONE
  → Admin self-assignment protection (DB-level)              DONE
  → Profile Setup                              NOT STARTED  <-- next
```
Everything above the line has been built, and — with the one noted
exception — live-tested against the real Supabase project across
multiple sessions, with regressions re-checked after each subsequent
change. The security model (RLS + the admin-protection trigger) has been
adversarially tested via direct REST calls bypassing the UI, not just
exercised through the app.

---

## 15. Next Development Phase: Profile Setup

**Not implemented. Do not implement it as part of reading this
document — this section is direction, not a task.**

The intended next phase, per the roadmap (§13), is **Profile Setup**:
building the role-specific profile experience for Student, Faculty,
Industry, and Institution users, presumably reached right after
onboarding role selection (or accessible later from account settings).

Before writing any code for this:
- **Inspect the current `profiles` table** (§7) — it currently has
  `id, email, username, role, full_name, avatar_url, created_at,
  updated_at`. Nothing role-specific exists yet (no bio, department,
  company, skills, etc. — those would be new fields or, more likely,
  new per-role tables).
- **Do not invent exact fields** — none are specified anywhere in this
  repository. Whatever fields each role's profile needs should be
  designed fresh, informed by what actually exists, not assumed from
  this document or from generic SaaS conventions.
- **Prefer a shared architecture over duplicating auth/profile logic.**
  The existing `profiles` table, RLS pattern (`auth.uid() = id`), and
  `lib/auth.ts`/`lib/supabase/*` client architecture should be extended,
  not replicated. If per-role tables are needed (e.g. `student_profiles`,
  `faculty_profiles`), follow the same RLS ownership pattern already
  established in `001_profiles.sql`.
- Consider whether profile setup is a hard gate (like onboarding role
  selection is) or optional/skippable — nothing in the current codebase
  answers this; it's a product decision to make, not something to infer.

---

## 16. Important Development Rules

For any future Claude Code session working on this repo:

- **Inspect existing code before modifying it.** This entire
  Authentication phase was built by repeatedly reading the actual
  current files first — don't break that pattern.
- **Reuse the existing authentication architecture** — `lib/auth.ts`,
  `lib/supabase/{client,server,middleware}.ts`, `components/auth/*`.
- **Do not create a second Supabase client implementation.** There is
  exactly one browser client factory and one server client factory.
- **Do not create a duplicate `profiles` table or a second profile
  system.** Extend what exists.
- **Do not create duplicate auth flows** (e.g. a second login form, a
  second OAuth implementation).
- **Do not modify working Google OAuth unnecessarily** — and never
  remove `prompt: "select_account"`.
- **Do not reintroduce OTP-based password recovery.** This project
  uses Supabase's default reset-**link** email. An OTP UI was built,
  found to be based on a wrong assumption, and deliberately removed —
  don't redo that work.
- **Registration is not meant to require email confirmation** — see the
  unresolved discrepancy in §5/§14 before touching this again.
- **`ADMIN` cannot be publicly self-assigned** — enforced by the
  `002_protect_admin_role.sql` trigger. Don't weaken it; don't add a
  workaround in application code instead of respecting the DB-level
  boundary.
- **Never put the service-role key in frontend code.**
- **Never log passwords, tokens, or secrets** — check console/localStorage
  after any auth-related change, as was done throughout this phase.
- **Never commit `.env` / `.env.local` files.**
- **Run TypeScript, ESLint, and a production build after any
  non-trivial change** — this was done after every task in this phase
  and caught real issues (e.g. a stale `.next` cache producing a
  spurious error once, a `react-hooks/set-state-in-effect` lint error
  from an early `useEffect` pattern).
- **Do not commit or push unless explicitly instructed** — no task in
  this entire phase has been committed; everything is still working-tree
  changes (§17).
- **Do not claim a test passed without actually running it** — this
  document itself follows that rule (see the email-confirmation
  discrepancy, explicitly flagged rather than glossed over).
- **Respect Supabase's rate limits.** Password-reset/signup emails were
  deliberately *not* re-sent repeatedly during testing in this phase —
  when in doubt, do one clean live test rather than several.

---

## 17. Git Status

(As of the end of this documentation task.)

- **Branch**: `main`
- **Remote**: `origin` → `https://github.com/Blaze-sketch-ally/hackheritage4.git`
  (public HTTPS URL, no embedded credentials — safe to record)
- **Latest commits**:
  ```
  468f603 chore: also ignore bare venv/ directory
  fec2502 chore: initialize AIC Portal scaffold
  ```
- **Uncommitted changes**: yes — **the entire Authentication + Onboarding
  phase described in this document exists only as uncommitted working-tree
  changes.** Nothing from this phase has been committed. Modified files
  include `database/migrations/001_profiles.sql`, most of
  `frontend/app/(auth)/*`, `frontend/lib/auth.ts`, `frontend/lib/constants.ts`,
  `frontend/lib/validations.ts`, `frontend/lib/supabase/middleware.ts`,
  `frontend/hooks/use-auth.ts`, `frontend/types/user.ts`, plus deletion of
  the old `frontend/middleware.ts`. New untracked files include
  `database/migrations/002_protect_admin_role.sql`,
  `frontend/proxy.ts`, `frontend/app/(auth)/reset-password/`,
  `frontend/app/auth/`, `frontend/components/auth/`,
  `frontend/components/onboarding/`, `frontend/components/ui/label.tsx`,
  and this file itself.
- **This is expected** — every task so far has explicitly said not to
  commit or push. A future session should not commit this work without
  being asked to.

---

## 18. File Change History (Authentication Phase)

Built/modified across this phase, grouped by purpose (not a literal
commit log, since nothing is committed — derived from `git status` +
actual file contents):

**Auth core**
- `frontend/lib/auth.ts` — grew from an empty placeholder to the full
  set of functions described in §5.
- `frontend/lib/constants.ts` — added `PUBLIC_ROLES`, `PublicRole`,
  `ROLE_LABELS` alongside the pre-existing `USER_ROLES`/`UserRole`.
- `frontend/lib/validations.ts` — added `isValidFullName`; an earlier
  `isValidOtp` was added then removed along with the OTP UI.
- `frontend/hooks/use-auth.ts` — grew from a placeholder to a real
  session hook.
- `frontend/types/user.ts` — added the real `Profile` interface.

**Supabase plumbing**
- `frontend/lib/supabase/middleware.ts` — `updateSession()` extended to
  return `{ response, user }` (originally just `response`), so
  `proxy.ts` could gate protected routes.
- `frontend/middleware.ts` **deleted**, replaced by `frontend/proxy.ts`
  — Next.js 16 renamed the convention; this is not a regression.

**Pages**
- `frontend/app/(auth)/login/page.tsx`,
  `frontend/app/(auth)/register/page.tsx`,
  `frontend/app/(auth)/forgot-password/page.tsx`,
  `frontend/app/(auth)/verify-email/page.tsx` — replaced "Coming Soon"
  placeholders with real pages wrapping the components below.
- `frontend/app/(auth)/reset-password/page.tsx` — new (route didn't
  exist before this phase).
- `frontend/app/(auth)/onboarding/page.tsx` — replaced the placeholder
  with the real Server Component described in §10.
- `frontend/app/auth/callback/route.ts` — new; grew over the phase to
  handle three cases (OAuth, registration confirmation, password
  recovery) via the `next` query param, plus username backfill.

**Components**
- `frontend/components/auth/` — entire directory is new this phase:
  `auth-shell.tsx`, `login-form.tsx`, `register-form.tsx`,
  `forgot-password-form.tsx`, `reset-password-form.tsx`,
  `verify-email-panel.tsx`, `password-input.tsx`, `password-strength.tsx`,
  `google-button.tsx`, `field-error.tsx`, `form-error.tsx`,
  `form-success.tsx`.
- `frontend/components/onboarding/role-selection.tsx` — new.
- `frontend/components/ui/label.tsx` — added via the shadcn CLI
  (needed for accessible form labels; wasn't in the original UI
  component scaffold).
- **Deleted** during the OTP-removal cleanup: `otp-input.tsx`,
  `forgot-password-flow.tsx`, and a `steps/` subfolder containing
  `email-step.tsx`, `otp-step.tsx`, `reset-password-step.tsx`,
  `success-step.tsx`.

**Database**
- `database/migrations/001_profiles.sql` — modified from its
  scaffold-era minimal version to the full schema in §7 (this happened
  *before* the phase this document primarily covers, but the file is
  still shown as modified relative to the last commit).
- `database/migrations/002_protect_admin_role.sql` — new, described in
  §7.

---

## 19. Supabase Dashboard Configuration Required

Manual settings that must exist in the Supabase project for this app to
work (no values recorded — just what must be configured):

- **Email provider enabled** (Authentication → Providers → Email).
- **"Confirm email" → OFF** is the *intended* setting (§5) — **status as
  of the last live check was still requiring confirmation despite being
  reportedly turned off. Re-verify before relying on this.**
- **Google provider enabled** (Authentication → Providers → Google),
  with a Google Cloud OAuth Client ID/Secret configured — values not
  recorded here.
- **Redirect URLs** (Authentication → URL Configuration) must include:
  - **Local development**: `http://localhost:3000/auth/callback`
  - **Production**: not yet configured — this project has not been
    deployed.
- The `profiles` table, its RLS policies, the `handle_new_user` trigger,
  the `get_email_for_identifier` function, and the
  `prevent_self_admin_promotion` trigger must all be applied (both
  migrations in `database/migrations/` run) — confirmed applied and
  live-tested as of this document.

---

## 20. How to Resume

1. Read this file (`docs/PROJECT_CONTEXT.md`) in full.
2. Run `git status` — expect the uncommitted working-tree state described
   in §17 unless someone has since committed or changed it.
3. Run `git log -5 --oneline` — sanity-check nothing has been committed
   since this document was written.
4. Before touching any specific file, read its current actual content —
   do not rely solely on this document's descriptions once real time has
   passed and further changes may have happened.
5. If frontend work is needed: `cd frontend && npm run dev` (verify
   `frontend/.env.local` has values for `NEXT_PUBLIC_SUPABASE_URL` and
   `NEXT_PUBLIC_SUPABASE_ANON_KEY` — check presence only, never print
   them).
6. If the task concerns registration/email-confirmation, **first
   re-test live** whether `signUp()` currently returns a session
   immediately or not (§5/§14) — don't assume either way.
7. Continue with **Profile Setup** (§15) as the next phase, unless
   explicitly directed elsewhere.
8. Run TypeScript, ESLint, and a production build after any non-trivial
   change.
9. Do not commit or push unless explicitly asked.

---

## 21. "Do Not Assume" — Read Before Coding

Do not assume, without checking the actual repository first:
- The exact current database schema — always re-read the migration
  files in `database/migrations/`.
- Current Supabase dashboard settings (email confirmation, OAuth
  config, redirect URLs) — these can change outside of this repo and
  this document may be stale by the time you read it.
- That every route listed in §2/§9 still behaves exactly as described —
  re-read the actual page/component files.
- Any API endpoint beyond `GET /` and `GET /health` exists on the
  FastAPI backend — it doesn't, as of this document, but check
  `backend/app/api/` yourself rather than trusting this line forever.
- Actual environment variable *values* — never assume, never print,
  never guess. Only variable *names* are documented here.
- That role values are exactly `STUDENT`/`FACULTY`/`INDUSTRY`/
  `INSTITUTION`/`ADMIN` forever — re-check the CHECK constraint in
  `001_profiles.sql` and `frontend/lib/constants.ts` if a task touches
  roles.
- That any dashboard page has real functionality — check first; as of
  this document, all five are "Coming Soon" placeholders.

**When in doubt: inspect the actual repository. This document is a
starting point for orientation, not a substitute for reading the code.**
