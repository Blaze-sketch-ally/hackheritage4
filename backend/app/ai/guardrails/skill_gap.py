"""Grounding/guardrail validation for the Skill Gap Analysis Agent.

Pure functions only: no Groq call, no Supabase access. `ground()` takes
the raw (flat, Phase 3.3) SkillGapLLMOutput plus canonical lookup
indexes -- keyed by the same short REF TOKENS (e.g. "G1", "O1", "P1")
app.ai.agents.skill_gap_agent assigned when building the prompt input --
and returns the final, rich SkillGapAnalysis the API returns.

Grammar each relevant SkillGapLLMOutput list item is expected to follow
(see that schema's own field descriptions, sent to Groq as part of the
JSON Schema):
  "<ref>: text"              -- priority_gap_reasons, priority_gap_actions,
                                 assessment_notes, and the single-ref form
                                 of portfolio_notes
  "<ref1> -> <ref2>: text"    -- transferable_skill_notes, and the
                                 two-ref form of portfolio_notes
  bare "<ref>"                -- learning_sequence only

Every ref is resolved against a CLOSED set built from canonical data --
anything that doesn't parse, or parses but doesn't resolve, is dropped
(sanitized), never passed through as fact. Every canonical_* field on
the output (status, priority, importance, skill_id, assessment_available)
is attached HERE from the matching CanonicalSkillRef -- never read from
the LLM's own output, which structurally cannot contain those fields
(see app.ai.schemas.skill_gap.SkillGapLLMOutput). `strengths`,
`next_actions`, and `summary` carry no ref convention and pass through
unchanged -- there is nothing to ground in free text with no reference.
"""

import re

from pydantic import BaseModel

from app.ai.schemas.skill_gap import (
    AssessmentAction,
    AssessmentActionType,
    PortfolioInsight,
    PriorityGapAnalysis,
    SequenceStep,
    SkillGapAnalysis,
    SkillGapLLMOutput,
    TransferableSkillInsight,
)

# Server-side caps mirroring the LLM output schema's own list caps --
# defense in depth so a future prompt/schema change can't silently
# balloon the response even if validation on the LLM side is loosened.
_MAX_ITEMS = 10

_REF_TOKEN = r"[A-Za-z]\d+"
_SINGLE_REF_RE = re.compile(rf"^\s*({_REF_TOKEN})\s*:\s*(.+)$")
_ARROW_REF_RE = re.compile(rf"^\s*({_REF_TOKEN})\s*->\s*({_REF_TOKEN})\s*:\s*(.+)$")
_BARE_REF_RE = re.compile(rf"^\s*({_REF_TOKEN})\s*$")


class CanonicalSkillRef(BaseModel):
    """One skill's canonical facts, as known ONLY to this guardrail --
    never constructed from, or influenced by, the LLM's output. `status`/
    `priority`/`importance` are None for a plain owned-skill reference
    (no gap concept applies); `is_tracked`/`is_verified` reflect
    student_skills exactly."""

    skill_id: str
    skill_name: str
    status: str | None = None
    priority: str | None = None
    importance: str | None = None
    assessment_available: bool = False
    is_tracked: bool = False
    is_verified: bool | None = None


def _determine_assessment_action(ref: CanonicalSkillRef) -> AssessmentActionType:
    """The ONLY place an assessment action is decided -- purely a
    function of canonical facts. The LLM's proposed action (if any) is
    never used; only its supporting note text survives into the
    response. This is what makes "never invent an assessment" and the
    Add-Skill-vs-Take-Assessment distinction structural, not prompted."""
    if ref.is_verified:
        return AssessmentActionType.ALREADY_VERIFIED
    if not ref.assessment_available:
        return AssessmentActionType.NO_ASSESSMENT_AVAILABLE
    if not ref.is_tracked:
        return AssessmentActionType.ADD_SKILL_THEN_ASSESS
    return AssessmentActionType.TAKE_ASSESSMENT


def _normalize_ref(token: str) -> str:
    return token.strip().upper()


def _resolve_gap(ref_token: str, gap_index: dict[str, CanonicalSkillRef]) -> CanonicalSkillRef | None:
    return gap_index.get(_normalize_ref(ref_token))


