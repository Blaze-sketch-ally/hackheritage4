# AIC Portal

Academia-Industry Collaboration Portal — connecting Student, Faculty,
Institution, and Industry around a skill-first workflow:

Skill Assessment -> Skill Profile -> Skill Gap Analysis -> Personalized
Learning -> Digital Portfolio -> Internship/Job Matching -> Apply ->
Application Tracking -> Interview -> Selection -> Internship Experience ->
Placement -> Analytics

## Status

The Student and Industry portals are fully built end-to-end (skill
assessment, applications, internships, jobs, analytics). The Institution
portal has a real dashboard, student directory, placements, industry
partners, and analytics. Faculty has authentication/role-gating and a
collaborations flow; most other Faculty screens and the entire Admin portal
are still placeholder stubs pending a provisioning path. See
`frontend/` and `backend/` for the actual route/router lists — treat
`docs/PROJECT_CONTEXT.md` as historical, not current.

## Stack

- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui,
  Recharts — deployed on Vercel
- **Backend**: Python, FastAPI, Pydantic — deployed on Render/Railway
- **Database/Auth/Storage**: Supabase (PostgreSQL)
- **AI**: LLM API accessed through FastAPI, isolated in `backend/app/ai/`

## Architecture

```
Browser -> Next.js Frontend -> REST/JSON -> FastAPI Backend -> Supabase PostgreSQL
                                                             -> Supabase Storage
                                                  FastAPI -> LLM / AI API
```

Next.js owns UI/pages/components/client interactions. FastAPI owns business
logic, API endpoints, and AI integration. See `docs/architecture/` for
details.

## Structure

```
AIC-Portal/
  frontend/     Next.js app
  backend/      FastAPI app
  database/     SQL migrations + seed data
  docs/         architecture, database, API, and presentation docs
```

## Local development

**Frontend** (macOS/Linux/Windows — same commands)

```bash
cd frontend
npm install
cp .env.example .env.local     # macOS/Linux — on Windows: copy .env.example .env.local
# then fill in the Supabase values
npm run dev                     # http://localhost:3000
```

**Backend**

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in Supabase/AI values
uvicorn app.main:app --reload   # http://localhost:8000
```

Windows:

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

See `backend/README.md` for the full backend setup, structure, and endpoint
reference (including the `/docs` Swagger UI).

**Or with Docker Compose**

```bash
docker compose up
```

## Environment variables

See `frontend/.env.example` and `backend/.env.example` — copy each to
`.env.local`/`.env` and fill in real values locally; the `.example` files
themselves stay committed with variable *names* only. Never commit `.env`
or `.env.local` files, and never expose `SUPABASE_SERVICE_ROLE_KEY` to the
frontend.

**Frontend** (`NEXT_PUBLIC_*` only — these are readable in the browser bundle,
so never put a secret here):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon (public) key |
| `NEXT_PUBLIC_API_URL` | Base URL of the deployed FastAPI backend |

**Backend** (server-only secrets — never expose these to the frontend):

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Anon key, used for RLS-scoped per-user requests |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key, bypasses RLS — used in 3 narrow spots only. **Never** expose this to the frontend. |
| `AI_API_KEY` | LLM provider key |
| `FRONTEND_URL` | The deployed frontend origin, used for CORS |
| `ADDITIONAL_CORS_ORIGINS` | Optional, comma-separated extra origins to allow (e.g. a preview deployment) |

## Deployment

This is not deployed automatically by any process in this repo — the steps
below are what a human operator runs manually. Nothing here has been
executed against a live production environment.

**1. Supabase (database/auth)**
- Create a Supabase project (or use the existing one for this environment).
- Apply every file in `database/migrations/` **in filename order** — there
  is no migration runner in this repo; use the Supabase SQL editor or
  `supabase db push` with the Supabase CLI pointed at the project.
- Copy the project's URL, `anon` key, and `service_role` key from
  Settings → API.
- Under Authentication → URL Configuration, add the deployed frontend's
  origin (and `https://<domain>/auth/callback`) to the redirect allow-list.

**2. Frontend → Vercel**
- Import the repo into Vercel; set the project's **Root Directory** to
  `frontend` (this is a monorepo, so this step is required — there is no
  `vercel.json` in this repo for it).
- Framework preset: Next.js (auto-detected).
- Set the three `NEXT_PUBLIC_*` environment variables above in the Vercel
  project settings (Production and Preview as needed).
- `NEXT_PUBLIC_API_URL` must point at the deployed backend's public URL
  (step 3), not `localhost`.
- Deploy. Vercel runs `npm run build` (or `npm run vercel-build` if added)
  from `frontend/` automatically.

**3. Backend → Render/Railway/Fly.io**
- Point the service at this repo with `backend/` as the root/working
  directory.
- Install: `pip install -r requirements.txt`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  (also available as `backend/Procfile` for platforms that read it).
- Set the backend environment variables above (`SUPABASE_URL`,
  `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `AI_API_KEY`,
  `FRONTEND_URL`) with `FRONTEND_URL` set to the deployed Vercel domain
  (not `localhost`).
- Confirm the platform's health check is `GET /health`.

**4. Google OAuth (if enabling "Sign in with Google")**
- In the Google Cloud Console OAuth client, add
  `https://<your-supabase-project>.supabase.co/auth/v1/callback` as an
  authorized redirect URI.
- In Supabase → Authentication → Providers → Google, enable the provider
  and paste the Google client ID/secret.
- No frontend/backend code change is needed beyond the environment
  variables above — `frontend/lib/auth.ts`'s `signInWithGoogle` already
  builds the redirect from the current origin.

**5. Post-deployment verification**
- `GET https://<backend-domain>/health` returns `{"status": "ok"}`.
- Sign up/sign in on the deployed frontend and confirm a session is set
  (check that role-gated routes like `/student/dashboard` load, not just
  the login page).
- Open the browser network tab and confirm API calls go to the deployed
  backend URL, not `localhost:8000`.
- Confirm a request from an *other* origin is rejected by CORS (no
  `Access-Control-Allow-Origin` header for a disallowed origin).
- Spot-check one write per role (e.g. student applies to an internship,
  industry publishes a posting) to confirm RLS + backend auth are both
  working against the production Supabase project, not a local one.

## CI

`.github/workflows/ci.yml` runs on every push to `main`/`feature/**` and on
every pull request into `main`:

- **Frontend**: `npm ci` → `npm run lint` → `npm run build`
- **Backend**: install `requirements-dev.txt` → `ruff check .` → import
  check → `pytest`

## Development workflow

Before pushing:

- Never commit `.env` or `.env.local` — copy from the matching `.env.example`.
- Pull `main` before starting new work.
- Run local checks before pushing:
  - Frontend: `npm run lint && npm run build`
  - Backend: `ruff check . && pytest`

### Git workflow

Three of us work on this simultaneously, so branch per task rather than
committing straight to `main`. PR approval isn't required — merge your own
branch once it's ready — but keeping work on a branch avoids stepping on
each other's uncommitted changes.

Before starting work:

```bash
git checkout main
git pull origin main
git checkout -b feature/my-task
```

During work:

```bash
git status
git add .
git commit -m "feat: description"
```

Push:

```bash
git push -u origin feature/my-task
```

Before merging:

```bash
git checkout main
git pull origin main
```

Then merge your feature branch (via a fast local merge or a PR, whichever's
convenient — no mandatory reviewers either way).
