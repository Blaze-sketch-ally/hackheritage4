"""Tests for the Question Bank + review workflow API (Phase 1K):
database/migrations/015_question_bank_random_assessment.sql,
app.schemas.question_bank, app.services.question_bank_service,
app.api.questions.

No live Supabase project or real token is used anywhere in this file --
tests mock the auth dependency chain (see conftest.py) and, where
appropriate, the Supabase client/service layer directly, matching the
pattern established in test_assessments.py/test_attempts.py.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import ValidationError

from app.main import app
from app.schemas.assessment import AssessmentQuestionResponse
from app.schemas.faculty_permissions import AssessmentCapability
from app.schemas.question_bank import (
    BlueprintRuleRequest,
    BlueprintUpsertRequest,
    QuestionBankResponse,
    QuestionCreateRequest,
    QuestionUpdateRequest,
)
from app.services import question_bank_service
from tests.conftest import authenticated_as

client = TestClient(app)

_AUTHOR = {AssessmentCapability.AUTHOR}
_REVIEWER = {AssessmentCapability.REVIEWER}


def _as_author():
    """Phase F5A: create_question/update_question now require
    assessment_author (041_assessment_capability_authorization.sql) --
    every test exercising those routes must mock the caller as holding
    it, exactly like test_faculty_permissions.py's own capability tests."""
    return patch(
        "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
        return_value=_AUTHOR,
    )


def _as_reviewer():
    """Phase F5A: approve_question/reject_question now require
    assessment_reviewer."""
    return patch(
        "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
        return_value=_REVIEWER,
    )


# ============================================================
# Schemas (no client/HTTP at all)
# ============================================================


def _valid_create_payload(**overrides) -> dict:
    payload = {
        "assessment_id": str(uuid4()),
        "question_text": "What is 2 + 2?",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "options": [
            {"option_text": "3", "display_order": 0},
            {"option_text": "4", "display_order": 1},
        ],
    }
    payload.update(overrides)
    return payload


def test_question_create_request_accepts_valid_payload():
    QuestionCreateRequest(**_valid_create_payload())


def test_question_create_request_rejects_unknown_field():
    with pytest.raises(ValidationError):
        QuestionCreateRequest(**_valid_create_payload(review_status="APPROVED"))


def test_question_create_request_rejects_created_by_override():
    """created_by must never be settable by the client -- it's always
    current_user.id, and this field simply doesn't exist on the model."""
    with pytest.raises(ValidationError):
        QuestionCreateRequest(**_valid_create_payload(created_by=str(uuid4())))


def test_question_bank_response_never_gains_answer_key_style_fields_on_the_student_schema():
    """The student-facing AssessmentQuestionResponse (Phase 1D/1J) must
    never gain review_status/created_by/answer_key -- QuestionBankResponse
    (faculty-only) is a structurally separate model, not a subclass or
    extension of it."""
    for leaking_field in ("review_status", "created_by", "answer_key", "is_active"):
        assert leaking_field not in AssessmentQuestionResponse.model_fields
    for expected_field in ("review_status", "created_by", "answer_key", "is_active"):
        assert expected_field in QuestionBankResponse.model_fields


def test_question_create_request_accepts_new_optional_metadata_fields():
    """Phase F6.1-F6.3: learning_objective/estimated_time_minutes are
    optional, additive fields -- present or absent, both are valid."""
    with_metadata = QuestionCreateRequest(
        **_valid_create_payload(learning_objective="Recall basic facts.", estimated_time_minutes=3)
    )
    assert with_metadata.learning_objective == "Recall basic facts."
    assert with_metadata.estimated_time_minutes == 3


def test_question_create_request_new_metadata_fields_default_to_none():
    """Existing callers that never heard of F6 must keep working
    unchanged -- omitting the new fields is always valid."""
    request = QuestionCreateRequest(**_valid_create_payload())
    assert request.learning_objective is None
    assert request.estimated_time_minutes is None


