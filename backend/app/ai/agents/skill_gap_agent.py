"""The Skill Gap Analysis Agent (Phase 3) -- the first AI specialist
agent, and an interpretation/reasoning layer only.

`analyze_student_skill_gap` is a thin orchestrator:
  1. gathers canonical skill-gap data + relevant context EXCLUSIVELY
     through Phase 2 tools (app.ai.tools.*) -- never Supabase directly,
     and never app.services.skill_gap_service directly either (it goes
     through app.ai.tools.skill_gap_tools, exactly like every other
     Phase 2 consumer);
  2. builds a minimal grounded SkillGapAgentInput (never the whole
     StudentCareerContext -- see app.ai.schemas.skill_gap);
  3. calls the Phase 1 Groq client for a structured response
     (SkillGapLLMOutput, which structurally cannot contain a canonical
     fact -- see that schema's own docstring);
  4. grounds that response against the SAME canonical data through
     app.ai.guardrails.skill_gap.ground(); and
  5. returns a response whose `canonical` section is built here,
     server-side, directly from app.services.skill_gap_service's own
     output (via skill_gap_tools) -- never from the LLM.

No database queries are made in this file. No formula from
skill_gap_service is reimplemented or altered.
"""

from supabase import Client

from app.ai.client import groq_client
from app.ai.config import ai_settings
from app.ai.guardrails.skill_gap import CanonicalSkillRef, ground
from app.ai.prompts.skill_gap import SKILL_GAP_SYSTEM_PROMPT_V1, build_user_prompt
from app.ai.schemas.base import AIResponseMeta
from app.ai.schemas.skill_gap import (
    CanonicalSkillGapSummary,
    InputAssessmentEvidence,
    InputGapSkill,
    InputOwnedSkill,
    InputPortfolioItem,
    SkillGapAgentInput,
    SkillGapAgentResponse,
    SkillGapAnalysis,
    SkillGapLLMOutput,
)
from app.ai.schemas.student_context import PortfolioSection, SkillGapSection, StudentSkillSummary
from app.ai.tools import assessment_tools, portfolio_tools, skill_gap_tools, skill_tools
from app.schemas.assessment import AttemptHistoryItemResponse
from app.schemas.skill_gap import AnalysisMode

# A degenerate case: brand-new student, no target role, no owned
# skills, and therefore no gap skills either. There is nothing
# grounded to reason about -- skip the Groq call entirely rather than
# ask the model to produce something from an empty context (see the
# module docstring's step 2/3; this is a deliberate efficiency + safety
# choice, not a Groq-failure fallback -- see app.ai.agents' own report
# note on this).
_NO_DATA_SUMMARY = (
    "Add some skills to your profile, or set a target job role on the "
    "Skill Gap page, to get an AI-powered analysis. There isn't enough "
    "data yet to generate one."
)


def _extract_gap_entries(section: SkillGapSection, owned_skills: list[StudentSkillSummary]) -> list[dict]:
    """One dict per gap-relevant skill, uniform across both modes:
    skill_id, skill_name, status, priority, importance,
    assessment_available, is_tracked, is_verified, current_level,
    target_level. Job-role mode includes EVERY requirement (including
    MATCHED, so strengths can be grounded); personal mode's
    recommendations are never MATCHED by construction, and
    progression entries retain null status/priority where the personal
    engine does not supply those fields. Verification is read from owned skills."""
    entries: list[dict] = []
    owned_by_id = {skill.skill_id: skill for skill in owned_skills}

    if section.mode == AnalysisMode.JOB_ROLE and section.job_role_analysis is not None:
        for item in section.job_role_analysis.skills:
            entries.append(
                {
                    "skill_id": str(item.skill_id),
                    "skill_name": item.skill_name,
                    "status": item.status.value,
                    "priority": item.priority.value,
                    "importance": item.importance.value,
                    "assessment_available": item.assessment_available,
                    "is_tracked": item.current_level is not None,
                    "is_verified": item.verification_status.value == "VERIFIED",
                    "current_level": item.current_level.value if item.current_level else None,
                    "target_level": item.required_level.value,
                }
            )
    elif section.mode == AnalysisMode.PERSONAL and section.personal_analysis is not None:
        for rec in section.personal_analysis.recommendations:
            entries.append(
                {
                    "skill_id": str(rec.skill_id),
                    "skill_name": rec.skill_name,
                    "status": None,  # Personal recommendations have no canonical gap status.
                    "priority": rec.priority.value,
                    "importance": None,
                    "assessment_available": rec.assessment_available,
                    "is_tracked": str(rec.skill_id) in owned_by_id,
                    "is_verified": rec.is_verified,
                    "current_level": rec.current_level.value if rec.current_level else None,
                    "target_level": rec.target_level.value if rec.target_level else None,
                }
            )
        for prog in section.personal_analysis.progressable_skills:
            entries.append(
                {
                    "skill_id": str(prog.skill_id),
                    "skill_name": prog.skill_name,
                    "status": None,
                    "priority": None,  # Progression has no canonical priority.
                    "importance": None,
                    "assessment_available": prog.assessment_available,
                    "is_tracked": True,
                    "is_verified": (
                        owned_by_id[str(prog.skill_id)].is_verified
                        if str(prog.skill_id) in owned_by_id else None
                    ),
                    "current_level": prog.current_level.value,
                    "target_level": prog.next_level.value,
                }
            )

    for number, entry in enumerate(entries, 1):
        entry["ref"] = f"G{number}"
    return entries


