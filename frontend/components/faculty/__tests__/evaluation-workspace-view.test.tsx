import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { listMyEvaluations } = vi.hoisted(() => ({
  listMyEvaluations: vi.fn(),
}));

vi.mock("@/lib/faculty/evaluations", () => ({
  listMyEvaluations,
}));

import { EvaluationWorkspaceView } from "@/components/faculty/evaluation-workspace-view";
import { ApiError } from "@/lib/api";

function evaluation(overrides = {}) {
  return {
    evaluation_id: "e1",
    assignment_id: "a1",
    status: "ASSIGNED",
    awarded_marks: null,
    attempt_id: "attempt-1",
    question_id: "q1",
    student_id: "student-1",
    assessment_title: "Java Fundamentals",
    assigned_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("EvaluationWorkspaceView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows an empty state with no fabricated statistics when there are no assignments", async () => {
    listMyEvaluations.mockResolvedValue([]);
    render(<EvaluationWorkspaceView />);

    expect(await screen.findByText(/no evaluations assigned yet/i)).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    // All three tallies show real zeros, not omitted or fabricated.
    expect(screen.getAllByText("0").length).toBe(3);
  });

  it("computes real tallies from the actual assignment statuses", async () => {
    listMyEvaluations.mockResolvedValue([
      evaluation({ evaluation_id: "e1", status: "ASSIGNED" }),
      evaluation({ evaluation_id: "e2", status: "IN_PROGRESS" }),
      evaluation({ evaluation_id: "e3", status: "SUBMITTED" }),
      evaluation({ evaluation_id: "e4", status: "FINALIZED" }),
    ]);
    render(<EvaluationWorkspaceView />);

    await screen.findAllByText("Pending");
    // Pending: 1 (ASSIGNED). In Progress: 2 (IN_PROGRESS + SUBMITTED). Completed: 1 (FINALIZED).
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows the correct context-sensitive action label per status", async () => {
    listMyEvaluations.mockResolvedValue([
      evaluation({ evaluation_id: "e1", status: "ASSIGNED", assessment_title: "Assigned Exam" }),
      evaluation({ evaluation_id: "e2", status: "IN_PROGRESS", assessment_title: "In Progress Exam" }),
      evaluation({ evaluation_id: "e3", status: "SUBMITTED", assessment_title: "Submitted Exam" }),
      evaluation({ evaluation_id: "e4", status: "FINALIZED", assessment_title: "Finalized Exam" }),
    ]);
    render(<EvaluationWorkspaceView />);

    await screen.findByText("Assigned Exam");
    expect(screen.getByRole("button", { name: /start evaluation/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace/e1",
    );
    expect(screen.getByRole("button", { name: /^continue$/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace/e2",
    );
    expect(screen.getByRole("button", { name: /^view$/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace/e3",
    );
    expect(screen.getByRole("button", { name: /view result/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace/e4",
    );
  });

  it("shows a retryable error state on load failure", async () => {
    listMyEvaluations.mockRejectedValueOnce(new ApiError(500, "Could not load evaluations."));
    listMyEvaluations.mockResolvedValueOnce([]);

    render(<EvaluationWorkspaceView />);

    expect(await screen.findByText("Could not load evaluations.")).toBeInTheDocument();
  });
});
