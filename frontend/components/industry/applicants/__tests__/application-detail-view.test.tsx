import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getApplication: vi.fn(),
  updateApplicationStatus: vi.fn(),
  getApplicationMatch: vi.fn(),
  provisionJobTraining: vi.fn(),
  getJobTrainingProgram: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/applications", () => ({
  getApplication: mocks.getApplication,
  updateApplicationStatus: mocks.updateApplicationStatus,
  getApplicationMatch: mocks.getApplicationMatch,
  provisionJobTraining: mocks.provisionJobTraining,
}));
vi.mock("@/lib/industry/job-training", () => ({
  getJobTrainingProgram: mocks.getJobTrainingProgram,
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

  it("shows the applicant's real name when the backend resolved one", async () => {
    mocks.getApplication.mockResolvedValueOnce(application({ student_name: "Arunangshu Pal" }));
    render(<ApplicationDetailView applicationId="app-1" />);

    expect(await screen.findByRole("heading", { name: "Arunangshu Pal" })).toBeInTheDocument();
    expect(screen.getByText("Applicant 11112222")).toBeInTheDocument();
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

  it("shows the backend provisioning message and a workspace link on SELECTED (internship)", async () => {
    mocks.getApplication.mockResolvedValueOnce(
      application({ status: "INTERVIEW_SCHEDULED" }),
    );
    mocks.updateApplicationStatus.mockResolvedValueOnce(
      application({
        status: "SELECTED",
        provisioning: {
          kind: "INTERNSHIP_WORKSPACE",
          outcome: "CREATED",
          provisioned: true,
          message: "Selected — Internship Workspace created.",
          internship_id: "int-1",
        },
      }),
    );

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Mark selected" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Mark selected" }));

    expect(
      await screen.findByText("Selected — Internship Workspace created."),
    ).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Open Internship Workspace/ });
    expect(link).toHaveAttribute("href", "/industry/internships/int-1/submissions");
  });

  it("shows the job-training-not-published provisioning message without a link", async () => {
    mocks.getApplication.mockResolvedValueOnce(
      application({
        status: "INTERVIEW_SCHEDULED",
        opportunity_type: "JOB",
        internship_id: null,
        job_id: "job-1",
      }),
    );
    mocks.updateApplicationStatus.mockResolvedValueOnce(
      application({
        status: "SELECTED",
        opportunity_type: "JOB",
        internship_id: null,
        job_id: "job-1",
        provisioning: {
          kind: "JOB_TRAINING",
          outcome: "SKIPPED_NO_PROGRAM",
          provisioned: false,
          message: "Selected — Job Training is not published yet.",
        },
      }),
    );
    // The Training panel does its own read-only program-status check —
    // no program exists yet, matching the SKIPPED_NO_PROGRAM outcome above.
    mocks.getJobTrainingProgram.mockRejectedValueOnce(new ApiError(404, "not found"));

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Mark selected" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Mark selected" }));

    expect(
      await screen.findByText("Selected — Job Training is not published yet."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Internship Workspace/ }),
    ).not.toBeInTheDocument();
  });

  it("falls back to the generic moved-to message when there is no provisioning info", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    mocks.updateApplicationStatus.mockResolvedValueOnce(
      application({ status: "INTERVIEW_SCHEDULED" }),
    );

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Schedule interview" }));

    expect(await screen.findByText(/moved to/i)).toBeInTheDocument();
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

  // ============================================================
  // Job Training "Assign Training" panel (JOB + SELECTED only)
  // ============================================================

  it("shows the Assign Training panel for a SELECTED JOB application with a published program", async () => {
    mocks.getApplication.mockResolvedValueOnce(
      application({
        status: "SELECTED",
        opportunity_type: "JOB",
        internship_id: null,
        job_id: "job-1",
        opportunity: { id: "job-1", title: "Site Reliability Engineer", status: "PUBLISHED" },
      }),
    );
    mocks.getJobTrainingProgram.mockResolvedValueOnce({
      job: { id: "job-1", title: "Site Reliability Engineer", status: "PUBLISHED" },
      program: {
        id: "prog-1",
        job_id: "job-1",
        title: "SRE Onboarding",
        summary: null,
        estimated_weeks: 8,
        status: "PUBLISHED",
        published_at: "2026-11-03T09:00:00Z",
        created_at: null,
        updated_at: null,
      },
      modules: [],
      skills: [],
      available_skills: [],
    });

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(await screen.findByText("SRE Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Status: Not assigned")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Training" })).toBeInTheDocument();
  });

  it("does not show the Assign Training panel for a non-SELECTED JOB application", async () => {
    mocks.getApplication.mockResolvedValueOnce(
      application({
        status: "SHORTLISTED",
        opportunity_type: "JOB",
        internship_id: null,
        job_id: "job-1",
        opportunity: { id: "job-1", title: "Site Reliability Engineer", status: "PUBLISHED" },
      }),
    );

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(screen.queryByText("Status: Not assigned")).not.toBeInTheDocument();
    expect(mocks.getJobTrainingProgram).not.toHaveBeenCalled();
  });

  it("does not show the Assign Training panel for a SELECTED internship application", async () => {
    mocks.getApplication.mockResolvedValueOnce(application({ status: "SELECTED" }));

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(screen.queryByText("Status: Not assigned")).not.toBeInTheDocument();
    expect(mocks.getJobTrainingProgram).not.toHaveBeenCalled();
  });

  it("shows Training Assigned immediately after a SELECTED transition that auto-provisioned it", async () => {
    mocks.getApplication.mockResolvedValueOnce(
      application({
        status: "INTERVIEW_SCHEDULED",
        opportunity_type: "JOB",
        internship_id: null,
        job_id: "job-1",
      }),
    );
    mocks.updateApplicationStatus.mockResolvedValueOnce(
      application({
        status: "SELECTED",
        opportunity_type: "JOB",
        internship_id: null,
        job_id: "job-1",
        provisioning: {
          kind: "JOB_TRAINING",
          outcome: "CREATED",
          provisioned: true,
          message: "Selected — Job Training enrollment created.",
          enrollment_id: "enr-1",
        },
      }),
    );
    mocks.getJobTrainingProgram.mockResolvedValueOnce({
      job: { id: "job-1", title: "Site Reliability Engineer", status: "PUBLISHED" },
      program: {
        id: "prog-1",
        job_id: "job-1",
        title: "SRE Onboarding",
        summary: null,
        estimated_weeks: 8,
        status: "PUBLISHED",
        published_at: "2026-11-03T09:00:00Z",
        created_at: null,
        updated_at: null,
      },
      modules: [],
      skills: [],
      available_skills: [],
    });

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Mark selected" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Mark selected" }));

    expect(await screen.findByText("Training Assigned")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
    expect(mocks.provisionJobTraining).not.toHaveBeenCalled();
  });
});