def test_question_create_request_rejects_correct_option_id_not_in_submitted_options():
    """Phase F6.3: the one answer-key/option coherence check safe to
    enforce from a single request's own payload -- a correct_option_ids
    entry that isn't one of the options in THIS SAME payload is always
    invalid, regardless of database state."""
    foreign_id = str(uuid4())
    with pytest.raises(ValidationError):
        QuestionCreateRequest(
            **_valid_create_payload(answer_key={"correct_option_ids": [foreign_id]})
        )


def test_question_create_request_accepts_correct_option_id_matching_submitted_option():
    payload = _valid_create_payload()
    matching_id = str(uuid4())
    payload["options"][1]["id"] = matching_id
    QuestionCreateRequest(**payload, answer_key={"correct_option_ids": [matching_id]})


def test_question_update_request_rejects_correct_option_id_not_in_submitted_options():
    with pytest.raises(ValidationError):
        QuestionUpdateRequest(
            options=[{"id": str(uuid4()), "option_text": "A", "display_order": 0}],
            answer_key={"correct_option_ids": [str(uuid4())]},
        )


def test_question_update_request_partial_edit_without_options_or_answer_key_is_unaffected():
    """Critical regression: the new F6.3 cross-field validator must NEVER
    require a complete answer key on a PATCH that doesn't touch options
    or the answer key at all -- that would silently break the existing,
    intentional partial-draft-editing workflow (015's own documented
    design). Touching only unrelated fields must remain valid."""
    QuestionUpdateRequest(points="2.00")
    QuestionUpdateRequest(learning_objective="Just updating this one field.")
    QuestionUpdateRequest(estimated_time_minutes=10)


def test_question_update_request_answer_key_only_patch_is_unaffected_by_missing_options():
    """A PATCH supplying only a NEW answer_key, leaving previously-saved
    options untouched (omitted, not resubmitted), has nothing in THIS
    payload to cross-check against -- must remain valid at the schema
    layer. (The corresponding stale-reference case, where an
    out-of-band options change leaves an old answer key referencing a
    now-foreign option, is exactly what the DB-side approval-readiness
    guard in 043_question_authoring_metadata.sql exists to catch --
    see the live integration test
    test_approve_blocked_when_correct_option_ids_reference_a_foreign_option.)"""
    QuestionUpdateRequest(answer_key={"correct_option_ids": [str(uuid4())]})


def test_question_bank_response_includes_new_f6_metadata_fields():
    for expected_field in ("learning_objective", "estimated_time_minutes"):
        assert expected_field in QuestionBankResponse.model_fields


def test_blueprint_rule_request_rejects_zero_or_negative_count():
    with pytest.raises(ValidationError):
        BlueprintRuleRequest(difficulty="Beginner", question_count=0)
    with pytest.raises(ValidationError):
        BlueprintRuleRequest(difficulty="Beginner", question_count=-1)


def test_blueprint_upsert_request_rejects_duplicate_difficulty():
    with pytest.raises(ValidationError):
        BlueprintUpsertRequest(
            rules=[
                {"difficulty": "Beginner", "question_count": 5},
                {"difficulty": "Beginner", "question_count": 3},
            ]
        )


def test_blueprint_upsert_request_accepts_one_rule_per_difficulty():
    BlueprintUpsertRequest(
        rules=[
            {"difficulty": "Beginner", "question_count": 8},
            {"difficulty": "Intermediate", "question_count": 7},
            {"difficulty": "Advanced", "question_count": 5},
        ]
    )


# ============================================================
# Service layer (mocked Supabase client)
# ============================================================


def _row_question(**overrides) -> dict:
    row = {
        "id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "question_text": "What is 2 + 2?",
        "question_type": "MCQ",
        "scoring_method": "OBJECTIVE",
        "difficulty": "Beginner",
        "points": "1.00",
        "display_order": 0,
        "learning_objective": None,
        "estimated_time_minutes": None,
        "review_status": "PENDING",
        "is_active": True,
        "created_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "options": [],
        "answer_key": None,
    }
    row.update(overrides)
    return row


