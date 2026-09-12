"""Phase 5: existing platform metadata and canonical match schemas, never LLM facts."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.schemas.base import AIResponseMeta
from app.schemas.student_opportunity import OpportunityMatchResponse, StudentOpportunityDetail


class OpportunityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_ref: str
    opportunity: StudentOpportunityDetail
    match: OpportunityMatchResponse
    metadata_source: Literal["platform/student_opportunity_service"] = "platform/student_opportunity_service"

    @model_validator(mode="after")
    def same_opportunity(self):
        if self.opportunity.id != self.match.opportunity_id:
            raise ValueError("Canonical opportunity and match identity must agree.")
        if self.opportunity.status != "PUBLISHED" or self.opportunity.has_applied:
            raise ValueError("Only published, unapplied candidates are allowed.")
        return self


class OpportunityCanonical(BaseModel):
    target_role: str | None = None
    candidate_count: int


class OpportunityInputCandidate(BaseModel):
    ref: str
    opportunity_type: str
    title: str
    description: str
    location: str | None
    work_mode: str | None
    score: int
    band: str
    matched_count: int
    improvement_count: int
    missing_count: int
    matched_skills: list[str]
    improvement_skills: list[str]
    missing_skills: list[str]
    allowed_reason_codes: list[str]


class OpportunityRecommendationAgentInput(BaseModel):
    target_role: str | None
    opportunity_candidates: list[OpportunityInputCandidate]


class OpportunityRecommendationLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommended_opportunity_refs: list[str] = Field(max_length=12)
    recommendation_codes: list[str] = Field(
        max_length=24, description="OP1: CODE using only that candidate's allowed_reason_codes"
    )
    application_order: list[str] = Field(max_length=12, description="Selected OP refs in suggested order")


class OpportunityRecommendation(BaseModel):
    candidate_ref: str
    opportunity: StudentOpportunityDetail
    match: OpportunityMatchResponse
    metadata_source: str
    reason_codes: list[str]
    reason: str
    rank: int


class ApplicationPlanStep(BaseModel):
    order: int
    opportunity_id: str
    instruction: str = "Review the posting requirements before deciding whether to apply."


class OpportunityRecommendationMeta(AIResponseMeta):
    ai_available: bool = False
    ranking_status: Literal["AI", "DETERMINISTIC", "NO_CANDIDATES"]
    message: str | None = None


class OpportunityRecommendationResponse(BaseModel):
    canonical: OpportunityCanonical
    recommendations: list[OpportunityRecommendation] = Field(default_factory=list)
    application_order: list[ApplicationPlanStep] = Field(default_factory=list)
    meta: OpportunityRecommendationMeta
    disclaimer: str = (
        "Ranking is advisory. Platform opportunity details and deterministic matches remain "
        "authoritative. A recommendation does not establish eligibility or submit an application."
    )
