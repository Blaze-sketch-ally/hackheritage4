import { describe, expect, it } from "vitest";
import { isUnansweredResult } from "@/lib/student/assessment";
import type { AssessmentResultQuestion } from "@/types/assessment";

function resultQuestion(
  overrides: Partial<AssessmentResultQuestion["student_answer"]>,
): AssessmentResultQuestion {
  return {
    question: {
      id: "q1",
      assessment_id: "a1",
      question_text: "?",
      question_type: "MCQ",
      scoring_method: "OBJECTIVE",
      difficulty: "Beginner",
      points: "10.00",
      display_order: 1,
      options: [],
    },
    student_answer: overrides
      ? {
          id: "ans1",
          attempt_id: "attempt1",
          question_id: "q1",
          answer_text: null,
          selected_option_ids: null,
          awarded_marks: null,
          is_correct: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          ...overrides,
        }
      : null,
    answer_key: { question_id: "q1", correct_option_ids: null, correct_answer_text: null, explanation: null },
  };
}

describe("isUnansweredResult", () => {
  it("is true for the Phase 1H unanswered-placeholder shape", () => {
    expect(
      isUnansweredResult(resultQuestion({ answer_text: null, selected_option_ids: [] })),
    ).toBe(true);
  });

  it("is true when student_answer is genuinely null", () => {
    const rq = resultQuestion({});
    rq.student_answer = null;
    expect(isUnansweredResult(rq)).toBe(true);
  });

  it("is false for a real MCQ answer (non-empty selected_option_ids)", () => {
    expect(
      isUnansweredResult(resultQuestion({ selected_option_ids: ["opt1"], answer_text: null })),
    ).toBe(false);
  });

  it("is false for a real SHORT_ANSWER answer (non-empty answer_text)", () => {
    expect(
      isUnansweredResult(resultQuestion({ answer_text: "def", selected_option_ids: null })),
    ).toBe(false);
  });
});
