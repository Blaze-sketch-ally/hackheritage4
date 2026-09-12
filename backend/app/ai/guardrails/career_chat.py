"""Deterministic intent routing and ref grounding for Career AI Chat.

Keyword classification runs FIRST and is preferred -- no LLM call at
all for the common cases the task explicitly lists. The bounded Groq
classifier (app.ai.chat.career_chat) is only a fallback for genuinely
ambiguous text, and even then its output is a single closed-vocabulary
field (IntentClassification) -- never a free-text plan.
"""

import re

from app.ai.schemas.career_chat import (
    ASSESSMENT,
    CAREER_PLAN,
    INTERNSHIP,
    JOB,
    LEARNING,
    OPPORTUNITY,
    READINESS,
    SKILL_GAP,
    YOUTUBE_LEARNING,
    ChatCard,
    ChatIntentValue,
    ChatLLMOutput,
)

# Order matters: earlier patterns win on a message that matches more
# than one (e.g. "learn" + "youtube" -> YOUTUBE_LEARNING, checked
# first, per the task's own routing examples).
_KEYWORD_RULES: list[tuple[re.Pattern[str], ChatIntentValue]] = [
    (re.compile(r"youtube|\bvideo(s)?\b|\btutorial(s)?\b", re.IGNORECASE), YOUTUBE_LEARNING),
    (re.compile(r"\binternship(s)?\b", re.IGNORECASE), INTERNSHIP),
    (re.compile(r"\bjob(s)?\b|\bplacement(s)?\b", re.IGNORECASE), JOB),
    (re.compile(r"\bopportunit(y|ies)\b", re.IGNORECASE), OPPORTUNITY),
    (re.compile(r"\bassessment(s)?\b|\btest my\b|\bverif(y|ication)\b", re.IGNORECASE), ASSESSMENT),
    (re.compile(r"\bcareer plan\b|\bwhat should i do\b|\bnext step\b", re.IGNORECASE), CAREER_PLAN),
    (re.compile(r"\bready\b|\breadiness\b", re.IGNORECASE), READINESS),
    (
        re.compile(
            r"\bskill gap(s)?\b|\bskills? should i improve\b|\bmissing skills?\b|"
            r"\bbiggest gap\b|\bskill.*\bgap\b",
            re.IGNORECASE,
        ),
        SKILL_GAP,
    ),
    (re.compile(r"\bcourse(s)?\b|\blearn\b|\blearning\b|\blearning resource(s)?\b", re.IGNORECASE), LEARNING),
]


def classify_intent_by_keyword(message: str) -> ChatIntentValue | None:
    """Deterministic, no Groq call. Returns None when nothing matches
    -- the caller falls back to the bounded AI classifier, then to
    GENERAL_CAREER."""
    for pattern, intent in _KEYWORD_RULES:
        if pattern.search(message):
            return intent
    return None


def ground(output: ChatLLMOutput, card_index: dict[str, ChatCard]) -> tuple[str, list[ChatCard]]:
    """Exact closed-set membership only -- no fuzzy title/URL matching.
    A ref Groq mentions that isn't in card_index (invented, or from a
    different turn) is silently dropped, never surfaced as an error."""
    seen: set[str] = set()
    cards: list[ChatCard] = []
    for ref in output.mentioned_refs:
        if ref in card_index and ref not in seen:
            cards.append(card_index[ref])
            seen.add(ref)
    message = output.message.strip()[:800]
    return message, cards
