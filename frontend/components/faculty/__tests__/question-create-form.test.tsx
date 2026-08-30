import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listAssessmentsForFaculty, createQuestion } = vi.hoisted(() => ({
  listAssessmentsForFaculty: vi.fn(),
  createQuestion: vi.fn(),
}));

const push = vi.hoisted(() => vi.fn());

vi.mock("@/lib/faculty/question-bank", () => ({
  listAssessmentsForFaculty,
  createQuestion,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

import { QuestionCreateForm } from "@/components/faculty/question-create-form";
import { ApiError } from "@/lib/api";

const assessment = {
  id: "a1",
  skill_id: "skill-1",
  title: "Python Fundamentals",
  description: null,
  difficulty: "Beginner",
  duration_minutes: 15,
  question_count: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("QuestionCreateForm", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("requires at least one correct option to be marked before submitting an MCQ", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });

    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    expect(await screen.findByText(/mark at least one option as correct/i)).toBeInTheDocument();
    expect(createQuestion).not.toHaveBeenCalled();
  });

  it("submits an MCQ with client-generated option ids matching correct_option_ids", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    createQuestion.mockResolvedValue({
      id: "new-question",
      assessment_id: "a1",
      question_text: "What is 2 + 2?",
      question_type: "MCQ",
      scoring_method: "OBJECTIVE",
      difficulty: "Beginner",
      points: "1.00",
      display_order: 0,
      review_status: "PENDING",
      is_active: true,
      created_by: "faculty-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      options: [],
      answer_key: null,
    });

    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");
    await userEvent.click(screen.getByRole("radio", { name: /mark option 2 correct/i }));

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    await waitFor(() => expect(createQuestion).toHaveBeenCalled());
    const payload = createQuestion.mock.calls[0][0];
    expect(payload.scoring_method).toBe("OBJECTIVE");
    expect(payload.options).toHaveLength(2);
    // The option marked correct must have a client-generated id that
    // exactly matches the one entry in correct_option_ids -- this is the
    // whole point of generating option ids client-side before the option
    // rows exist server-side.
    const correctOption = payload.options.find((o: { option_text: string }) => o.option_text === "4");
    expect(payload.answer_key.correct_option_ids).toEqual([correctOption.id]);
    expect(correctOption.id).toBeTruthy();

    expect(push).toHaveBeenCalledWith("/faculty/questions/new-question");
  });

  it("shows a load error if assessments fail to load", async () => {
    listAssessmentsForFaculty.mockRejectedValue(new ApiError(500, "Could not load assessments."));
    render(<QuestionCreateForm />);
    expect(await screen.findByText("Could not load assessments.")).toBeInTheDocument();
  });
});
