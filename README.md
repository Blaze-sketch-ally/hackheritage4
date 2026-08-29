# AIC Portal

Academia-Industry Collaboration Portal — connecting Student, Faculty,
Institution, and Industry around a skill-first workflow:

Skill Assessment -> Skill Profile -> Skill Gap Analysis -> Personalized
Learning -> Digital Portfolio -> Internship/Job Matching -> Apply ->
Application Tracking -> Interview -> Selection -> Internship Experience ->
Placement -> Analytics

## Status

Environment scaffold only. Authentication and business features are not
implemented yet — see `frontend/` and `backend/` READMEs for what exists.

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
