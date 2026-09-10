"""Skill-agnostic, template-based assessment content.

Purpose: give EVERY active catalog skill (database/seed/skills.sql, 100+
rows) a Beginner / Intermediate / Advanced assessment, so the
data-driven Assessments page has something to show for whatever skill a
student selects -- without hand-authoring a domain-specific question bank
for every skill.

NO LLM. NO runtime generation. The questions are fixed templates,
parameterised ONLY by:
  - the skill's own name, read from the `skills` table at seed time
    (never hardcoded here -- there is no skill name anywhere in this file), and
  - the difficulty tier.

They are deliberately generic "how do you build, verify, and demonstrate
proficiency" questions, each with a single defensible correct answer
(MCQ / OBJECTIVE scoring), so they slot into the existing schema
(004_assessments.sql / 015_assessment_verification.sql) and the existing
score_assessment_attempt() RPC completely unchanged.

Skills that DO have a curated, domain-specific bank in
assessment_catalog_data.py are covered by generate_assessment_catalog.py
instead; generate_generic_skill_assessments.py skips them so the richer
content always wins. A skill can be "graduated" from generic to curated
later just by adding it to assessment_catalog_data.SKILLS -- no schema
change, and the idempotent generators will not duplicate anything.

Consumed by generate_generic_skill_assessments.py.
"""

DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"]

# Per-tier assessment metadata. select_count MUST stay strictly below the
# generated pool size (see build_questions) -- generate_generic_skill_
# assessments.py raises if that ever stops being true, matching
# generate_assessment_catalog.py's own guard.
DIFFICULTY_CONFIG = {
    "Beginner": {"duration_minutes": 10, "select_count": 4, "passing_percentage": 60},
    "Intermediate": {"duration_minutes": 15, "select_count": 4, "passing_percentage": 65},
    "Advanced": {"duration_minutes": 20, "select_count": 5, "passing_percentage": 70},
}

# The one tier-specific question -- what a practitioner at this level is
# generally expected to be able to do. `{skill}` is filled with the real
# catalog skill name at seed time.
_TIER_EXPECTATION = {
    "Beginner": (
        "At a beginner level with {skill}, which is the most realistic expectation of your ability?",
        [
            "Understand the core concepts and complete guided exercises with reference material to hand",
            "Design large systems end to end with no assistance",
            "Mentor experienced practitioners and set team-wide standards",
            "Have nothing left to learn about the topic",
        ],
        0,
        (
            "Beginner-level proficiency is about grasping fundamentals and working through guided "
            "practice, not independent system design or mentoring."
        ),
    ),
    "Intermediate": (
        "At an intermediate level with {skill}, which is the most realistic expectation of your ability?",
        [
            "Build small-to-medium pieces of work independently and debug common problems without step-by-step guidance",
            "Only follow tutorials line by line",
            "Never need to consult documentation again",
            "Guarantee bug-free work in every situation",
        ],
        0,
        (
            "Intermediate proficiency means working independently on realistic tasks and resolving "
            "the everyday problems that come up, while still learning."
        ),
    ),
    "Advanced": (
        "At an advanced level with {skill}, which is the most realistic expectation of your ability?",
        [
            "Design robust solutions, weigh trade-offs deliberately, and help others grow in the topic",
            "Complete only the exercises a beginner course provides",
            "Avoid ever reviewing or refactoring existing work",
            "Assume expertise removes the need for testing",
        ],
        0,
        (
            "Advanced proficiency is characterised by sound judgement about trade-offs, resilient "
            "design, and the ability to raise the capability of others."
        ),
    ),
}

