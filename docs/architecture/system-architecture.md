# System Architecture

> `system-architecture.png` is a 1x1 placeholder — replace with a real
> diagram once the architecture is finalized.

```
Browser
   |
Next.js Frontend (Vercel)
   |  REST / JSON
   v
FastAPI Backend (Render/Railway)
   |
   +--> Supabase PostgreSQL
   +--> Supabase Storage
   +--> LLM / AI API
```

## Layers

- **Next.js (frontend/)** — UI, pages, components, client-side interactions,
  frontend API calls, authentication state/UI. No business logic.
- **FastAPI (backend/)** — business logic, API endpoints, skill
  calculations, assessments, recommendations, AI integration, analytics,
  backend validation.
- **Supabase** — PostgreSQL database, authentication, storage.

The frontend never talks to Supabase's PostgreSQL directly for business
data — it goes through the FastAPI REST API. Supabase Auth/Storage are used
directly from the frontend where appropriate (session state, file access).
