"""Business logic for Participation Evaluation Criteria, Evaluations, and
Completion (`participation_evaluation_criteria` / `participation_evaluations`
/ `participation_evaluation_scores` / `participation_completions`,
database/migrations/065_participation_evaluation_completion.sql).

The final `overall_score` is ALWAYS computed here from the weighted
criterion scores -- never accepted verbatim from a client request, mirroring
app.services.match_service's "the backend is the sole source of the score"
stance for Skill Match.
"""

from datetime import UTC, datetime

from supabase import Client

_CRITERION_SELECT = "id, program_id, name, description, max_score, weight, sequence_order, created_at, updated_at"
_EVALUATION_SELECT = (
    "id, workspace_id, evaluator_id, status, overall_score, overall_feedback, evaluated_at, "
    "created_at, updated_at"
)
_SCORE_SELECT = (
    "id, evaluation_id, criterion_id, score, feedback, "
    "criterion:participation_evaluation_criteria(name, max_score)"
)
_COMPLETION_SELECT = "id, workspace_id, final_evaluation_id, completed_at, completion_status, final_score, created_at"


class EvaluationFinalizedError(Exception):
    """The evaluation is already FINALIZED and cannot be edited further."""


class IncompleteRubricError(Exception):
    """Not every criterion on the program has a score yet."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Missing scores for: " + ", ".join(missing))


class CompletionNotAllowedError(Exception):
    """The workspace does not yet satisfy completion's business rules."""


# ---- criteria ----


def list_criteria(client: Client, program_id: str) -> list[dict]:
    return (
        client.table("participation_evaluation_criteria")
        .select(_CRITERION_SELECT)
        .eq("program_id", program_id)
        .order("sequence_order")
        .execute()
        .data
        or []
    )


def create_criterion(client: Client, program_id: str, data: dict) -> dict:
    payload = {
        "program_id": program_id,
        "name": data["name"],
        "description": data.get("description"),
        "max_score": data["max_score"],
        "weight": data["weight"],
        "sequence_order": data.get("sequence_order", 0),
    }
    response = client.table("participation_evaluation_criteria").insert(payload).execute()
    return response.data[0]


