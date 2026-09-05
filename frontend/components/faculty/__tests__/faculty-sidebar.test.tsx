import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/faculty/dashboard",
}));

const { useFacultyCapabilitiesContext } = vi.hoisted(() => ({
  useFacultyCapabilitiesContext: vi.fn(),
}));

vi.mock("@/lib/faculty/capabilities", async () => {
  const actual = await vi.importActual<typeof import("@/lib/faculty/capabilities")>("@/lib/faculty/capabilities");
  return { ...actual, useFacultyCapabilitiesContext };
});

import { FacultySidebar } from "@/components/faculty/faculty-sidebar";

describe("FacultySidebar", () => {
  it("links every implemented Faculty Connect route as a real navigable link", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
    render(<FacultySidebar />);

    for (const [name, href] of [
      ["Dashboard", "/faculty/dashboard"],
      ["Opportunities", "/faculty/opportunities"],
      ["Applications", "/faculty/applications"],
      ["Mentorship", "/faculty/mentorship"],
      ["Profile", "/faculty/profile"],
      ["Settings", "/faculty/settings"],
    ] as const) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });

  it("shows not-yet-implemented Faculty Connect features as disabled 'Soon' items, not fake links", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
    render(<FacultySidebar />);

    for (const label of [
      "Research",
      "Consultancy",
      "FDPs",
      "Workshops",
      "Collaborations",
      "Calendar",
      "Internships",
    ]) {
      expect(screen.queryByRole("link", { name: label })).not.toBeInTheDocument();
      const row = screen.getByText(label).closest("div");
      expect(row).toHaveTextContent("Soon");
    }
  });

  // ============================================================
  // Phase 1 (Faculty Dashboard Architecture): capability-aware nav
  // ============================================================

  it("shows no Question Studio or Evaluation Workspace links while capabilities are still loading", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "loading" });
    render(<FacultySidebar />);

    expect(screen.queryByRole("link", { name: "Overview" })).not.toBeInTheDocument();
    expect(screen.queryByText("Question Studio")).not.toBeInTheDocument();
    expect(screen.queryByText("Evaluation Workspace")).not.toBeInTheDocument();
  });

  it("shows no Question Studio or Evaluation Workspace links on a capability load error", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "error", error: new Error("boom") });
    render(<FacultySidebar />);

    expect(screen.queryByText("Question Studio")).not.toBeInTheDocument();
    expect(screen.queryByText("Evaluation Workspace")).not.toBeInTheDocument();
  });

  it("shows neither Question Studio nor Evaluation Workspace for plain Faculty with no capability", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
    render(<FacultySidebar />);

    expect(screen.queryByText("Question Studio")).not.toBeInTheDocument();
    expect(screen.queryByText("Evaluation Workspace")).not.toBeInTheDocument();
  });

  it("shows Question Studio for a Faculty member with assessment_author", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    render(<FacultySidebar />);

    expect(screen.getByText("Question Studio")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Question Bank" })).toHaveAttribute("href", "/faculty/questions");
    expect(screen.getByRole("link", { name: "Blueprints" })).toHaveAttribute("href", "/faculty/blueprint");
    expect(screen.queryByText("Evaluation Workspace")).not.toBeInTheDocument();
  });

  it("shows Question Studio for a Faculty member with only assessment_reviewer (no author)", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_reviewer"] });
    render(<FacultySidebar />);

    expect(screen.getByText("Question Studio")).toBeInTheDocument();
  });

  it("shows Evaluation Workspace for a Faculty member with assessment_evaluator, but not Question Studio", () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_evaluator"] });
    render(<FacultySidebar />);

    expect(screen.queryByText("Question Studio")).not.toBeInTheDocument();
    expect(screen.getByText("Evaluation Workspace")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Overview" })[0]).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace",
    );
  });

  it("shows both Question Studio and Evaluation Workspace for a Faculty member with both capabilities", () => {
    useFacultyCapabilitiesContext.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_author", "assessment_evaluator"],
    });
    render(<FacultySidebar />);

    expect(screen.getByText("Question Studio")).toBeInTheDocument();
    expect(screen.getByText("Evaluation Workspace")).toBeInTheDocument();
  });

  it("does not grant Question Studio or Evaluation Workspace access from moderator/lead alone", () => {
    useFacultyCapabilitiesContext.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_moderator", "assessment_lead"],
    });
    render(<FacultySidebar />);

    expect(screen.queryByText("Question Studio")).not.toBeInTheDocument();
    expect(screen.queryByText("Evaluation Workspace")).not.toBeInTheDocument();
  });
});