def _resolve_owned(
    ref_token: str,
    owned_index: dict[str, CanonicalSkillRef],
    gap_index: dict[str, CanonicalSkillRef],
) -> CanonicalSkillRef | None:
    """A ref counts as "owned" if it's in the student's own
    student_skills (owned_index), OR it's a gap-index entry the student
    has already MATCHED (a required skill they already have, which is
    "owned" for transferable-skill purposes even though it also has a
    role-requirement record)."""
    key = _normalize_ref(ref_token)
    if key in owned_index:
        return owned_index[key]
    ref = gap_index.get(key)
    if ref is not None and ref.status == "MATCHED":
        return ref
    return None


def _resolve_any(
    ref_token: str,
    gap_index: dict[str, CanonicalSkillRef],
    owned_index: dict[str, CanonicalSkillRef],
) -> CanonicalSkillRef | None:
    """Gap skills take priority (an assessment/portfolio note is more
    likely about an active gap than an unrelated owned skill), falling
    back to a plain owned-skill ref."""
    return _resolve_gap(ref_token, gap_index) or owned_index.get(_normalize_ref(ref_token))


def _parse_single_ref(line: str) -> tuple[str, str] | None:
    match = _SINGLE_REF_RE.match(line)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def _parse_arrow_ref(line: str) -> tuple[str, str, str] | None:
    match = _ARROW_REF_RE.match(line)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3).strip()


def _index_single_ref_lines(lines: list[str]) -> dict[str, str]:
    """{ref: text}, last occurrence wins if the model repeats a ref --
    lines that don't match "<ref>: text" at all are dropped (sanitize)."""
    result: dict[str, str] = {}
    for line in lines[:_MAX_ITEMS]:
        parsed = _parse_single_ref(line)
        if parsed is None:
            continue
        ref_token, text = parsed
        if text:
            result[_normalize_ref(ref_token)] = text
    return result


def _ground_priority_gaps(
    llm_output: SkillGapLLMOutput, gap_index: dict[str, CanonicalSkillRef]
) -> list[PriorityGapAnalysis]:
    reasons = _index_single_ref_lines(llm_output.priority_gap_reasons)
    actions = _index_single_ref_lines(llm_output.priority_gap_actions)

    priority_gaps: list[PriorityGapAnalysis] = []
    # A complete item needs BOTH a reason and an action for the same ref
    # -- one-sided data is dropped rather than shown with a missing half.
    for ref_token in reasons:
        if ref_token not in actions:
            continue
        ref = gap_index.get(ref_token)
        if ref is None or ref.status == "MATCHED":
            # Unknown ref, or the LLM mistakenly called an already-
            # matched requirement a "gap" -- never represent either as
            # a real priority gap.
            continue
        priority_gaps.append(
            PriorityGapAnalysis(
                skill_id=ref.skill_id,
                skill_name=ref.skill_name,
                canonical_status=ref.status,
                canonical_priority=ref.priority,
                canonical_importance=ref.importance,
                reason=reasons[ref_token],
                suggested_action=actions[ref_token],
            )
        )
        if len(priority_gaps) >= _MAX_ITEMS:
            break
    return priority_gaps


def _ground_transferable_skills(
    llm_output: SkillGapLLMOutput,
    gap_index: dict[str, CanonicalSkillRef],
    owned_index: dict[str, CanonicalSkillRef],
) -> list[TransferableSkillInsight]:
    results: list[TransferableSkillInsight] = []
    for line in llm_output.transferable_skill_notes[:_MAX_ITEMS]:
        parsed = _parse_arrow_ref(line)
        if parsed is None:
            continue
        from_token, to_token, explanation = parsed
        from_ref = _resolve_owned(from_token, owned_index, gap_index)
        supports_ref = _resolve_gap(to_token, gap_index)
        if from_ref is None or supports_ref is None or supports_ref.status == "MATCHED" or not explanation:
            continue
        results.append(
            TransferableSkillInsight(
                from_skill_id=from_ref.skill_id,
                from_skill_name=from_ref.skill_name,
                supports_skill_id=supports_ref.skill_id,
                supports_skill_name=supports_ref.skill_name,
                explanation=explanation,
            )
        )
    return results


