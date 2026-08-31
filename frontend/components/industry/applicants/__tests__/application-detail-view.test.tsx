import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getApplication: vi.fn(),
  updateApplicationStatus: vi.fn(),
  getApplicationMatch: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/applications", () => ({
  getApplication: mocks.getApplication,
  updateApplicationStatus: mocks.updateApplicationStatus,
  getApplicationMatch: mocks.getApplicationMatch,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { ApplicationDetailView } from "@/components/industry/applicants/application-detail-view";
import { ApiError } from "@/lib/api";
import type { Application } from "@/types/application";

function application(overrides: Partial<Application> = {}): Application {
  return {
    id: "app-1",
    student_id: "11112222-3333-4444-5555-666677778888",
    industry_id: "industry-1",
    opportunity_type: "INTERNSHIP",
    internship_id: "int-1",
    job_id: null,
    status: "SHORTLISTED",
    cover_note: "I built three side projects with your stack.",
    match_score: null,
    applied_at: "2026-09-01T00:00:00Z",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-02T00:00:00Z",
    opportunity: { id: "int-1", title: "Backend Intern", status: "PUBLISHED" },
    ...overrides,
  };
}

describe("ApplicationDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getApplication.mockReturnValue(new Promise(() => {}));
    render(<ApplicationDetailView applicationId="app-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getApplication.mockRejectedValueOnce(new ApiError(404, "Application not found."));
    render(<ApplicationDetailView applicationId="app-x" />);
    expect(await screen.findByText(/doesn't exist or isn't for one of your postings/i)).toBeInTheDocument();
  });

  it("renders application detail with status, opportunity and cover note", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    render(<ApplicationDetailView applicationId="app-1" />);

    expect(await screen.findByRole("heading", { name: /Applicant 11112222/ })).toBeInTheDocument();
    expect(screen.getByText("Shortlisted")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Backend Intern" })).toBeInTheDocument();
    expect(screen.getByText(/three side projects/)).toBeInTheDocument();
  });

  it("does not expose applicant profile fields, only the student id", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(screen.getByText("11112222-3333-4444-5555-666677778888")).toBeInTheDocument();
    expect(screen.getByText(/not available to companies/i)).toBeInTheDocument();
  });

  it("moves the application to a new status via the confirmation dialog", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    mocks.updateApplicationStatus.mockResolvedValueOnce(application({ status: "INTERVIEW_SCHEDULED" }));

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Schedule interview" }));

    await waitFor(() =>
      expect(mocks.updateApplicationStatus).toHaveBeenCalledWith("app-1", "INTERVIEW_SCHEDULED"),
    );
    expect(await screen.findByText(/moved to/i)).toBeInTheDocument();
    expect(screen.getByText("Interview scheduled")).toBeInTheDocument();
  });

  it("handles a 409 invalid-transition from a stale tab", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    mocks.updateApplicationStatus.mockRejectedValueOnce(
      new ApiError(409, "An application at 'SELECTED' can't be moved to 'REJECTED'."),
    );

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

    expect(await screen.findByText(/can't be moved/i)).toBeInTheDocument();
  });

  it("offers no status actions for a terminal application", async () => {
    mocks.getApplication.mockResolvedValueOnce(application({ status: "SELECTED" }));
    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Schedule interview/ })).not.toBeInTheDocument();
  });

  it("shows the Skill Match card idle, and calculates on demand without auto-running", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    mocks.getApplicationMatch.mockResolvedValueOnce({
      application_id: "app-1",
      score: 66,
      recommendation: "GOOD",
      skill_coverage: "2 / 3",
      required_count: 3,
      matched_count: 2,
      needs_improvement_count: 0,
      missing_count: 1,
      matched_skills: [],
      needs_improvement_skills: [],
      missing_skills: [],
    });

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(screen.getByText("Skill Match")).toBeInTheDocument();
    expect(mocks.getApplicationMatch).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));
    await waitFor(() => expect(mocks.getApplicationMatch).toHaveBeenCalledWith("app-1"));
    expect(await screen.findByText("66")).toBeInTheDocument();
  });
});
