"""Career AI Chat orchestration (Phase 7).

User message -> deterministic (or bounded-classifier) intent -> exactly
ONE primary canonical/deterministic data source -> grounded cards -> one
bounded Groq call for a conversational wrapper (or the deterministic
message alone, if there's nothing grounded to discuss or Groq fails) ->
CareerChatResponse.

Architecture rule (see the task brief this implements): this is never
"message -> Groq -> answer". Only CAREER_PLAN routes through the full
Career Orchestrator (app.ai.orchestrator.build_career_guidance), by
design, matching that intent's own scope. Every OTHER intent reads
canonical/deterministic building blocks directly -- course_discovery,
youtube_learning, opportunity_candidates, skill_gap_tools -- and
deliberately skips the corresponding specialist AGENT's own internal
Groq ranking call (course_recommendation_agent.recommend_courses(),
youtube_recommendation_agent.recommend_youtube_videos(),
opportunity_recommendation_agent.recommend_opportunities()) so that one
chat turn never triggers more than ONE additional Groq call beyond
whatever CAREER_PLAN's own full pipeline needs -- the chat's own LLM
call already adds a conversational explanation on top of the same
grounded facts those specialist rankings would have produced.

Groq NEVER: queries Supabase, decides a score/match/verification/
readiness value, or invents a job/course/video. Every fact in every
card is attached here from the SAME canonical/deterministic sources
every other AI route already trusts, via app.ai.guardrails.career_chat.ground().
"""

import logging
import re

from supabase import Client

from app.ai.agents import course_recommendation_agent
from app.ai.agents.skill_gap_agent import _extract_gap_entries, build_canonical_summary_only
from app.ai.client import groq_client
from app.ai.config import ai_settings
from app.ai.exceptions import AIError
from app.ai.guardrails.career_chat import classify_intent_by_keyword, ground
from app.ai.guardrails.opportunity_recommendation import (
    deterministic_fallback as opportunity_deterministic_fallback,
)
from app.ai.guardrails.skill_gap import CanonicalSkillRef, _determine_assessment_action
from app.ai.orchestrator import build_career_guidance
from app.ai.prompts.career_chat import (
    CHAT_SYSTEM_PROMPT,
    CLASSIFIER_SYSTEM_PROMPT,
    build_classifier_prompt,
    build_user_prompt,
)
from app.ai.schemas.career_chat import (
    ASSESSMENT,
    CAREER_PLAN,
    GENERAL_CAREER,
    INTERNSHIP,
    JOB,
    LEARNING,
    OPPORTUNITY,
    READINESS,
    SKILL_GAP,
    YOUTUBE_LEARNING,
    AssessmentCard,
    CareerActionCard,
    CareerChatMeta,
    CareerChatResponse,
    ChatAgentInput,
    ChatCard,
    ChatHistoryTurn,
    ChatInputCard,
    ChatLLMOutput,
    ChatMessage,
    CourseCard,
    IntentClassification,
    OpportunityCard,
    SkillCard,
    SuggestedAction,
    YouTubeVideoCard,
)
from app.ai.tools import (
    course_discovery,
    opportunity_candidates,
    skill_gap_tools,
    skill_tools,
    youtube_learning,
)

logger = logging.getLogger("app.ai")

_ALL_INTENTS = {
    SKILL_GAP, LEARNING, YOUTUBE_LEARNING, JOB, INTERNSHIP, OPPORTUNITY,
    ASSESSMENT, CAREER_PLAN, READINESS, GENERAL_CAREER,
}
_PRIORITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}
_IMPORTANCE_RANK = {"CORE": 0, "IMPORTANT": 1, "OPTIONAL": 2, None: 3}
_MAX_CARDS = 6
_GENERIC_CAPITALIZED_TOKENS = {
    "I", "What", "Show", "Recommend", "Which", "Give", "My", "Am", "Is",
    "YouTube", "Video", "Videos", "Course", "Courses", "Skill", "Career",
}


class _IntentResult:
    """One intent handler's grounded output -- never touched by Groq;
    `deterministic_message` is what the chatbot says when Groq is
    unavailable or there is nothing grounded to discuss (see this
    module's own docstring / the task's "MUST remain useful without
    Groq" requirement)."""

    __slots__ = ("cards_by_ref", "deterministic_message", "input_cards", "suggested_actions")

    def __init__(
        self,
        cards_by_ref: dict[str, ChatCard],
        input_cards: list[ChatInputCard],
        deterministic_message: str,
        suggested_actions: list[SuggestedAction],
    ) -> None:
        self.cards_by_ref = cards_by_ref
        self.input_cards = input_cards
        self.deterministic_message = deterministic_message
        self.suggested_actions = suggested_actions


