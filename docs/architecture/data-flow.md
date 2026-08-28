# Data Flow

Placeholder — expanded once features are implemented.

High-level request flow:

1. Browser calls a Next.js page/component.
2. Component calls `frontend/lib/api.ts`, which hits the FastAPI backend
   at `NEXT_PUBLIC_API_URL`.
3. FastAPI route (`app/api/*`) delegates to a service (`app/services/*`)
   for business logic.
4. Service reads/writes Supabase PostgreSQL via `app/database/supabase.py`,
   and calls the AI module (`app/ai/*`) when LLM output is needed.
5. Response flows back through FastAPI -> Next.js -> browser as JSON.

Future workflow this will support:

Skill Assessment -> Skill Profile -> Skill Gap Analysis -> Personalized
Learning -> Digital Portfolio -> Internship/Job Matching -> Apply ->
Application Tracking -> Interview -> Selection -> Internship Experience ->
Placement -> Analytics
