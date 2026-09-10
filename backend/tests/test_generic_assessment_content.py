"""Unit tests for the skill-agnostic assessment content templates
(database/seed/generic_assessment_content.py) used by
generate_generic_skill_assessments.py to give every catalog skill a
Beginner/Intermediate/Advanced assessment.

No live database -- these test the pure template-expansion logic only.
The seed script itself (which does talk to Supabase) is not exercised
here, matching tests/test_learning_schema.py's "check the seed for scope,
not execution" convention.
"""

import sys
from pathlib import Path

import pytest

SEED_DIR = Path(__file__).resolve().parents[2] / "database" / "seed"
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import generic_assessment_content as gac


def test_difficulties_are_the_three_product_tiers():
    assert gac.DIFFICULTIES == ["Beginner", "Intermediate", "Advanced"]


@pytest.mark.parametrize("difficulty", gac.DIFFICULTIES)
def test_pool_size_strictly_exceeds_select_count(difficulty):
    """generate_generic_skill_assessments.py raises if this ever fails --
    the per-attempt random selection must have something to choose from."""
    questions = gac.build_questions("Some Skill", difficulty)
    assert len(questions) > gac.DIFFICULTY_CONFIG[difficulty]["select_count"]


@pytest.mark.parametrize("difficulty", gac.DIFFICULTIES)
def test_every_question_is_a_well_formed_mcq(difficulty):
    for question_text, options, correct_index, explanation in gac.build_questions("Rust", difficulty):
        assert isinstance(question_text, str) and question_text.strip()
        assert isinstance(options, list) and len(options) >= 2
        assert len(set(options)) == len(options), "options must be distinct"
        assert 0 <= correct_index < len(options)
        assert isinstance(explanation, str) and explanation.strip()


@pytest.mark.parametrize("difficulty", gac.DIFFICULTIES)
def test_skill_name_is_substituted_not_hardcoded(difficulty):
    """The skill name always comes from the caller (the live `skills`
    table). Confirm no template silently drops it and no unrendered
    `{skill}` placeholder leaks through."""
    skill_name = "Zzql Widgetry"
    rendered = gac.build_questions(skill_name, difficulty)
    blob = " ".join(part for q in rendered for part in [q[0], *q[1], q[3]])
    assert "{skill}" not in blob
    assert skill_name in blob
    # No specific programming language / framework baked into the templates.
    for banned in ("Python", "FastAPI", "JavaScript", "C++"):
        assert banned not in blob


def test_tier_expectation_question_differs_per_difficulty():
    first_q = {d: gac.build_questions("Go", d)[0][0] for d in gac.DIFFICULTIES}
    assert len(set(first_q.values())) == len(gac.DIFFICULTIES)


def test_unknown_difficulty_rejected():
    with pytest.raises(ValueError):
        gac.build_questions("Go", "Expert")
