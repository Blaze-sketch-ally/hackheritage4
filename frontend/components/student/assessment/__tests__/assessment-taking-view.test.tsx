import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  getAssessment,
  getCurrentAttempt,
  getAttemptQuestions,
  createAttempt,
  saveAnswer,
  submitAttempt,
  scoreAttempt,
  getAttemptResult,
} = vi.hoisted(() => ({
  getAssessment: vi.fn(),
  getCurrentAttempt: vi.fn(),
  getAttemptQuestions: vi.fn(),
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
    getCurrentAttempt,
    getAttemptQuestions,
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
  passing_percentage: "70.00",
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

  it("shows the start screen (with no in-progress attempt), then creates an attempt and fetches its frozen questions", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(null);
    createAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);

    expect(await screen.findByText("Python Basics")).toBeInTheDocument();
    expect(screen.getByText("1 questions")).toBeInTheDocument();
    expect(screen.getByText("Passing score: 70.00%")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /start assessment/i }));

    expect(createAttempt).toHaveBeenCalledWith(ASSESSMENT_ID);
    expect(getAttemptQuestions).toHaveBeenCalledWith("attempt-1");
    expect(await screen.findByText("Question 1 of 1")).toBeInTheDocument();
    expect(screen.getByText(question.question_text)).toBeInTheDocument();
  });

  it("resumes a genuinely in-progress attempt on load, using its frozen question set -- never the live pool", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);

    expect(await screen.findByText("Question 1 of 1")).toBeInTheDocument();
    expect(getAttemptQuestions).toHaveBeenCalledWith("attempt-1");
    // Never fetched or fabricated an attempt -- resume only reads.
    expect(createAttempt).not.toHaveBeenCalled();
  });

  it("recovers via getCurrentAttempt on a 409 race instead of a dead-end message", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValueOnce(null); // initial load: nothing in progress yet
    createAttempt.mockRejectedValue(
      new ApiError(409, "You already have an in-progress attempt for this assessment."),
    );
    getCurrentAttempt.mockResolvedValueOnce(attemptRow()); // a race winner already created one
    getAttemptQuestions.mockResolvedValue([question]);

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));

    expect(await screen.findByText("Question 1 of 1")).toBeInTheDocument();
    expect(createAttempt).toHaveBeenCalledTimes(1);
  });

  it("shows an honest, unrecoverable message when even the post-409 resume lookup fails", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValueOnce(null);
    createAttempt.mockRejectedValue(
      new ApiError(409, "You already have an in-progress attempt for this assessment."),
    );
    getCurrentAttempt.mockResolvedValueOnce(null);

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));

    expect(await screen.findByText(/already have an assessment in progress/i)).toBeInTheDocument();
    expect(await screen.findByText(/cannot be recovered from this device/i)).toBeInTheDocument();
    // A second attempt must never be created just because the first 409'd.
    expect(createAttempt).toHaveBeenCalledTimes(1);
  });

  it("saves an MCQ answer through the API and marks it answered in progress", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(null);
    createAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);
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

  it("full happy path: submit -> score -> result, showing pass/fail and verification from the backend only", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(null);
    createAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);
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
        passed: true,
        skill_verified: true,
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
      passed: true,
      skill_verified: true,
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
    expect(screen.getByText("PASSED")).toBeInTheDocument();
    expect(screen.getByText("Skill Verified")).toBeInTheDocument();
    expect(screen.getByText("Correct")).toBeInTheDocument();
  });

  it("shows NOT PASSED and unverified when the backend reports a failing result", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(null);
    createAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);
    saveAnswer.mockResolvedValue({
      id: "ans1",
      attempt_id: "attempt-1",
      question_id: "q1",
      answer_text: null,
      selected_option_ids: ["opt-python"],
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
        score: "0.00",
        total_marks: "10.00",
        percentage: "0.00",
        passed: false,
        skill_verified: false,
      }),
    );
    getAttemptResult.mockResolvedValue({
      attempt: attemptRow({
        status: "COMPLETED",
        submitted_at: "2026-01-01T00:05:00Z",
        score: "0.00",
        total_marks: "10.00",
        percentage: "0.00",
      }),
      passed: false,
      skill_verified: false,
      questions: [],
    });

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));
    await screen.findByText("Question 1 of 1");
    await userEvent.click(screen.getByRole("radio", { name: ".python" }));
    await waitFor(() => expect(saveAnswer).toHaveBeenCalled());
    await userEvent.click(await screen.findByRole("button", { name: /^submit assessment$/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm submit/i }));

    expect(await screen.findByText("NOT PASSED")).toBeInTheDocument();
    expect(screen.getByText("Skill remains unverified")).toBeInTheDocument();
    // The "why wasn't it verified" hint is only for a PASS that still
    // didn't verify -- a failing result must not show it.
    expect(screen.queryByText(/never creates a skill on its own/i)).not.toBeInTheDocument();
  });

  it("explains why a passing result did not verify a skill", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(null);
    createAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);
    saveAnswer.mockResolvedValue({
      id: "ans1",
      attempt_id: "attempt-1",
      question_id: "q1",
      answer_text: null,
      selected_option_ids: ["opt-python"],
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
        passed: true,
        skill_verified: false,
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
      passed: true,
      skill_verified: false,
      questions: [],
    });

    render(<AssessmentTakingView assessmentId={ASSESSMENT_ID} />);
    await userEvent.click(await screen.findByRole("button", { name: /start assessment/i }));
    await screen.findByText("Question 1 of 1");
    await userEvent.click(screen.getByRole("radio", { name: ".python" }));
    await waitFor(() => expect(saveAnswer).toHaveBeenCalled());
    await userEvent.click(await screen.findByRole("button", { name: /^submit assessment$/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirm submit/i }));

    expect(await screen.findByText("PASSED")).toBeInTheDocument();
    expect(screen.getByText("Skill remains unverified")).toBeInTheDocument();
    expect(screen.getByText(/never creates a skill on its own/i)).toBeInTheDocument();
  });

  it("a scoring failure lets the student retry without re-submitting", async () => {
    getAssessment.mockResolvedValue(assessment);
    getCurrentAttempt.mockResolvedValue(null);
    createAttempt.mockResolvedValue(attemptRow());
    getAttemptQuestions.mockResolvedValue([question]);
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
      attemptRow({
        status: "COMPLETED",
        submitted_at: "2026-01-01T00:05:00Z",
        score: "10.00",
        total_marks: "10.00",
        percentage: "100.00",
        passed: true,
        skill_verified: true,
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
      passed: true,
      skill_verified: true,
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
