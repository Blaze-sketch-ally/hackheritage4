import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyQuestions, approveQuestion, rejectQuestion } = vi.hoisted(() => ({
  listMyQuestions: vi.fn(),
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
}));

vi.mock("@/lib/faculty/question-bank", () => ({
  listMyQuestions,
  approveQuestion,
  rejectQuestion,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: "faculty-me" } }),
}));

import { QuestionBankView } from "@/components/faculty/question-bank-view";
import { ApiError } from "@/lib/api";

function question(overrides = {}) {
  return {
    id: "q1",
    assessment_id: "a1",
    question_text: "What is a closure?",
    question_type: "MCQ",
    scoring_method: "OBJECTIVE",
    difficulty: "Intermediate",
    points: "5.00",
    display_order: 0,
    review_status: "PENDING",
    is_active: true,
    created_by: "faculty-other",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    options: [],
    answer_key: null,
    ...overrides,
  };
}

describe("QuestionBankView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows Approve/Reject only for another setter's PENDING question, never for the caller's own", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "Other setter's question", created_by: "faculty-other", review_status: "PENDING" }),
      question({ id: "q2", question_text: "My own question", created_by: "faculty-me", review_status: "PENDING" }),
    ]);

    render(<QuestionBankView />);

    expect(await screen.findByText("Other setter's question")).toBeInTheDocument();
    expect(screen.getByText("My own question")).toBeInTheDocument();
    const approveButtons = screen.getAllByRole("button", { name: /approve/i });
    // Only one row (the other setter's) gets an Approve button.
    expect(approveButtons).toHaveLength(1);
    expect(screen.getByText("Awaiting another setter")).toBeInTheDocument();
  });

  it("approving a question calls the API and updates the row in place", async () => {
    listMyQuestions.mockResolvedValue([question({ id: "q1", created_by: "faculty-other" })]);
    approveQuestion.mockResolvedValue(question({ id: "q1", created_by: "faculty-other", review_status: "APPROVED" }));

    render(<QuestionBankView />);
    await screen.findByText("What is a closure?");

    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(approveQuestion).toHaveBeenCalledWith("q1"));
    expect(await screen.findByText("Approved")).toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    listMyQuestions.mockRejectedValueOnce(new ApiError(500, "Could not load questions."));
    listMyQuestions.mockResolvedValueOnce([question()]);

    render(<QuestionBankView />);

    expect(await screen.findByText("Could not load questions.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByText("What is a closure?")).toBeInTheDocument();
    expect(listMyQuestions).toHaveBeenCalledTimes(2);
  });

  it("shows an empty state when there are no questions", async () => {
    listMyQuestions.mockResolvedValue([]);
    render(<QuestionBankView />);
    expect(await screen.findByText(/no questions yet/i)).toBeInTheDocument();
  });
});
