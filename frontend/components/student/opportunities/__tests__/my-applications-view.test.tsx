import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listMyApplications: vi.fn(),
  listMyInternshipWorkspaces: vi.fn(),
  listMyJobTraining: vi.fn(),
  withdrawApplication: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({
  listMyApplications: mocks.listMyApplications,
  withdrawApplication: mocks.withdrawApplication,
}));

vi.mock("@/lib/student/internship-workspace", () => ({
  listMyInternshipWorkspaces: mocks.listMyInternshipWorkspaces,
}));

vi.mock("@/lib/student/job-training", () => ({
  listMyJobTraining: mocks.listMyJobTraining,
}));

import { MyApplicationsView } from "@/components/student/opportunities/my-applications-view";
import { ApplicationStatusBadge } from "@/components/student/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import {
  STUDENT_APPLICATION_STATUSES,
  type StudentApplication,
  type StudentApplicationInterview,
} from "@/types/student-opportunity";
import type { JobTrainingEnrollmentSummary } from "@/types/job-training";

function application(overrides: Partial<StudentApplication> = {}): StudentApplication {
  return {
    id: "app-1",
    student_id: "student-1",
    opportunity_type: "INTERNSHIP",
    internship_id: "int-1",
    job_id: null,
    status: "APPLIED",
    cover_note: null,
    match_score: null,
    applied_at: "2026-09-02T00:00:00Z",
    created_at: "2026-09-02T00:00:00Z",
    updated_at: "2026-09-02T00:00:00Z",
    opportunity: {
      id: "internship_int-1",
      source_type: "INTERNSHIP",
      title: "Backend Intern",
      industry: { id: "industry-1", company_name: "Acme", industry_sector: null, logo_url: null },
      location: "Pune",
      work_mode: "HYBRID",
    },
    interview: null,
    ...overrides,
  };
}

function jobApplication(overrides: Partial<StudentApplication> = {}): StudentApplication {
  return application({
    id: "job-app",
    opportunity_type: "JOB",
    internship_id: null,
    job_id: "j-1",
    opportunity: {
      id: "job_j-1",
      source_type: "JOB",
      title: "Platform Engineer",
      industry: { id: "industry-1", company_name: "Acme", industry_sector: null, logo_url: null },
      location: "Remote",
      work_mode: "REMOTE",
    },
    ...overrides,
  });
}

function scheduledInterview(
  overrides: Partial<StudentApplicationInterview> = {},
): StudentApplicationInterview {
  return {
    id: "iv-1",
    application_id: "app-1",
    scheduled_at: "2026-09-12T09:30:00Z",
    duration_minutes: 30,
    mode: "ONLINE",
    location: "https://meet.example.com/abc",
    status: "SCHEDULED",
    ...overrides,
  };
}

