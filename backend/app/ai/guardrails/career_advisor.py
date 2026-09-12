"""Grounding for the Career Advisor synthesis agent (Phase 6).

Pure functions only: no Groq call, no Supabase access. Every ref the
LLM produces is resolved against closed indexes built by
app.ai.orchestrator from the three specialists' OWN already-grounded
output objects -- an unresolvable ref, or a ref/action-code pairing
that isn't actually valid for that ref's kind, is dropped, never passed
through as fact.
"""

import re

from app.ai.schemas.career_guidance import ActionCode, CareerAdvisorLLMOutput

_MAX_ITEMS = 10
_REF_RE = re.compile(r"^(OP|G|C|A)(\d+)$")
_NOTE_RE = re.compile(r"^\s*((?:OP|G|C|A)\d+)\s*:\s*([A-Z_]+)\s*$")

# Which ref namespace an action code may legitimately apply to.
_VALID_NAMESPACES_FOR_CODE: dict[str, set[str]] = {
    ActionCode.LEARN_SKILL.value: {"G"},
    ActionCode.BUILD_PROJECT.value: {"G"},
    ActionCode.REASSESS_SKILL.value: {"G", "A"},
    ActionCode.TAKE_ASSESSMENT.value: {"A"},
    ActionCode.START_COURSE.value: {"C"},
    ActionCode.APPLY_OPPORTUNITY.value: {"OP"},
}

# Assessment actions (from the Skill Gap Agent's own server-determined
# AssessmentActionType) for which "take the assessment" is genuinely
# actionable right now -- ALREADY_VERIFIED / NO_ASSESSMENT_AVAILABLE
# must never be paired with a TAKE_ASSESSMENT suggestion.
_ACTIONABLE_ASSESSMENT_STATES = {"TAKE_ASSESSMENT", "ADD_SKILL_THEN_ASSESS"}


def ref_namespace(ref: str) -> str | None:
    match = _REF_RE.fullmatch(ref.strip())
    return match.group(1) if match else None


class GroundedAdvisorOutput:
    """Plain holder for the guardrail's result -- app.ai.orchestrator
    reads these fields directly to build the rich CareerGuidanceResponse.
    Not a Pydantic model: nothing here is ever serialized on its own."""

    def __init__(self) -> None:
        self.headline: str = ""
        self.focus_skill_refs: list[str] = []
        self.course_refs: list[str] = []
        self.opportunity_refs: list[str] = []
        self.actions: list[tuple[str, str]] = []  # (ref, ACTION_CODE)
        self.learning_sequence: list[str] = []


def ground_advisor(
    output: CareerAdvisorLLMOutput,
    *,
    skill_index: dict[str, object],
    course_index: dict[str, object],
    opportunity_index: dict[str, object],
    assessment_index: dict[str, object],
) -> GroundedAdvisorOutput:
    result = GroundedAdvisorOutput()
    result.headline = output.headline.strip()

    result.focus_skill_refs = _dedupe_known(output.focus_skill_refs, skill_index)
    result.course_refs = _dedupe_known(output.course_refs, course_index)
    result.opportunity_refs = _dedupe_known(output.opportunity_refs, opportunity_index)
    result.learning_sequence = _dedupe_known(output.learning_sequence, skill_index)

    indexes = {"G": skill_index, "C": course_index, "OP": opportunity_index, "A": assessment_index}
    seen: set[tuple[str, str]] = set()
    for line in output.action_notes[:_MAX_ITEMS]:
        match = _NOTE_RE.fullmatch(line)
        if not match:
            continue
        ref, code = match.groups()
        namespace = ref_namespace(ref)
        if namespace is None or ref not in indexes[namespace]:
            continue
        if code not in ActionCode.__members__ or namespace not in _VALID_NAMESPACES_FOR_CODE.get(code, set()):
            continue
        if code == ActionCode.TAKE_ASSESSMENT.value:
            entry = assessment_index[ref]
            action_value = getattr(entry, "action", None)
            action_value = getattr(action_value, "value", action_value)
            if action_value not in _ACTIONABLE_ASSESSMENT_STATES:
                continue
        pair = (ref, code)
        if pair in seen:
            continue
        seen.add(pair)
        result.actions.append(pair)
        if len(result.actions) >= _MAX_ITEMS:
            break

    return result


def _dedupe_known(refs: list[str], index: dict[str, object]) -> list[str]:
    seen: list[str] = []
    for ref in refs[:_MAX_ITEMS]:
        cleaned = ref.strip()
        if cleaned in index and cleaned not in seen:
            seen.append(cleaned)
    return seen[:_MAX_ITEMS]