def _ground_learning_sequence(
    llm_output: SkillGapLLMOutput, gap_index: dict[str, CanonicalSkillRef]
) -> list[SequenceStep]:
    steps: list[SequenceStep] = []
    seen: set[str] = set()
    for token in llm_output.learning_sequence[:_MAX_ITEMS]:
        match = _BARE_REF_RE.match(token)
        if not match:
            continue
        ref_token = _normalize_ref(match.group(1))
        if ref_token in seen:
            continue
        ref = gap_index.get(ref_token)
        if ref is None or ref.status == "MATCHED":
            continue
        seen.add(ref_token)
        steps.append(
            SequenceStep(
                order=len(steps) + 1,
                skill_id=ref.skill_id,
                skill_name=ref.skill_name,
                canonical_priority=ref.priority,
                # Server-templated, not LLM-authored -- deterministic and
                # traceable to the same canonical priority every other
                # field on this step already carries.
                rationale=(
                    f"{ref.priority} priority from your deterministic skill analysis."
                    if ref.priority else "Progression option from your existing skill analysis."
                ),
            )
        )
    return steps


def _ground_assessment_actions(
    llm_output: SkillGapLLMOutput,
    gap_index: dict[str, CanonicalSkillRef],
    owned_index: dict[str, CanonicalSkillRef],
) -> list[AssessmentAction]:
    results: list[AssessmentAction] = []
    seen: set[str] = set()
    for line in llm_output.assessment_notes[:_MAX_ITEMS]:
        parsed = _parse_single_ref(line)
        if parsed is None:
            continue
        ref_token, note = parsed
        normalized = _normalize_ref(ref_token)
        if normalized in seen or not note:
            continue
        ref = _resolve_any(ref_token, gap_index, owned_index)
        if ref is None:
            continue
        seen.add(normalized)
        results.append(
            AssessmentAction(
                skill_id=ref.skill_id,
                skill_name=ref.skill_name,
                action=_determine_assessment_action(ref),
                assessment_available=ref.assessment_available,
                note=note,
            )
        )
    return results


def _ground_portfolio_insights(
    llm_output: SkillGapLLMOutput,
    gap_index: dict[str, CanonicalSkillRef],
    owned_index: dict[str, CanonicalSkillRef],
    portfolio_index: dict[str, str],
) -> list[PortfolioInsight]:
    results: list[PortfolioInsight] = []
    for line in llm_output.portfolio_notes[:_MAX_ITEMS]:
        related_ref = None

        arrow_parsed = _parse_arrow_ref(line)
        if arrow_parsed is not None:
            portfolio_token, skill_token, note = arrow_parsed
            related_ref = _resolve_any(skill_token, gap_index, owned_index)
            if related_ref is None:
                continue
        else:
            single_parsed = _parse_single_ref(line)
            if single_parsed is None:
                continue
            portfolio_token, note = single_parsed

        title = portfolio_index.get(_normalize_ref(portfolio_token))
        if title is None or not note:
            # Unknown portfolio item -- never fabricate evidence.
            continue

        results.append(
            PortfolioInsight(
                source_title=title,
                related_skill_id=related_ref.skill_id if related_ref else None,
                related_skill_name=related_ref.skill_name if related_ref else None,
                note=note,
            )
        )
    return results


def ground(
    llm_output: SkillGapLLMOutput,
    *,
    gap_index: dict[str, CanonicalSkillRef],
    owned_index: dict[str, CanonicalSkillRef],
    portfolio_index: dict[str, str],
) -> SkillGapAnalysis:
    """Resolve, sanitize, and attach canonical fields to every part of
    the LLM's output. Anything that fails to parse or resolve is
    silently dropped (sanitized) rather than passed through as fact --
    see the module docstring. `summary`/`strengths`/`next_actions` carry
    no ref convention and pass through unchanged; Pydantic's own field
    constraints on SkillGapLLMOutput already rejected an empty/oversized
    response before this function runs.
    """
    return SkillGapAnalysis(
        summary=llm_output.summary,
        strengths=list(llm_output.strengths[:_MAX_ITEMS]),
        priority_gaps=_ground_priority_gaps(llm_output, gap_index),
        transferable_skills=_ground_transferable_skills(llm_output, gap_index, owned_index),
        recommended_sequence=_ground_learning_sequence(llm_output, gap_index),
        assessment_actions=_ground_assessment_actions(llm_output, gap_index, owned_index),
        portfolio_insights=_ground_portfolio_insights(llm_output, gap_index, owned_index, portfolio_index),
        next_actions=list(llm_output.next_actions[:_MAX_ITEMS]),
    )