# Shared, tier-independent questions. Each is a genuine multiple-choice
# question with one correct answer, about the practice of learning and
# working with ANY skill.
_SHARED = [
    (
        "Which approach most reliably builds lasting proficiency in {skill}?",
        [
            "Regular hands-on practice on progressively harder problems, with feedback",
            "Reading about it once and never applying it",
            "Memorising terminology without ever using it in practice",
            "Avoiding anything you find difficult",
        ],
        0,
        (
            "Deliberate, progressively challenging practice with feedback is what actually develops "
            "skill; passive reading or rote memorisation on their own do not."
        ),
    ),
    (
        "You hit an unfamiliar error while working with {skill}. What is the best first step?",
        [
            "Read the error message carefully and check the official documentation or a primary reference",
            "Immediately delete large parts of your work and start over",
            "Ignore it and hope it goes away",
            "Change random settings until something appears to work",
        ],
        0,
        (
            "The error message plus authoritative documentation is almost always the fastest route "
            "to the real cause; guessing or wholesale deletion tends to hide the problem rather "
            "than fix it."
        ),
    ),
    (
        "When learning {skill}, which source is generally the most authoritative?",
        [
            "The official documentation and other primary references",
            "An unattributed comment on a random forum",
            "A tutorial that no longer matches current versions",
            "A guess based on an unrelated tool",
        ],
        0,
        (
            "Primary references (official docs, specifications, maintainer guidance) are the most "
            "trustworthy baseline; secondary material can help but should be cross-checked against "
            "them."
        ),
    ),
    (
        "Why does testing or otherwise verifying your work matter when practising {skill}?",
        [
            "It catches mistakes early and builds well-founded confidence that the work is correct",
            "It only ever slows things down with no benefit",
            "It is something only experts are allowed to do",
            "It removes any need to understand the topic",
        ],
        0,
        (
            "Verification surfaces defects while they are cheap to fix and gives you evidence the "
            "work behaves as intended -- it complements understanding rather than replacing it."
        ),
    ),
    (
        "Which habit most improves the long-term maintainability of work involving {skill}?",
        [
            "Producing clear, well-structured, documented solutions",
            "Using the shortest possible names for everything, everywhere",
            "Never revisiting anything once it appears to work",
            "Keeping no record of why decisions were made",
        ],
        0,
        (
            "Clarity, structure and a record of intent are what let you (and others) safely change "
            "the work later; terseness and undocumented decisions make future change risky."
        ),
    ),
    (
        "How does working with others (reviews, pairing, feedback) typically affect your growth in {skill}?",
        [
            "It exposes blind spots and spreads good practice, accelerating learning",
            "It has no effect on how quickly anyone learns",
            "It is only useful once you are already an expert",
            "It should be avoided so mistakes stay hidden",
        ],
        0,
        (
            "Feedback from others reveals gaps you cannot see yourself and transfers techniques "
            "between people; hiding work from review slows everyone down."
        ),
    ),
    (
        "You are unsure whether you truly understand a concept in {skill}. What is the best way to check?",
        [
            "Try to apply it to a small new problem and explain your reasoning",
            "Assume you understand it because it looked familiar",
            "Avoid the concept entirely from now on",
            "Wait for someone else to do it for you",
        ],
        0,
        (
            "Applying a concept to something new -- and being able to explain why it works -- is a "
            "far more reliable test of understanding than a sense of familiarity."
        ),
    ),
]


def build_questions(skill_name: str, difficulty: str) -> list[tuple]:
    """The generic MCQ pool for one (skill, difficulty) pair.

    Returns a list of (question_text, [option, ...], correct_index,
    explanation) tuples in exactly the shape generate_assessment_catalog.py
    already consumes. `skill_name` is substituted verbatim into each
    template -- it comes from the caller (the live `skills` table), never
    from this module.

    Pool size is len(_SHARED) + 1 == 8, comfortably above every
    DIFFICULTY_CONFIG select_count, so the per-attempt random selection in
    create_assessment_attempt() stays meaningful.
    """
    if difficulty not in _TIER_EXPECTATION:
        raise ValueError(f"Unsupported difficulty: {difficulty!r}")

    templates = [_TIER_EXPECTATION[difficulty], *_SHARED]
    questions: list[tuple] = []
    for text, options, correct_index, explanation in templates:
        questions.append(
            (
                text.format(skill=skill_name),
                [option.format(skill=skill_name) for option in options],
                correct_index,
                explanation.format(skill=skill_name),
            )
        )
    return questions
