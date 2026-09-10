import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getSkillGapApplications: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/institution/skill-gaps", () => ({
  getSkillGapApplications: mocks.getSkillGapApplications,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

import { SkillGapList } from "@/components/institution/skill-gaps/skill-gap-list";
import { ApiError } from "@/lib/api";
import type { SkillGapApplicationSummary } from "@/types/institution-skill-gap";

function application(overrides: Partial<SkillGapApplicationSummary> = {}): SkillGapApplicationSummary {
  return {
    application_id: "app-1",
    student_id: "student-1",
    full_name: "Tapan",
    username: "tapan1",
    opportunity_type: "INTERNSHIP",
    opportunity_title: "Software Intern",
    company_name: "Robotics Inc",
    status: "APPLIED",
    applied_at: "2026-01-01T00:00:00Z",
    score: 67,
    recommendation: "PARTIAL",
    skill_coverage: "2 / 3",
    matched_count: 2,
    needs_improvement_count: 0,
    missing_count: 1,
    ...overrides,
  };
}

describe("SkillGapList", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches applications on mount", () => {
    mocks.getSkillGapApplications.mockReturnValue(new Promise(() => {}));
    render(<SkillGapList />);
    expect(mocks.getSkillGapApplications).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getSkillGapApplications.mockReturnValue(new Promise(() => {}));
    render(<SkillGapList />);
    expect(screen.getByText(/Loading skill gap data/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getSkillGapApplications.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<SkillGapList />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows an empty state instead of Coming Soon when there are no applications", async () => {
    mocks.getSkillGapApplications.mockResolvedValueOnce({ applications: [] });
    render(<SkillGapList />);
    expect(
      await screen.findByText("No student applications available for skill-gap analysis."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });

  it("renders the application list with student, opportunity, company, status and match info", async () => {
    mocks.getSkillGapApplications.mockResolvedValueOnce({ applications: [application()] });
    render(<SkillGapList />);

    expect(await screen.findByText("Tapan")).toBeInTheDocument();
    expect(screen.getByText("Software Intern")).toBeInTheDocument();
    expect(screen.getByText("Robotics Inc")).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
    expect(screen.getByText("Internship")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // matched
    expect(screen.getByText("1")).toBeInTheDocument(); // missing
  });

  it("renders a job application distinctly from an internship", async () => {
    mocks.getSkillGapApplications.mockResolvedValueOnce({
      applications: [application({ application_id: "app-2", opportunity_type: "JOB", opportunity_title: "Backend Developer" })],
    });
    render(<SkillGapList />);
    expect(await screen.findByText("Backend Developer")).toBeInTheDocument();
    expect(screen.getByText("Job")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getSkillGapApplications.mockResolvedValue({ applications: [application()] });
    render(<SkillGapList />);
    await screen.findByText("Tapan");

    await userEvent.type(screen.getByLabelText("Search applications"), "tapan");
    await waitFor(() =>
      expect(mocks.getSkillGapApplications).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "tapan" }),
      ),
    );
  });

  it("navigates to the skill gap detail page when View Skill Gap is clicked", async () => {
    mocks.getSkillGapApplications.mockResolvedValueOnce({ applications: [application()] });
    render(<SkillGapList />);
    await userEvent.click(await screen.findByRole("button", { name: /view skill gap/i }));
    expect(mocks.push).toHaveBeenCalledWith("/institution/skill-gaps/app-1");
  });

  it("navigates to the skill gap detail page when a row is clicked", async () => {
    mocks.getSkillGapApplications.mockResolvedValueOnce({ applications: [application()] });
    render(<SkillGapList />);
    await userEvent.click(await screen.findByText("Tapan"));
    expect(mocks.push).toHaveBeenCalledWith("/institution/skill-gaps/app-1");
  });
});