def test_service_create_question_sends_pending_and_created_by():
    """Confirms exactly what WE send -- review_status is always forced to
    PENDING and created_by is always the caller's own id, regardless of
    what the payload dict might otherwise contain, mirroring the RLS WITH
    CHECK as defense in depth."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = [_row_question()]
    mock_client.table.return_value.insert.return_value.execute.return_value = response

    payload = {"question_text": "x", "question_type": "MCQ"}
    question_bank_service.create_question(mock_client, "faculty-a", payload)

    inserted = mock_client.table.return_value.insert.call_args[0][0]
    assert inserted["created_by"] == "faculty-a"
    assert inserted["review_status"] == "PENDING"


def test_service_update_question_returns_none_when_rls_denies():
    """A row RLS makes invisible to this UPDATE (not owned, not PENDING)
    simply matches zero rows -- not an exception -- and the route layer
    must turn that into a 404."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = []
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = response

    result = question_bank_service.update_question(mock_client, uuid4(), {"points": "2.00"})
    assert result is None


def test_service_set_review_status_calls_review_question_rpc():
    """Phase 1K bug fix (016_review_question_rpc.sql): approve/reject go
    through the review_question() RPC, not a plain table update -- see
    that migration's header comment for why a plain RLS-gated UPDATE
    unreliably rejected this exact transition on the real database."""
    mock_client = MagicMock()
    response = MagicMock()
    response.data = _row_question(review_status="APPROVED")
    mock_client.rpc.return_value.execute.return_value = response

    question_id = uuid4()
    question_bank_service.set_review_status(mock_client, question_id, "APPROVED")

    mock_client.rpc.assert_called_once_with(
        "review_question",
        {"p_question_id": str(question_id), "p_decision": "APPROVED"},
    )


def test_service_set_review_status_translates_42501_to_own_question_error():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "42501", "message": "Cannot review your own question."}
    )
    with pytest.raises(question_bank_service.OwnQuestionReviewError):
        question_bank_service.set_review_status(mock_client, uuid4(), "APPROVED")


def test_service_set_review_status_translates_55000_to_not_pending_error():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "55000", "message": "Question is not pending review."}
    )
    with pytest.raises(question_bank_service.QuestionNotPendingError):
        question_bank_service.set_review_status(mock_client, uuid4(), "APPROVED")


def test_service_set_review_status_translates_55001_to_not_approvable_error():
    """Phase F6.3: review_question()'s new approval-readiness guard
    (043_question_authoring_metadata.sql) raises SQLSTATE 55001 when the
    question isn't yet structurally scoreable -- must translate to a
    dedicated typed error, same pattern as every other RPC error code
    this function already handles."""
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "55001", "message": "Cannot approve question: no answer key exists."}
    )
    with pytest.raises(question_bank_service.QuestionNotApprovableError):
        question_bank_service.set_review_status(mock_client, uuid4(), "APPROVED")


def test_service_set_review_status_translates_p0002_to_none():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.side_effect = APIError(
        {"code": "P0002", "message": "Question not found."}
    )
    assert question_bank_service.set_review_status(mock_client, uuid4(), "APPROVED") is None


def test_service_replace_options_deletes_then_inserts():
    mock_client = MagicMock()
    question_id = uuid4()
    question_bank_service.replace_options(
        mock_client, question_id, [{"option_text": "A", "display_order": 0}]
    )

    mock_client.table.return_value.delete.return_value.eq.assert_called_once_with(
        "question_id", str(question_id)
    )
    inserted = mock_client.table.return_value.insert.call_args[0][0]
    assert inserted == [{"option_text": "A", "display_order": 0, "question_id": str(question_id)}]


