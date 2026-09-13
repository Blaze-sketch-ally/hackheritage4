import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getApplication: vi.fn(),
  updateApplicationStatus: vi.fn(),
  getApplicationMatch: vi.fn(),
  provisionJobTraining: vi.fn(),
  provisionInternshipWorkspace: vi.fn(),
  getJobTrainingProgram: vi.fn(),
  getInternshipProgram: vi.fn(),
  scheduleInterview: vi.fn(),
  getInterviews: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/applications", () => ({
  getApplication: mocks.getApplication,
  updateApplicationStatus: mocks.updateApplicationStatus,
  getApplicationMatch: mocks.getApplicationMatch,
  provisionJobTraining: mocks.provisionJobTraining,
  provisionInternshipWorkspace: mocks.provisionInternshipWorkspace,
}));
vi.mock("@/lib/industry/job-training", () => ({
  getJobTrainingProgram: mocks.getJobTrainingProgram,
}));
vi.mock("@/lib/industry/internship-program", () => ({
  getInternshipProgram: mocks.getInternshipProgram,
}));
vi.mock("@/lib/industry/interviews", () => ({
  scheduleInterview: mocks.scheduleInterview,
  getInterviews: mocks.getInterviews,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { ApplicationDetailView } from "@/components/industry/applicants/application-detail-view";
import { ApiError } from "@/lib/api";
import type { Application } from "@/types/application";
import type { Interview } from "@/types/interview";

function interview(overrides: Partial<Interview> = {}): Interview {
  return {
    id: "iv-1",
    application_id: "app-1",
    industry_id: "industry-1",
    student_id: "11112222-3333-4444-5555-666677778888",
    student_name: null,
    scheduled_at: "2099-01-01T10:00:00.000Z",
    duration_minutes: 30,
    mode: "ONLINE",
    location: "https://meet.example.com/x",
    notes: null,
    status: "SCHEDULED",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    opportunity: { id: "int-1", title: "Backend Intern", status: "PUBLISHED" },
    opportunity_type: "INTERNSHIP",
    ...overrides,
  };
}

function futureLocal(daysAhead = 3): string {
  const d = new Date(Date.now() + daysAhead * 86400000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

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

  // Harmless defaults for the two silent, read-only checks every
  // INTERVIEW_SCHEDULED / SELECTED-internship application now triggers
  // (the interview card and the Internship Workspace panel) -- most tests
  // below don't care about either and would otherwise need to stub them
  // individually. Any test that DOES care overrides with its own
  // mockResolvedValueOnce before rendering.
  beforeEach(() => {
    mocks.getInterviews.mockResolvedValue({ interviews: [] });
    mocks.getInternshipProgram.mockResolvedValue({
      internship: { id: "int-1", title: "Backend Intern", status: "PUBLISHED" },
      program: null,
      modules: [],
      skills: [],
      available_skills: [],
    });
  });

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

  it("clicking Schedule interview opens the real scheduling dialog directly, with candidate/opportunity context, instead of the generic confirm dialog", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");

    // Context: candidate + opportunity shown right in the dialog header, no
    // need to re-search for the applicant. The single eligible application
    // is already preselected in the (still-present) candidate field too.
    const description = dialog.querySelector('[data-slot="dialog-description"]');
    expect(description).toHaveTextContent("Applicant 11112222");
    expect(description).toHaveTextContent("Backend Intern");
    expect((within(dialog).getByLabelText("Candidate") as HTMLSelectElement).value).toBe("app-1");
    // Not the old generic transition dialog.
    expect(within(dialog).queryByText("This updates where the application sits")).not.toBeInTheDocument();
  });

  it("submits a valid schedule, closes the dialog, and reflects INTERVIEW_SCHEDULED without a page reload", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    mocks.scheduleInterview.mockResolvedValueOnce(interview());
    // The interview card's own fetch (triggered once status flips to
    // INTERVIEW_SCHEDULED) finds the interview that was just scheduled.
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [interview()] });

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Date & time"), futureLocal());
    await userEvent.click(within(dialog).getByRole("button", { name: "Schedule interview" }));

    await waitFor(() => expect(mocks.scheduleInterview).toHaveBeenCalledTimes(1));
    const payload = mocks.scheduleInterview.mock.calls[0][0];
    expect(payload.application_id).toBe("app-1");
    expect(mocks.updateApplicationStatus).not.toHaveBeenCalled();

    expect(await screen.findByText("Interview scheduled.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByText("Interview scheduled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Schedule interview" })).not.toBeInTheDocument();
  });

  it("keeps the dialog open, preserves entered values, and does not change status when scheduling fails", async () => {
    mocks.getApplication.mockResolvedValueOnce(application());
    mocks.scheduleInterview.mockRejectedValueOnce(
      new ApiError(409, "This application already has a scheduled interview."),
    );

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");
    const when = futureLocal();
    await userEvent.type(within(dialog).getByLabelText("Date & time"), when);
    await userEvent.click(within(dialog).getByRole("button", { name: "Schedule interview" }));

    expect(
      await screen.findByText("This application already has a scheduled interview."),
    ).toBeInTheDocument();
    // Dialog stays open with the entered value intact.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect((within(dialog).getByLabelText("Date & time") as HTMLInputElement).value).toBe(when);
    // Still Shortlisted -- no false transition.
    expect(screen.getByText("Shortlisted")).toBeInTheDocument();
    expect(screen.queryByText("Interview scheduled.")).not.toBeInTheDocument();
  });

  it("does not offer Schedule interview once already INTERVIEW_SCHEDULED", async () => {
    mocks.getApplication.mockResolvedValueOnce(application({ status: "INTERVIEW_SCHEDULED" }));
    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(screen.queryByRole("button", { name: "Schedule interview" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark selected" })).toBeInTheDocument();
  });

  it.each(["SELECTED", "REJECTED", "WITHDRAWN"] as const)(
    "never offers Schedule interview for a %s application",
    async (status) => {
      mocks.getApplication.mockResolvedValueOnce(application({ status }));
      render(<ApplicationDetailView applicationId="app-1" />);
      await screen.findByRole("heading", { name: /Applicant 11112222/ });

      expect(screen.queryByRole("button", { name: "Schedule interview" })).not.toBeInTheDocument();
    },
  );

  it("shows the backend provisioning message and a persisted Internship Workspace panel with a working Open Workspace link on SELECTED (internship)", async () => {
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
    mocks.getInternshipProgram.mockResolvedValueOnce({
      internship: { id: "int-1", title: "Backend Intern", status: "PUBLISHED" },
      program: {
        id: "prog-1",
        internship_id: "int-1",
        title: "Backend Internship Onboarding",
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
    mocks.provisionInternshipWorkspace.mockResolvedValueOnce({
      outcome: "CREATED",
      detail: "created",
      work_mode: "REMOTE",
      workspace: {
        id: "ws-1",
        application_id: "app-1",
        internship_id: "int-1",
        student_id: "11112222-3333-4444-5555-666677778888",
        industry_id: "industry-1",
        work_mode: "REMOTE",
        workspace_status: "PENDING_ACCEPTANCE",
        accepted_at: null,
        started_at: null,
        completed_at: null,
        declined_at: null,
        decline_reason: null,
        rescinded_at: null,
        rescind_reason: null,
        created_at: null,
        updated_at: null,
      },
    });

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Mark selected" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Mark selected" }));

    expect(
      await screen.findByText("Selected — Internship Workspace created."),
    ).toBeInTheDocument();
    // The panel derives this from its own persisted-state check
    // (provisionInternshipWorkspace called on mount), never from the
    // transition's own one-shot response -- it would be identical after a
    // refresh.
    expect(await screen.findByText("Pending Acceptance")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Open Workspace" });
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
    mocks.updateApplicationStatus.mockResolvedValueOnce(application({ status: "REJECTED" }));

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

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
    // No initialProvisioning here (a fresh page load, not a live
    // transition) -- the panel's own silent, refresh-safe verify call
    // resolves the real state on mount. This scenario's backend genuinely
    // has nothing enrolled yet.
    mocks.provisionJobTraining.mockResolvedValueOnce({
      outcome: "SKIPPED_NOT_SELECTED",
      detail: "not yet",
      enrollment: null,
    });

    render(<ApplicationDetailView applicationId="app-1" />);
    await screen.findByRole("heading", { name: /Applicant 11112222/ });

    expect(await screen.findByText("SRE Onboarding")).toBeInTheDocument();
    expect(await screen.findByText("Status: Not assigned")).toBeInTheDocument();
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
