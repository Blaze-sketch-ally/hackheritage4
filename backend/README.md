# AIC Portal — Backend

FastAPI backend for the Academia-Industry Collaboration Portal. `app/main.py`
registers 30+ routers under `/api/v1` (student, industry, institution,
assessments, applications, internships, jobs, analytics, and more) on top
of `GET /` and `GET /health`. Some files under `app/api/` are still empty,
unregistered scaffolds for features not yet built (Faculty's own endpoints,
notifications, recommendations, etc.) — being a file in that directory does
not mean it's live; check `app/main.py`'s router list for what's actually
mounted.

## Stack

- Python 3.11
- FastAPI + Uvicorn
- Pydantic / pydantic-settings
- Supabase (PostgreSQL, Auth, Storage) as the data layer, via the `supabase`
  Python client — server-side only, using the service-role key
- LLM API access via Groq, isolated behind `app/ai/` (Phase 1: client +
  config foundation and `GET /api/v1/ai/health` only; no agent endpoints yet)

## Requirements

- Python **3.11** (pinned in `.python-version`; matches what this backend is
  developed and tested against)

## Setup

**macOS / Linux**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the values
```

**Windows**

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

- App: http://localhost:8000
- `GET /` → `{"message": "AIC Portal API is running"}`
- `GET /health` → `{"status": "ok"}`
- Interactive API docs (Swagger UI): http://localhost:8000/docs

## Environment variables

See `.env.example`. Names only — never commit real values.

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side Supabase key. **Never** expose this to the frontend. |
| `GROQ_API_KEY` | Groq API key, used by `app/ai/` (Phase 1: config/client foundation; see `app/ai/config.py` for optional `GROQ_MODEL`/`GROQ_TIMEOUT_SECONDS`/`GROQ_MAX_RETRIES` overrides) |
| `FRONTEND_URL` | Used for CORS (`app/main.py` allows this origin); defaults to `http://localhost:3000` |

## Structure

- `app/api/` — route modules (one per resource), included in `app/main.py` as features are built
- `app/schemas/` — Pydantic request/response models
- `app/services/` — business logic, separated from route handlers
- `app/ai/` — LLM integration, isolated from the rest of the app
- `app/database/` — Supabase client + query helpers
- `app/core/` — settings, security, shared dependencies, exceptions
- `app/utils/` — small stateless helpers
- `tests/` — pytest suite, one file per resource; most are placeholders
  populated alongside their feature — `test_health.py` is the one real
  suite today, covering `GET /` and `GET /health`

## Testing

```bash
pytest
```

## Linting

[Ruff](https://docs.astral.sh/ruff/) is configured in `pyproject.toml`. It's
a dev-only dependency — install it via `requirements-dev.txt` instead of
`requirements.txt`:

```bash
pip install -r requirements-dev.txt
ruff check .
```

CI (`.github/workflows/ci.yml`) runs both `ruff check .` and `pytest` on
every push/PR.

## Notes

- `SUPABASE_SERVICE_ROLE_KEY` must never be exposed to the frontend.
- Do not commit `.venv/` or `.env` — both are gitignored.
- Authentication and business-logic endpoints are not implemented yet on
  this backend — the equivalent auth flows currently run directly against
  Supabase from the frontend (see `frontend/lib/auth.ts`).


### Phase 4: AI course recommendations

`POST /api/v1/ai/course-recommendations` requires a STUDENT bearer token and
accepts no student ID. It reads the existing canonical skill-gap output, selects
up to five skills, and reuses `learning_recommendation_service` to retrieve mapped
catalog resources. No database mutation or new migration is involved.

Candidates retain catalog metadata, with unknown price/rating/certificate fields
left null. Groq receives at most twelve candidates with C refs and skill G refs,
without URLs, identity, applications, or learning-progress data. Its flat output
selects ranks, learning order, and one of three rationale codes: SKILL_MATCH,
LEVEL_MATCH, FOUNDATION. Grounding checks each code's source-data prerequisites
and renders the explanation server-side. No generated prose or metadata is
returned, preventing invented certificate/completion/verification claims.

External discovery is **not configured or connected**. The
`CourseDiscoveryProvider` protocol and normalization boundary support future
reviewed adapters; `get_external_provider()` currently returns an unavailable
provider. Adding an API key alone does not activate discovery: a real adapter,
source contract, and configuration must first be implemented. No scraping or fake
provider URLs are used. Catalog resources can already link to external websites;
these remain INTERNAL candidates because their metadata comes from the catalog.

Response metadata distinguishes CONFIGURATION_REQUIRED / AVAILABLE / FAILED for
external discovery, source failures for internal discovery, and AI / DETERMINISTIC /
NO_GAPS / NO_COURSES ranking states. Groq failure or ungroundable output preserves
source-backed recommendations in deterministic source order. Empty skills/courses
skip Groq. URLs are checked for HTTP(S) syntax, not fetched or independently audited
for availability. Rank is advisory and distinct from canonical skill priority.
