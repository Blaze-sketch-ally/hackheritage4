# AIC Portal — Backend

FastAPI backend for the Academia-Industry Collaboration Portal.

## Stack

- Python + FastAPI
- Pydantic / pydantic-settings
- Supabase (PostgreSQL, Auth, Storage) as the data layer
- LLM API access, isolated behind `app/ai/`

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in the values
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- `GET /` → `{"message": "AIC Portal API is running"}`
- `GET /health` → `{"status": "ok"}`

## Structure

- `app/api/` — route modules (one per resource), included in `app/main.py` as features are built
- `app/schemas/` — Pydantic request/response models
- `app/services/` — business logic, separated from route handlers
- `app/ai/` — LLM integration, isolated from the rest of the app
- `app/database/` — Supabase client + query helpers
- `app/core/` — settings, security, shared dependencies, exceptions
- `app/utils/` — small stateless helpers
- `tests/` — pytest suite, one file per resource

## Notes

- `SUPABASE_SERVICE_ROLE_KEY` must never be exposed to the frontend.
- Authentication and business-logic endpoints are not implemented yet — this
  is intentionally just the scaffold.
