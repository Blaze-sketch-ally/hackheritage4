"""Ground reason codes against canonical evidence; never return generated prose."""
import re

from app.ai.schemas.opportunity_recommendation import (
    ApplicationPlanStep,
    OpportunityCandidate,
    OpportunityRecommendation,
    OpportunityRecommendationLLMOutput,
)


def _words(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def allowed_codes(candidate: OpportunityCandidate, target_role: str | None) -> list[str]:
    match = candidate.match
    codes = []
    if match.matched_count > 0 and match.matched_skills:
        codes.append("CANONICAL_SKILL_MATCH")
    if match.recommendation == "STRONG":
        codes.append("STRONG_CANONICAL_MATCH")
    if match.required_count > 0 and match.missing_count == 0 and match.needs_improvement_count == 0:
        codes.append("LOW_SKILL_GAP")
    if match.missing_count > 0 or match.needs_improvement_count > 0:
        codes.append("STRETCH_OPPORTUNITY")
    if any(s.candidate_verified for s in match.matched_skills):
        codes.append("VERIFIED_SKILL_ALIGNMENT")
    # Lexical evidence only: no semantic role or eligibility inference.
    role = _words(target_role or "")
    if role and f" {role} " in f" {_words(candidate.opportunity.title)} ":
        codes.append("TARGET_ROLE_ALIGNMENT")
    return codes


def explain(code: str, candidate: OpportunityCandidate) -> str:
    messages = {
        "CANONICAL_SKILL_MATCH": "The deterministic matcher identifies matching required skills.",
        "STRONG_CANONICAL_MATCH": (
            f"The deterministic match score is {candidate.match.score}, with a "
            f"{candidate.match.recommendation} band."
        ),
        "LOW_SKILL_GAP": "The deterministic matcher reports no missing or below-level requirements.",
        "STRETCH_OPPORTUNITY": "The deterministic matcher identifies missing or below-level requirements to review.",
        "VERIFIED_SKILL_ALIGNMENT": "At least one matched required skill has assessment verification.",
        "TARGET_ROLE_ALIGNMENT": "The posting title contains your selected target role.",
    }
    return messages[code]


def ground(output: OpportunityRecommendationLLMOutput, candidates: list[OpportunityCandidate],
           target_role: str | None):
    index = {c.candidate_ref: c for c in candidates}
    reasons: dict[str, list[str]] = {}
    for line in output.recommendation_codes:
        parts = line.split(": ")
        if len(parts) != 2:
            continue
        ref, code = parts
        if ref not in index or code not in allowed_codes(index[ref], target_role):
            continue
        codes = reasons.setdefault(ref, [])
        if code not in codes:
            codes.append(code)
    selected = {}
    for ref in output.recommended_opportunity_refs:
        if ref in selected or ref not in reasons:
            continue
        candidate = index[ref]
        codes = reasons[ref]
        selected[ref] = OpportunityRecommendation(candidate_ref=ref,
            opportunity=candidate.opportunity, match=candidate.match,
            metadata_source=candidate.metadata_source, reason_codes=codes,
            reason=" ".join(explain(code, candidate) for code in codes), rank=len(selected) + 1)
    order = list(dict.fromkeys(ref for ref in output.application_order if ref in selected))
    order.extend(ref for ref in selected if ref not in order)
    plan = [ApplicationPlanStep(order=n, opportunity_id=selected[ref].opportunity.id)
            for n, ref in enumerate(order, 1)]
    return list(selected.values()), plan


def deterministic_fallback(candidates: list[OpportunityCandidate]):
    """Retain the recommendation service's candidate order, with no AI rationale."""
    recommendations = [OpportunityRecommendation(candidate_ref=c.candidate_ref,
        opportunity=c.opportunity, match=c.match, metadata_source=c.metadata_source,
        reason_codes=[], reason="Shown in the platform's deterministic recommendation order.", rank=n)
        for n, c in enumerate(candidates, 1)]
    plan = [ApplicationPlanStep(order=n, opportunity_id=c.opportunity.id)
            for n, c in enumerate(candidates, 1)]
    return recommendations, plan