def _mentioned_skill(message: str, skills):
    lowered = message.lower()
    for skill in skills:
        if skill.skill_name and skill.skill_name.lower() in lowered:
            return skill
    return None


def _off_gap_notice(message: str, skills) -> str | None:
    """A crude, deliberately conservative heuristic (a capitalized
    token in the message that isn't already one of the canonical
    skills) used ONLY to decide whether to show the task's own
    suggested "not currently one of your priority gaps" copy -- never
    used to decide what data to fetch, which always stays
    canonical-only (see this module's own docstring)."""
    if _mentioned_skill(message, skills) is not None:
        return None
    tokens = [t for t in re.findall(r"\b[A-Z][A-Za-z0-9+.#]{1,30}\b", message) if t not in _GENERIC_CAPITALIZED_TOKENS]
    return tokens[0] if tokens else None


def _skill_input_detail(skill) -> str | None:
    parts = [p for p in (skill.status, skill.priority, skill.importance) if p]
    return ", ".join(parts) if parts else None


def _handle_skill_gap(client: Client, student_id: str, _message: str) -> _IntentResult:
    section = skill_gap_tools.get_current_skill_gap(client, student_id)
    canonical = course_recommendation_agent.select_skills(section)
    skills = canonical.skills_considered
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []
    for skill in skills:
        cards[skill.ref] = SkillCard(
            skill_id=skill.skill_id, skill_name=skill.skill_name,
            current_level=skill.current_level, target_level=skill.target_level,
            status=skill.status, priority=skill.priority, importance=skill.importance,
            reason=skill.reason,
        )
        input_cards.append(
            ChatInputCard(ref=skill.ref, kind="SKILL", title=skill.skill_name, detail=_skill_input_detail(skill))
        )
    if skills:
        top = skills[0]
        msg = f"Your highest-priority skill gap is {top.skill_name}."
        if top.current_level and top.target_level:
            msg += f" You're currently {top.current_level}, and the target is {top.target_level}."
    else:
        msg = "You don't have any canonical skill gaps right now. Add skills or set a target role to see one."
    return _IntentResult(cards, input_cards, msg, [SuggestedAction(label="View Skill Gap", url="/student/skill-gap")])


def _handle_learning(client: Client, student_id: str, message: str) -> _IntentResult:
    section = skill_gap_tools.get_current_skill_gap(client, student_id)
    canonical = course_recommendation_agent.select_skills(section)
    if not canonical.skills_considered:
        return _IntentResult(
            {}, [], "You don't have any canonical skill gaps to recommend learning for yet.",
            [SuggestedAction(label="View Skill Gap", url="/student/skill-gap")],
        )
    off_gap = _off_gap_notice(message, canonical.skills_considered)
    found, _internal_available, _external_status = course_discovery.discover_candidates(
        client, student_id, canonical.skills_considered
    )
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []
    for n, candidate in enumerate(found[:5], 1):
        ref = f"C{n}"
        skill_name = candidate.skill_names[0] if candidate.skill_names else None
        cards[ref] = CourseCard(
            candidate_id=candidate.candidate_id, title=candidate.title, provider=candidate.provider,
            url=candidate.url, level=candidate.level, duration_text=candidate.duration_text,
            skill_name=skill_name,
        )
        input_cards.append(ChatInputCard(ref=ref, kind="COURSE", title=candidate.title, detail=candidate.provider))
    top_skill_name = canonical.skills_considered[0].skill_name
    if off_gap:
        msg = (
            f"{off_gap} is not currently one of your priority gaps, but I can still show your "
            f"current priority learning recommendations" + (f" for {top_skill_name}." if cards else ".")
        )
    elif cards:
        msg = f"Here are current learning recommendations for {top_skill_name}."
    else:
        msg = "No source-backed learning resources are available for your current gaps yet."
    return _IntentResult(cards, input_cards, msg, [SuggestedAction(label="View Career Page", url="/student/career")])


