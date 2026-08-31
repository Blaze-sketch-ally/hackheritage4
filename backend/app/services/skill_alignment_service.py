"""Deterministic, explainable skill-alignment engine (Phase 1L).

Computes how well a set of "student skill scores" aligns with a set of
"required skills." Deliberately generic over the CALLER: today the only
caller is career-role skill-gap analysis
(app.services.career_role_service + app.api.career_roles), but this
module knows nothing about career_roles specifically -- it operates only
on SkillRequirement inputs and a plain skill_id -> score mapping. A
future opportunity-matching feature (Phase 1M, per
docs/architecture/assessment-lifecycle.md's "Skill Evidence Boundary"
section) can reuse compute_alignment() unchanged by building its own
list[SkillRequirement] from opportunity_required_skills instead of
career_role_skill_requirements -- the algorithm itself must never be
duplicated for a second caller.

No database access happens here -- this is pure computation over data its
callers already fetched. No AI is used anywhere in this module.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class AlignmentStatus(str, Enum):
    STRONG = "STRONG"
    GAP = "GAP"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class SkillRequirement:
    """One required skill, independent of whether the caller is a career
    role or (future) an opportunity."""

    skill_id: str
    skill_name: str
    required_level: Decimal
    weight: Decimal


@dataclass(frozen=True)
class SkillAlignmentResult:
    skill_id: str
    skill_name: str
    required_level: Decimal
    student_score: Decimal
    gap: Decimal
    weight: Decimal
    status: AlignmentStatus


@dataclass(frozen=True)
class AlignmentSummary:
    overall_score: Decimal
    results: list[SkillAlignmentResult]


def compute_alignment(
    requirements: list[SkillRequirement],
    student_scores: dict[str, Decimal],
) -> AlignmentSummary:
    """The core deterministic gap/match calculation.

    student_scores: skill_id -> the student's current evidence (the best
    percentage across their own COMPLETED assessment attempts covering
    that skill -- see app.services.assessment_service.
    get_student_skill_scores()). A skill_id ABSENT from this dict means
    the student has never completed an assessment covering it; this is
    treated as a score of 0 for the gap/ratio math, but classified
    NOT_ASSESSED rather than GAP, so callers can distinguish "assessed and
    below the bar" from "never assessed at all" -- an absent key is never
    silently conflated with an assessed 0.

    Per skill:
      gap    = max(required_level - score, 0)
      status = STRONG   if required_level == 0 (auto-satisfied), or if
                         assessed and score >= required_level
               GAP       if assessed and score < required_level
               NOT_ASSESSED  if never assessed (and required_level > 0)

    Weighted overall score (0-100), the same formula for every skill:
      ratio_i = 1.0                              if required_level_i == 0
                min(score_i / required_level_i, 1.0)   otherwise
      overall = 100 * sum(weight_i * ratio_i) / sum(weight_i)

    Division-by-zero is impossible by construction: required_level == 0
    never reaches the division (short-circuited to ratio = 1.0), and a
    total weight of 0 (every requirement weighted 0, or no requirements at
    all) makes overall_score exactly 0 rather than raising or producing
    NaN/Infinity -- there is nothing to weight, so there is nothing to
    report as aligned.
    """
    results: list[SkillAlignmentResult] = []
    weighted_sum = Decimal(0)
    total_weight = Decimal(0)

    for req in requirements:
        assessed = req.skill_id in student_scores
        score = student_scores.get(req.skill_id, Decimal(0))
        gap = max(req.required_level - score, Decimal(0))

        if req.required_level == 0:
            status = AlignmentStatus.STRONG
        elif not assessed:
            status = AlignmentStatus.NOT_ASSESSED
        elif score >= req.required_level:
            status = AlignmentStatus.STRONG
        else:
            status = AlignmentStatus.GAP

        results.append(
            SkillAlignmentResult(
                skill_id=req.skill_id,
                skill_name=req.skill_name,
                required_level=req.required_level,
                student_score=score,
                gap=gap,
                weight=req.weight,
                status=status,
            )
        )

        ratio = Decimal(1) if req.required_level == 0 else min(score / req.required_level, Decimal(1))
        weighted_sum += req.weight * ratio
        total_weight += req.weight

    overall = (weighted_sum / total_weight * 100) if total_weight > 0 else Decimal(0)
    return AlignmentSummary(overall_score=overall.quantize(Decimal("0.01")), results=results)
