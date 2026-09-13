"""Business logic for Participation Submissions and Reviews
(`participation_submissions` / `participation_submission_reviews`,
database/migrations/064_participation_submissions_feedback.sql).
"""

from supabase import Client

_SUBMISSION_SELECT = (
    "id, workspace_id, assignment_id, attempt_number, submission_text, submission_url, "
    "submitted_at, status, created_at, assignment:participation_assignments(title)"
)
_REVIEW_SELECT = "id, submission_id, reviewer_id, score, feedback, status, reviewed_at, created_at"


def _shape_submission(row: dict) -> dict:
    assignment = row.pop("assignment", None)
    row["assignment_title"] = assignment.get("title") if assignment else None
    return row


def _attach_latest_reviews(client: Client, rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    ids = [r["id"] for r in rows]
    reviews = (
        client.table("participation_submission_reviews")
        .select(_REVIEW_SELECT)
        .in_("submission_id", ids)
        .order("reviewed_at", desc=True)
        .execute()
        .data
        or []
    )
    latest: dict[str, dict] = {}
    for r in reviews:
        latest.setdefault(r["submission_id"], r)  # first seen per id = latest, due to desc order
    for row in rows:
        row["latest_review"] = latest.get(row["id"])
    return rows


def list_submissions(client: Client, workspace_id: str) -> list[dict]:
    rows = (
        client.table("participation_submissions")
        .select(_SUBMISSION_SELECT)
        .eq("workspace_id", workspace_id)
        .order("submitted_at", desc=True)
        .execute()
        .data
        or []
    )
    return _attach_latest_reviews(client, [_shape_submission(r) for r in rows])


def create_submission(client: Client, workspace_id: str, data: dict) -> dict:
    payload = {
        "workspace_id": workspace_id,
        "assignment_id": data["assignment_id"],
        "submission_text": data.get("submission_text"),
        "submission_url": data.get("submission_url"),
    }
    response = client.table("participation_submissions").insert(payload).execute()
    new_id = response.data[0]["id"]
    row = (
        client.table("participation_submissions")
        .select(_SUBMISSION_SELECT)
        .eq("id", new_id)
        .maybe_single()
        .execute()
        .data
    )
    return _shape_submission(dict(row))


def list_reviews(client: Client, submission_id: str) -> list[dict]:
    return (
        client.table("participation_submission_reviews")
        .select(_REVIEW_SELECT)
        .eq("submission_id", submission_id)
        .order("reviewed_at", desc=True)
        .execute()
        .data
        or []
    )


def create_review(client: Client, submission_id: str, data: dict) -> dict:
    payload = {
        "submission_id": submission_id,
        "score": data.get("score"),
        "feedback": data.get("feedback"),
        "status": data["status"],
    }
    response = client.table("participation_submission_reviews").insert(payload).execute()
    new_row = response.data[0]

    # A review having been recorded at all moves the submission out of
    # SUBMITTED -- the review's own `status` (ACCEPTED/NEEDS_REVISION/
    # REVIEWED) carries the actual verdict; this column only tracks the
    # submission's own workflow state.
    client.table("participation_submissions").update({"status": "REVIEWED"}).eq("id", submission_id).execute()

    return new_row
