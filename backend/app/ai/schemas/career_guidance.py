"""Phase 6: Career Orchestrator + Career Advisor schemas.

Three groups, same separation as every earlier phase:

1. CareerAdvisorAgentInput -- minimal, ref-annotated input built ONLY
   from the three specialists' ALREADY-GROUNDED outputs (never raw
   student data, never a second StudentCareerContext fetch). Refs here
   are a FRESH namespace the Career Advisor owns (G#/C#/OP#/A#), built
   from the specialists' final response objects (skill_id /
   candidate_id / opportunity.id) -- not the same ref tokens those
   agents used internally with Groq, which do not survive into their
   final response objects.

2. CareerAdvisorLLMOutput -- exactly what Groq is asked to produce.
   Flat only: a headline string, three ref-list fields, and one
   "<ref>: ACTION_CODE" note list. No canonical field (score, band,
   status, priority, verification, price, url, ...) exists anywhere in
   this class.

3. The rich CareerGuidanceResponse -- what
   POST /api/v1/ai/career-guidance returns. Every canonical_*/
   skill_id/course/opportunity/action field is attached server-side by
   app.ai.guardrails.career_advisor + app.ai.orchestrator, reusing the
   specialists' own already-grounded objects verbatim -- never
   reconstructed from LLM text.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas.base import AIResponseMeta
from app.ai.schemas.course_recommendation import CourseCandidate
from app.ai.schemas.skill_gap import AssessmentActionType
from app.ai.schemas.youtube_learning import YouTubeVideoCandidate
from app.schemas.skill_gap import AnalysisMode
from app.schemas.student_opportunity import OpportunityMatchResponse, StudentOpportunityDetail

_MAX_LIST_ITEMS = 10
_MAX_TEXT = 400

# ============================================================
# 1. Advisor input -- minimal, ref-annotated, built from specialist output
# ============================================================


class AdvisorInputSkill(BaseModel):
    ref: str
    skill_name: str
    canonical_status: str | None
    canonical_priority: str | None
    canonical_importance: str | None


class AdvisorInputCourse(BaseModel):
    ref: str
    title: str
    for_skill_ref: str | None


class AdvisorInputOpportunity(BaseModel):
    ref: str
    title: str
    opportunity_type: str
    match_band: str
    match_score: int


class AdvisorInputAssessmentAction(BaseModel):
    ref: str
    skill_name: str
    action: str


class CareerAdvisorAgentInput(BaseModel):
    """Never contains student_id, email, phone, or portfolio text --
    only refs and the small canonical fields needed to reason about
    them. Built by app.ai.orchestrator from the three specialists'
    OWN grounded outputs, never from a fresh context/DB read."""

    target_role: str | None
    readiness_score: int | None
    mode: AnalysisMode
    skills: list[AdvisorInputSkill] = Field(default_factory=list)
    courses: list[AdvisorInputCourse] = Field(default_factory=list)
    opportunities: list[AdvisorInputOpportunity] = Field(default_factory=list)
    assessment_actions: list[AdvisorInputAssessmentAction] = Field(default_factory=list)


# ============================================================
# 2. Raw LLM output -- flat, ref + action-code only
# ============================================================


class CareerAdvisorLLMOutput(BaseModel):
    """What Groq must produce. No skill_id, no score, no band, no
    status, no priority, no verification, no URL -- only refs, a short
    headline, and "<ref>: ACTION_CODE" notes validated server-side."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=_MAX_TEXT)
    focus_skill_refs: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description="Bare G# refs, most important first.",
    )
    course_refs: list[str] = Field(
        default_factory=list, max_length=_MAX_LIST_ITEMS, description="Bare C# refs to highlight."
    )
    opportunity_refs: list[str] = Field(
        default_factory=list, max_length=_MAX_LIST_ITEMS, description="Bare OP# refs to highlight."
    )
    action_notes: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description=(
            'One string per suggested action, formatted exactly as "<ref>: ACTION_CODE" -- ref is '
            "any supplied G#/C#/OP#/A# token; ACTION_CODE is one of LEARN_SKILL, TAKE_ASSESSMENT, "
            "START_COURSE, APPLY_OPPORTUNITY, BUILD_PROJECT, REASSESS_SKILL."
        ),
    )
    learning_sequence: list[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description="Bare G# refs in suggested learning order.",
    )