def test_service_replace_blueprint_deletes_then_inserts():
    mock_client = MagicMock()
    assessment_id = uuid4()
    question_bank_service.replace_blueprint(
        mock_client, assessment_id, [{"difficulty": "Beginner", "question_count": 8}]
    )

    mock_client.table.return_value.delete.return_value.eq.assert_called_once_with(
        "assessment_id", str(assessment_id)
    )
    inserted = mock_client.table.return_value.insert.call_args[0][0]
    assert inserted == [
        {"difficulty": "Beginner", "question_count": 8, "assessment_id": str(assessment_id)}
    ]


# ============================================================
# Route layer: AUTH
# ============================================================


def test_list_questions_missing_token_returns_401():
    response = client.get("/api/v1/questions")
    assert response.status_code == 401


def test_list_questions_student_forbidden():
    with authenticated_as("STUDENT"):
        response = client.get("/api/v1/questions", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_create_question_student_forbidden():
    with authenticated_as("STUDENT"):
        response = client.post(
            "/api/v1/questions",
            json=_valid_create_payload(),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["INDUSTRY", "INSTITUTION", "ADMIN"])
def test_question_routes_forbidden_for_other_non_faculty_roles(role):
    with authenticated_as(role):
        response = client.get("/api/v1/questions", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403


def test_question_routes_allowed_for_faculty():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        patch.object(question_bank_service, "list_my_questions", return_value=[]),
    ):
        response = client.get("/api/v1/questions", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json() == []


# ============================================================
# Route layer: create / read / update
# ============================================================


def test_create_question_creates_row_options_and_answer_key():
    question_row = _row_question()
    payload = _valid_create_payload()
    # Phase F6.3's cross-field validator requires correct_option_ids to
    # reference an id present in THIS SAME payload's options -- give the
    # second option an explicit client-generated id and point the answer
    # key at it, matching how the frontend actually builds this request.
    matching_id = str(uuid4())
    payload["options"][1]["id"] = matching_id
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_author(),
        patch.object(
            question_bank_service, "create_question", return_value=question_row
        ) as mock_create,
        patch.object(question_bank_service, "replace_options", return_value=[]) as mock_options,
        patch.object(
            question_bank_service, "upsert_answer_key", return_value={}
        ) as mock_answer_key,
        patch.object(question_bank_service, "get_my_question", return_value=question_row),
    ):
        response = client.post(
            "/api/v1/questions",
            json={**payload, "answer_key": {"correct_option_ids": [matching_id]}},
            headers={"Authorization": "Bearer token"},
        )

    assert response.status_code == 201
    assert mock_create.call_args[0][1] == "faculty-a"
    mock_options.assert_called_once()
    mock_answer_key.assert_called_once()


def test_create_question_never_accepts_review_status_override():
    """extra="forbid" on QuestionCreateRequest rejects this at the
    validation layer, before any handler code runs -- 422, never a
    silently-approved question."""
    with authenticated_as("FACULTY", user_id="faculty-a"), _as_author():
        response = client.post(
            "/api/v1/questions",
            json=_valid_create_payload(review_status="APPROVED"),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_create_question_denied_without_author_capability():
    """Phase F5A: a plain FACULTY account with no assessment_author grant
    must be denied at the dependency layer, before ever reaching the
    service."""
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value=set(),
        ),
        patch.object(question_bank_service, "create_question") as mock_create,
    ):
        response = client.post(
            "/api/v1/questions",
            json=_valid_create_payload(),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    mock_create.assert_not_called()


def test_create_question_denied_with_only_reviewer_capability():
    """assessment_reviewer alone must not imply assessment_author --
    the two capabilities are independent, matching
    test_capability_dependencies_do_not_imply_other_capabilities in
    test_faculty_permissions.py."""
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_reviewer(),
        patch.object(question_bank_service, "create_question") as mock_create,
    ):
        response = client.post(
            "/api/v1/questions",
            json=_valid_create_payload(),
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    mock_create.assert_not_called()


def test_get_question_not_visible_returns_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        patch.object(question_bank_service, "get_my_question", return_value=None),
    ):
        response = client.get(
            f"/api/v1/questions/{uuid4()}", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_update_question_rls_denial_returns_403():
    """A trigger rejection (prevent_unauthorized_question_review, code
    42501) -- e.g. a reviewer trying to change content, or anyone trying
    to edit an approved question -- must surface as 403, not a generic
    500."""
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_author(),
        patch.object(
            question_bank_service,
            "update_question",
            side_effect=APIError({"code": "42501", "message": "Reviewers may only change review_status."}),
        ),
    ):
        response = client.patch(
            f"/api/v1/questions/{uuid4()}",
            json={"question_text": "edited"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403


def test_update_question_denied_without_author_capability():
    """Phase F5A: PATCH .../questions/{id} now requires assessment_author."""
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value=set(),
        ),
        patch.object(question_bank_service, "update_question") as mock_update,
    ):
        response = client.patch(
            f"/api/v1/questions/{uuid4()}",
            json={"points": "2.00"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 403
    mock_update.assert_not_called()


def test_update_question_rejects_review_status_other_than_pending():
    """422 before any handler code runs -- approve/reject only go through
    the dedicated routes, never through PATCH's review_status field."""
    with authenticated_as("FACULTY", user_id="faculty-a"), _as_author():
        response = client.patch(
            f"/api/v1/questions/{uuid4()}",
            json={"review_status": "APPROVED"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422


def test_update_question_resubmit_sends_pending_review_status():
    """The one intended use of review_status in PATCH: a creator resubmits
    a REJECTED question by setting it back to PENDING."""
    updated_row = _row_question(review_status="PENDING")
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_author(),
        patch.object(
            question_bank_service, "update_question", return_value=updated_row
        ) as mock_update,
        patch.object(question_bank_service, "get_my_question", return_value=updated_row),
    ):
        response = client.patch(
            f"/api/v1/questions/{uuid4()}",
            json={"review_status": "PENDING"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert mock_update.call_args[0][2] == {"review_status": "PENDING"}


def test_update_question_metadata_only_patch_does_not_touch_options_or_answer_key():
    """Phase F6.1-F6.3 regression: PATCHing only the new metadata fields
    must behave exactly like PATCHing only `points` already does --
    options/replace_options and upsert_answer_key must never be called
    for a payload that never mentioned them."""
    updated_row = _row_question(learning_objective="Updated.", estimated_time_minutes=7)
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_author(),
        patch.object(
            question_bank_service, "update_question", return_value=updated_row
        ) as mock_update,
        patch.object(question_bank_service, "get_my_question", return_value=updated_row),
        patch.object(question_bank_service, "replace_options") as mock_options,
        patch.object(question_bank_service, "upsert_answer_key") as mock_answer_key,
        patch.object(question_bank_service, "clear_answer_key") as mock_clear,
    ):
        response = client.patch(
            f"/api/v1/questions/{uuid4()}",
            json={"learning_objective": "Updated.", "estimated_time_minutes": 7},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 200
    assert mock_update.call_args[0][2] == {
        "learning_objective": "Updated.",
        "estimated_time_minutes": 7,
    }
    mock_options.assert_not_called()
    mock_answer_key.assert_not_called()
    mock_clear.assert_not_called()


def test_update_question_not_visible_returns_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_author(),
        patch.object(question_bank_service, "update_question", return_value=None),
    ):
        response = client.patch(
            f"/api/v1/questions/{uuid4()}",
            json={"points": "2.00"},
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 404


# ============================================================
# Route layer: review (approve/reject)
# ============================================================


def test_approve_own_question_returns_403():
    """review_question() rejects a setter approving their own question --
    this test confirms the route maps that rejection to 403, not that the
    RPC itself is exercised (that's the real Supabase verification's
    job)."""
    with (
        authenticated_as("FACULTY", user_id="faculty-a"),
        _as_reviewer(),
        patch.object(
            question_bank_service,
            "set_review_status",
            side_effect=question_bank_service.OwnQuestionReviewError(),
        ),
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403


def test_approve_denied_without_reviewer_capability():
    """Phase F5A: approve/reject now require assessment_reviewer -- a
    plain FACULTY account (even the question's own author) is denied at
    the dependency layer, before ever reaching review_question()."""
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        patch(
            "app.core.dependencies.faculty_permission_service.get_effective_capabilities",
            return_value=set(),
        ),
        patch.object(question_bank_service, "set_review_status") as mock_review,
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403
    mock_review.assert_not_called()


def test_reject_denied_with_only_author_capability():
    """assessment_author alone must not imply assessment_reviewer."""
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_author(),
        patch.object(question_bank_service, "set_review_status") as mock_review,
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/reject", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 403
    mock_review.assert_not_called()


def test_approve_no_longer_pending_returns_409():
    """A concurrent review that already resolved the question (someone
    else approved/rejected it a moment earlier) surfaces as 409, never a
    silent no-op or a generic 500."""
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_reviewer(),
        patch.object(
            question_bank_service,
            "set_review_status",
            side_effect=question_bank_service.QuestionNotPendingError(),
        ),
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


def test_approve_not_approvable_returns_409():
    """Phase F6.3: an approval blocked by the new database-side
    scoreability guard must surface as 409 (a structurally-invalid
    approval attempt, same status family as QuestionNotPendingError),
    never a generic 500 -- the real guard behavior is verified live in
    test_question_lifecycle_live.py; this confirms the route layer's
    error-to-HTTP-status mapping."""
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_reviewer(),
        patch.object(
            question_bank_service,
            "set_review_status",
            side_effect=question_bank_service.QuestionNotApprovableError(),
        ),
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 409


def test_reject_not_blocked_by_approvability_guard():
    """The scoreability guard must apply ONLY to APPROVED decisions --
    rejecting an incomplete/broken draft must always remain possible, so
    a reject call must never even reach QuestionNotApprovableError."""
    rejected_row = _row_question(review_status="REJECTED")
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_reviewer(),
        patch.object(question_bank_service, "set_review_status", return_value=rejected_row),
        patch.object(question_bank_service, "get_my_question", return_value=rejected_row),
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/reject", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["review_status"] == "REJECTED"


def test_approve_pending_question_by_different_faculty_succeeds():
    approved_row = _row_question(review_status="APPROVED", created_by=str(uuid4()))
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_reviewer(),
        patch.object(question_bank_service, "set_review_status", return_value=approved_row),
        patch.object(question_bank_service, "get_my_question", return_value=approved_row),
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/approve", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 200
    assert response.json()["review_status"] == "APPROVED"


def test_reject_nonexistent_or_invisible_question_returns_404():
    with (
        authenticated_as("FACULTY", user_id="faculty-b"),
        _as_reviewer(),
        patch.object(question_bank_service, "set_review_status", return_value=None),
    ):
        response = client.post(
            f"/api/v1/questions/{uuid4()}/reject", headers={"Authorization": "Bearer token"}
        )
    assert response.status_code == 404


def test_reject_response_never_contains_correctness_fields_for_options():
    """AssessmentOptionResponse (reused here from app.schemas.assessment)
    structurally has no correctness column -- confirming the review
    response shape carries no more than it should."""
    from app.schemas.assessment import AssessmentOptionResponse

    assert "is_correct" not in AssessmentOptionResponse.model_fields
    assert "correct_option_ids" not in AssessmentOptionResponse.model_fields


# ============================================================
# Security
# ============================================================


def test_service_role_never_referenced_in_questions_routes_or_service():
    """Unlike app.api.assessments (create_attempt) and app.api.attempts
    (score_attempt), nothing in the question-bank/review workflow needs
    service-role -- RLS + the review trigger are the entire enforcement
    mechanism, and every write here is an ordinary, non-time-critical
    CRUD operation."""
    from app.api import questions as questions_routes

    assert not hasattr(questions_routes, "get_supabase")
    assert not hasattr(question_bank_service, "get_supabase")
