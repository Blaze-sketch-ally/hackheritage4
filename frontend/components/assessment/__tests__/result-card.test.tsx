import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResultCard } from "@/components/assessment/result-card";
import type { AssessmentResultQuestion } from "@/types/assessment";

const question: AssessmentResultQuestion["question"] = {
  id: "q1",
  assessment_id: "a1",
  question_text: "Which keyword defines a function in Python?",
  question_type: "MCQ",
  scoring_method: "OBJECTIVE",
  difficulty: "Beginner",
  points: "10.00",
  display_order: 1,
  options: [
    { id: "opt-def", question_id: "q1", option_text: "def", display_order: 1 },
    { id: "opt-func", question_id: "q1", option_text: "func", display_order: 2 },
  ],
};

function makeAnswer(overrides: Partial<NonNullable<AssessmentResultQuestion["student_answer"]>>) {
  return {
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
  };
}

describe("ResultCard", () => {
  it("shows the correct answer, marks awarded, and a Correct badge for a right answer", () => {
    render(
      <ResultCard
        questionNumber={1}
        result={{
          question,
          student_answer: makeAnswer({ selected_option_ids: ["opt-def"], awarded_marks: "10.00", is_correct: true }),
          answer_key: { question_id: "q1", correct_option_ids: ["opt-def"], correct_answer_text: null, explanation: "def defines a function." },
        }}
      />,
    );

    expect(screen.getByText("Correct")).toBeInTheDocument();
    expect(screen.getByText("10.00 / 10.00 pts")).toBeInTheDocument();
    expect(screen.getByText("def defines a function.")).toBeInTheDocument();
  });

  it("shows an Incorrect badge for a wrong answer", () => {
    render(
      <ResultCard
        questionNumber={1}
        result={{
          question,
          student_answer: makeAnswer({ selected_option_ids: ["opt-func"], awarded_marks: "0.00", is_correct: false }),
          answer_key: { question_id: "q1", correct_option_ids: ["opt-def"], correct_answer_text: null, explanation: null },
        }}
      />,
    );

    expect(screen.getByText("Incorrect")).toBeInTheDocument();
  });

  it("renders the Phase 1H unanswered placeholder as 'Not answered', never the raw empty array", () => {
    render(
      <ResultCard
        questionNumber={1}
        result={{
          question,
          student_answer: makeAnswer({ answer_text: null, selected_option_ids: [], awarded_marks: "0.00", is_correct: false }),
          answer_key: { question_id: "q1", correct_option_ids: ["opt-def"], correct_answer_text: null, explanation: null },
        }}
      />,
    );

    expect(screen.getAllByText("Not answered").length).toBeGreaterThan(0);
    expect(screen.queryByText("[]")).not.toBeInTheDocument();
    expect(screen.queryByText(/selected_option_ids/)).not.toBeInTheDocument();
  });

  it("marks the correct option even when the student didn't select it", () => {
    render(
      <ResultCard
        questionNumber={1}
        result={{
          question,
          student_answer: makeAnswer({ selected_option_ids: ["opt-func"], awarded_marks: "0.00", is_correct: false }),
          answer_key: { question_id: "q1", correct_option_ids: ["opt-def"], correct_answer_text: null, explanation: null },
        }}
      />,
    );

    // "def" is the correct option and should be visually distinguished
    // from a plain unselected option -- rendered inside a highlighted list item.
    const defItem = screen.getByText("def").closest("li");
    expect(defItem?.className).toContain("emerald");
  });
});
