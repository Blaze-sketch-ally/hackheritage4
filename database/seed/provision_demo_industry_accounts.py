"""Provisions demo INDUSTRY accounts for local development (Phase 1M).

WHY THIS IS A SCRIPT, NOT A .sql FILE: every other seed file in this
directory is pure SQL because it only populates catalog/reference tables.
Industry demo accounts need real rows in Supabase Auth's `auth.users`
table first (profiles.id has a foreign key to it, and `handle_new_user()`
-- 001_profiles.sql -- is what creates the matching `profiles` row,
copying full_name from auth metadata). There is no safe, pure-SQL way to
create a real Supabase Auth user -- inserting directly into `auth.users`
would bypass Supabase Auth's own password hashing and session machinery
entirely, and is exactly the kind of "unsafe direct auth insert" this
phase's own design brief says not to do. This script instead uses the
same trusted, already-proven mechanism this project's own live
integration test suite uses throughout (`admin.create_user()` via the
service-role client -- see backend/tests/integration/conftest.py) --
just run once, for permanent demo data, rather than per-test and cleaned
up afterward.

Idempotent: checks for each account by email before creating it, so
running this more than once does nothing destructive and creates nothing
twice. Non-destructive: never deletes or modifies any existing user.
Never hardcodes a password -- generates one per run and prints it once;
these are local-development demo accounts, not production credentials.

Usage (from backend/, with backend/.env populated -- same requirements
as backend/tests/integration/):

    cd backend
    source .venv/bin/activate
    python3 ../database/seed/provision_demo_industry_accounts.py

After this succeeds, apply database/seed/opportunities.sql (pure SQL,
via the Supabase Dashboard SQL Editor like every other seed file) to
create the actual opportunity postings owned by these accounts.
"""

import os
import secrets
import sys

from dotenv import load_dotenv

# Demo companies -- reuses the exact same fictional company names already
# used in frontend/lib/mock/student-dashboard.ts's MOCK_RECOMMENDATIONS,
# so the student dashboard's illustrative "Nimbus Systems" / "Verdant
# Labs" / "Orbit Analytics" / "Brightline Tech" postings now correspond
# to real, seeded opportunities under the same names -- a deliberate
# continuity touch, not required, but free to do.
DEMO_INDUSTRY_ACCOUNTS = [
    {"email": "nimbus@aicportal.dev", "full_name": "Nimbus Systems", "username": "nimbussystems"},
    {"email": "verdant@aicportal.dev", "full_name": "Verdant Labs", "username": "verdantlabs"},
    {"email": "orbit@aicportal.dev", "full_name": "Orbit Analytics", "username": "orbitanalytics"},
    {"email": "brightline@aicportal.dev", "full_name": "Brightline Tech", "username": "brightlinetech"},
]


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))

    missing = [name for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not os.environ.get(name)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Populate backend/.env first (see backend/tests/integration/README.md).")
        sys.exit(1)

    from supabase import create_client

    admin = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    password = f"Demo!{secrets.token_hex(6)}"
    created = []
    skipped = []

    for account in DEMO_INDUSTRY_ACCOUNTS:
        existing = admin.table("profiles").select("id").eq("email", account["email"]).execute().data
        if existing:
            skipped.append(account["email"])
            continue

        resp = admin.auth.admin.create_user(
            {
                "email": account["email"],
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": account["full_name"]},
            }
        )
        user_id = resp.user.id
        # handle_new_user() already created the profiles row (role NULL,
        # full_name from metadata) -- service_role is the only path that
        # can set role directly, matching the same trusted mechanism
        # 023_role_and_attempt_integrity_hardening.sql's own comments
        # describe as the only legitimate way to assign a role outside
        # the one-time self-service onboarding flow.
        admin.table("profiles").update({"role": "INDUSTRY", "username": account["username"]}).eq(
            "id", user_id
        ).execute()
        created.append(account["email"])

    print(f"Created: {len(created)} account(s)")
    for email in created:
        print(f"  - {email}")
    if skipped:
        print(f"Already existed, skipped: {len(skipped)} account(s)")
        for email in skipped:
            print(f"  - {email}")
    if created:
        print(f"\nPassword for newly created accounts: {password}")
        print("(Not stored anywhere -- save it now if you need to log in as one of these accounts.)")


if __name__ == "__main__":
    main()
