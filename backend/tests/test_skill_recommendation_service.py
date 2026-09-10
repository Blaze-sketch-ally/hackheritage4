"""Tests for app.services.skill_recommendation_service -- the aggregate
skill-gap engine behind GET /api/v1/student/learning/recommended (Phase
6D, adapted from a collaborator branch to this project's own
career_roles-based skill-gap engine instead of a persisted "target job
role" concept this project never adopted -- see that module's own
docstring).

No live Supabase project or real token is used anywhere in this file --
the service is driven by mocking career_role_service.list_career_roles /
get_career_role_requirements and assessment_service.get_student_skill_scores
directly, matching the existing pattern in test_career_roles.py.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services import (
    assessment_service,
    career_role_service,
    skill_recommendation_service,
)
from app.services.skill_alignment_service import SkillRequirement


def _req(skill_id: str, skill_name: str, required_level: str, weight: str = "1.0") -> SkillRequirement:
    return SkillRequirement(
        skill_id=skill_id,
        skill_name=skill_name,
        required_level=Decimal(required_level),
        weight=Decimal(weight),
    )


# get_aggregate_skill_gaps passes each role's "id" through uuid.UUID(...)
# before handing it back to get_career_role_requirements -- role ids must
# be well-formed UUID strings, not arbitrary labels.
_ROLE_1 = str(uuid4())
_ROLE_2 = str(uuid4())
_ROLE_3 = str(uuid4())
_ROLE_4 = str(uuid4())
_ROLE_5 = str(uuid4())
_GAP_ROLE = str(uuid4())


def test_empty_catalog_returns_no_recommendations():
    with (
        patch.object(career_role_service, "list_career_roles", return_value=[]),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert result == []


def test_roles_with_no_requirements_are_not_considered():
    """A career role with zero requirements contributes nothing and does
    not count toward the 'considered roles' denominator."""
    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(career_role_service, "get_career_role_requirements", return_value=[]),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert result == []


def test_strong_skill_is_never_recommended():
    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[_req("skill-1", "Python", "50")],
        ),
        patch.object(
            assessment_service,
            "get_student_skill_scores",
            return_value={"skill-1": Decimal(90)},
        ),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert result == []


def test_gap_and_not_assessed_skills_are_both_recommended():
    """A skill scored below the required level (GAP) and a skill never
    assessed at all (NOT_ASSESSED) both count as recommendation
    candidates -- only STRONG is excluded."""
    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[
                _req("skill-gap", "Python", "80"),
                _req("skill-unassessed", "Docker", "50"),
            ],
        ),
        patch.object(
            assessment_service,
            "get_student_skill_scores",
            return_value={"skill-gap": Decimal(40)},
        ),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    skill_ids = {r["skill_id"] for r in result}
    assert skill_ids == {"skill-gap", "skill-unassessed"}


def test_skill_gap_in_every_role_is_high_priority():
    with (
        patch.object(
            career_role_service,
            "list_career_roles",
            return_value=[{"id": _ROLE_1}, {"id": _ROLE_2}],
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[_req("skill-1", "Python", "80")],
        ),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert len(result) == 1
    assert result[0]["priority"] == "HIGH"
    assert "2 of 2" in result[0]["reason"]


def test_skill_gap_in_a_minority_of_roles_is_low_priority():
    """4 roles considered, the skill is a gap in only 1 of them ->
    fraction 0.25, which is exactly the MEDIUM threshold boundary; a
    3rd, non-overlapping role that's STRONG for this skill (not a gap)
    lowers the fraction below MEDIUM into LOW."""

    def fake_requirements(_client, role_id):
        role_id = str(role_id)
        if role_id == _GAP_ROLE:
            return [_req("skill-1", "Python", "80")]
        # Every other role requires the same skill but at a trivially low
        # bar (0) -- always STRONG, never counted as a gap -- diluting the
        # fraction without inventing a second skill.
        return [_req("skill-1", "Python", "0")]

    with (
        patch.object(
            career_role_service,
            "list_career_roles",
            return_value=[
                {"id": _GAP_ROLE},
                {"id": _ROLE_2},
                {"id": _ROLE_3},
                {"id": _ROLE_4},
                {"id": _ROLE_5},
            ],
        ),
        patch.object(
            career_role_service, "get_career_role_requirements", side_effect=fake_requirements
        ),
        patch.object(
            assessment_service,
            "get_student_skill_scores",
            return_value={"skill-1": Decimal(10)},
        ),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert len(result) == 1
    # 1 of 5 considered roles -> fraction 0.2, below the 0.25 MEDIUM floor.
    assert result[0]["priority"] == "LOW"


def test_results_are_sorted_by_priority_then_skill_name():
    def fake_requirements(_client, role_id):
        role_id = str(role_id)
        if role_id == _ROLE_1:
            return [_req("skill-zebra", "Zebra", "80"), _req("skill-apple", "Apple", "80")]
        return [_req("skill-apple", "Apple", "80")]

    with (
        patch.object(
            career_role_service,
            "list_career_roles",
            return_value=[{"id": _ROLE_1}, {"id": _ROLE_2}],
        ),
        patch.object(
            career_role_service, "get_career_role_requirements", side_effect=fake_requirements
        ),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    # skill-apple is a gap in both roles (HIGH), skill-zebra in only one (LOW-ish).
    assert result[0]["skill_id"] == "skill-apple"
    assert result[-1]["skill_id"] == "skill-zebra"


def test_gap_entry_status_reflects_gap_alignment():
    """Phase 3D: each recommendation carries the underlying AlignmentStatus
    ('GAP' here, since the skill was assessed but scored below the
    required level) as an additive 'status' field -- used downstream by
    recommend_assessments to pick SKILL_GAP vs NOT_ASSESSED without
    recomputing alignment."""
    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[_req("skill-gap", "Python", "80")],
        ),
        patch.object(
            assessment_service,
            "get_student_skill_scores",
            return_value={"skill-gap": Decimal(40)},
        ),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert len(result) == 1
    assert result[0]["status"] == "GAP"


def test_gap_entry_status_reflects_not_assessed_alignment():
    """A skill the student has never been assessed for at all -> 'status'
    is 'NOT_ASSESSED', not 'GAP'."""
    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[_req("skill-unassessed", "Docker", "50")],
        ),
        patch.object(assessment_service, "get_student_skill_scores", return_value={}),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(None, "student-1")
    assert len(result) == 1
    assert result[0]["status"] == "NOT_ASSESSED"


def test_pending_evaluation_does_not_fabricate_a_strong_skill_from_raw_percentage():
    """Phase 3D / Phase 3A integration regression: a COMPLETED attempt with
    a fabricated-looking raw percentage=100 but evaluation_status=PENDING
    must NOT make its skill look STRONG here -- get_aggregate_skill_gaps
    (unmocked) calls the real, unmocked assessment_service.get_student_skill_scores,
    so this proves the whole chain (which recommend_assessments and
    recommend_learning both consume via `analysis`) still honors the
    Phase 3A eligibility contract rather than reading raw percentage."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        {
            "percentage": "100.00",
            "evaluation_status": "PENDING",
            "final_percentage": None,
            "assessment": {"skill_id": "skill-1"},
        }
    ]
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response

    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[_req("skill-1", "Python", "80")],
        ),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(mock_client, "student-1")

    # The PENDING attempt contributes nothing, so skill-1 is NOT_ASSESSED
    # (never STRONG, despite the raw 100% sitting unused in that row).
    assert len(result) == 1
    assert result[0]["skill_id"] == "skill-1"
    assert result[0]["status"] == "NOT_ASSESSED"


