# Database

PostgreSQL schema for the AIC Portal, managed through Supabase.

## Structure

- `migrations/` — numbered SQL migrations, applied in order via the Supabase
  SQL editor or CLI. Only `001_profiles.sql` currently has real DDL (enough
  to verify Supabase connectivity); the rest are placeholders documenting
  what each future migration will contain.
- `seed/` — sample/demo data, applied after migrations. Currently empty
  placeholders — populated once their corresponding schema exists.

## Applying migrations

Run each file in `migrations/` in order against your Supabase project
(SQL editor, or `supabase db push` if using the Supabase CLI).
