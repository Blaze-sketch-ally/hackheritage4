"""Explicit, operator-run backfill: provision job_training_enrollments for
applications that are ALREADY in SELECTED status for a JOB.

WHY A SEPARATE SCRIPT
---------------------
Phase J3 wires job training provisioning into the SELECTED transition
(app.services.application_service.update_status), but deliberately does
NOT provision retroactively: migrations never run application logic, and
an automatic sweep on deploy is a surprise. Any JOB application that
reached SELECTED before Phase J3 -- or whose provisioning was skipped
because the industry had not yet authored its job_program -- is picked up
here, by an operator, on purpose.

Mirrors scripts/backfill_internship_workspaces.py exactly.

SAFETY
------
* READ-ONLY by default. Pass --apply to actually provision.
* Idempotent: provision_for_selection() is a no-op when an enrollment
  already exists (ALREADY_EXISTS), and REVOKED_BLOCKED for a revoked one
  -- it is never silently resurrected.
* Only ever provisions eligible rows -- the same checks as the live path
  (JOB + SELECTED + a job_program exists), and the J1
  set_job_training_enrollment_derived_ids DB trigger independently
  enforces JOB + SELECTED regardless of this script.
* NEVER imported or called by a migration or by the running app. It is
  not on any request code path.
* Reports every outcome.

USAGE
-----
    # from the backend/ directory, with backend/.env populated
    # (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY):

    python -m scripts.backfill_job_training_enrollments            # report only
    python -m scripts.backfill_job_training_enrollments --apply    # provision

Exit code is 0 on success, 1 if any per-row provisioning failed (--apply).
"""

import argparse
import sys
from collections import Counter

from app.database.supabase import get_supabase
from app.services import job_training_service


def _selected_job_applications(sb) -> list[dict]:
    response = (
        sb.table("applications")
        .select("id, job_id, opportunity_type, status")
        .eq("opportunity_type", "JOB")
        .eq("status", "SELECTED")
        .execute()
    )
    return response.data or []


def _existing_enrollment_application_ids(sb) -> set[str]:
    response = sb.table("job_training_enrollments").select("application_id").execute()
    return {row["application_id"] for row in (response.data or [])}


def run(*, apply: bool) -> int:
    sb = get_supabase()  # service role: an operator-run sweep across every industry account
    applications = _selected_job_applications(sb)
    print(f"Found {len(applications)} SELECTED job application(s).")

    if not apply:
        have_enrollment = _existing_enrollment_application_ids(sb)
        already = sum(1 for a in applications if a["id"] in have_enrollment)
        print(f"  {already} already have a job training enrollment.")
        print(f"  {len(applications) - already} would be evaluated for provisioning.")
        print("\nDRY RUN -- nothing was written. Re-run with --apply to provision.")
        return 0

    tally: Counter[str] = Counter()
    failures: list[tuple[str, str]] = []
    for application in applications:
        application_id = application["id"]
        try:
            result = job_training_service.provision_for_selection(sb, application_id)
            tally[result.outcome] += 1
            print(f"  {application_id}  {result.outcome}  -- {result.detail}")
        except Exception as exc:  # noqa: BLE001 -- per-row isolation: report and continue
            tally["FAILED"] += 1
            failures.append((application_id, f"{type(exc).__name__}: {exc}"))
            print(f"  {application_id}  FAILED  -- {type(exc).__name__}: {exc}")

    print("\n=== BACKFILL REPORT ===")
    print(f"  created:                          {tally['CREATED']}")
    print(f"  already existed:                  {tally['ALREADY_EXISTS']}")
    print(f"  skipped (no job_program):         {tally['SKIPPED_NO_PROGRAM']}")
    print(
        "  skipped (not selected / not a job): "
        f"{tally['SKIPPED_NOT_SELECTED'] + tally['SKIPPED_NOT_JOB']}"
    )
    print(f"  blocked (enrollment revoked):     {tally['REVOKED_BLOCKED']}")
    print(f"  failures:                         {tally['FAILED']}")
    for application_id, message in failures:
        print(f"    - {application_id}: {message}")

    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill job_training_enrollments for already-SELECTED job applications."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually provision enrollments (default: report only, no writes).",
    )
    args = parser.parse_args()
    sys.exit(run(apply=args.apply))


if __name__ == "__main__":
    main()
