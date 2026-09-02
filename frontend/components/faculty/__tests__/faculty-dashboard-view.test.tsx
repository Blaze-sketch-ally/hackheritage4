import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const {
  listMyQuestions,
  listAssessmentsForFaculty,
  getFacultyProfile,
  listFacultyOpportunities,
  getIncomingCollaborations,
} = vi.hoisted(() => ({
  listMyQuestions: vi.fn(),
  listAssessmentsForFaculty: vi.fn(),
  getFacultyProfile: vi.fn(),
  listFacultyOpportunities: vi.fn(),
  getIncomingCollaborations: vi.fn(),
}));

vi.mock("@/lib/faculty/question-bank", () => ({
  listMyQuestions,
  listAssessmentsForFaculty,
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
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the existing assessment activity stats unchanged", async () => {
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
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView facultyId="faculty-1" />);

    expect(await screen.findByText("Questions Authored")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
  });

  it("shows a 'complete your profile' prompt and 0% completeness for a brand-new profile", async () => {
    listMyQuestions.mockResolvedValue([]);
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [] });
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView facultyId="faculty-1" />);

    expect(await screen.findByText(/complete your academic profile/i)).toBeInTheDocument();
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /complete your profile/i })).toBeInTheDocument();
  });

  it("shows the profile summary instead of the completion prompt once filled in", async () => {
    listMyQuestions.mockResolvedValue([]);
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [] });
    getFacultyProfile.mockResolvedValue(
      profile({ designation: "Professor", department: "CSE", completeness: 1 }),
    );

    render(<FacultyDashboardView facultyId="faculty-1" />);

    expect(await screen.findByText("Professor · CSE")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    // Fully complete -- no "complete your profile" quick action shown.
    expect(screen.queryByRole("button", { name: /complete your profile/i })).not.toBeInTheDocument();
  });

  it("shows a retryable error state if any dashboard data fails to load", async () => {
    listMyQuestions.mockRejectedValueOnce(new ApiError(500, "Backend temporarily unavailable."));
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [] });
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView facultyId="faculty-1" />);
    expect(await screen.findByText("Backend temporarily unavailable.")).toBeInTheDocument();
  });

  it("shows real counts for available opportunities and pending applications (F3.2)", async () => {
    listMyQuestions.mockResolvedValue([]);
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [] });
    getFacultyProfile.mockResolvedValue(profile({ completeness: 1 }));
    listFacultyOpportunities.mockResolvedValue({
      opportunities: [{ id: "o1" }, { id: "o2" }, { id: "o3" }],
    });
    getIncomingCollaborations.mockResolvedValue({ collaborations: [{ id: "c1" }] });

    render(<FacultyDashboardView facultyId="faculty-1" />);

    expect(await screen.findByText("Available Opportunities")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Applications Needing Action")).toBeInTheDocument();
    // "1" appears both as the stat value and as the Quick Actions badge count.
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
  });

  it("requests only SENT collaborations for the pending-applications count", async () => {
    listMyQuestions.mockResolvedValue([]);
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [] });
    getFacultyProfile.mockResolvedValue(profile());

    render(<FacultyDashboardView facultyId="faculty-1" />);
    await screen.findByText("Available Opportunities");

    expect(getIncomingCollaborations).toHaveBeenCalledWith({ status: "SENT" });
  });
});
