import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  listMyApplications: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({
  listMyApplications: mocks.listMyApplications,
}));

import { MyApplicationsView } from "@/components/student/opportunities/my-applications-view";
import { ApplicationStatusBadge } from "@/components/student/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import {
  STUDENT_APPLICATION_STATUSES,
  type StudentApplication,
} from "@/types/student-opportunity";

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
    },
    ...overrides,
  };
}

describe("MyApplicationsView", () => {
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
        application({ id: "app-2", status: "SELECTED", opportunity: { ...application().opportunity!, title: "Platform Eng", source_type: "JOB", id: "job_j-1" }, opportunity_type: "JOB" }),
      ],
    });
    render(<MyApplicationsView />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
    expect(screen.getByText("Platform Eng")).toBeInTheDocument();
    expect(screen.getByText("Selected")).toBeInTheDocument();
  });

  it("renders safely for a row whose posting is no longer visible", async () => {
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ opportunity: { id: "", source_type: "INTERNSHIP", title: null, industry: null, location: null } })],
    });
    render(<MyApplicationsView />);
    expect(await screen.findByText("Internship")).toBeInTheDocument();
  });
});

describe("ApplicationStatusBadge", () => {
  it("renders every one of the seven statuses", () => {
    for (const status of STUDENT_APPLICATION_STATUSES) {
      const { unmount } = render(<ApplicationStatusBadge status={status} />);
      unmount();
    }
    // A friendly label is shown for the multi-word statuses.
    render(<ApplicationStatusBadge status="INTERVIEW_SCHEDULED" />);
    expect(screen.getByText("Interview Scheduled")).toBeInTheDocument();
    render(<ApplicationStatusBadge status="UNDER_REVIEW" />);
    expect(screen.getByText("Under Review")).toBeInTheDocument();
  });
});
