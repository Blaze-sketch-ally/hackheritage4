import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { useFacultyCapabilities } = vi.hoisted(() => ({
  useFacultyCapabilities: vi.fn(),
}));

vi.mock("@/lib/faculty/capabilities", async () => {
  const actual = await vi.importActual<typeof import("@/lib/faculty/capabilities")>(
    "@/lib/faculty/capabilities",
  );
  return {
    ...actual,
    useFacultyCapabilities,
  };
});

import { AssessmentStudioOverview } from "@/components/faculty/assessment-studio-overview";

describe("AssessmentStudioOverview", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("links to the existing Question Bank and Blueprints pages", () => {
    useFacultyCapabilities.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    render(<AssessmentStudioOverview />);

    expect(screen.getByRole("button", { name: /open question bank/i })).toHaveAttribute(
      "href",
      "/faculty/questions",
    );
    expect(screen.getByRole("button", { name: /open blueprints/i })).toHaveAttribute("href", "/faculty/blueprint");
  });

  it("does not crash while capabilities are loading, and shows no capability claims yet", () => {
    useFacultyCapabilities.mockReturnValue({ status: "loading" });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText(/loading your capabilities/i)).toBeInTheDocument();
    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.queryByText("Reviewer")).not.toBeInTheDocument();
  });

  it("does not crash on a capability load error", () => {
    useFacultyCapabilities.mockReturnValue({ status: "error", error: new Error("boom") });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText(/could not load your capabilities/i)).toBeInTheDocument();
  });

  it("shows a hint, not a crash, when the caller holds neither capability", () => {
    useFacultyCapabilities.mockReturnValue({ status: "ready", capabilities: [] });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText(/has not yet granted you an assessment capability/i)).toBeInTheDocument();
    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.queryByText("Reviewer")).not.toBeInTheDocument();
  });

  it("shows both badges when the caller holds both capabilities", () => {
    useFacultyCapabilities.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_author", "assessment_reviewer"],
    });
    render(<AssessmentStudioOverview />);

    expect(screen.getByText("Author")).toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
  });

  it("shows only the Reviewer badge when only reviewer is granted", () => {
    useFacultyCapabilities.mockReturnValue({ status: "ready", capabilities: ["assessment_reviewer"] });
    render(<AssessmentStudioOverview />);

    expect(screen.queryByText("Author")).not.toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
  });

  it("never renders an evaluator/moderator/lead capability badge, even when granted", () => {
    useFacultyCapabilities.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_author", "assessment_reviewer", "assessment_evaluator"],
    });
    render(<AssessmentStudioOverview />);

    for (const badge of ["Evaluator", "Moderator", "Lead"]) {
      expect(screen.queryByText(badge)).not.toBeInTheDocument();
    }
  });

  it("shows no numeric metrics or fabricated statistics", () => {
    useFacultyCapabilities.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    render(<AssessmentStudioOverview />);

    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /overview|analytics|dashboard/i })).not.toBeInTheDocument();
  });
});
