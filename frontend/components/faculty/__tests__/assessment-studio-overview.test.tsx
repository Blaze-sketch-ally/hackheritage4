import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { useFacultyCapabilitiesContext } = vi.hoisted(() => ({
  useFacultyCapabilitiesContext: vi.fn(),
}));

vi.mock("@/lib/faculty/capabilities", async () => {
  const actual = await vi.importActual<typeof import("@/lib/faculty/capabilities")>(
    "@/lib/faculty/capabilities",
  );
  return {
    ...actual,
    useFacultyCapabilitiesContext,
  };
});

const { listMyQuestions, listAssessmentsForFaculty } = vi.hoisted(() => ({
  listMyQuestions: vi.fn(),
  listAssessmentsForFaculty: vi.fn(),
}));

vi.mock("@/lib/faculty/question-bank", () => ({
  listMyQuestions,
  listAssessmentsForFaculty,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: "faculty-1" } }),
}));

import { AssessmentStudioOverview } from "@/components/faculty/assessment-studio-overview";

describe("AssessmentStudioOverview", () => {
  beforeEach(() => {
    listMyQuestions.mockResolvedValue([]);
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [] });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("links to the existing Question Bank and Blueprints pages", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    render(<AssessmentStudioOverview />);

    expect(await screen.findByRole("button", { name: /open question bank/i })).toHaveAttribute(
      "href",
      "/faculty/questions",
    );
    expect(screen.getByRole("button", { name: /open blueprints/i })).toHaveAttribute("href", "/faculty/blueprint");
  });

  it("does not crash while capabilities are loading, and shows no capability claims yet", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "loading" });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText(/loading your capabilities/i)).toBeInTheDocument();
    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.queryByText("Reviewer")).not.toBeInTheDocument();
  });

  it("does not crash on a capability load error", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "error", error: new Error("boom") });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText(/could not load your capabilities/i)).toBeInTheDocument();
  });

  it("shows a hint, not a crash, when the caller holds neither capability", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText(/has not yet granted you an assessment capability/i)).toBeInTheDocument();
    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.queryByText("Reviewer")).not.toBeInTheDocument();
  });

  it("shows both badges when the caller holds both capabilities", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_author", "assessment_reviewer"],
    });
    render(<AssessmentStudioOverview />);

    expect(await screen.findByText("Author")).toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
  });

  it("shows only the Reviewer badge when only reviewer is granted", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_reviewer"] });
    render(<AssessmentStudioOverview />);

    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
  });

  it("never renders an evaluator/moderator/lead capability badge, even when granted", () => {
    useFacultyCapabilitiesContext.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_author", "assessment_reviewer", "assessment_evaluator"],
    });
    render(<AssessmentStudioOverview />);

    for (const badge of ["Evaluator", "Moderator", "Lead"]) {
      expect(screen.queryByText(badge)).not.toBeInTheDocument();
    }
  });

  // ============================================================
  // Phase 1 (Faculty Dashboard Architecture): moved-in KPIs/actions
  // ============================================================

  it("shows the question-authoring/review KPIs that used to live on Faculty Connect", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    listMyQuestions.mockResolvedValue([
      {
        id: "q1",
        question_text: "Q1",
        review_status: "APPROVED",
        is_active: true,
        created_by: "faculty-1",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [{ id: "a1" }] });

    render(<AssessmentStudioOverview />);

    expect(await screen.findByText("Questions Authored")).toBeInTheDocument();
    expect(screen.getByText("Pending Your Review")).toBeInTheDocument();
    // "Approved" also appears as the mocked recent question's own status
    // badge -- at least one match (the KPI stat label) is what matters here.
    expect(screen.getAllByText("Approved").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Needs Revision")).toBeInTheDocument();
  });

  it("shows the Create Question action only for a caller with assessment_author", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    render(<AssessmentStudioOverview />);

    expect(await screen.findByRole("button", { name: /create question/i })).toHaveAttribute(
      "href",
      "/faculty/questions/new",
    );
  });

  it("hides the Create Question action for a reviewer without author capability", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_reviewer"] });
    render(<AssessmentStudioOverview />);

    await screen.findByRole("button", { name: /open question bank/i });
    expect(screen.queryByRole("button", { name: /create question/i })).not.toBeInTheDocument();
  });

  it("shows a retryable error state if question activity fails to load", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    listMyQuestions.mockRejectedValueOnce(new Error("boom"));

    render(<AssessmentStudioOverview />);

    expect(await screen.findByText("Could not load your question-authoring activity.")).toBeInTheDocument();
  });

  it("shows no numeric metrics or fabricated statistics when capabilities are not yet granted", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
    render(<AssessmentStudioOverview />);

    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
  });
});
