# AIC Portal — Backend

FastAPI backend for the Academia-Industry Collaboration Portal. Currently a
scaffold: `GET /` and `GET /health` are the only live endpoints — see
`app/api/` for route modules awaiting implementation as features are built.

## Stack

- Python 3.11
- FastAPI + Uvicorn
- Pydantic / pydantic-settings
- Supabase (PostgreSQL, Auth, Storage) as the data layer, via the `supabase`
  Python client — server-side only, using the service-role key
- LLM API access, isolated behind `app/ai/` (not implemented yet)

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
| `AI_API_KEY` | LLM provider key, used once `app/ai/` is implemented |
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