def _build_gap_index(entries: list[dict]) -> dict[str, CanonicalSkillRef]:
    return {
        entry["ref"]: CanonicalSkillRef(
            skill_id=entry["skill_id"],
            skill_name=entry["skill_name"],
            status=entry["status"],
            priority=entry["priority"],
            importance=entry["importance"],
            assessment_available=entry["assessment_available"],
            is_tracked=entry["is_tracked"],
            is_verified=entry["is_verified"],
        )
        for entry in entries
    }


def _build_owned_index(
    owned_skills: list[StudentSkillSummary], availability: dict[tuple[str, str], str]
) -> dict[str, CanonicalSkillRef]:
    return {
        f"O{number}": CanonicalSkillRef(
            skill_id=skill.skill_id,
            skill_name=skill.skill_name,
            is_tracked=True,
            is_verified=skill.is_verified,
            assessment_available=(skill.skill_id, skill.proficiency_level) in availability,
        )
        for number, skill in enumerate(owned_skills, 1)
    }


def _build_portfolio_input(portfolio: PortfolioSection) -> list[InputPortfolioItem]:
    items = [
        InputPortfolioItem(
            ref=f"P{number}",
            title=project.title,
            source_type="PROJECT",
            related_skill_names=[skill.skill_name for skill in project.skills],
        )
        for number, project in enumerate(portfolio.projects, 1)
    ]
    items += [
        InputPortfolioItem(
            ref=f"P{number}",
            title=cert.name,
            source_type="CERTIFICATION",
            organization=cert.issuing_organization,
        )
        for number, cert in enumerate(portfolio.certifications, len(items) + 1)
    ]
    items += [
        InputPortfolioItem(
            ref=f"P{number}",
            title=achievement.title,
            source_type="ACHIEVEMENT",
            organization=achievement.issuing_organization,
        )
        for number, achievement in enumerate(portfolio.achievements, len(items) + 1)
    ]
    return items


def _build_portfolio_index(items: list[InputPortfolioItem]) -> dict[str, str]:
    return {item.ref: item.title for item in items}


def _build_assessment_evidence(
    recent_attempts: list[AttemptHistoryItemResponse], entries: list[dict]
) -> list[InputAssessmentEvidence]:
    """Only attempts whose skill is ALSO one of the current gap-relevant
    skills -- unrelated assessment history is excluded (see the Phase 3
    brief's minimal-input guidance)."""
    name_by_skill_id = {entry["skill_id"]: entry["skill_name"] for entry in entries}
    evidence: list[InputAssessmentEvidence] = []
    for attempt in recent_attempts:
        if attempt.assessment is None or attempt.passed is None:
            continue
        skill_id = str(attempt.assessment.skill_id)
        if skill_id not in name_by_skill_id:
            continue
        evidence.append(
            InputAssessmentEvidence(
                skill_name=name_by_skill_id[skill_id],
                difficulty=attempt.assessment.difficulty.value,
                passed=attempt.passed,
            )
        )
    return evidence[:10]


def _build_canonical_summary(
    section: SkillGapSection, target_role_name: str | None
) -> CanonicalSkillGapSummary:
    """Built directly from skill_gap_service's own output (via
    section) -- independent of anything the LLM does or returns."""
    if section.mode == AnalysisMode.JOB_ROLE and section.job_role_analysis is not None:
        jr = section.job_role_analysis
        return CanonicalSkillGapSummary(
            mode=AnalysisMode.JOB_ROLE,
            target_role=target_role_name,
            readiness_score=jr.readiness_percentage,
            matched_count=jr.summary.matched,
            needs_improvement_count=jr.summary.needs_improvement,
            missing_count=jr.summary.missing,
            unverified_count=jr.summary.unverified,
        )

    if section.mode == AnalysisMode.PERSONAL and section.personal_analysis is not None:
        pa = section.personal_analysis
        return CanonicalSkillGapSummary(
            mode=AnalysisMode.PERSONAL,
            total_active_skills=pa.counts.total_active_skills,
            verified_skills=pa.counts.verified_skills,
        )

    # Structurally unreachable given SkillGapSection's own construction
    # (app.ai.tools.skill_gap_tools always populates exactly one
    # analysis matching `mode`), kept only as a safe default.
    return CanonicalSkillGapSummary(mode=section.mode)