function enrollment(
  overrides: Partial<JobTrainingEnrollmentSummary> = {},
): JobTrainingEnrollmentSummary {
  return {
    enrollment_id: "enr-1",
    application_id: "job-app",
    job_id: "j-1",
    job_title: "Platform Engineer",
    program_id: "prog-1",
    program_title: "Onboarding",
    program_status: "PUBLISHED",
    enrollment_status: "ACTIVE",
    created_at: "2026-09-08T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

describe("MyApplicationsView", () => {
  beforeEach(() => {
    mocks.listMyInternshipWorkspaces.mockResolvedValue({ workspaces: [] });
    mocks.listMyJobTraining.mockResolvedValue({ enrollments: [] });
  });
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listMyApplications.mockReturnValue(new Promise(() => {}));
    render(<MyApplicationsView />);
    expect(screen.getByLabelText("Loading applications")).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [] });
    render(<MyApplicationsView />);
    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listMyApplications.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<MyApplicationsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders each application with its Industry-set status", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application(),
        jobApplication({ id: "app-2", status: "SELECTED" }),
      ],
    });
    render(<MyApplicationsView />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
    expect(screen.getByText("Platform Engineer")).toBeInTheDocument();
    expect(screen.getByText("Selected")).toBeInTheDocument();
  });

  it("renders safely for a row whose posting is no longer visible", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ opportunity: { id: "", source_type: "INTERNSHIP", title: null, industry: null, location: null, work_mode: null } })],
    });
    render(<MyApplicationsView />);
    expect(await screen.findByText("Internship")).toBeInTheDocument();
  });

  it("shows an Open Internship Workspace CTA for a SELECTED internship that has a workspace", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-9", status: "SELECTED" })],
    });
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({
      workspaces: [
        {
          id: "ws-42",
          application_id: "app-9",
          internship_id: "int-1",
          student_id: "student-1",
          industry_id: "industry-1",
          work_mode: "HYBRID",
          workspace_status: "PENDING_ACCEPTANCE",
          accepted_at: null, started_at: null, completed_at: null,
          declined_at: null, decline_reason: null, rescinded_at: null, rescind_reason: null,
          created_at: null, updated_at: null, internship: null,
        },
      ],
    });
    render(<MyApplicationsView />);
    const cta = await screen.findByRole("button", { name: /open internship workspace/i });
    expect(cta).toHaveAttribute("href", "/student/my-internships/ws-42");
  });

  it("does not fabricate a workspace for a SELECTED internship without one", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-9", status: "SELECTED" })], // work_mode HYBRID
    });
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    render(<MyApplicationsView />);
    expect(
      await screen.findByText("Internship workspace is not available yet."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /open internship workspace/i }),
    ).not.toBeInTheDocument();
  });

  it("tells the student an on-site SELECTED internship has no online workspace", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({
          id: "app-9",
          status: "SELECTED",
          opportunity: { ...application().opportunity!, work_mode: "ONSITE" },
        }),
      ],
    });
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    render(<MyApplicationsView />);
    expect(
      await screen.findByText("On-site internship — no online workspace."),
    ).toBeInTheDocument();
  });

  it("shows the applications list even if the workspace / job-training lookup fails", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [application()] });
    mocks.listMyInternshipWorkspaces.mockRejectedValueOnce(new ApiError(500, "down"));
    mocks.listMyJobTraining.mockRejectedValueOnce(new ApiError(500, "down"));
    render(<MyApplicationsView />);
    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
  });

  // ---- Job Training CTA (J5) ----

  it("shows an Open Job Training CTA for a SELECTED job that has an enrollment", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [jobApplication({ status: "SELECTED" })],
    });
    mocks.listMyJobTraining.mockResolvedValueOnce({ enrollments: [enrollment()] });
    render(<MyApplicationsView />);
    const cta = await screen.findByRole("button", { name: /open job training/i });
    expect(cta).toHaveAttribute("href", "/student/job-training/enr-1");
  });

  it("does NOT fabricate a training CTA for a SELECTED job with no enrollment", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [jobApplication({ status: "SELECTED" })],
    });
    mocks.listMyJobTraining.mockResolvedValueOnce({ enrollments: [] });
    render(<MyApplicationsView />);
    expect(
      await screen.findByText("Job training isn't available for this role."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /job training/i }),
    ).not.toBeInTheDocument();
  });

  it("does NOT show a training CTA for a non-selected job even if some enrollment exists", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [jobApplication({ status: "SHORTLISTED" })],
    });
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [enrollment({ application_id: "other" })],
    });
    render(<MyApplicationsView />);
    await screen.findByText("Platform Engineer");
    expect(screen.queryByRole("button", { name: /job training/i })).not.toBeInTheDocument();
  });

  it("never shows a Job Training CTA for a SELECTED internship", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ id: "int-app", status: "SELECTED" })],
    });
    // even if an unrelated enrollment is returned
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [enrollment({ application_id: "int-app" })],
    });
    render(<MyApplicationsView />);
    await screen.findByText("Backend Intern");
    expect(screen.queryByRole("button", { name: /job training/i })).not.toBeInTheDocument();
    // the internship keeps its own (not-yet-available) workspace messaging
    expect(
      screen.getByText("Internship workspace is not available yet."),
    ).toBeInTheDocument();
  });

  // ---- Interview details (Student Interview Details feature) ----

  it("shows interview details for an INTERVIEW_SCHEDULED application with a live interview", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({ status: "INTERVIEW_SCHEDULED", interview: scheduledInterview() }),
      ],
    });
    render(<MyApplicationsView />);

    expect(await screen.findByText("Interview scheduled")).toBeInTheDocument();
    expect(screen.getByText(/^Date:/)).toHaveTextContent(/2026/);
    expect(screen.getByText(/^Time:/)).toHaveTextContent(/\d{1,2}:\d{2}/);
    expect(screen.getByText(/^Duration:/)).toHaveTextContent("30 minutes");
    expect(screen.getByText(/^Mode:/)).toHaveTextContent("Online");
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument();
  });

  it("renders a clickable, safe Join meeting link for an online interview", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({ status: "INTERVIEW_SCHEDULED", interview: scheduledInterview() }),
      ],
    });
    render(<MyApplicationsView />);

    const link = await screen.findByRole("link", { name: /join meeting/i });
    expect(link).toHaveAttribute("href", "https://meet.example.com/abc");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the phone number as plain text (no Join link) for a phone interview", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({
          status: "INTERVIEW_SCHEDULED",
          interview: scheduledInterview({ mode: "PHONE", location: "+91 98765 43210" }),
        }),
      ],
    });
    render(<MyApplicationsView />);

    expect(await screen.findByText(/^Phone number:/)).toHaveTextContent("+91 98765 43210");
    expect(screen.getByText(/^Mode:/)).toHaveTextContent("Phone");
    expect(screen.queryByRole("link", { name: /join meeting/i })).not.toBeInTheDocument();
  });

  it("does not render an anchor when an online interview location is not a URL", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({
          status: "INTERVIEW_SCHEDULED",
          interview: scheduledInterview({ location: "TB2 conference room" }),
        }),
      ],
    });
    render(<MyApplicationsView />);

    expect(await screen.findByText("Interview scheduled")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /join meeting/i })).not.toBeInTheDocument();
    expect(screen.getByText(/^Meeting link:/)).toHaveTextContent("TB2 conference room");
  });

  it("shows a 'being scheduled' note for INTERVIEW_SCHEDULED with no live interview", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ status: "INTERVIEW_SCHEDULED", interview: null })],
    });
    render(<MyApplicationsView />);

    expect(
      await screen.findByText("Your interview is being scheduled — check back soon."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Interview scheduled")).not.toBeInTheDocument();
  });

  it("never shows 'Invalid Date' when scheduled_at is malformed", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({
          status: "INTERVIEW_SCHEDULED",
          interview: scheduledInterview({ scheduled_at: "not-a-real-timestamp" }),
        }),
      ],
    });
    render(<MyApplicationsView />);

    expect(
      await screen.findByText("Your interview is being scheduled — check back soon."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument();
  });

  it("leaves APPLIED / SHORTLISTED / SELECTED behaviour unchanged", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "a-applied", status: "APPLIED" }),
        application({ id: "a-shortlisted", status: "SHORTLISTED" }),
        application({ id: "a-selected", status: "SELECTED" }),
      ],
    });
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    render(<MyApplicationsView />);

    // SELECTED internship (HYBRID) keeps its existing workspace messaging
    expect(
      await screen.findByText("Internship workspace is not available yet."),
    ).toBeInTheDocument();
    // no interview UI leaks onto non-interview rows
    expect(screen.queryByText("Interview scheduled")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Your interview is being scheduled — check back soon."),
    ).not.toBeInTheDocument();
  });

  // ---- Application withdrawal ----

  it.each(["APPLIED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW_SCHEDULED"] as const)(
    "shows a Withdraw action for an eligible application (%s)",
    async (status) => {
      mocks.listMyApplications.mockResolvedValueOnce({
        applications: [application({ status })],
      });
      render(<MyApplicationsView />);
      await screen.findByText("Backend Intern");
      expect(screen.getByRole("button", { name: /withdraw/i })).toBeInTheDocument();
    },
  );

  it.each(["SELECTED", "REJECTED", "WITHDRAWN"] as const)(
    "never shows a Withdraw action for a terminal application (%s)",
    async (status) => {
      mocks.listMyApplications.mockResolvedValueOnce({
        applications: [application({ status })],
      });
      render(<MyApplicationsView />);
      await screen.findByText("Backend Intern");
      expect(screen.queryByRole("button", { name: /withdraw/i })).not.toBeInTheDocument();
    },
  );

  it("shows a meaningful cell (not a bare dash) for a withdrawn application", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ status: "WITHDRAWN" })],
    });
    render(<MyApplicationsView />);
    expect(await screen.findByText("You withdrew this application.")).toBeInTheDocument();
    expect(screen.getByText("Withdrawn")).toBeInTheDocument();
  });

  it("opens a confirmation dialog and does NOT mutate on cancel", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ status: "APPLIED" })],
    });
    render(<MyApplicationsView />);
    await screen.findByText("Backend Intern");

    await userEvent.click(screen.getByRole("button", { name: /withdraw/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/no longer be considered/i)).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: /keep application/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mocks.withdrawApplication).not.toHaveBeenCalled();
  });

  it("withdraws on confirm, updates the row status and shows success feedback", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-9", status: "SHORTLISTED" })],
    });
    mocks.withdrawApplication.mockResolvedValueOnce(
      application({ id: "app-9", status: "WITHDRAWN" }),
    );
    render(<MyApplicationsView />);
    await screen.findByText("Backend Intern");

    await userEvent.click(screen.getByRole("button", { name: /withdraw/i }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: /withdraw application/i }),
    );

    await waitFor(() =>
      expect(mocks.withdrawApplication).toHaveBeenCalledWith("app-9"),
    );
    expect(
      await screen.findByText(/withdrew your application for/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Withdrawn")).toBeInTheDocument();
    expect(screen.getByText("You withdrew this application.")).toBeInTheDocument();
    // the trigger is gone now that the row is terminal
    expect(screen.queryByRole("button", { name: /^withdraw$/i })).not.toBeInTheDocument();
  });

  it("disables the confirm button while the withdrawal is in flight", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ status: "APPLIED" })],
    });
    let resolve: (v: StudentApplication) => void = () => {};
    mocks.withdrawApplication.mockReturnValueOnce(
      new Promise<StudentApplication>((r) => {
        resolve = r;
      }),
    );
    render(<MyApplicationsView />);
    await screen.findByText("Backend Intern");

    await userEvent.click(screen.getByRole("button", { name: /withdraw/i }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: /withdraw application/i });
    await userEvent.click(confirm);

    await waitFor(() =>
      expect(within(dialog).getByRole("button", { name: /please wait/i })).toBeDisabled(),
    );
    resolve(application({ status: "WITHDRAWN" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows a clear error and leaves the status unchanged when withdrawal fails", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ status: "APPLIED" })],
    });
    mocks.withdrawApplication.mockRejectedValueOnce(
      new ApiError(409, "An application at 'SELECTED' can no longer be withdrawn."),
    );
    render(<MyApplicationsView />);
    await screen.findByText("Backend Intern");

    await userEvent.click(screen.getByRole("button", { name: /withdraw/i }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: /withdraw application/i }),
    );

    expect(
      await screen.findByText(/can no longer be withdrawn/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /withdraw/i })).toBeInTheDocument();
  });

  it("keeps the SELECTED internship-workspace CTA (no Withdraw) after adding withdrawal", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-sel", status: "SELECTED" })],
    });
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({
      workspaces: [
        {
          id: "ws-1",
          application_id: "app-sel",
          internship_id: "int-1",
          student_id: "student-1",
          industry_id: "industry-1",
          work_mode: "HYBRID",
          workspace_status: "PENDING_ACCEPTANCE",
          accepted_at: null, started_at: null, completed_at: null,
          declined_at: null, decline_reason: null, rescinded_at: null, rescind_reason: null,
          created_at: null, updated_at: null, internship: null,
        },
      ],
    });
    render(<MyApplicationsView />);
    expect(
      await screen.findByRole("button", { name: /open internship workspace/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /withdraw/i })).not.toBeInTheDocument();
  });
});

describe("ApplicationStatusBadge", () => {
  it("renders every one of the seven statuses", () => {
    for (const status of STUDENT_APPLICATION_STATUSES) {
      const { unmount } = render(<ApplicationStatusBadge status={status} />);
      unmount();
    }
    render(<ApplicationStatusBadge status="INTERVIEW_SCHEDULED" />);
    expect(screen.getByText("Interview Scheduled")).toBeInTheDocument();
    render(<ApplicationStatusBadge status="UNDER_REVIEW" />);
    expect(screen.getByText("Under Review")).toBeInTheDocument();
  });
});
