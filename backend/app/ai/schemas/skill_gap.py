"""Schemas for the Skill Gap Analysis Agent (Phase 3 + 3.3).

Three distinct groups of types, deliberately kept apart:

1. SkillGapAgentInput -- the MINIMAL grounded input handed to Groq (as
   JSON text in the user message -- NOT itself schema-validated by Groq,
   so its own complexity has no bearing on structured-output
   reliability). Never the whole StudentCareerContext (see
   app.ai.agents.skill_gap_agent). Phase 3.3 adds a short `ref` token
   (e.g. "G1", "O1", "P1") to each item -- the closed vocabulary the LLM
   must use to refer back to that exact item in its output, instead of
   free-text names.

2. SkillGapLLMOutput -- exactly what Groq is asked to produce
   (response_model of complete_structured, and therefore what strict
   JSON-schema mode must validate). Phase 3.3 REPLACES the original
   nested-object version (8 properties, 5 $defs, 5 array-of-object
   fields -- see the Phase 3.3 report for the measured complexity that
   made Groq's strict mode unreliable) with a FLAT shape: every field is
   a bare `str` or `list[str]`. Zero nested objects, zero $defs, zero
   $ref anywhere. Association with a specific skill/portfolio item is
   carried inside each string via a plain "<REF>: text" or
   "<REF1> -> <REF2>: text" prefix convention (see
   app.ai.guardrails.skill_gap for the exact grammar and parsing) --
   never a nested object, and never a canonical fact: no skill_id, no
   status, no priority, no importance, no readiness, no verification
   field anywhere in this class.

3. The grounded response models (PriorityGapAnalysis, SequenceStep, ...,
   SkillGapAnalysis, SkillGapAgentResponse) -- retain the rich API shape.
   What the API actually returns stays exactly as rich as Phase 3 built
   it; absent personal status/priority are now honestly nullable. Every canonical_* / skill_id
   / assessment_available field on these is populated by the guardrail
   layer from app.services.skill_gap_service's own output, not from the
   LLM.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas.base import AIResponseMeta
from app.schemas.skill_gap import AnalysisMode

_MAX_LIST_ITEMS = 10
_MAX_LONG_TEXT = 800

# ============================================================
# 1. Agent input -- minimal, grounded, closed-set ref tokens
# ============================================================


class InputGapSkill(BaseModel):
    """One canonical gap-worthy skill the LLM may reason about, tagged
    with a stable `ref` token (e.g. "G1") -- the ONLY way the LLM may
    refer back to this skill in its output. `status`/`priority`/
    `importance`/`assessment_available` are copied verbatim from
    skill_gap_service's own output -- the LLM reads these, it never
    restates or overrides them in its output."""

    ref: str
    skill_name: str
    status: str | None  # GapStatus: MATCHED / NEEDS_IMPROVEMENT / MISSING
    priority: str | None  # Priority: HIGH / MEDIUM / LOW
    importance: str | None = None  # Importance: CORE/IMPORTANT/OPTIONAL -- None in personal mode
    current_level: str | None = None
    target_level: str | None = None  # required_level (job-role) or next_level (personal)
    is_verified: bool | None = None
    assessment_available: bool = False


class InputOwnedSkill(BaseModel):
    """One of the student's own current skills, tagged with a stable
    `ref` token (e.g. "O1") -- context for transferable-skill reasoning,
    never a gap."""

    ref: str
    skill_name: str
    proficiency_level: str
    is_verified: bool
    assessment_available: bool = False  # At the owned proficiency level.


class InputPortfolioItem(BaseModel):
    """One piece of portfolio evidence, tagged with a stable `ref` token
    (e.g. "P1"). `related_skill_names` is only ever populated for a
    project (student_project_skills) -- certs and achievements carry no
    skill link in the schema, so it stays empty for those; the title/
    organization is still useful context."""

    ref: str
    title: str
    source_type: Literal["PROJECT", "CERTIFICATION", "ACHIEVEMENT"]
    organization: str | None = None
    related_skill_names: list[str] = Field(default_factory=list)


class InputAssessmentEvidence(BaseModel):
    """One past attempt at a skill that is ALSO one of the gap-relevant
    skills below -- unrelated assessment history is deliberately
    excluded (see the Phase 3 brief's minimal-input guidance)."""

    skill_name: str
    difficulty: str
    passed: bool


class SkillGapAgentInput(BaseModel):
    """The complete, minimal grounded input for one Skill Gap Agent call.
    Never the whole StudentCareerContext -- application history,
    recommended opportunities, and unrelated learning progress are
    excluded entirely (see app.ai.agents.skill_gap_agent)."""

    mode: AnalysisMode
    target_role: str | None = None
    gap_skills: list[InputGapSkill] = Field(default_factory=list)
    owned_skills: list[InputOwnedSkill] = Field(default_factory=list)
    portfolio_items: list[InputPortfolioItem] = Field(default_factory=list)
    assessment_evidence: list[InputAssessmentEvidence] = Field(default_factory=list)


# ============================================================
# 2. Raw LLM output (Phase 3.3) -- flat, ref-token-annotated strings,
#    no nested objects, no canonical fields
# ============================================================


class SkillGapLLMOutput(BaseModel):
    """What Groq must produce. Flat only: every field is a bare `str` or
    `list[str]` -- see app.ai.guardrails.skill_gap for how each is
    parsed back into a canonical entity server-side."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=_MAX_LONG_TEXT, description="A short overall summary.")
    strengths: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description="Plain notes about the student's matched/verified strengths. No ref prefix needed.",
    )
    priority_gap_reasons: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description='One string per gap skill you discuss, formatted exactly as "<ref>: reason" -- e.g. "G1: Focused practice may help build fluency."',
    )
    priority_gap_actions: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description='One string per gap skill, formatted exactly as "<ref>: suggested action" -- use the SAME ref as in priority_gap_reasons.',
    )
    transferable_skill_notes: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description='Formatted exactly as "<owned_or_matched_ref> -> <gap_ref>: explanation" -- e.g. "O1 -> G2: explanation."',
    )
    learning_sequence: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description='Bare gap refs only, in recommended order -- e.g. ["G1", "G3"]. No other text.',
    )
    portfolio_notes: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description='Formatted as "<portfolio_ref>: note" or "<portfolio_ref> -> <skill_ref>: note".',
    )
    assessment_notes: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description='Formatted exactly as "<ref>: note", ref being any gap or owned skill ref.',
    )
    next_actions: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description="Plain, concise next-step suggestions. No ref prefix needed.",
    )


# ============================================================
# 3. Grounded response -- canonical_* fields are server-attached
# ============================================================


class AssessmentActionType(str, Enum):
    """Server-DETERMINED, never LLM-chosen (app.ai.guardrails.skill_gap):
    purely a function of (is the skill tracked in student_skills, is a
    real assessment available for it, is it already verified). The LLM
    can never invent an assessment or a verification state here."""

    ADD_SKILL_THEN_ASSESS = "ADD_SKILL_THEN_ASSESS"
    TAKE_ASSESSMENT = "TAKE_ASSESSMENT"
    ALREADY_VERIFIED = "ALREADY_VERIFIED"
    NO_ASSESSMENT_AVAILABLE = "NO_ASSESSMENT_AVAILABLE"


class PriorityGapAnalysis(BaseModel):
    skill_id: str
    skill_name: str
    canonical_status: str | None
    canonical_priority: str | None
    canonical_importance: str | None = None
    reason: str
    suggested_action: str


class TransferableSkillInsight(BaseModel):
    from_skill_id: str
    from_skill_name: str
    supports_skill_id: str
    supports_skill_name: str
    explanation: str


class SequenceStep(BaseModel):
    order: int
    skill_id: str
    skill_name: str
    canonical_priority: str | None
    rationale: str


class AssessmentAction(BaseModel):
    skill_id: str
    skill_name: str
    action: AssessmentActionType
    assessment_available: bool
    note: str


class PortfolioInsight(BaseModel):
    source_title: str
    related_skill_id: str | None = None
    related_skill_name: str | None = None
    note: str


class CanonicalSkillGapSummary(BaseModel):
    """Attached server-side from app.services.skill_gap_service's own
    output -- never echoed from, or overridable by, the LLM. Job-role
    fields are None in personal mode and vice versa."""

    mode: AnalysisMode
    target_role: str | None = None
    readiness_score: int | None = None
    matched_count: int | None = None
    needs_improvement_count: int | None = None
    missing_count: int | None = None
    unverified_count: int | None = None
    total_active_skills: int | None = None
    verified_skills: int | None = None


class SkillGapAnalysis(BaseModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    priority_gaps: list[PriorityGapAnalysis] = Field(default_factory=list)
    transferable_skills: list[TransferableSkillInsight] = Field(default_factory=list)
    recommended_sequence: list[SequenceStep] = Field(default_factory=list)
    assessment_actions: list[AssessmentAction] = Field(default_factory=list)
    portfolio_insights: list[PortfolioInsight] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "AI-generated interpretation of your canonical skill gap data. "
        "Portfolio and certification evidence is contextual only -- it is "
        "not verified proficiency."
    )


class SkillGapAgentResponse(BaseModel):
    """POST /api/v1/ai/skill-gap's response. `canonical` never depends on
    the LLM reproducing anything correctly -- it is built directly from
    app.services.skill_gap_service's own output, independent of
    `analysis`."""

    canonical: CanonicalSkillGapSummary
    analysis: SkillGapAnalysis
    meta: AIResponseMeta


class SkillGapAIUnavailableResponse(BaseModel):
    """Returned (still HTTP 200) when canonical data exists but the AI
    layer itself failed -- Groq unavailable, no API key, rate limit,
    timeout, or a malformed/ungroundable response. Canonical data is
    NEVER withheld because of an AI failure; GET /api/v1/skill-gap is
    also completely unaffected (see the Phase 3 report)."""

    canonical: CanonicalSkillGapSummary
    ai_available: Literal[False] = False
    reason: str
