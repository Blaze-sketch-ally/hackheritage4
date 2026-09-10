import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const {
  getFacultyProfile,
  listFacultyOpportunities,
  getIncomingCollaborations,
  getFacultyTasks,
  useFacultyCapabilitiesContext,
} = vi.hoisted(() => ({
  getFacultyProfile: vi.fn(),
  listFacultyOpportunities: vi.fn(),
  getIncomingCollaborations: vi.fn(),
  getFacultyTasks: vi.fn(),
  useFacultyCapabilitiesContext: vi.fn(),
}));

vi.mock("@/lib/faculty/profile", () => ({
  getFacultyProfile,
}));

vi.mock("@/lib/faculty/opportunities", () => ({
  listFacultyOpportunities,
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getIncomingCollaborations,
}));

vi.mock("@/lib/faculty/tasks", () => ({
  getFacultyTasks,
}));

vi.mock("@/lib/faculty/capabilities", async () => {
  const actual = await vi.importActual<typeof import("@/lib/faculty/capabilities")>("@/lib/faculty/capabilities");
  return { ...actual, useFacultyCapabilitiesContext };
});

import { FacultyDashboardView } from "@/components/faculty/faculty-dashboard-view";
import { ApiError } from "@/lib/api";

function profile(overrides = {}) {
  return {
    id: "faculty-1",
    designation: null,
    department: null,
    institution_name: null,
    phone: null,
    bio: null,
    expertise_areas: [],
    years_of_experience: null,
    created_at: null,
    updated_at: null,
    completeness: 0,
    ...overrides,
  };
}

describe("FacultyDashboardView", () => {
  beforeEach(() => {
    listFacultyOpportunities.mockResolvedValue({ opportunities: [] });
    getIncomingCollaborations.mockResolvedValue({ collaborations: [] });
    getFacultyTasks.mockResolvedValue({
      pending_reviews: [],
      pending_evaluations: [],
      mentorship_attention: [],
      pending_reconciliations: [],
    });
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: [] });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a 'complete your profile' prompt and 0% completeness for a brand-new profile", async () => {
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);

    expect(await screen.findByText(/complete your academic profile/i)).toBeInTheDocument();
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /complete your profile/i })).toBeInTheDocument();
  });

  it("shows the profile summary instead of the completion prompt once filled in", async () => {
    getFacultyProfile.mockResolvedValue(profile({ designation: "Professor", department: "CSE", completeness: 1 }));

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Professor · CSE")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /complete your profile/i })).not.toBeInTheDocument();
  });

  it("shows a retryable error state if any dashboard data fails to load", async () => {
    getFacultyProfile.mockRejectedValueOnce(new ApiError(500, "Backend temporarily unavailable."));

    render(<FacultyDashboardView />);
    expect(await screen.findByText("Backend temporarily unavailable.")).toBeInTheDocument();
  });

  it("shows real counts for available opportunities and pending applications (F3.2)", async () => {
    getFacultyProfile.mockResolvedValue(profile({ completeness: 1 }));
    listFacultyOpportunities.mockResolvedValue({
      opportunities: [{ id: "o1" }, { id: "o2" }, { id: "o3" }],
    });
    getIncomingCollaborations.mockResolvedValue({ collaborations: [{ id: "c1" }] });

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Available Opportunities")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Applications Needing Action")).toBeInTheDocument();
    // "1" appears both as the stat value and as the Quick Actions badge count.
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
  });

  it("requests only SENT collaborations for the pending-applications count", async () => {
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);
    await screen.findByText("Available Opportunities");

    expect(getIncomingCollaborations).toHaveBeenCalledWith({ status: "SENT" });
  });

  // ============================================================
  // Phase 1 (Faculty Dashboard Architecture)
  // ============================================================

  it("shows no question-contribution content merely because the viewer is Faculty", async () => {
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);
    await screen.findByText("Available Opportunities");

    for (const label of ["Questions Authored", "Pending Your Review", "Approved", "Needs Revision", "Create Question"]) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it("shows no workspace switcher for a Faculty member with no extra capability", async () => {
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);
    await screen.findByText("Available Opportunities");

    expect(screen.queryByText("Your Faculty Workspaces")).not.toBeInTheDocument();
  });

  it("shows a Question Studio switcher link for an author", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Your Faculty Workspaces")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /question studio/i })).toHaveAttribute(
      "href",
      "/faculty/assessment-studio",
    );
    expect(screen.queryByRole("button", { name: /evaluation workspace/i })).not.toBeInTheDocument();
  });

  it("shows both switcher links for an author + evaluator", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_author", "assessment_evaluator"],
    });
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Your Faculty Workspaces")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /question studio/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /evaluation workspace/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace",
    );
  });

  // ============================================================
  // Faculty Module audit: deterministic "Needs Your Attention" tasks
  // ============================================================

  it("shows no tasks card when every category is empty", async () => {
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);
    await screen.findByText("Available Opportunities");

    expect(screen.queryByText("Needs Your Attention")).not.toBeInTheDocument();
  });

  it("shows a ranked count per non-empty task category, linking to the owning page", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    getFacultyTasks.mockResolvedValue({
      pending_reviews: [
        { question_id: "q1", assessment_id: "a1", question_text: "Q1", created_at: "2026-01-01T00:00:00Z" },
      ],
      pending_evaluations: [
        {
          evaluation_id: "e1",
          attempt_id: "at1",
          assessment_title: "Python Basics",
          status: "ASSIGNED",
          assigned_at: "2026-01-01T00:00:00Z",
        },
      ],
      mentorship_attention: [],
      pending_reconciliations: [],
    });

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Needs Your Attention")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /questions awaiting your review/i })).toHaveAttribute(
      "href",
      "/faculty/questions",
    );
    expect(screen.getByRole("button", { name: /evaluations awaiting your marks/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace",
    );
    expect(screen.queryByRole("button", { name: /mentorships awaiting your action/i })).not.toBeInTheDocument();
  });

  it("shows the mentorship-attention row linking to the mentorship page", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    getFacultyTasks.mockResolvedValue({
      pending_reviews: [],
      pending_evaluations: [],
      mentorship_attention: [
        {
          mentorship_id: "m1",
          student_id: "s1",
          student_name: "Jane Doe",
          status: "REQUESTED",
          reason: "Awaiting your response to a student's mentorship request.",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      pending_reconciliations: [],
    });

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Needs Your Attention")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /mentorships awaiting your action/i })).toHaveAttribute(
      "href",
      "/faculty/mentorship",
    );
  });

  it("shows the reconciliation row linking to the reconciliation workspace", async () => {
    getFacultyProfile.mockResolvedValue(profile());
    getFacultyTasks.mockResolvedValue({
      pending_reviews: [],
      pending_evaluations: [],
      mentorship_attention: [],
      pending_reconciliations: [
        {
          attempt_id: "at-1",
          assessment_id: "a-1",
          assessment_title: "Python Basics",
          student_label: "Student abcd1234",
          question_id: "q-1",
          question_text: "Explain closures.",
          points: "10.00",
        },
      ],
    });

    render(<FacultyDashboardView />);

    expect(await screen.findByText("Needs Your Attention")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /evaluations requiring reconciliation/i }),
    ).toHaveAttribute("href", "/faculty/reconciliation");
  });

  it("does not show a switcher link from moderator/lead alone", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({
      status: "ready",
      capabilities: ["assessment_moderator", "assessment_lead"],
    });
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView />);
    await screen.findByText("Available Opportunities");

    expect(screen.queryByText("Your Faculty Workspaces")).not.toBeInTheDocument();
  });
});
