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

**Frontend**

```bash
cd frontend
npm install
copy .env.example .env.local   # then fill in Supabase values
npm run dev                     # http://localhost:3000
```

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then fill in Supabase/AI values
uvicorn app.main:app --reload --port 8000   # http://localhost:8000
```

**Or with Docker Compose**

```bash
docker compose up
```

## Environment variables

See `frontend/.env.example` and `backend/.env.example`. Never commit `.env`
or `.env.local` files, and never expose `SUPABASE_SERVICE_ROLE_KEY` to the
frontend.
