"""Tools: the student's own assessment attempt history, summarized.

`get_assessment_summary` is a thin adapter over the EXISTING
assessment_service.list_own_attempts + get_skill_verification -- the
same two calls, with the same distinct-(skill_id, difficulty) caching,
that app.api.attempts.list_history (GET /api/v1/attempts) already uses
to build AttemptHistoryItemResponse rows. This module does not
recompute score, percentage, passed, or skill_verified differently; it
only re-derives small aggregate counts (totals) over rows those two
calls already produced. See app.ai.tools's package docstring.
"""

from supabase import Client

from app.ai.schemas.student_context import AssessmentSummary
from app.schemas.assessment import AssessmentResponse, AttemptHistoryItemResponse
from app.services import assessment_service, skill_gap_service

# Context-size hygiene for a future agent's prompt budget, matching the
# equivalent cap documented in app.ai.schemas.student_context -- the full
# history is still reachable through the existing GET /attempts endpoint.
_RECENT_ATTEMPTS_LIMIT = 10


def get_assessment_summary(client: Client, student_id: str) -> AssessmentSummary:
    """Aggregate counts + the most recent attempts, most recent first.
    Every count is 0 and `recent_attempts` is [] for a student who has
    never attempted an assessment -- not an error."""
    rows = assessment_service.list_own_attempts(client, student_id)

    verified_cache: dict[tuple[str, str], bool] = {}
    items: list[AttemptHistoryItemResponse] = []
    completed_attempts = 0
    passed_attempts = 0
    verified_skill_ids: set[str] = set()

    for row in rows:
        assessment = row.get("assessment")
        passed: bool | None = None
        skill_verified: bool | None = None

        if row["status"] == "COMPLETED":
            completed_attempts += 1

        if assessment is not None and row.get("percentage") is not None:
            passed = float(row["percentage"]) >= float(assessment["passing_percentage"])
            if passed:
                passed_attempts += 1

            cache_key = (assessment["skill_id"], assessment["difficulty"])
            if cache_key not in verified_cache:
                verified_cache[cache_key] = assessment_service.get_skill_verification(
                    client, student_id, assessment["skill_id"], assessment["difficulty"]
                )
            skill_verified = verified_cache[cache_key]
            if skill_verified:
                verified_skill_ids.add(assessment["skill_id"])

        items.append(
            AttemptHistoryItemResponse(
                **{k: v for k, v in row.items() if k != "assessment"},
                passed=passed,
                skill_verified=skill_verified,
                assessment=AssessmentResponse(**assessment) if assessment is not None else None,
            )
        )

    return AssessmentSummary(
        total_attempts=len(items),
        completed_attempts=completed_attempts,
        passed_attempts=passed_attempts,
        verified_skill_count=len(verified_skill_ids),
        recent_attempts=items[:_RECENT_ATTEMPTS_LIMIT],
    )


def get_assessment_availability(client: Client, skill_ids: list[str]) -> dict[tuple[str, str], str]:
    """Read active assessments through the canonical lookup; no scoring or writes.

    The agent resolves owned refs at their current proficiency, while gap refs
    retain the target-level availability already supplied by the gap engine.
    """
    return skill_gap_service.get_assessment_availability(client, skill_ids)
