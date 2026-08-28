# Database Design

> `er-diagram.png` is a 1x1 placeholder — replace with a real ER diagram
> once the schema is fleshed out.

Only `database/migrations/001_profiles.sql` has real DDL today (a minimal
`profiles` table, enough to verify Supabase connectivity). The remaining
migration files (`002` through `010`) are placeholders with a comment
describing what each will eventually hold — skills, assessments,
internships, jobs, learning, portfolio, collaboration, notifications, and
analytics.

See `database/README.md` for how to apply migrations.