def test_finalized_evaluation_changes_the_gap_state_via_final_percentage():
    """Once the same attempt's AI evaluation finalizes (COMPLETE,
    final_percentage=63.64, below the 80 required level), the skill
    becomes a GAP -- proving the pipeline reacts to the Phase 3A-corrected
    final_percentage, not a stale/cached value."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [
        {
            "percentage": "100.00",
            "evaluation_status": "COMPLETE",
            "final_percentage": "63.64",
            "assessment": {"skill_id": "skill-1"},
        }
    ]
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute
    ).return_value = response

    with (
        patch.object(
            career_role_service, "list_career_roles", return_value=[{"id": _ROLE_1}]
        ),
        patch.object(
            career_role_service,
            "get_career_role_requirements",
            return_value=[_req("skill-1", "Python", "80")],
        ),
    ):
        result = skill_recommendation_service.get_aggregate_skill_gaps(mock_client, "student-1")

    assert len(result) == 1
    assert result[0]["status"] == "GAP"


def test_never_writes_anything():
    import inspect

    src = inspect.getsource(skill_recommendation_service)
    for verb in (".insert(", ".update(", ".upsert(", ".delete("):
        assert verb not in src, f"skill_recommendation_service must not {verb}"


def test_never_uses_service_role():
    assert not hasattr(skill_recommendation_service, "get_supabase")
