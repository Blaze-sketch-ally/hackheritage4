import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listAssessments, fetchActiveSkills } = vi.hoisted(() => ({
  listAssessments: vi.fn(),
  fetchActiveSkills: vi.fn(),
}));

vi.mock("@/lib/student/assessment", () => ({ listAssessments }));
vi.mock("@/lib/student/skills", () => ({ fetchActiveSkills }));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

import { AssessmentListView } from "@/components/student/assessment/assessment-list-view";
import { ApiError } from "@/lib/api";

function assessment(overrides = {}) {
  return {
    id: "a1",
    skill_id: "s1",
    title: "Python Basics",
    description: "Test your Python fundamentals.",
    difficulty: "Beginner",
    duration_minutes: 10,
    question_count: 5,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("AssessmentListView", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    listAssessments.mockReturnValue(new Promise(() => {}));
    fetchActiveSkills.mockReturnValue(new Promise(() => {}));
    render(<AssessmentListView />);
    expect(screen.getByLabelText("Loading assessments")).toBeInTheDocument();
  });

  it("renders assessments with their skill name once loaded", async () => {
    listAssessments.mockResolvedValue({ assessments: [assessment()] });
    fetchActiveSkills.mockResolvedValue([{ id: "s1", name: "Python", category_id: "c1", description: null }]);

    render(<AssessmentListView />);

    expect(await screen.findByText("Python Basics")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("5 questions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start assessment" })).toHaveAttribute(
      "href",
      "/student/assessment/a1",
    );
  });

  it("shows an empty state when there are no assessments", async () => {
    listAssessments.mockResolvedValue({ assessments: [] });
    fetchActiveSkills.mockResolvedValue([]);

    render(<AssessmentListView />);

    expect(await screen.findByText("No assessments available right now")).toBeInTheDocument();
  });

  it("shows an error state with retry when the API call fails", async () => {
    listAssessments.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    fetchActiveSkills.mockResolvedValue([]);

    render(<AssessmentListView />);

    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows a session-expired message for a 401, without a generic retry button", async () => {
    listAssessments.mockRejectedValue(new ApiError(401, "You must be signed in to do this."));
    fetchActiveSkills.mockResolvedValue([]);

    render(<AssessmentListView />);

    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
  });

  it("retry re-fetches the list", async () => {
    listAssessments
      .mockRejectedValueOnce(new ApiError(500, "Backend unavailable right now."))
      .mockResolvedValueOnce({ assessments: [assessment()] });
    fetchActiveSkills.mockResolvedValue([]);

    render(<AssessmentListView />);
    await screen.findByText("Backend unavailable right now.");

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(listAssessments).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Python Basics")).toBeInTheDocument();
  });

  it("never renders an answer key or scoring field on the list", async () => {
    listAssessments.mockResolvedValue({ assessments: [assessment()] });
    fetchActiveSkills.mockResolvedValue([]);

    render(<AssessmentListView />);
    await screen.findByText("Python Basics");

    expect(screen.queryByText(/correct_option_ids/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/awarded_marks/i)).not.toBeInTheDocument();
  });
});
