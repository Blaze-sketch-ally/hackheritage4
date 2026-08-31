"""Unit tests for the deterministic skill-alignment engine (Phase 1L).

Pure computation, no Supabase/network involved -- see
app.services.skill_alignment_service for the algorithm itself.
"""

from decimal import Decimal

from app.services.skill_alignment_service import (
    AlignmentStatus,
    SkillRequirement,
    compute_alignment,
)


def _req(skill_id="skill-1", skill_name="Python", required_level="70", weight="1.0"):
    return SkillRequirement(
        skill_id=skill_id,
        skill_name=skill_name,
        required_level=Decimal(required_level),
        weight=Decimal(weight),
    )


# Case 1: student exceeds all requirements -> all STRONG, high alignment.
def test_student_exceeds_all_requirements():
    requirements = [
        _req("s1", "Python", "70", "1.0"),
        _req("s2", "SQL", "60", "1.0"),
    ]
    scores = {"s1": Decimal(90), "s2": Decimal(85)}
    summary = compute_alignment(requirements, scores)

    assert all(r.status == AlignmentStatus.STRONG for r in summary.results)
    assert all(r.gap == Decimal(0) for r in summary.results)
    assert summary.overall_score == Decimal("100.00")


# Case 2: student is below every requirement -> all GAP.
def test_student_below_all_requirements():
    requirements = [
        _req("s1", "Python", "70", "1.0"),
        _req("s2", "SQL", "60", "1.0"),
    ]
    scores = {"s1": Decimal(40), "s2": Decimal(30)}
    summary = compute_alignment(requirements, scores)

    assert all(r.status == AlignmentStatus.GAP for r in summary.results)
    assert summary.results[0].gap == Decimal(30)
    assert summary.results[1].gap == Decimal(30)
    assert summary.overall_score < Decimal("100.00")


# Case 3: student has never been assessed on a required skill.
def test_never_assessed_skill():
    requirements = [_req("s1", "Docker", "60", "1.0")]
    summary = compute_alignment(requirements, {})

    result = summary.results[0]
    assert result.student_score == Decimal(0)
    assert result.status == AlignmentStatus.NOT_ASSESSED
    assert result.gap == Decimal(60)


# Case 4: mixed strengths and gaps.
def test_mixed_strengths_and_gaps():
    requirements = [
        _req("s1", "Python", "70", "1.0"),
        _req("s2", "SQL", "70", "1.0"),
        _req("s3", "Docker", "60", "1.0"),
    ]
    scores = {"s1": Decimal(85), "s2": Decimal(50)}  # s3 never assessed
    summary = compute_alignment(requirements, scores)

    statuses = {r.skill_id: r.status for r in summary.results}
    assert statuses["s1"] == AlignmentStatus.STRONG
    assert statuses["s2"] == AlignmentStatus.GAP
    assert statuses["s3"] == AlignmentStatus.NOT_ASSESSED
    assert Decimal(0) < summary.overall_score < Decimal("100.00")


# Case 5: required_level = 0 -> automatically satisfied, no division by zero.
def test_required_level_zero_is_auto_satisfied():
    requirements = [_req("s1", "Python", "0", "1.0")]
    summary = compute_alignment(requirements, {})  # never assessed either

    result = summary.results[0]
    assert result.status == AlignmentStatus.STRONG
    assert result.gap == Decimal(0)
    assert summary.overall_score == Decimal("100.00")


# Case 6: zero total weight -> safe, deterministic, no NaN/Infinity.
def test_zero_total_weight_is_safe():
    requirements = [
        _req("s1", "Python", "70", "0"),
        _req("s2", "SQL", "60", "0"),
    ]
    scores = {"s1": Decimal(90), "s2": Decimal(90)}
    summary = compute_alignment(requirements, scores)

    assert summary.overall_score == Decimal(0)
    # Per-skill classification is unaffected by weight being zero.
    assert summary.results[0].status == AlignmentStatus.STRONG


def test_no_requirements_at_all_is_safe():
    summary = compute_alignment([], {})
    assert summary.overall_score == Decimal(0)
    assert summary.results == []


# Case 7: boundary -- student_score == required_level -> STRONG, gap = 0.
def test_boundary_score_equals_required_level():
    requirements = [_req("s1", "Python", "70", "1.0")]
    summary = compute_alignment(requirements, {"s1": Decimal(70)})

    result = summary.results[0]
    assert result.status == AlignmentStatus.STRONG
    assert result.gap == Decimal(0)
    assert summary.overall_score == Decimal("100.00")


# Case 8: boundary -- student_score == required_level - 1 -> GAP.
def test_boundary_score_one_below_required_level():
    requirements = [_req("s1", "Python", "70", "1.0")]
    summary = compute_alignment(requirements, {"s1": Decimal(69)})

    result = summary.results[0]
    assert result.status == AlignmentStatus.GAP
    assert result.gap == Decimal(1)


def test_negative_gap_never_produced():
    """A student well above the bar must never show a negative gap --
    max(required - score, 0) is the whole point of the max()."""
    requirements = [_req("s1", "Python", "50", "1.0")]
    summary = compute_alignment(requirements, {"s1": Decimal(95)})
    assert summary.results[0].gap == Decimal(0)


def test_weighted_overall_score_reflects_relative_weight():
    """A heavily-weighted STRONG skill pulls the overall score up more
    than a lightly-weighted one, and vice versa for a GAP."""
    requirements = [
        _req("s1", "Python", "70", "3.0"),  # heavy weight, will be STRONG
        _req("s2", "Docker", "70", "1.0"),  # light weight, will be GAP
    ]
    scores = {"s1": Decimal(90), "s2": Decimal(0)}
    summary = compute_alignment(requirements, scores)

    # weighted_sum = 3.0*1.0 + 1.0*0.0 = 3.0; total_weight = 4.0 -> 75%
    assert summary.overall_score == Decimal("75.00")