def _handle_youtube_learning(client: Client, student_id: str, message: str) -> _IntentResult:
    section = skill_gap_tools.get_current_skill_gap(client, student_id)
    canonical = course_recommendation_agent.select_skills(section)
    if not canonical.skills_considered:
        return _IntentResult(
            {}, [], "You don't have any canonical skill gaps to find YouTube videos for yet.",
            [SuggestedAction(label="View Skill Gap", url="/student/skill-gap")],
        )
    off_gap = _off_gap_notice(message, canonical.skills_considered)
    found, status = youtube_learning.discover_for_skills(canonical.skills_considered)
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []
    for n, video in enumerate(found[:5], 1):
        ref = f"Y{n}"
        cards[ref] = YouTubeVideoCard(
            video_id=video.video_id, title=video.title, channel_title=video.channel_title,
            thumbnail_url=video.thumbnail_url, watch_url=video.watch_url, duration_text=video.duration_text,
            view_count=video.view_count, published_at=video.published_at, skill_name=video.skill_name,
        )
        input_cards.append(
            ChatInputCard(ref=ref, kind="YOUTUBE_VIDEO", title=video.title, detail=video.channel_title)
        )
    top_skill_name = canonical.skills_considered[0].skill_name
    if off_gap:
        msg = (
            f"{off_gap} is not currently one of your priority gaps, but I can still show your "
            f"current priority learning recommendations" + (f" for {top_skill_name}." if cards else ".")
        )
    elif cards:
        msg = f"Here are current YouTube learning recommendations for {top_skill_name}."
    elif status == "CONFIGURATION_REQUIRED":
        msg = f"Video recommendations aren't available right now. Your top priority skill is {top_skill_name}."
    else:
        msg = f"No YouTube videos are currently available for {top_skill_name}."
    return _IntentResult(cards, input_cards, msg, [SuggestedAction(label="View Skill Gap", url="/student/skill-gap")])


def _handle_opportunity(client: Client, student_id: str, _message: str, intent: str) -> _IntentResult:
    candidates = opportunity_candidates.get_candidates(client, student_id)
    if intent == JOB:
        candidates = [c for c in candidates if c.opportunity.source_type == "JOB"]
    elif intent == INTERNSHIP:
        candidates = [c for c in candidates if c.opportunity.source_type == "INTERNSHIP"]
    recommendations, _plan = opportunity_deterministic_fallback(candidates)
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []
    for n, rec in enumerate(recommendations[:5], 1):
        ref = f"OP{n}"
        opp = rec.opportunity
        segment = "internships" if opp.source_type == "INTERNSHIP" else "jobs"
        company = opp.industry.company_name if opp.industry else None
        cards[ref] = OpportunityCard(
            opportunity_id=opp.id, opportunity_type=opp.source_type, title=opp.title, company=company,
            match_score=rec.match.score, match_band=rec.match.recommendation,
            matched_count=rec.match.matched_count, gap_count=rec.match.missing_count,
            detail_url=f"/student/{segment}/{opp.id}",
        )
        input_cards.append(
            ChatInputCard(
                ref=ref, kind="OPPORTUNITY", title=opp.title,
                detail=f"{rec.match.score}% {rec.match.recommendation}",
            )
        )
    label = {"JOB": "job", "INTERNSHIP": "internship"}.get(intent, "opportunity")
    msg = (
        f"Here are your strongest current {label} matches." if cards
        else f"No current {label} recommendations are available yet."
    )
    return _IntentResult(
        cards, input_cards, msg, [SuggestedAction(label="View Recommendations", url="/student/recommendations")]
    )


def _handle_assessment(client: Client, student_id: str, _message: str) -> _IntentResult:
    section = skill_gap_tools.get_current_skill_gap(client, student_id)
    owned_skills = skill_tools.get_student_skills(client, student_id)
    # Reuses the Skill Gap Agent's own canonical-entry extraction and
    # the same deterministic action rule its guardrail already uses --
    # never a second, competing implementation of "which assessment
    # action applies" (see app.ai.guardrails.skill_gap's own docstring
    # on why that decision is structural, not prompted).
    entries = _extract_gap_entries(section, owned_skills)
    entries.sort(key=lambda e: (_PRIORITY_RANK.get(e["priority"]), _IMPORTANCE_RANK.get(e["importance"])))
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []
    action_notes = {
        "TAKE_ASSESSMENT": "Take the {name} assessment to verify this skill.",
        "ADD_SKILL_THEN_ASSESS": "Add {name} to your profile, then take its assessment.",
        "ALREADY_VERIFIED": "{name} is already verified.",
        "NO_ASSESSMENT_AVAILABLE": "No assessment is available yet for {name}.",
    }
    for n, entry in enumerate(entries[:5], 1):
        ref = f"A{n}"
        ref_data = CanonicalSkillRef(
            skill_id=entry["skill_id"], skill_name=entry["skill_name"],
            assessment_available=entry["assessment_available"], is_tracked=entry["is_tracked"],
            is_verified=bool(entry["is_verified"]),
        )
        action = _determine_assessment_action(ref_data)
        note = action_notes[action.value].format(name=entry["skill_name"])
        cards[ref] = AssessmentCard(
            skill_id=entry["skill_id"], skill_name=entry["skill_name"], action=action.value, note=note
        )
        input_cards.append(ChatInputCard(ref=ref, kind="ASSESSMENT", title=entry["skill_name"], detail=action.value))
    msg = cards["A1"].note if cards else "You don't have any skill gaps that need an assessment action right now."
    return _IntentResult(cards, input_cards, msg, [SuggestedAction(label="View Skill Gap", url="/student/skill-gap")])


