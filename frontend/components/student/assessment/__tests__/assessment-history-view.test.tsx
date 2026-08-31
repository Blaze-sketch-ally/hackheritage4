import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { getAttemptHistory } = vi.hoisted(() => ({ getAttemptHistory: vi.fn() }));

vi.mock("@/lib/student/assessment", () => ({ getAttemptHistory }));

import { AssessmentHistoryView } from "@/components/student/assessment/assessment-history-view";

function historyItem(overrides = {}) {
  return {
    id: "attempt-1",
    status: "COMPLETED" as const,
    started_at: "2026-01-01T00:00:00Z",
    submitted_at: "2026-01-01T00:05:00Z",
    score: "17.00",
    total_marks: "20.00",
    percentage: "85.00",
    passed: true,
    skill_verified: true,
    assessment: {
      id: "assessment-1",
      skill_id: "skill-1",
      title: "Python",
      description: null,
      difficulty: "Advanced" as const,
      duration_minutes: 20,
      question_count: 20,
      passing_percentage: "70.00",
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    ...overrides,
  };
}

describe("AssessmentHistoryView", () => {
  it("shows an empty state when there are no attempts", async () => {
    getAttemptHistory.mockResolvedValue([]);
    render(<AssessmentHistoryView />);

    expect(await screen.findByText("No assessment attempts yet")).toBeInTheDocument();
  });

  it("renders a passed, verified attempt using only backend-provided values", async () => {
    getAttemptHistory.mockResolvedValue([historyItem()]);
    render(<AssessmentHistoryView />);

    expect(await screen.findByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
    expect(screen.getByText("17.00 / 20.00")).toBeInTheDocument();
    expect(screen.getByText("85.00%")).toBeInTheDocument();
    expect(screen.getByText("Passed")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("renders a failed, unverified attempt distinctly", async () => {
    getAttemptHistory.mockResolvedValue([
      historyItem({ percentage: "55.00", score: "11.00", passed: false, skill_verified: false }),
    ]);
    render(<AssessmentHistoryView />);

    expect(await screen.findByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Not Verified")).toBeInTheDocument();
  });

  it("never fabricates pass/fail or verification for an attempt with no assessment embed", async () => {
    getAttemptHistory.mockResolvedValue([
      historyItem({ assessment: null, passed: null, skill_verified: null }),
    ]);
    render(<AssessmentHistoryView />);

    expect(await screen.findByText("Assessment no longer available")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });
});
