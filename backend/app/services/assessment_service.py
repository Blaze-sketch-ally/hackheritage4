"""Authoritative, deterministic assessment scoring.

No LLM, no AI evaluation — this phase scores MCQ and MULTIPLE_SELECT
questions only, per the schema actually defined in
database/migrations/004_assessments.sql.

Scoring rule (both MCQ and MULTIPLE_SELECT): full question points if the
student's selected option set exactly equals the answer key's correct
option set, otherwise 0. The schema has no column representing a
per-option weight or partial-credit ratio anywhere (assessment_answers
and assessment_question_answers both only carry a single points/marks
value per *question*, not per option) — so exact-set-match is the only
scoring rule the schema actually supports; partial credit is not
invented here.

Runs entirely on the service_role Supabase client (see
app/database/supabase.py) — this is required for two independent
reasons: (1) reading assessment_question_answers, the protected answer
key table, which has no policy granting a student's own token read
access to it before their attempt is COMPLETED (a chicken-and-egg
problem this scoring step itself resolves), and (2) writing
assessment_attempts.status/score/total_marks/percentage and
assessment_answers.awarded_marks/is_correct, which the
prevent_self_attempt_scoring / prevent_self_answer_scoring triggers
(004_assessments.sql) unconditionally reject for any non-service_role
caller. Ownership (`attempt.student_id == student_id`) is therefore
verified explicitly in this function, in Python — with service_role
bypassing RLS entirely, that check is the actual enforcement here, not
a redundant belt-and-suspenders addition to RLS.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from supabase import Client

from app.schemas.assessment import SubmitAssessmentResult

SCORABLE_TYPES = {"MCQ", "MULTIPLE_SELECT"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _result_from_completed_attempt(supabase: Client, attempt: dict) -> SubmitAssessmentResult:
    """Rebuilds the result for an attempt that was already scored earlier
    (idempotent re-submit) — reads only, never re-scores or re-writes."""
    answers = (
        supabase.table("assessment_answers")
        .select("is_correct")
        .eq("attempt_id", attempt["id"])
        .execute()
        .data
        or []
    )
    correct_count = sum(1 for a in answers if a.get("is_correct") is True)
    incorrect_count = sum(1 for a in answers if a.get("is_correct") is False)

    return SubmitAssessmentResult(
        attempt_id=attempt["id"],
        status=attempt["status"],
        score=float(attempt["score"] or 0),
        total_marks=float(attempt["total_marks"] or 0),
        percentage=float(attempt["percentage"] or 0),
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        submitted_at=attempt["submitted_at"],
    )


def submit_and_score_attempt(supabase: Client, attempt_id: str, student_id: str) -> SubmitAssessmentResult:
    # 1 & 2. Fetch the attempt and verify it belongs to the authenticated student.
    attempt_res = supabase.table("assessment_attempts").select("*").eq("id", attempt_id).maybe_single().execute()
    attempt = attempt_res.data if attempt_res else None
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")
    if attempt["student_id"] != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This attempt does not belong to you.")

    # Idempotent: a second submit call (e.g. a retried request) returns the
    # already-persisted result instead of re-scoring or erroring.
    if attempt["status"] == "COMPLETED":
        return _result_from_completed_attempt(supabase, attempt)

    # 3. Verify the attempt is eligible for submission.
    if attempt["status"] != "IN_PROGRESS":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This attempt cannot be submitted (it was abandoned).",
        )

    questions = (
        supabase.table("assessment_questions")
        .select("id, question_type, points")
        .eq("assessment_id", attempt["assessment_id"])
        .execute()
        .data
        or []
    )
    if not questions:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This assessment has no questions.")

    question_ids = [q["id"] for q in questions]

    # 4. Fetch the submitted answers for this attempt.
    answers = (
        supabase.table("assessment_answers")
        .select("id, question_id, selected_option_ids")
        .eq("attempt_id", attempt_id)
        .execute()
        .data
        or []
    )
    answers_by_question = {a["question_id"]: a for a in answers}

    # 5. Fetch the protected answer keys for these questions.
    keys = (
        supabase.table("assessment_question_answers")
        .select("question_id, correct_option_ids")
        .in_("question_id", question_ids)
        .execute()
        .data
        or []
    )
    keys_by_question = {k["question_id"]: k for k in keys}

    # 6 & 7. Compare answers, calculate awarded marks per question.
    total_marks = 0.0
    score = 0.0
    correct_count = 0
    incorrect_count = 0

    for question in questions:
        points = float(question["points"])
        total_marks += points

        answer = answers_by_question.get(question["id"])

        if question["question_type"] not in SCORABLE_TYPES:
            # SHORT_ANSWER / CODE / SUBJECTIVE: not auto-scorable in this
            # deterministic-only phase (no AI evaluation, no manual grading
            # UI yet). Recorded as 0 / incorrect rather than silently
            # skipped, so total_marks still reflects every question.
            if answer:
                supabase.table("assessment_answers").update(
                    {"awarded_marks": 0, "is_correct": False}
                ).eq("id", answer["id"]).execute()
            incorrect_count += 1
            continue

        key = keys_by_question.get(question["id"])
        correct_options = set(key["correct_option_ids"] or []) if key else set()
        selected_options = set((answer or {}).get("selected_option_ids") or [])

        is_correct = bool(correct_options) and selected_options == correct_options
        awarded = points if is_correct else 0.0
        score += awarded

        if is_correct:
            correct_count += 1
        else:
            incorrect_count += 1

        if answer:
            supabase.table("assessment_answers").update(
                {"awarded_marks": awarded, "is_correct": is_correct}
            ).eq("id", answer["id"]).execute()
        # else: the student never answered this question — nothing to
        # update; it contributes 0 to score and is already counted in
        # total_marks above.

    percentage = round((score / total_marks) * 100, 2) if total_marks > 0 else 0.0

    # 8 & 9. Persist the authoritative result and mark the attempt COMPLETED.
    updated = (
        supabase.table("assessment_attempts")
        .update(
            {
                "status": "COMPLETED",
                "submitted_at": attempt["submitted_at"] or _now_iso(),
                "score": score,
                "total_marks": total_marks,
                "percentage": percentage,
            }
        )
        .eq("id", attempt_id)
        .execute()
    )
    submitted_at = updated.data[0]["submitted_at"] if updated.data else attempt["submitted_at"]

    # 10. Return only safe result information.
    return SubmitAssessmentResult(
        attempt_id=attempt_id,
        status="COMPLETED",
        score=score,
        total_marks=total_marks,
        percentage=percentage,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
        submitted_at=submitted_at,
    )