def _build_agent_input(
    section: SkillGapSection,
    entries: list[dict],
    owned_skills: list[StudentSkillSummary],
    portfolio_items: list[InputPortfolioItem],
    recent_attempts: list[AttemptHistoryItemResponse],
    target_role_name: str | None,
    owned_index: dict[str, CanonicalSkillRef],
) -> SkillGapAgentInput:
    return SkillGapAgentInput(
        mode=section.mode,
        target_role=target_role_name,
        gap_skills=[
            InputGapSkill(
                ref=entry["ref"],
                skill_name=entry["skill_name"],
                status=entry["status"],
                priority=entry["priority"],
                importance=entry["importance"],
                current_level=entry["current_level"],
                target_level=entry["target_level"],
                is_verified=entry["is_verified"],
                assessment_available=entry["assessment_available"],
            )
            for entry in entries
        ],
        owned_skills=[
            InputOwnedSkill(
                ref=f"O{number}",
                assessment_available=owned_index[f"O{number}"].assessment_available,
                skill_name=skill.skill_name,
                proficiency_level=skill.proficiency_level,
                is_verified=skill.is_verified,
            )
            for number, skill in enumerate(owned_skills, 1)
        ],
        portfolio_items=portfolio_items,
        assessment_evidence=_build_assessment_evidence(recent_attempts, entries),
    )


def _empty_analysis() -> SkillGapAnalysis:
    return SkillGapAnalysis(summary=_NO_DATA_SUMMARY)


def build_canonical_summary_only(client: Client, student_id: str) -> CanonicalSkillGapSummary:
    """Canonical-only, no Groq call at all. Used by app.api.ai's
    graceful-degradation path (POST /api/v1/ai/skill-gap) when the AI
    call itself fails partway through -- canonical data must still be
    returned even when the AI layer is unavailable (see the Phase 3
    report's "Groq failure behavior" section)."""
    section = skill_gap_tools.get_current_skill_gap(client, student_id)
    target_role_name = (
        section.job_role_analysis.job_role.name
        if section.mode == AnalysisMode.JOB_ROLE and section.job_role_analysis
        else None
    )
    return _build_canonical_summary(section, target_role_name)


def analyze_student_skill_gap(client: Client, student_id: str) -> SkillGapAgentResponse:
    """The caller's own AI-interpreted skill gap analysis. Raises
    whatever app.ai.client.groq_client.complete_structured raises
    (AIConfigurationError / AIProviderError / AIResponseError /
    AIStructuredOutputError) -- the caller (app.api.ai) decides how to
    degrade gracefully; this function never swallows a provider failure
    into fabricated advice (see the Phase 3 report)."""
    section = skill_gap_tools.get_current_skill_gap(client, student_id)
    owned_skills = skill_tools.get_student_skills(client, student_id)
    portfolio = portfolio_tools.get_student_portfolio(client, student_id)
    assessment_summary = assessment_tools.get_assessment_summary(client, student_id)

    entries = _extract_gap_entries(section, owned_skills)
    portfolio_items = _build_portfolio_input(portfolio)

    target_role_name = (
        section.job_role_analysis.job_role.name
        if section.mode == AnalysisMode.JOB_ROLE and section.job_role_analysis
        else None
    )
    canonical = _build_canonical_summary(section, target_role_name)

    if not entries and not owned_skills:
        # Nothing grounded to reason about -- see the module-level
        # docstring on _NO_DATA_SUMMARY for why this skips Groq entirely
        # rather than prompting from an empty context.
        return SkillGapAgentResponse(
            canonical=canonical,
            analysis=_empty_analysis(),
            meta=AIResponseMeta(model=ai_settings.groq_model),
        )

    gap_index = _build_gap_index(entries)
    availability = assessment_tools.get_assessment_availability(
        client, [skill.skill_id for skill in owned_skills]
    )
    owned_index = _build_owned_index(owned_skills, availability)
    portfolio_index = _build_portfolio_index(portfolio_items)

    agent_input = _build_agent_input(
        section,
        entries,
        owned_skills,
        portfolio_items,
        assessment_summary.recent_attempts,
        target_role_name,
        owned_index,
    )

    llm_output = groq_client.complete_structured(
        system=SKILL_GAP_SYSTEM_PROMPT_V1,
        user=build_user_prompt(agent_input),
        response_model=SkillGapLLMOutput,
    )

    analysis = ground(
        llm_output,
        gap_index=gap_index,
        owned_index=owned_index,
        portfolio_index=portfolio_index,
    )

    return SkillGapAgentResponse(
        canonical=canonical,
        analysis=analysis,
        meta=AIResponseMeta(model=ai_settings.groq_model),
    )
