"""Phase 5A offline tests for the existing opportunity recommendation agent.

Every provider/network boundary is mocked; no live Groq call, no live
Supabase, no DB write anywhere in this file. Style mirrors
tests/test_ai_course_recommendation.py (the Phase 4 reference), adapted
to the opportunity domain's real behavior -- not a blind copy.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai import exceptions
from app.ai.agents import opportunity_recommendation_agent as agent
from app.ai.client import GroqClient, build_strict_json_schema
from app.ai.config import AISettings
from app.ai.exceptions import AIProviderError
from app.ai.guardrails.opportunity_recommendation import (
    allowed_codes,
    deterministic_fallback,
    ground,
)
from app.ai.schemas.opportunity_recommendation import (
    OpportunityCandidate,
    OpportunityRecommendationLLMOutput,
)
from app.ai.tools import opportunity_candidates as candidates_module
from app.ai.tools import opportunity_tools
from app.main import app
from app.schemas.student_opportunity import (
    MatchSkill,
    OpportunityMatchResponse,
    StudentOpportunityDetail,
)
from app.schemas.student_recommendation import RecommendedOpportunity
from app.services import student_opportunity_service
from tests.conftest import authenticated_as

_TODAY = datetime.now(UTC).date()


def match_skill(skill_id="s1", **kwargs):
    defaults = {
        "skill_id": skill_id,
        "skill_name": "Python",
        "required_level": "Advanced",
        "importance": "CORE",
        "candidate_has": True,
        "candidate_level": "Intermediate",
        "candidate_verified": False,
        "status": "NEEDS_IMPROVEMENT",
    }
    defaults.update(kwargs)
    return MatchSkill(**defaults)


def match(opportunity_id="internship_op-1", **kwargs):
    defaults = {
        "opportunity_id": opportunity_id,
        "score": 80,
        "recommendation": "STRONG",
        "skill_coverage": "1 / 1",
        "required_count": 1,
        "matched_count": 1,
        "needs_improvement_count": 0,
        "missing_count": 0,
        "matched_skills": [match_skill()],
        "needs_improvement_skills": [],
        "missing_skills": [],
    }
    defaults.update(kwargs)
    return OpportunityMatchResponse(**defaults)


def opportunity(id="internship_op-1", **kwargs):
    defaults = {
        "id": id,
        "source_type": "INTERNSHIP",
        "title": "Backend Developer Intern",
        "description": "Build APIs.",
        "status": "PUBLISHED",
        "has_applied": False,
        "application_deadline": None,
        "skills": [],
    }
    defaults.update(kwargs)
    return StudentOpportunityDetail(**defaults)


def candidate(ref="OP1", opportunity_kwargs=None, match_kwargs=None, **kwargs):
    opp = opportunity(**(opportunity_kwargs or {}))
    m = match(opportunity_id=opp.id, **(match_kwargs or {}))
    return OpportunityCandidate(candidate_ref=ref, opportunity=opp, match=m, **kwargs)


def recommended_summary(id="internship_op-1", type_="INTERNSHIP", **kwargs):
    defaults = {
        "type": type_,
        "id": id,
        "title": "Backend Developer Intern",
        "description": "Build APIs.",
        "detail_path": f"/student/internships/{id}",
        "match_score": 80,
        "match_band": "STRONG",
        "matched_skill_count": 1,
        "required_skill_count": 1,
    }
    defaults.update(kwargs)
    return RecommendedOpportunity(**defaults)


def flat_output(refs=("OP1",), codes=("OP1: CANONICAL_SKILL_MATCH",), order=None):
    return OpportunityRecommendationLLMOutput(
        recommended_opportunity_refs=list(refs),
        recommendation_codes=list(codes),
        application_order=list(order if order is not None else refs),
    )


@pytest.fixture
def candidates():
    return [
        candidate("OP1", opportunity_kwargs={"id": "internship_a", "title": "Backend Intern"}),
        candidate("OP2", opportunity_kwargs={"id": "job_b", "title": "SQL Analyst", "source_type": "JOB"}),
    ]


# ============================================================
# A. Candidate construction (app.ai.tools.opportunity_candidates)
# ============================================================


def test_published_unapplied_opportunity_included():
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(
            student_opportunity_service, "get_opportunity", return_value=opportunity().model_dump()
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            return_value=match().model_dump(),
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    assert len(result) == 1
    assert result[0].candidate_ref == "OP1"
    assert result[0].opportunity.title == "Backend Developer Intern"


def test_unpublished_opportunity_excluded():
    detail = opportunity(status="CLOSED").model_dump()
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(student_opportunity_service, "get_opportunity", return_value=detail),
    ):
        assert candidates_module.get_candidates(MagicMock(), "student-1") == []


def test_already_applied_opportunity_excluded():
    """Matches the existing deterministic recommend_opportunities behavior,
    which already excludes applied postings -- Phase 5 must not diverge."""
    detail = opportunity(has_applied=True).model_dump()
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(student_opportunity_service, "get_opportunity", return_value=detail),
    ):
        assert candidates_module.get_candidates(MagicMock(), "student-1") == []


def test_expired_deadline_excluded():
    expired = (_TODAY - timedelta(days=1)).isoformat()
    detail = opportunity(application_deadline=expired).model_dump()
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(student_opportunity_service, "get_opportunity", return_value=detail),
    ):
        assert candidates_module.get_candidates(MagicMock(), "student-1") == []


def test_future_deadline_included():
    future = (_TODAY + timedelta(days=30)).isoformat()
    detail = opportunity(application_deadline=future).model_dump()
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(student_opportunity_service, "get_opportunity", return_value=detail),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            return_value=match().model_dump(),
        ),
    ):
        assert len(candidates_module.get_candidates(MagicMock(), "student-1")) == 1


def test_vanished_posting_dropped_not_errored():
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(student_opportunity_service, "get_opportunity", return_value=None),
    ):
        assert candidates_module.get_candidates(MagicMock(), "student-1") == []


def test_zero_skill_overlap_excluded_since_skills_may_have_changed():
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(
            student_opportunity_service, "get_opportunity", return_value=opportunity().model_dump()
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            return_value=match(matched_count=0, matched_skills=[]).model_dump(),
        ),
    ):
        assert candidates_module.get_candidates(MagicMock(), "student-1") == []


def test_identity_mismatch_between_summary_and_detail_raises():
    """A recommendation-service/detail-service disagreement is a bug, not
    a normal empty state -- it must never be silently swallowed into an
    AI-facing candidate."""
    mismatched = opportunity(id="internship_DIFFERENT").model_dump()
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(student_opportunity_service, "get_opportunity", return_value=mismatched),
        pytest.raises(ValueError),
    ):
        candidates_module.get_candidates(MagicMock(), "student-1")


def test_matching_failure_propagates_never_becomes_ai_data():
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(
            student_opportunity_service, "get_opportunity", return_value=opportunity().model_dump()
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            side_effect=RuntimeError("db exploded"),
        ),
        pytest.raises(RuntimeError),
    ):
        candidates_module.get_candidates(MagicMock(), "student-1")


def test_candidate_limit_enforced_at_twelve():
    summaries = [recommended_summary(id=f"internship_{n}") for n in range(20)]
    with (
        patch.object(opportunity_tools, "get_recommended_opportunities", return_value=summaries) as tool,
        patch.object(
            student_opportunity_service,
            "get_opportunity",
            side_effect=lambda client, sid, oid: opportunity(id=oid).model_dump(),
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            side_effect=lambda client, sid, oid: match(opportunity_id=oid).model_dump(),
        ),
    ):
        client = MagicMock()
        result = candidates_module.get_candidates(client, "student-1")
    tool.assert_called_once_with(client, "student-1", limit=candidates_module.MAX_CANDIDATES)
    assert len(result) == candidates_module.MAX_CANDIDATES == 12


def test_refs_are_deterministic_and_sequential():
    summaries = [recommended_summary(id=f"internship_{n}") for n in range(3)]
    with (
        patch.object(opportunity_tools, "get_recommended_opportunities", return_value=summaries),
        patch.object(
            student_opportunity_service,
            "get_opportunity",
            side_effect=lambda client, sid, oid: opportunity(id=oid).model_dump(),
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            side_effect=lambda client, sid, oid: match(opportunity_id=oid).model_dump(),
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    assert [c.candidate_ref for c in result] == ["OP1", "OP2", "OP3"]


def test_duplicate_summary_ids_deduplicated():
    summaries = [recommended_summary(), recommended_summary()]
    with (
        patch.object(opportunity_tools, "get_recommended_opportunities", return_value=summaries),
        patch.object(
            student_opportunity_service, "get_opportunity", return_value=opportunity().model_dump()
        ) as get_opp,
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            return_value=match().model_dump(),
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    assert len(result) == 1
    get_opp.assert_called_once()


def test_duplicate_titles_on_distinct_ids_do_not_collide():
    summaries = [recommended_summary(id="internship_a"), recommended_summary(id="job_b", type_="JOB")]
    with (
        patch.object(opportunity_tools, "get_recommended_opportunities", return_value=summaries),
        patch.object(
            student_opportunity_service,
            "get_opportunity",
            side_effect=lambda client, sid, oid: opportunity(
                id=oid, title="Same Title", source_type="JOB" if oid.startswith("job") else "INTERNSHIP"
            ).model_dump(),
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            side_effect=lambda client, sid, oid: match(opportunity_id=oid).model_dump(),
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    assert len(result) == 2
    assert result[0].opportunity.id != result[1].opportunity.id
    assert result[0].candidate_ref != result[1].candidate_ref


def test_internship_and_job_normalize_through_the_same_detail_schema():
    internship_summary = recommended_summary(id="internship_a", type_="INTERNSHIP")
    job_summary = recommended_summary(id="job_b", type_="JOB")
    with (
        patch.object(
            opportunity_tools,
            "get_recommended_opportunities",
            return_value=[internship_summary, job_summary],
        ),
        patch.object(
            student_opportunity_service,
            "get_opportunity",
            side_effect=lambda client, sid, oid: opportunity(
                id=oid,
                source_type="JOB" if oid.startswith("job") else "INTERNSHIP",
                employment_type="Full-time" if oid.startswith("job") else None,
                duration_months=3 if oid.startswith("internship") else None,
            ).model_dump(),
        ),
        patch.object(
            student_opportunity_service,
            "compute_opportunity_match",
            side_effect=lambda client, sid, oid: match(opportunity_id=oid).model_dump(),
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    by_type = {c.opportunity.source_type: c for c in result}
    assert by_type["INTERNSHIP"].opportunity.duration_months == 3
    assert by_type["JOB"].opportunity.employment_type == "Full-time"


def test_match_score_and_band_preserved_exactly():
    exact_match = match(score=57, recommendation="PARTIAL")
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(
            student_opportunity_service, "get_opportunity", return_value=opportunity().model_dump()
        ),
        patch.object(
            student_opportunity_service, "compute_opportunity_match", return_value=exact_match.model_dump()
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    assert result[0].match.score == 57
    assert result[0].match.recommendation == "PARTIAL"


def test_matched_missing_improvement_lists_preserved():
    detailed = match(
        matched_skills=[match_skill("a", skill_name="Python")],
        needs_improvement_skills=[match_skill("b", skill_name="SQL", status="NEEDS_IMPROVEMENT")],
        missing_skills=[match_skill("c", skill_name="Docker", candidate_has=False, status="MISSING")],
        matched_count=1,
        needs_improvement_count=1,
        missing_count=1,
    )
    with (
        patch.object(
            opportunity_tools, "get_recommended_opportunities", return_value=[recommended_summary()]
        ),
        patch.object(
            student_opportunity_service, "get_opportunity", return_value=opportunity().model_dump()
        ),
        patch.object(
            student_opportunity_service, "compute_opportunity_match", return_value=detailed.model_dump()
        ),
    ):
        result = candidates_module.get_candidates(MagicMock(), "student-1")
    m = result[0].match
    assert [s.skill_name for s in m.matched_skills] == ["Python"]
    assert [s.skill_name for s in m.needs_improvement_skills] == ["SQL"]
    assert [s.skill_name for s in m.missing_skills] == ["Docker"]


# ============================================================
# OpportunityCandidate model-level invariants
# ============================================================


def test_candidate_rejects_unpublished_or_applied_defensively():
    with pytest.raises(ValidationError):
        candidate(opportunity_kwargs={"status": "CLOSED"})
    with pytest.raises(ValidationError):
        candidate(opportunity_kwargs={"has_applied": True})


def test_candidate_rejects_identity_mismatch():
    with pytest.raises(ValidationError):
        OpportunityCandidate(
            candidate_ref="OP1", opportunity=opportunity(id="internship_a"), match=match(opportunity_id="internship_b")
        )


# ============================================================
# B. LLM output schema
# ============================================================


def test_llm_output_schema_is_flat_with_no_defs():
    schema = build_strict_json_schema(OpportunityRecommendationLLMOutput)
    assert "$defs" not in schema
    assert "$ref" not in str(schema)
    assert schema["additionalProperties"] is False
    assert len(schema["properties"]) == 3
    for field in schema["properties"].values():
        assert field["type"] == "array"
        assert field["items"]["type"] == "string"


def test_llm_output_forbids_unknown_extra_fields():
    with pytest.raises(ValidationError):
        OpportunityRecommendationLLMOutput.model_validate(
            {**flat_output().model_dump(), "extra_field": "x"}
        )


@pytest.mark.parametrize(
    "field",
    [
        "match_score",
        "match_band",
        "company",
        "title",
        "location",
        "salary",
        "salary_min",
        "salary_max",
        "stipend",
        "stipend_amount",
        "application_status",
        "has_applied",
        "opportunity_id",
        "work_mode",
        "deadline",
        "application_deadline",
        "required_skills",
        "matched_skills",
        "eligibility_criteria",
    ],
)
def test_canonical_fields_cannot_be_supplied_by_the_model(field):
    with pytest.raises(ValidationError):
        OpportunityRecommendationLLMOutput.model_validate({**flat_output().model_dump(), field: "invented"})


def test_llm_output_caps_list_length_at_bounds():
    with pytest.raises(ValidationError):
        OpportunityRecommendationLLMOutput.model_validate(
            {
                "recommended_opportunity_refs": [f"OP{n}" for n in range(13)],
                "recommendation_codes": [],
                "application_order": [],
            }
        )


# ============================================================
# C. Guardrails
# ============================================================


def test_valid_ref_and_code_resolves(candidates):
    index = {c.candidate_ref: c for c in candidates}
    output = flat_output(codes=["OP1: CANONICAL_SKILL_MATCH"])
    recs, _plan = ground(output, candidates, target_role=None)
    assert len(recs) == 1
    assert recs[0].candidate_ref == "OP1"
    assert recs[0].opportunity == index["OP1"].opportunity
    assert recs[0].match == index["OP1"].match


def test_unknown_ref_rejected(candidates):
    output = flat_output(refs=["OP99"], codes=["OP99: CANONICAL_SKILL_MATCH"])
    recs, plan = ground(output, candidates, target_role=None)
    assert recs == [] and plan == []


def test_duplicate_ref_in_recommended_list_deduplicated(candidates):
    output = OpportunityRecommendationLLMOutput(
        recommended_opportunity_refs=["OP1", "OP1"],
        recommendation_codes=["OP1: CANONICAL_SKILL_MATCH"],
        application_order=["OP1", "OP1"],
    )
    recs, plan = ground(output, candidates, target_role=None)
    assert len(recs) == 1
    assert len(plan) == 1


def test_invalid_reason_code_name_rejected(candidates):
    output = flat_output(codes=["OP1: FREE_LUNCH_PROVIDED"])
    recs, _plan = ground(output, candidates, target_role=None)
    assert recs == []


def test_conditionally_invalid_reason_code_rejected(candidates):
    """STRONG_CANONICAL_MATCH is a real code, but this candidate's band
    is not STRONG -- the code must be rejected even though it's spelled
    correctly and refers to a real candidate."""
    weak = [candidate("OP1", match_kwargs={"recommendation": "LOW", "score": 10})]
    output = flat_output(codes=["OP1: STRONG_CANONICAL_MATCH"])
    recs, _plan = ground(output, weak, target_role=None)
    assert recs == []


def test_verified_skill_alignment_requires_real_verification(candidates):
    output = flat_output(codes=["OP1: VERIFIED_SKILL_ALIGNMENT"])
    # candidates fixture has candidate_verified=False on its only matched skill.
    recs, _plan = ground(output, candidates, target_role=None)
    assert recs == []

    verified = [
        candidate("OP1", match_kwargs={"matched_skills": [match_skill(candidate_verified=True)]})
    ]
    recs2, _plan2 = ground(output, verified, target_role=None)
    assert len(recs2) == 1


def test_target_role_alignment_requires_lexical_match_in_title():
    aligned = [candidate("OP1", opportunity_kwargs={"title": "Backend Developer Intern"})]
    output = flat_output(codes=["OP1: TARGET_ROLE_ALIGNMENT"])
    recs, _plan = ground(output, aligned, target_role="Backend Developer")
    assert len(recs) == 1
    recs2, _plan2 = ground(output, aligned, target_role="Data Scientist")
    assert recs2 == []


def test_metadata_and_match_evidence_are_server_attached_not_llm_supplied(candidates):
    output = flat_output(codes=["OP1: CANONICAL_SKILL_MATCH"])
    recs, _plan = ground(output, candidates, target_role=None)
    rec = recs[0]
    assert rec.opportunity.title == candidates[0].opportunity.title
    assert rec.match.score == candidates[0].match.score
    assert rec.metadata_source == candidates[0].metadata_source


def test_fabricated_application_state_is_impossible(candidates):
    """There is no application-state field anywhere in the LLM schema;
    the response's opportunity.has_applied always comes from the
    candidate, which is only ever constructed for unapplied postings."""
    output = flat_output(codes=["OP1: CANONICAL_SKILL_MATCH"])
    recs, _plan = ground(output, candidates, target_role=None)
    assert recs[0].opportunity.has_applied is False
    # An attempt to smuggle a status via the code channel is just an
    # unknown/invalid code and is dropped like any other.
    bad = flat_output(codes=["OP1: APPLICATION_STATUS_SELECTED"])
    recs2, _ = ground(bad, candidates, target_role=None)
    assert recs2 == []


def test_application_order_never_omits_an_accepted_recommendation(candidates):
    output = OpportunityRecommendationLLMOutput(
        recommended_opportunity_refs=["OP1", "OP2"],
        recommendation_codes=["OP1: CANONICAL_SKILL_MATCH", "OP2: CANONICAL_SKILL_MATCH"],
        application_order=["OP2"],
    )
    recs, plan = ground(output, candidates, target_role=None)
    assert {p.opportunity_id for p in plan} == {r.opportunity.id for r in recs}


def test_allowed_codes_reflects_only_true_canonical_conditions(candidates):
    codes = allowed_codes(candidates[0], target_role=None)
    assert "CANONICAL_SKILL_MATCH" in codes
    assert "STRONG_CANONICAL_MATCH" in codes  # fixture band is STRONG
    assert "VERIFIED_SKILL_ALIGNMENT" not in codes  # fixture skill is unverified


def test_grounding_all_rejected_yields_empty_not_fabricated(candidates):
    output = flat_output(refs=["OP99"], codes=["OP99: CANONICAL_SKILL_MATCH"], order=["OP99"])
    recs, plan = ground(output, candidates, target_role=None)
    assert recs == [] and plan == []


def test_deterministic_fallback_preserves_candidate_order_with_no_ai_rationale(candidates):
    recs, plan = deterministic_fallback(candidates)
    assert [r.candidate_ref for r in recs] == ["OP1", "OP2"]
    assert all(r.reason_codes == [] for r in recs)
    assert [p.opportunity_id for p in plan] == [c.opportunity.id for c in candidates]


# ============================================================
# D. Agent orchestration
# ============================================================


def test_agent_input_excludes_identity_and_is_bounded(candidates):
    data = agent.build_agent_input(candidates, target_role="Backend Developer")
    payload = data.model_dump_json()
    for excluded in ("student_id", "email", "phone", "portfolio", "application_history"):
        assert excluded not in payload
    assert data.opportunity_candidates[0].ref == "OP1"
    assert set(data.opportunity_candidates[0].allowed_reason_codes) == set(
        allowed_codes(candidates[0], "Backend Developer")
    )


def test_no_candidates_skips_groq_entirely():
    with (
        patch.object(candidates_module, "get_candidates", return_value=[]),
        patch.object(agent.groq_client, "complete_structured") as llm,
    ):
        result = agent.recommend_opportunities(MagicMock(), "student-1")
    llm.assert_not_called()
    assert result.meta.ranking_status == "NO_CANDIDATES"
    assert result.recommendations == []


def test_deterministic_baseline_exists_before_groq_is_ever_called(candidates):
    """Even if we never inspected the mocked call, the response already
    contains the real candidates if Groq fails -- proving the fallback
    is the baseline, not a reaction."""
    with (
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(agent.groq_client, "complete_structured", side_effect=AIProviderError("down")),
    ):
        result = agent.recommend_opportunities(MagicMock(), "student-1")
    assert [r.candidate_ref for r in result.recommendations] == ["OP1", "OP2"]
    assert result.meta.ai_available is False
    assert result.meta.ranking_status == "DETERMINISTIC"


def test_successful_groq_ranking_reorders_and_marks_ai_available(candidates):
    output = flat_output(
        refs=["OP2", "OP1"],
        codes=["OP2: CANONICAL_SKILL_MATCH", "OP1: CANONICAL_SKILL_MATCH"],
        order=["OP2", "OP1"],
    )
    with (
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(agent.groq_client, "complete_structured", return_value=output) as llm,
    ):
        result = agent.recommend_opportunities(MagicMock(), "student-1")
    llm.assert_called_once()
    assert result.meta.ai_available is True
    assert result.meta.ranking_status == "AI"
    assert [r.candidate_ref for r in result.recommendations] == ["OP2", "OP1"]


@pytest.mark.parametrize(
    "failure", ["AIConfigurationError", "AIProviderError", "AIResponseError", "AIStructuredOutputError"]
)
def test_groq_or_malformed_output_failure_falls_back_to_deterministic(failure, candidates):
    with (
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(
            agent.groq_client,
            "complete_structured",
            side_effect=getattr(exceptions, failure)("private detail"),
        ),
    ):
        result = agent.recommend_opportunities(MagicMock(), "student-1")
    assert [r.candidate_ref for r in result.recommendations] == ["OP1", "OP2"]
    assert result.meta.ai_available is False
    assert "private detail" not in result.model_dump_json()


def test_grounding_leaves_no_valid_items_keeps_deterministic_fallback(candidates):
    ungroundable = flat_output(refs=["OP99"], codes=["OP99: CANONICAL_SKILL_MATCH"], order=["OP99"])
    with (
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(agent.groq_client, "complete_structured", return_value=ungroundable),
    ):
        result = agent.recommend_opportunities(MagicMock(), "student-1")
    assert [r.candidate_ref for r in result.recommendations] == ["OP1", "OP2"]
    assert result.meta.ai_available is False
    assert "could not be grounded" in result.meta.message


def test_target_role_is_read_once_and_only_when_candidates_exist():
    with (
        patch.object(candidates_module, "get_candidates", return_value=[]),
        patch.object(agent.skill_tools, "get_target_job_role") as target,
    ):
        agent.recommend_opportunities(MagicMock(), "student-1")
    target.assert_not_called()


def test_populated_agent_runs_real_client_validation_with_mocked_network(candidates):
    client = GroqClient(AISettings(groq_api_key="test-only"))
    completion = MagicMock()
    completion.choices[0].message.content = flat_output().model_dump_json()
    with (
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(agent, "groq_client", client),
        patch.object(client, "_create_completion", return_value=completion) as network,
    ):
        result = agent.recommend_opportunities(MagicMock(), "student-1")
    assert result.meta.ai_available is True
    assert network.call_args.kwargs["response_format"]["type"] == "json_schema"
    payload = json.loads(network.call_args.kwargs["messages"][1]["content"])
    assert payload["opportunity_candidates"][0]["ref"] == "OP1"
    assert "email" not in payload and "student_id" not in payload


# ============================================================
# E. API — POST /api/v1/ai/opportunity-recommendations
# ============================================================


def test_api_requires_authentication():
    assert TestClient(app).post("/api/v1/ai/opportunity-recommendations").status_code == 401


@pytest.mark.parametrize("role", ["INDUSTRY", "INSTITUTION", "FACULTY", "ADMIN", None])
def test_api_requires_student_role(role):
    with authenticated_as(role):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_api_uses_authenticated_user_id_never_a_supplied_one(candidates):
    with (
        authenticated_as("STUDENT", user_id="authenticated-student"),
        patch.object(candidates_module, "get_candidates", return_value=candidates) as get_c,
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(agent.groq_client, "complete_structured", side_effect=AIProviderError("x")),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations?student_id=victim",
            json={"student_id": "victim"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert get_c.call_args.args[1] == "authenticated-student"
    assert "victim" not in response.text


def test_api_success_returns_ranked_recommendations(candidates):
    output = flat_output(codes=["OP1: CANONICAL_SKILL_MATCH"])
    with (
        authenticated_as("STUDENT"),
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(agent.groq_client, "complete_structured", return_value=output),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["ai_available"] is True
    assert len(body["recommendations"]) == 1


def test_api_groq_failure_returns_deterministic_recommendations_at_200(candidates):
    with (
        authenticated_as("STUDENT"),
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(
            agent.groq_client, "complete_structured", side_effect=AIProviderError("gsk_SECRET_TOKEN")
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["ai_available"] is False
    assert len(body["recommendations"]) == 2
    assert "gsk_SECRET_TOKEN" not in response.text


def test_api_no_candidates_returns_empty_not_an_error():
    with authenticated_as("STUDENT"), patch.object(candidates_module, "get_candidates", return_value=[]):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["recommendations"] == []
    assert response.json()["meta"]["ranking_status"] == "NO_CANDIDATES"


def test_api_unexpected_candidate_failure_is_a_safe_generic_500():
    with (
        authenticated_as("STUDENT"),
        patch.object(
            candidates_module, "get_candidates", side_effect=RuntimeError("internal secret detail")
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 500
    assert "internal secret detail" not in response.text


def test_api_never_leaks_raw_provider_exception_text(candidates):
    with (
        authenticated_as("STUDENT"),
        patch.object(candidates_module, "get_candidates", return_value=candidates),
        patch.object(agent.skill_tools, "get_target_job_role", return_value=None),
        patch.object(
            agent.groq_client,
            "complete_structured",
            side_effect=AIProviderError("upstream said: leaked-secret-xyz"),
        ),
    ):
        response = TestClient(app).post(
            "/api/v1/ai/opportunity-recommendations", headers={"Authorization": "Bearer token"}
        )
    assert "leaked-secret-xyz" not in response.text


def test_route_registered_exactly_once_no_doubling():
    schema = TestClient(app).get("/openapi.json").json()
    assert "/api/v1/ai/opportunity-recommendations" in schema["paths"]
    assert "/api/v1/ai/ai/opportunity-recommendations" not in schema["paths"]
    assert list(schema["paths"]["/api/v1/ai/opportunity-recommendations"].keys()) == ["post"]
