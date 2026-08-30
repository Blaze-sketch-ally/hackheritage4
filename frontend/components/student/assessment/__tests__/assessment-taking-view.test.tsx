import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  getAssessment,
  getAssessmentQuestions,
  createAttempt,
  saveAnswer,
  submitAttempt,
  scoreAttempt,
  getAttemptResult,
} = vi.hoisted(() => ({
  getAssessment: vi.fn(),
  getAssessmentQuestions: vi.fn(),
  createAttempt: vi.fn(),
  saveAnswer: vi.fn(),
  submitAttempt: vi.fn(),
  scoreAttempt: vi.fn(),
  getAttemptResult: vi.fn(),
}));

vi.mock("@/lib/student/assessment", async () => {
  const actual = await vi.importActual<typeof import("@/lib/student/assessment")>(
    "@/lib/student/assessment",
  );
  return {
    ...actual,
    getAssessment,
    getAssessmentQuestions,
    createAttempt,
    saveAnswer,
    submitAttempt,
    scoreAttempt,
    getAttemptResult,
  };
});

import { AssessmentTakingView } from "@/components/student/assessment/assessment-taking-view";
import { ApiError } from "@/lib/api";
import { clearStoredAttempt } from "@/lib/student/assessment-session";

const ASSESSMENT_ID = "assessment-1";

