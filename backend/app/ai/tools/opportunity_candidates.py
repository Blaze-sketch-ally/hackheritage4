"""Bounded platform candidates in existing recommendation-service order. Read-only."""
from datetime import UTC, date, datetime

from supabase import Client

from app.ai.schemas.opportunity_recommendation import OpportunityCandidate
from app.ai.tools import opportunity_tools
from app.schemas.student_opportunity import OpportunityMatchResponse, StudentOpportunityDetail
from app.services import student_opportunity_service

MAX_CANDIDATES = 12


def get_candidates(client: Client, student_id: str) -> list[OpportunityCandidate]:
    """Start with canonical recommendations (already excludes applied/no-match).

    Recheck published/visible/unapplied detail and current deadline before matching.
    A vanished posting is dropped; matching failures propagate, never become AI data.
    The existing recommendation service may scan more postings internally; the detail
    reads and LLM candidate set here are capped at twelve.
    """
    summaries = opportunity_tools.get_recommended_opportunities(client, student_id, limit=MAX_CANDIDATES)
    today = datetime.now(UTC).date()
    candidates = []
    seen = set()
    for summary in summaries[:MAX_CANDIDATES]:
        if summary.id in seen:
            continue
        seen.add(summary.id)
        row = student_opportunity_service.get_opportunity(client, student_id, summary.id)
        if row is None:
            continue
        detail = StudentOpportunityDetail.model_validate(row)
        if detail.status != "PUBLISHED" or detail.has_applied:
            continue
        if detail.application_deadline and date.fromisoformat(detail.application_deadline) < today:
            continue
        if detail.id != summary.id or detail.source_type != summary.type:
            raise ValueError("Platform recommendation and detail identity must agree.")
        match = OpportunityMatchResponse.model_validate(
            student_opportunity_service.compute_opportunity_match(client, student_id, summary.id))
        if match.matched_count < 1:
            continue  # The student's skills may have changed since initial recommendation.
        candidates.append(OpportunityCandidate(candidate_ref=f"OP{len(candidates) + 1}",
                                               opportunity=detail, match=match))
    return candidates