def update_criterion(client: Client, program_id: str, criterion_id: str, data: dict) -> dict | None:
    payload = {k: v for k, v in data.items() if k in ("name", "description", "max_score", "weight", "sequence_order")}
    if payload:
        client.table("participation_evaluation_criteria").update(payload).eq("id", criterion_id).eq("program_id", program_id).execute()
    response = (
        client.table("participation_evaluation_criteria")
        .select(_CRITERION_SELECT)
        .eq("id", criterion_id)
        .eq("program_id", program_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def delete_criterion(client: Client, program_id: str, criterion_id: str) -> bool:
    """True if removed. Fails at the DB level (ON DELETE RESTRICT) if any
    evaluation has already scored this criterion -- the route surfaces
    that as a 409, not a 500."""
    client.table("participation_evaluation_criteria").delete().eq("id", criterion_id).eq("program_id", program_id).execute()
    return True


# ---- evaluations ----


def _shape_scores(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        criterion = row.pop("criterion", None) or {}
        row["criterion_name"] = criterion.get("name")
        row["max_score"] = criterion.get("max_score")
        out.append(row)
    return out


def get_evaluation(client: Client, workspace_id: str) -> dict | None:
    response = (
        client.table("participation_evaluations").select(_EVALUATION_SELECT).eq("workspace_id", workspace_id).maybe_single().execute()
    )
    row = response.data if response is not None else None
    if not row:
        return None
    scores = (
        client.table("participation_evaluation_scores").select(_SCORE_SELECT).eq("evaluation_id", row["id"]).execute().data or []
    )
    row["scores"] = _shape_scores(scores)
    return row


def ensure_evaluation(client: Client, workspace_id: str) -> dict:
    """Idempotent ensure-or-create: a DRAFT evaluation shell for this
    workspace, so Industry always has a row to save scores against."""
    existing = get_evaluation(client, workspace_id)
    if existing:
        return existing
    client.table("participation_evaluations").insert({"workspace_id": workspace_id}).execute()
    row = get_evaluation(client, workspace_id)
    if row is None:
        raise RuntimeError("evaluation could not be read back after create.")
    return row


def save_evaluation(client: Client, workspace_id: str, data: dict) -> dict:
    """Upserts overall_feedback and every score in `data['scores']` on the
    DRAFT evaluation. Raises EvaluationFinalizedError (route -> 409) if
    already finalized -- checked here so the error is friendly; the DB
    trigger is the real backstop regardless."""
    evaluation = ensure_evaluation(client, workspace_id)
    if evaluation["status"] == "FINALIZED":
        raise EvaluationFinalizedError()

    if data.get("overall_feedback") is not None:
        client.table("participation_evaluations").update({"overall_feedback": data["overall_feedback"]}).eq("id", evaluation["id"]).execute()

    for s in data.get("scores", []):
        existing_score = (
            client.table("participation_evaluation_scores")
            .select("id")
            .eq("evaluation_id", evaluation["id"])
            .eq("criterion_id", s["criterion_id"])
            .maybe_single()
            .execute()
        )
        found = existing_score.data if existing_score is not None else None
        payload = {"score": s["score"], "feedback": s.get("feedback")}
        if found:
            client.table("participation_evaluation_scores").update(payload).eq("id", found["id"]).execute()
        else:
            client.table("participation_evaluation_scores").insert(
                {"evaluation_id": evaluation["id"], "criterion_id": s["criterion_id"], **payload}
            ).execute()

    result = get_evaluation(client, workspace_id)
    if result is None:
        raise RuntimeError("evaluation could not be read back after save.")
    return result


def finalize_evaluation(client: Client, program_id: str, workspace_id: str) -> dict:
    """Computes overall_score as the weighted average of every criterion's
    score/max_score, requires every criterion on the program to have a
    score first (IncompleteRubricError -> 422), then locks the evaluation.
    A program with zero criteria finalizes with overall_score = None
    (nothing to compute) -- a lightweight Workshop is not forced to author
    a rubric."""
    evaluation = ensure_evaluation(client, workspace_id)
    if evaluation["status"] == "FINALIZED":
        raise EvaluationFinalizedError()

    criteria = list_criteria(client, program_id)
    if criteria:
        scored_ids = {s["criterion_id"] for s in evaluation["scores"]}
        missing = [c["name"] for c in criteria if c["id"] not in scored_ids]
        if missing:
            raise IncompleteRubricError(missing)

        weighted_sum = 0.0
        weight_total = 0.0
        by_id = {c["id"]: c for c in criteria}
        for s in evaluation["scores"]:
            criterion = by_id.get(s["criterion_id"])
            if not criterion or not criterion["max_score"]:
                continue
            pct = (s["score"] / criterion["max_score"]) * 100
            weighted_sum += pct * criterion["weight"]
            weight_total += criterion["weight"]
        overall_score = round(weighted_sum / weight_total, 2) if weight_total > 0 else None
    else:
        overall_score = None

    client.table("participation_evaluations").update(
        {"status": "FINALIZED", "overall_score": overall_score, "evaluated_at": datetime.now(UTC).isoformat()}
    ).eq("id", evaluation["id"]).execute()

    result = get_evaluation(client, workspace_id)
    if result is None:
        raise RuntimeError("evaluation could not be read back after finalize.")
    return result


# ---- completion ----


def get_completion(client: Client, workspace_id: str) -> dict | None:
    response = client.table("participation_completions").select(_COMPLETION_SELECT).eq("workspace_id", workspace_id).maybe_single().execute()
    return response.data if response is not None else None


def create_completion(client: Client, program_id: str | None, workspace_id: str) -> dict:
    """Records completion. If the program has any evaluation criteria
    authored, a FINALIZED evaluation is required first
    (CompletionNotAllowedError -> 409); a program with no criteria (a
    lightweight Workshop with no formal rubric) can complete without one."""
    existing = get_completion(client, workspace_id)
    if existing:
        return existing

    evaluation = get_evaluation(client, workspace_id)
    criteria = list_criteria(client, program_id) if program_id else []
    if criteria and (not evaluation or evaluation["status"] != "FINALIZED"):
        raise CompletionNotAllowedError("This program has evaluation criteria -- finalize the evaluation before completing.")

    payload = {"workspace_id": workspace_id}
    if evaluation and evaluation["status"] == "FINALIZED":
        payload["final_evaluation_id"] = evaluation["id"]
        payload["final_score"] = evaluation["overall_score"]

    response = client.table("participation_completions").insert(payload).execute()
    new_id = response.data[0]["id"]

    # Best-effort: mark the workspace itself COMPLETED too, so it drops out
    # of "Active" lists everywhere consistently.
    client.table("participation_workspaces").update(
        {"workspace_status": "COMPLETED", "completed_at": datetime.now(UTC).isoformat()}
    ).eq("id", workspace_id).execute()

    result = client.table("participation_completions").select(_COMPLETION_SELECT).eq("id", new_id).maybe_single().execute()
    return result.data if result is not None else payload
