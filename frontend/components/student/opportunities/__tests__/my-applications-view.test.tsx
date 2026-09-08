import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  listMyApplications: vi.fn(),
  listMyInternshipWorkspaces: vi.fn(),
  listMyJobTraining: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({
  listMyApplications: mocks.listMyApplications,
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
