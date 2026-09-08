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

## Migration renumbering (049–053)

Two feature lines were developed on separate branches and both claimed
`037`–`041`. Merging them required a one-time repository renumber so every
file has a unique, contiguous number:

| Current file | Pre-merge number | Feature |
|---|---|---|
| `049_internship_program.sql` | `037` | Internship Workspace — program/template |
| `050_internship_workspace.sql` | `038` | Internship Workspace — workspace instance |
| `051_workspace_submissions_completion.sql` | `039` | Internship Workspace — submissions / completion / certificate |
| `052_job_training.sql` | `040` | Job Training — program + enrollment |
| `053_job_training_completion.sql` | `041` | Job Training — completion + certificate |

The SQL bodies are unchanged (only in-file comment cross-references and the
`-- Migration:` headers were updated). The live database does **not** track
these filenames or numbers — it only holds the resulting schema — so this
is a repository numbering/provenance correction, **not** a database
migration.

- **On an existing database** where `037`–`041` were already applied under
  their old numbers: do **NOT** re-run `049`–`053`. Their SQL has already
  executed.
- **On a fresh database**: run every file in `migrations/` in strict
  numeric order. `052`/`053` (Job Training) intentionally follow `051`
  because `052`'s `student_notifications` CHECK widening must be the last
  one to run.
