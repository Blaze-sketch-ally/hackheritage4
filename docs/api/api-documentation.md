# API Documentation

Placeholder — expanded as endpoints are implemented.

## Current endpoints

| Method | Path      | Description                     |
|--------|-----------|----------------------------------|
| GET    | `/`       | API liveness message             |
| GET    | `/health` | Health check                     |

FastAPI also serves interactive docs at `/docs` (Swagger UI) and `/redoc`
once the backend is running.

## Planned route groups

One router per resource under `backend/app/api/`: auth, users, students,
faculty, industry, institution, skills, assessments, internships, jobs,
applications, courses, certifications, projects, mentorship,
collaborations, notifications, analytics, recommendations, ai. Each is
currently an empty `APIRouter` placeholder, not yet mounted on the app.
