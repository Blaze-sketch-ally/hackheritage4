"""Explicit, operator-run backfill: provision internship_workspaces for
applications that are ALREADY in SELECTED status.

WHY A SEPARATE SCRIPT
---------------------
Phase 2 wires workspace provisioning into the SELECTED transition
(app.services.application_service.update_status), but deliberately does
NOT provision retroactively: migrations never run application logic, and
an automatic sweep on deploy is a surprise. Any application that reached
SELECTED before Phase 2 -- or whose provisioning was skipped because the
industry had not yet created its internship_program -- is picked up here,
by an operator, on purpose.

SAFETY
------
* READ-ONLY by default. Pass --apply to actually provision.
* Idempotent: provision_for_selection() is a no-op when a workspace
  already exists, so re-running is safe.
* Only ever provisions eligible rows -- the same checks as the live path
  (SELECTED + REMOTE/HYBRID + an internship_program exists), and the
  set_workspace_derived_ids DB trigger independently enforces
  SELECTED + REMOTE/HYBRID regardless of this script.
* NEVER imported or called by a migration or by the running app. It is
  not on any request code path.
* Reports every outcome: created / already existed / skipped (work mode)
  / skipped (no program) / skipped (not selected or not an internship) /
  failures.

USAGE
-----
    # from the backend/ directory, with backend/.env populated
    # (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY):

    python -m scripts.backfill_internship_workspaces            # report only
    python -m scripts.backfill_internship_workspaces --apply    # provision

Exit code is 0 on success, 1 if any per-row provisioning failed (--apply).
"""

import argparse
import sys
from collections import Counter

from app.database.supabase import get_supabase
from app.services import internship_workspace_service


def _selected_internship_applications(sb) -> list[dict]:
    response = (
        sb.table("applications")
        .select("id, internship_id, opportunity_type, status")
        .eq("opportunity_type", "INTERNSHIP")
        .eq("status", "SELECTED")
        .execute()
    )
    return response.data or []


def _existing_workspace_application_ids(sb) -> set[str]:
    response = sb.table("internship_workspaces").select("application_id").execute()
    return {row["application_id"] for row in (response.data or [])}


def run(*, apply: bool) -> int:
    sb = get_supabase()  # service role: an operator-run sweep across every industry account
    applications = _selected_internship_applications(sb)
    print(f"Found {len(applications)} SELECTED internship application(s).")

    if not apply:
        have_workspace = _existing_workspace_application_ids(sb)
        already = sum(1 for a in applications if a["id"] in have_workspace)
        print(f"  {already} already have an internship workspace.")
        print(f"  {len(applications) - already} would be evaluated for provisioning.")
        print("\nDRY RUN -- nothing was written. Re-run with --apply to provision.")
        return 0

    tally: Counter[str] = Counter()
    failures: list[tuple[str, str]] = []
    for application in applications:
        application_id = application["id"]
        try:
            result = internship_workspace_service.provision_for_selection(sb, application_id)
            tally[result.outcome] += 1
            print(f"  {application_id}  {result.outcome}  -- {result.detail}")
        except Exception as exc:  # noqa: BLE001 -- per-row isolation: report and continue
            tally["FAILED"] += 1
            failures.append((application_id, f"{type(exc).__name__}: {exc}"))
            print(f"  {application_id}  FAILED  -- {type(exc).__name__}: {exc}")

    print("\n=== BACKFILL REPORT ===")
    print(f"  created:                          {tally['CREATED']}")
    print(f"  already existed:                  {tally['ALREADY_EXISTS']}")
    print(f"  skipped (work mode ONSITE/NULL):  {tally['SKIPPED_WORK_MODE']}")
    print(f"  skipped (no internship_program):  {tally['SKIPPED_NO_PROGRAM']}")
    print(
        "  skipped (not selected / not internship): "
        f"{tally['SKIPPED_NOT_SELECTED'] + tally['SKIPPED_NOT_INTERNSHIP']}"
    )
    print(f"  failures:                         {tally['FAILED']}")
    for application_id, message in failures:
        print(f"    - {application_id}: {message}")

    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill internship_workspaces for already-SELECTED applications."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually provision workspaces (default: report only, no writes).",
    )
    args = parser.parse_args()
    sys.exit(run(apply=args.apply))


if __name__ == "__main__":
    main()