# ============================================================
# 3. Grounded, rich response -- canonical fields server-attached
# ============================================================


class ActionCode(str, Enum):
    LEARN_SKILL = "LEARN_SKILL"
    TAKE_ASSESSMENT = "TAKE_ASSESSMENT"
    START_COURSE = "START_COURSE"
    APPLY_OPPORTUNITY = "APPLY_OPPORTUNITY"
    BUILD_PROJECT = "BUILD_PROJECT"
    REASSESS_SKILL = "REASSESS_SKILL"


class CareerSummary(BaseModel):
    """Every field here comes from skill_gap_service's own canonical
    output (via the Skill Gap Agent's own `canonical` section) --
    `headline` is the only AI-authored field, and is None whenever the
    Career Advisor synthesis itself did not run."""

    mode: AnalysisMode
    target_role: str | None = None
    readiness_score: int | None = None
    headline: str | None = None


class PrioritySkill(BaseModel):
    skill_id: str
    skill_name: str
    canonical_status: str | None
    canonical_priority: str | None
    canonical_importance: str | None
    reason: str
    suggested_action: str
    highlighted_by_advisor: bool = False


class LearningRecommendationItem(BaseModel):
    course: CourseCandidate
    for_skill_id: str | None
    for_skill_name: str | None
    reason: str
    highlighted_by_advisor: bool = False


class YouTubeRecommendationItem(BaseModel):
    """Additive sibling of LearningRecommendationItem -- see
    app.ai.schemas.youtube_learning.YouTubeVideoCandidate's own
    docstring on why a video stays its own type rather than a
    CourseCandidate. Never touched by the Career Advisor: video is not
    part of its G#/C#/OP#/A# ref namespace, so `highlighted_by_advisor`
    does not apply here -- see app.ai.orchestrator."""

    video: YouTubeVideoCandidate
    for_skill_id: str | None
    for_skill_name: str | None
    reason: str


class OpportunityRecommendationItem(BaseModel):
    opportunity: StudentOpportunityDetail
    match: OpportunityMatchResponse
    reason: str
    highlighted_by_advisor: bool = False


class AssessmentRecommendationItem(BaseModel):
    skill_id: str
    skill_name: str
    action: AssessmentActionType
    assessment_available: bool
    note: str
    highlighted_by_advisor: bool = False


class NextAction(BaseModel):
    """One concrete, ranked next step. `entity_id`/`entity_name` are
    always copied from a specialist's own grounded object -- never from
    LLM text. `order` is server-assigned (either the Career Advisor's
    grounded sequence, or a deterministic priority-based fallback)."""

    order: int
    type: ActionCode
    entity_type: Literal["SKILL", "COURSE", "OPPORTUNITY", "ASSESSMENT"]
    entity_id: str
    entity_name: str


class AgentStatus(BaseModel):
    available: bool
    fallback_used: bool
    detail: str | None = None


class CareerGuidanceAgentsUsed(BaseModel):
    skill_gap_agent: AgentStatus
    course_agent: AgentStatus
    opportunity_agent: AgentStatus
    career_advisor: AgentStatus


class CareerGuidanceMeta(AIResponseMeta):
    ai_available: bool = False
    agents_used: CareerGuidanceAgentsUsed


class CareerGuidanceResponse(BaseModel):
    career_summary: CareerSummary
    priority_skills: list[PrioritySkill] = Field(default_factory=list)
    learning_recommendations: list[LearningRecommendationItem] = Field(default_factory=list)
    youtube_videos: list[YouTubeRecommendationItem] = Field(default_factory=list)
    opportunity_recommendations: list[OpportunityRecommendationItem] = Field(default_factory=list)
    assessment_recommendations: list[AssessmentRecommendationItem] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    meta: CareerGuidanceMeta
    disclaimer: str = (
        "This career plan combines your canonical skill, course, and opportunity data. "
        "AI synthesis is advisory only -- it never changes your readiness, verification, "
        "match scores, or any other canonical fact."
    )
