import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionCard } from "@/components/assessment/question-card";
import type { AssessmentQuestion } from "@/types/assessment";

const mcqQuestion: AssessmentQuestion = {
  id: "q1",
  assessment_id: "a1",
  question_text: "What is the correct file extension for a Python file?",
  question_type: "MCQ",
  scoring_method: "OBJECTIVE",
  difficulty: "Beginner",
  points: "10.00",
  display_order: 1,
  options: [
    { id: "opt-py", question_id: "q1", option_text: ".py", display_order: 1 },
    { id: "opt-python", question_id: "q1", option_text: ".python", display_order: 2 },
  ],
};

const multiQuestion: AssessmentQuestion = {
  ...mcqQuestion,
  id: "q2",
  question_type: "MULTIPLE_SELECT",
  options: [
    { id: "opt-a", question_id: "q2", option_text: "A", display_order: 1 },
    { id: "opt-b", question_id: "q2", option_text: "B", display_order: 2 },
  ],
};

const shortAnswerQuestion: AssessmentQuestion = {
  ...mcqQuestion,
  id: "q3",
  question_type: "SHORT_ANSWER",
  options: [],
};

describe("QuestionCard", () => {
  it("selecting an MCQ option calls onChange with exactly that one option id", async () => {
    const onChange = vi.fn();
    render(
      <QuestionCard
        question={mcqQuestion}
        questionNumber={1}
        value={undefined}
        onChange={onChange}
        saveState="idle"
      />,
    );

    await userEvent.click(screen.getByRole("radio", { name: ".py" }));
    expect(onChange).toHaveBeenCalledWith({ question_id: "q1", selected_option_ids: ["opt-py"] });
  });

  it("MULTIPLE_SELECT toggles options in and out of the selection", async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <QuestionCard
        question={multiQuestion}
        questionNumber={2}
        value={undefined}
        onChange={onChange}
        saveState="idle"
      />,
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "A" }));
    expect(onChange).toHaveBeenLastCalledWith({ question_id: "q2", selected_option_ids: ["opt-a"] });

    rerender(
      <QuestionCard
        question={multiQuestion}
        questionNumber={2}
        value={{ question_id: "q2", selected_option_ids: ["opt-a"] }}
        onChange={onChange}
        saveState="idle"
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "B" }));
    expect(onChange).toHaveBeenLastCalledWith({
      question_id: "q2",
      selected_option_ids: ["opt-a", "opt-b"],
    });
  });

  it("never calls onChange with an empty selected_option_ids array (backend rejects it)", async () => {
    const onChange = vi.fn();
    render(
      <QuestionCard
        question={multiQuestion}
        questionNumber={2}
        value={{ question_id: "q2", selected_option_ids: ["opt-a"] }}
        onChange={onChange}
        saveState="idle"
      />,
    );

    // Deselecting the only selected option would produce [] -- must be a no-op.
    await userEvent.click(screen.getByRole("checkbox", { name: "A" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("SHORT_ANSWER calls onChange with the typed text on blur, not per keystroke", async () => {
    const onChange = vi.fn();
    render(
      <QuestionCard
        question={shortAnswerQuestion}
        questionNumber={3}
        value={undefined}
        onChange={onChange}
        saveState="idle"
      />,
    );

    const input = screen.getByLabelText("Your answer");
    await userEvent.type(input, "def");
    expect(onChange).not.toHaveBeenCalled();

    await userEvent.tab();
    expect(onChange).toHaveBeenCalledWith({ question_id: "q3", answer_text: "def" });
  });

  it("never renders any correctness or answer-key information", () => {
    render(
      <QuestionCard
        question={mcqQuestion}
        questionNumber={1}
        value={undefined}
        onChange={vi.fn()}
        saveState="idle"
      />,
    );
    expect(screen.queryByText(/is_correct/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/awarded_marks/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/explanation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Correct$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Incorrect$/)).not.toBeInTheDocument();
  });

  it("disables all inputs when disabled is true", () => {
    render(
      <QuestionCard
        question={mcqQuestion}
        questionNumber={1}
        value={undefined}
        onChange={vi.fn()}
        saveState="idle"
        disabled
      />,
    );
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).toBeDisabled();
    }
  });
});
