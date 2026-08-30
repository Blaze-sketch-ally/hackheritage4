# Live integration tests

Everything in `tests/` outside this directory is fast, mocked, and runs
in plain `pytest -q` / CI with no credentials at all (see the top of
`tests/conftest.py`). Phase 1K's own verification proved those mocked
tests — 238 of them, all green throughout — cannot catch a real RLS
policy or `SECURITY DEFINER` RPC behaving unexpectedly: every real bug
found in Phase 1K (the peer-review RLS failure, the reviewer-visibility
gap, the deactivation-before-answering gap) was only caught by running
against the **real** Supabase project. This directory is where that kind
of test lives from now on, instead of as one-off throwaway scripts.

## Opt-in, never accidental

Every test here is skipped automatically unless `RUN_LIVE_INTEGRATION_TESTS=1`
is set, **in addition to** real `SUPABASE_URL` / `SUPABASE_ANON_KEY` /
`SUPABASE_SERVICE_ROLE_KEY` being present in the environment (`backend/.env`,
loaded via `python-dotenv`, same as the app itself). A plain `pytest -q` —
locally or in CI — never touches the live database. To actually run these:

```bash
RUN_LIVE_INTEGRATION_TESTS=1 pytest tests/integration -v
```

Never commit real credentials to get these to run in CI. If/when this
suite is wired into CI, the service-role key must come from a secret,
never from a file in the repository, and the job that runs it should stay
clearly separate from the ordinary mocked test job.

## Fixture safety — read this before writing a new test

The prior QA process accidentally deleted a pre-existing, unrelated
fixture because a cleanup query matched on a bare `LIKE '__QA_%'` prefix.
**Never do that.** Every fixture this suite creates must be tagged with a
unique run identifier and cleaned up by that exact identifier:

```python
RUN_ID = f"integration_{uuid.uuid4().hex[:12]}"
# every fixture: title=f"__QA_{RUN_ID}_...", email=f"__qa_{RUN_ID}_...@example.com"
# cleanup: .eq("title", exact_value) or .ilike("title", f"__QA_{RUN_ID}_%") — never a bare "__QA_%"
```

Delete only what this specific test run created, in FK-safe order
(`assessment_attempts` before `assessments` — the FK is `ON DELETE
RESTRICT`, not `CASCADE`), and verify a full sweep returns zero residue
before considering a test run "clean." See `conftest.py` in this
directory for the shared fixture factory that already does this
correctly — use it rather than writing a new one per test file.

## What belongs here

RLS correctness, `SECURITY DEFINER` RPC authorization, cross-user IDOR,
role boundaries, atomicity/rollback, and any other invariant that only
the real database can actually prove. Ordinary application logic
(request validation, response shaping, error mapping) belongs in the
mocked suite, not here — this directory should stay small and focused on
the class of bug mocks structurally cannot catch.
