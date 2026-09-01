# Database

PostgreSQL schema for the AIC Portal, managed through Supabase.

## Structure

- `migrations/` — numbered SQL migrations, applied in order via the Supabase
  SQL editor or CLI. `001_profiles.sql` through `004_assessments.sql` and
  `017_industry_profiles.sql` onward have real DDL; a few numbers in
  between (e.g. `005_internships.sql`, `006_jobs.sql`) are early
  placeholders superseded by a later, real migration (`018_internships.sql`,
  `019_jobs.sql`) rather than being edited in place — see the note at the
  top of each placeholder file.
- `seed/` — sample/demo data, applied after migrations. See
  `seed/README.md` for what's populated and how to (re-)apply it.

## Applying migrations

Run each file in `migrations/` in order against your Supabase project
(SQL editor, or `supabase db push` if using the Supabase CLI).