const assessment = {
  id: ASSESSMENT_ID,
  skill_id: "skill-1",
  title: "Python Basics",
  description: "Basics quiz",
  difficulty: "Beginner",
  duration_minutes: 10,
  question_count: 1,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const question = {
  id: "q1",
  assessment_id: ASSESSMENT_ID,
  question_text: "What is the correct file extension for a Python file?",
  question_type: "MCQ" as const,
  scoring_method: "OBJECTIVE" as const,
  difficulty: "Beginner" as const,
  points: "10.00",
  display_order: 1,
  options: [
    { id: "opt-py", question_id: "q1", option_text: ".py", display_order: 1 },
    { id: "opt-python", question_id: "q1", option_text: ".python", display_order: 2 },
  ],
};

function attemptRow(overrides = {}) {
  return {
    id: "attempt-1",
    student_id: "student-1",
    assessment_id: ASSESSMENT_ID,
    status: "IN_PROGRESS",
    started_at: "2026-01-01T00:00:00Z",
    submitted_at: null,
    score: null,
    total_marks: null,
    percentage: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("AssessmentTakingView", () => {
  afterEach(() => {
    vi.clearAllMocks();
    clearStoredAttempt(ASSESSMENT_ID);
    window.sessionStorage.clear();
  });

  it("shows the start screen, then creates an attempt and moves to taking", async () => {
    getAssessment.mockResolvedValue(assessment);
    getAssessmentQuestions.mockResolvedValue([question]);
    createAttempt.mockResolvedValue(attemptRow());

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);

    expect(await screen.findByText("Python Basics")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /start assessment/i }));

    expect(createAttempt).toHaveBeenCalledWith(ASSESSMENT_ID);
    expect(await screen.findByText("Question 1 of 1")).toBeInTheDocument();
    expect(screen.getByText(question.question_text)).toBeInTheDocument();
  });

  it("shows an honest, unrecoverable message on 409 without fabricating an attempt id", async () => {
    getAssessment.mockResolvedValue(assessment);
    getAssessmentQuestions.mockResolvedValue([question]);
    createAttempt.mockRejectedValue(new ApiError(409, "You already have an in-progress attempt for this assessment."));

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));

    expect(await screen.findByText(/already have an assessment in progress/i)).toBeInTheDocument();
    expect(await screen.findByText(/cannot be recovered from this device/i)).toBeInTheDocument();
    // A second attempt must never be created just because the first 409'd.
    expect(createAttempt).toHaveBeenCalledTimes(1);
  });

  it("saves an MCQ answer through the API and marks it answered in progress", async () => {
    getAssessment.mockResolvedValue(assessment);
    getAssessmentQuestions.mockResolvedValue([question]);
    createAttempt.mockResolvedValue(attemptRow());
    saveAnswer.mockResolvedValue({
      id: "ans1",
      attempt_id: "attempt-1",
      question_id: "q1",
      answer_text: null,
      selected_option_ids: ["opt-py"],
      awarded_marks: null,
      is_correct: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));
    await screen.findByText("Question 1 of 1");

    await userEvent.click(screen.getByRole("radio", { name: ".py" }));

    await waitFor(() =>
      expect(saveAnswer).toHaveBeenCalledWith("attempt-1", {
        question_id: "q1",
        selected_option_ids: ["opt-py"],
      }),
    );
    expect(await screen.findByText("1 of 1 answered")).toBeInTheDocument();
  });

  it("full happy path: submit -> score -> result, displaying only backend-provided values", async () => {
    getAssessment.mockResolvedValue(assessment);
    getAssessmentQuestions.mockResolvedValue([question]);
    createAttempt.mockResolvedValue(attemptRow());
    saveAnswer.mockResolvedValue({
      id: "ans1",
      attempt_id: "attempt-1",
      question_id: "q1",
      answer_text: null,
      selected_option_ids: ["opt-py"],
      awarded_marks: null,
      is_correct: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    submitAttempt.mockResolvedValue(attemptRow({ submitted_at: "2026-01-01T00:05:00Z" }));
    scoreAttempt.mockResolvedValue(
      attemptRow({
        status: "COMPLETED",
        submitted_at: "2026-01-01T00:05:00Z",
        score: "10.00",
        total_marks: "10.00",
        percentage: "100.00",
      }),
    );
    getAttemptResult.mockResolvedValue({
      attempt: attemptRow({
        status: "COMPLETED",
        submitted_at: "2026-01-01T00:05:00Z",
        score: "10.00",
        total_marks: "10.00",
        percentage: "100.00",
      }),
      questions: [
        {
          question,
          student_answer: {
            id: "ans1",
            attempt_id: "attempt-1",
            question_id: "q1",
            answer_text: null,
            selected_option_ids: ["opt-py"],
            awarded_marks: "10.00",
            is_correct: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:05:00Z",
          },
          answer_key: {
            question_id: "q1",
            correct_option_ids: ["opt-py"],
            correct_answer_text: null,
            explanation: null,
          },
        },
      ],
    });

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));
    await screen.findByText("Question 1 of 1");
    await userEvent.click(screen.getByRole("radio", { name: ".py" }));
    await waitFor(() => expect(saveAnswer).toHaveBeenCalled());

    const submitButton = await screen.findByRole("button", { name: /^submit assessment$/i });
    expect(submitButton).toBeEnabled();
    await userEvent.click(submitButton);
    await userEvent.click(await screen.findByRole("button", { name: /confirm submit/i }));

    await waitFor(() => expect(submitAttempt).toHaveBeenCalledWith("attempt-1"));
    await waitFor(() => expect(scoreAttempt).toHaveBeenCalledWith("attempt-1"));
    await waitFor(() => expect(getAttemptResult).toHaveBeenCalledWith("attempt-1"));

    expect(await screen.findByText("Assessment complete")).toBeInTheDocument();
    expect(screen.getByText("10.00 / 10.00")).toBeInTheDocument();
    expect(screen.getByText("100.00%")).toBeInTheDocument();
    expect(screen.getByText("Correct")).toBeInTheDocument();
  });

  it("a scoring failure lets the student retry without re-submitting", async () => {
    getAssessment.mockResolvedValue(assessment);
    getAssessmentQuestions.mockResolvedValue([question]);
    createAttempt.mockResolvedValue(attemptRow());
    saveAnswer.mockResolvedValue({
      id: "ans1",
      attempt_id: "attempt-1",
      question_id: "q1",
      answer_text: null,
      selected_option_ids: ["opt-py"],
      awarded_marks: null,
      is_correct: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    submitAttempt.mockResolvedValue(attemptRow({ submitted_at: "2026-01-01T00:05:00Z" }));
    scoreAttempt.mockRejectedValueOnce(new ApiError(500, "Could not score the attempt."));
    scoreAttempt.mockResolvedValueOnce(
      attemptRow({ status: "COMPLETED", submitted_at: "2026-01-01T00:05:00Z", score: "10.00", total_marks: "10.00", percentage: "100.00" }),
    );
    getAttemptResult.mockResolvedValue({
      attempt: attemptRow({ status: "COMPLETED", submitted_at: "2026-01-01T00:05:00Z", score: "10.00", total_marks: "10.00", percentage: "100.00" }),
      questions: [],
    });

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));
    await screen.findByText("Question 1 of 1");
    await userEvent.click(screen.getByRole("radio", { name: ".py" }));
    await waitFor(() => expect(saveAnswer).toHaveBeenCalled());
    await userEvent.click(await screen.findByRole("button", { name: /^submit assessment$/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm submit/i }));

    expect(await screen.findByText(/scoring failed/i)).toBeInTheDocument();
    expect(submitAttempt).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(scoreAttempt).toHaveBeenCalledTimes(2));
    // Retrying scoring must never call submit a second time.
    expect(submitAttempt).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Assessment complete")).toBeInTheDocument();
  });
});