def _handle_career_plan(client: Client, student_id: str, _message: str) -> _IntentResult:
    guidance = build_career_guidance(client, student_id)
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []

    for n, skill in enumerate(guidance.priority_skills[:3], 1):
        ref = f"G{n}"
        cards[ref] = SkillCard(
            skill_id=skill.skill_id, skill_name=skill.skill_name, status=skill.canonical_status,
            priority=skill.canonical_priority, importance=skill.canonical_importance, reason=skill.reason,
        )
        input_cards.append(ChatInputCard(ref=ref, kind="SKILL", title=skill.skill_name, detail=skill.reason))

    for n, item in enumerate(guidance.learning_recommendations[:2], 1):
        ref = f"C{n}"
        cards[ref] = CourseCard(
            candidate_id=item.course.candidate_id, title=item.course.title, provider=item.course.provider,
            url=item.course.url, level=item.course.level, duration_text=item.course.duration_text,
            skill_name=item.for_skill_name, reason=item.reason,
        )
        input_cards.append(ChatInputCard(ref=ref, kind="COURSE", title=item.course.title, detail=item.reason))

    for n, item in enumerate(guidance.youtube_videos[:2], 1):
        ref = f"Y{n}"
        v = item.video
        cards[ref] = YouTubeVideoCard(
            video_id=v.video_id, title=v.title, channel_title=v.channel_title, thumbnail_url=v.thumbnail_url,
            watch_url=v.watch_url, duration_text=v.duration_text, view_count=v.view_count,
            published_at=v.published_at, skill_name=item.for_skill_name, reason=item.reason,
        )
        input_cards.append(ChatInputCard(ref=ref, kind="YOUTUBE_VIDEO", title=v.title, detail=item.reason))

    for n, item in enumerate(guidance.opportunity_recommendations[:2], 1):
        ref = f"OP{n}"
        opp = item.opportunity
        segment = "internships" if opp.source_type == "INTERNSHIP" else "jobs"
        company = opp.industry.company_name if opp.industry else None
        cards[ref] = OpportunityCard(
            opportunity_id=opp.id, opportunity_type=opp.source_type, title=opp.title, company=company,
            match_score=item.match.score, match_band=item.match.recommendation,
            matched_count=item.match.matched_count, gap_count=item.match.missing_count,
            detail_url=f"/student/{segment}/{opp.id}", reason=item.reason,
        )
        input_cards.append(ChatInputCard(ref=ref, kind="OPPORTUNITY", title=opp.title, detail=item.reason))

    for n, item in enumerate(guidance.assessment_recommendations[:2], 1):
        ref = f"A{n}"
        cards[ref] = AssessmentCard(
            skill_id=item.skill_id, skill_name=item.skill_name, action=item.action.value, note=item.note
        )
        input_cards.append(ChatInputCard(ref=ref, kind="ASSESSMENT", title=item.skill_name, detail=item.note))

    if guidance.career_summary.headline:
        msg = guidance.career_summary.headline
    elif guidance.career_summary.readiness_score is not None:
        msg = (
            f"You're at {guidance.career_summary.readiness_score}% readiness"
            f"{f' for {guidance.career_summary.target_role}' if guidance.career_summary.target_role else ''}."
        )
    else:
        msg = "Here's your current career plan based on your canonical data."
    return _IntentResult(
        cards, input_cards, msg, [SuggestedAction(label="Open full Career Plan", url="/student/career")]
    )


