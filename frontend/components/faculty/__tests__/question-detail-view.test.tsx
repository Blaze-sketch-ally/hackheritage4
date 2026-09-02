import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getQuestion, updateQuestion, approveQuestion, rejectQuestion } = vi.hoisted(() => ({
  getQuestion: vi.fn(),
  updateQuestion: vi.fn(),
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
}));

vi.mock("@/lib/faculty/question-bank", () => ({
  getQuestion,
  updateQuestion,
  approveQuestion,
  rejectQuestion,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: "faculty-me" } }),
}));

import { QuestionDetailView } from "@/components/faculty/question-detail-view";
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
    learning_objective: null,
    estimated_time_minutes: null,
    review_status: "PENDING",
    is_active: true,
    created_by: "faculty-me",
    reviewed_by: null,
    review_note: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    options: [],
    answer_key: { correct_answer_text: "A function bound to its lexical scope." },
    ...overrides,
  };
}

describe("QuestionDetailView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("displays learning objective and estimated time when present", async () => {
    getQuestion.mockResolvedValue(
      question({ learning_objective: "Understand closures.", estimated_time_minutes: 4 }),
    );
    render(<QuestionDetailView questionId="q1" />);

    expect(await screen.findByText(/understand closures\./i)).toBeInTheDocument();
    expect(screen.getByText(/~4 min/i)).toBeInTheDocument();
  });

  it("edits metadata only (learning objective + estimated time) without touching question text", async () => {
    getQuestion.mockResolvedValue(question());
    updateQuestion.mockResolvedValue(question({ learning_objective: "New objective.", estimated_time_minutes: 6 }));

    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");

    await userEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    await userEvent.type(screen.getByLabelText(/learning objective/i), "New objective.");
    await userEvent.type(screen.getByLabelText(/estimated time/i), "6");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(updateQuestion).toHaveBeenCalled());
    const [, payload] = updateQuestion.mock.calls[0];
    expect(payload.learning_objective).toBe("New objective.");
    expect(payload.estimated_time_minutes).toBe(6);
    expect(payload.question_text).toBe("What is a closure?");
  });

  it("rejects a non-positive-integer estimated time client-side before calling the API", async () => {
    getQuestion.mockResolvedValue(question());
    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");

    await userEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    await userEvent.type(screen.getByLabelText(/estimated time/i), "0");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByText(/positive whole number of minutes/i)).toBeInTheDocument();
    expect(updateQuestion).not.toHaveBeenCalled();
  });

  it("an APPROVED question offers no editable controls", async () => {
    getQuestion.mockResolvedValue(question({ review_status: "APPROVED", created_by: "faculty-me" }));
    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");

    expect(screen.queryByRole("button", { name: /^edit$/i })).not.toBeInTheDocument();
  });

  it("surfaces the backend's 409 not-approvable message verbatim, not a generic error", async () => {
    getQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "PENDING" }));
    approveQuestion.mockRejectedValue(
      new ApiError(
        409,
        "This question cannot be approved yet: it is not a complete, scoreable question (missing or invalid answer key, an unsupported question type/scoring combination, or too few options).",
      ),
    );

    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");

    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    expect(await screen.findByText(/not a complete, scoreable question/i)).toBeInTheDocument();
  });

  it("shows an explicit unsupported-type notice for a CODE question", async () => {
    getQuestion.mockResolvedValue(question({ question_type: "CODE", scoring_method: "OBJECTIVE" }));
    render(<QuestionDetailView questionId="q1" />);

    expect(
      await screen.findByText(/code questions aren.t supported for automatic scoring yet/i),
    ).toBeInTheDocument();
  });

  it("offers an optional review-note field for a reviewer on a PENDING question", async () => {
    getQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "PENDING" }));
    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");

    expect(screen.getByLabelText(/review note/i)).toBeInTheDocument();
  });

  it("approves without a note when the reviewer leaves the note field blank", async () => {
    getQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "PENDING" }));
    approveQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "APPROVED" }));

    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(approveQuestion).toHaveBeenCalledWith("q1", null));
  });

  it("passes a trimmed note through to approveQuestion when the reviewer types one", async () => {
    getQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "PENDING" }));
    approveQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "APPROVED" }));

    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");
    await userEvent.type(screen.getByLabelText(/review note/i), "  Looks good.  ");
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(approveQuestion).toHaveBeenCalledWith("q1", "Looks good."));
  });

  it("passes a note through to rejectQuestion", async () => {
    getQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "PENDING" }));
    rejectQuestion.mockResolvedValue(question({ created_by: "faculty-other", review_status: "REJECTED" }));

    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");
    await userEvent.type(screen.getByLabelText(/review note/i), "Needs a better distractor.");
    await userEvent.click(screen.getByRole("button", { name: /reject/i }));

    await waitFor(() => expect(rejectQuestion).toHaveBeenCalledWith("q1", "Needs a better distractor."));
  });

  it("shows the reviewer as \"You\" and the note when the current user was the reviewer", async () => {
    getQuestion.mockResolvedValue(
      question({ review_status: "APPROVED", reviewed_by: "faculty-me", review_note: "Nice work." }),
    );
    render(<QuestionDetailView questionId="q1" />);

    expect(await screen.findByText(/reviewed by you/i)).toBeInTheDocument();
    expect(screen.getByText("Nice work.")).toBeInTheDocument();
  });

  it("shows an abbreviated, clearly-labeled identifier for a different reviewer, never a raw name", async () => {
    getQuestion.mockResolvedValue(
      question({ review_status: "REJECTED", reviewed_by: "11111111-2222-3333-4444-555555555555", review_note: null }),
    );
    render(<QuestionDetailView questionId="q1" />);

    expect(await screen.findByText(/reviewed by reviewer 11111111/i)).toBeInTheDocument();
  });

  it("does not render a latest-review section when the question has never been reviewed", async () => {
    getQuestion.mockResolvedValue(question({ reviewed_by: null, review_note: null }));
    render(<QuestionDetailView questionId="q1" />);
    await screen.findByText("What is a closure?");

    expect(screen.queryByText(/latest review/i)).not.toBeInTheDocument();
  });

  it("shows read-only latest-review info on an APPROVED question with no edit-review control", async () => {
    getQuestion.mockResolvedValue(
      question({
        review_status: "APPROVED",
        created_by: "faculty-me",
        reviewed_by: "faculty-other",
        review_note: "Approved as-is.",
      }),
    );
    render(<QuestionDetailView questionId="q1" />);

    expect(await screen.findByText(/latest review/i)).toBeInTheDocument();
    expect(screen.getByText("Approved as-is.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit review/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/review note/i)).not.toBeInTheDocument();
  });

  it("shows no stale review metadata once a rejected question has been resubmitted to PENDING", async () => {
    getQuestion.mockResolvedValue(
      question({
        review_status: "REJECTED",
        created_by: "faculty-me",
        reviewed_by: "faculty-other",
        review_note: "Please fix the wording.",
      }),
    );
    updateQuestion.mockResolvedValue(
      question({ review_status: "PENDING", created_by: "faculty-me", reviewed_by: null, review_note: null }),
    );

    render(<QuestionDetailView questionId="q1" />);
    expect(await screen.findByText("Please fix the wording.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /resubmit for review/i }));

    await waitFor(() => expect(screen.queryByText("Please fix the wording.")).not.toBeInTheDocument());
    expect(screen.queryByText(/latest review/i)).not.toBeInTheDocument();
  });
});