def _handle_readiness(client: Client, student_id: str, _message: str) -> _IntentResult:
    summary = build_canonical_summary_only(client, student_id)
    cards: dict[str, ChatCard] = {}
    input_cards: list[ChatInputCard] = []
    if summary.readiness_score is not None:
        ref = "G1"
        cards[ref] = CareerActionCard(
            label=f"Readiness: {summary.readiness_score}%", url="/student/career"
        )
        input_cards.append(
            ChatInputCard(ref=ref, kind="CAREER_ACTION", title=f"Readiness {summary.readiness_score}%")
        )
        msg = (
            f"Your current readiness for {summary.target_role or 'your target role'} is "
            f"{summary.readiness_score}%."
        )
    else:
        msg = (
            "You haven't set a target role yet, so there's no readiness score to show. "
            "Set one on your Skill Gap page to get one."
        )
    return _IntentResult(cards, input_cards, msg, [SuggestedAction(label="View Career Plan", url="/student/career")])


_HANDLERS = {
    SKILL_GAP: _handle_skill_gap,
    LEARNING: _handle_learning,
    YOUTUBE_LEARNING: _handle_youtube_learning,
    JOB: lambda client, student_id, message: _handle_opportunity(client, student_id, message, JOB),
    INTERNSHIP: lambda client, student_id, message: _handle_opportunity(client, student_id, message, INTERNSHIP),
    OPPORTUNITY: lambda client, student_id, message: _handle_opportunity(client, student_id, message, OPPORTUNITY),
    ASSESSMENT: _handle_assessment,
    CAREER_PLAN: _handle_career_plan,
    READINESS: _handle_readiness,
    # A genuinely ambiguous message gets the same safe, canonical-only
    # grounding as READINESS -- never an invented answer (see this
    # module's own docstring / the task's own explicit instruction).
    GENERAL_CAREER: _handle_readiness,
}


def _classify_intent(message: str) -> tuple[str, str]:
    """Returns (intent, source). Deterministic keyword match first --
    no LLM call at all for the cases the task explicitly lists. Falls
    back to a bounded, closed-vocabulary Groq classifier (a single
    Literal field -- see IntentClassification) only for genuinely
    ambiguous text; falls back to GENERAL_CAREER if that also fails.
    Never raises."""
    keyword_intent = classify_intent_by_keyword(message)
    if keyword_intent is not None:
        return keyword_intent, "KEYWORD"
    try:
        result = groq_client.complete_structured(
            system=CLASSIFIER_SYSTEM_PROMPT,
            user=build_classifier_prompt(message),
            response_model=IntentClassification,
        )
        if result.intent in _ALL_INTENTS:
            return result.intent, "AI_CLASSIFIER"
    except AIError:
        pass
    return GENERAL_CAREER, "DEFAULT"


def career_chat(
    client: Client, student_id: str, message: str, history: list[ChatMessage]
) -> CareerChatResponse:
    intent, intent_source = _classify_intent(message)
    handler = _HANDLERS[intent]
    try:
        result = handler(client, student_id, message)
    except Exception:
        logger.exception("Career Chat specialist failed for intent=%s student=%s", intent, student_id)
        result = _IntentResult({}, [], "I couldn't load that just now. Please try again in a moment.", [])

    ai_available = False
    final_message = result.deterministic_message
    cards = list(result.cards_by_ref.values())[:_MAX_CARDS]

    if result.input_cards:
        try:
            agent_input = ChatAgentInput(
                user_message=message[:1500],
                intent=intent,
                grounded_cards=result.input_cards[:_MAX_CARDS],
                recent_history=[
                    ChatHistoryTurn(role=turn.role, content=turn.content[:1500]) for turn in history[-6:]
                ],
            )
            output = groq_client.complete_structured(
                system=CHAT_SYSTEM_PROMPT, user=build_user_prompt(agent_input), response_model=ChatLLMOutput,
            )
            grounded_message, grounded_cards = ground(output, result.cards_by_ref)
            if grounded_message:
                final_message = grounded_message
                if grounded_cards:
                    cards = grounded_cards[:_MAX_CARDS]
                ai_available = True
        except AIError:
            pass

    return CareerChatResponse(
        message=final_message,
        intent=intent,
        cards=cards,
        suggested_actions=result.suggested_actions,
        meta=CareerChatMeta(
            model=ai_settings.groq_model, ai_available=ai_available, intent=intent, intent_source=intent_source
        ),
    )
