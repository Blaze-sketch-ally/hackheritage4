import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getApplications: vi.fn(),
  getApplicationsSummary: vi.fn(),
  updateApplicationStatus: vi.fn(),
}));

vi.mock("@/lib/industry/applications", () => ({
  getApplications: mocks.getApplications,
  getApplicationsSummary: mocks.getApplicationsSummary,
  updateApplicationStatus: mocks.updateApplicationStatus,
}));

import { RecruitmentApplications } from "@/components/industry/recruitment/recruitment-applications";
import { ApiError } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/types/application";

function application(overrides: Partial<Application> = {}): Application {
  return {
    id: "app-1",
    student_id: "11112222-3333-4444-5555-666677778888",
    industry_id: "industry-1",
    opportunity_type: "INTERNSHIP",
    internship_id: "int-1",
    job_id: null,
    status: "APPLIED",
    cover_note: "Keen.",
    match_score: null,
    applied_at: "2026-09-01T00:00:00Z",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    opportunity: { id: "int-1", title: "Backend Intern", status: "PUBLISHED" },
    ...overrides,
  };
}

function summary(counts: Partial<Record<ApplicationStatus, number>> = {}) {
  const base: Record<ApplicationStatus, number> = {
    APPLIED: 0,
    UNDER_REVIEW: 0,
    SHORTLISTED: 0,
    INTERVIEW_SCHEDULED: 0,
    SELECTED: 0,
    REJECTED: 0,
    WITHDRAWN: 0,
  };
  const merged = { ...base, ...counts };
  return { counts: merged, total: Object.values(merged).reduce((a, b) => a + b, 0) };
}

function renderApplicants() {
  return render(
    <RecruitmentApplications
      heading="Applicants"
      description="All applications."
      emptyTitle="No applications yet"
      showFunnel
      showStatusFilter
      showTypeFilter
      layout="table"
    />,
  );
}

function renderStage(lockedStatuses: ApplicationStatus[], props: Partial<React.ComponentProps<typeof RecruitmentApplications>> = {}) {
  return render(
    <RecruitmentApplications
      heading="Shortlisted"
      description="Shortlisted candidates."
      emptyTitle="No shortlisted candidates"
      lockedStatuses={lockedStatuses}
      layout="cards"
      {...props}
    />,
  );
}

describe("RecruitmentApplications", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getApplications.mockReturnValue(new Promise(() => {}));
    mocks.getApplicationsSummary.mockReturnValue(new Promise(() => {}));
    renderApplicants();
    expect(screen.getByText(/Loading applications/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getApplications.mockRejectedValueOnce(new ApiError(500, "Backend down."));
    mocks.getApplicationsSummary.mockResolvedValue(summary());
    renderApplicants();
    expect(await screen.findByText("Backend down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no applications", async () => {
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    renderApplicants();
    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
  });

  it("renders the funnel with per-status counts", async () => {
    mocks.getApplications.mockResolvedValueOnce({ applications: [application()] });
    mocks.getApplicationsSummary.mockResolvedValueOnce(
      summary({ APPLIED: 5, SHORTLISTED: 2, REJECTED: 1 }),
    );
    renderApplicants();

    const funnel = await screen.findByRole("region", { name: "Recruitment pipeline" });
    expect(within(funnel).getByText("8 applications")).toBeInTheDocument();
    const applied = within(funnel).getByRole("button", { name: /Applied/ });
    expect(within(applied).getByText("5")).toBeInTheDocument();
    expect(within(funnel).getByText(/Rejected:/)).toBeInTheDocument();
  });

  it("renders the applicant table with candidate, opportunity and status", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application(), application({ id: "app-2", status: "SHORTLISTED" })],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1, SHORTLISTED: 1 }));
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    expect(table.getAllByText(/Applicant 11112222/).length).toBe(2);
    expect(table.getAllByText("Backend Intern").length).toBe(2);
    expect(table.getByText("Applied")).toBeInTheDocument();
    expect(table.getByText("Shortlisted")).toBeInTheDocument();
  });

  it("shows the applicant's real name when the backend resolved one", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ student_name: "Arunangshu Pal" })],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1 }));
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    expect(table.getByText("Arunangshu Pal")).toBeInTheDocument();
    expect(table.queryByText(/Applicant 11112222/)).not.toBeInTheDocument();
  });

  it("filters the table when a funnel stage is clicked", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-1", status: "APPLIED", opportunity: { id: "i1", title: "Alpha role", status: "PUBLISHED" } }),
        application({ id: "app-2", status: "SHORTLISTED", opportunity: { id: "i2", title: "Beta role", status: "PUBLISHED" } }),
      ],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1, SHORTLISTED: 1 }));
    renderApplicants();

    await screen.findByRole("table");
    const funnel = screen.getByRole("region", { name: "Recruitment pipeline" });
    await userEvent.click(within(funnel).getByRole("button", { name: /Shortlisted/ }));

    const table = within(screen.getByRole("table"));
    expect(table.getByText("Beta role")).toBeInTheDocument();
    expect(table.queryByText("Alpha role")).not.toBeInTheDocument();
  });

  it("moves an application forward via the confirmation dialog and updates the funnel", async () => {
    mocks.getApplications.mockResolvedValueOnce({ applications: [application({ status: "APPLIED" })] });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1 }));
    mocks.updateApplicationStatus.mockResolvedValueOnce(application({ status: "SHORTLISTED" }));
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    await userEvent.click(table.getByRole("button", { name: "Shortlist" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Shortlist" }));

    await waitFor(() => expect(mocks.updateApplicationStatus).toHaveBeenCalledWith("app-1", "SHORTLISTED"));
    expect(await screen.findByText(/Moved to/i)).toBeInTheDocument();

    const funnel = screen.getByRole("region", { name: "Recruitment pipeline" });
    const shortlisted = within(funnel).getByRole("button", { name: /Shortlisted/ });
    expect(within(shortlisted).getByText("1")).toBeInTheDocument();
  });

  it("surfaces a 409 stale-transition from the API", async () => {
    mocks.getApplications.mockResolvedValueOnce({ applications: [application()] });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1 }));
    mocks.updateApplicationStatus.mockRejectedValueOnce(
      new ApiError(409, "An application at 'SELECTED' can't be moved to 'SHORTLISTED'."),
    );
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    await userEvent.click(table.getByRole("button", { name: "Shortlist" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Shortlist" }));

    expect(await screen.findByText(/can't be moved/i)).toBeInTheDocument();
  });

  // ---- stage-locked (Shortlisted / Interviews / Selected) ----

  it("stage view shows only applications in the locked statuses", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "a1", status: "SHORTLISTED", opportunity: { id: "i", title: "Kept", status: "PUBLISHED" } }),
        application({ id: "a2", status: "APPLIED", opportunity: { id: "i", title: "Filtered out", status: "PUBLISHED" } }),
      ],
    });
    renderStage(["SHORTLISTED"]);

    expect(await screen.findByText(/Kept/)).toBeInTheDocument();
    expect(screen.queryByText(/Filtered out/)).not.toBeInTheDocument();
    expect(mocks.getApplicationsSummary).not.toHaveBeenCalled();
  });

  it("stage view shows a stage-specific empty state", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ status: "APPLIED" })],
    });
    renderStage(["SELECTED"], { heading: "Selected", emptyTitle: "No selected candidates yet" });
    expect(await screen.findByText("No selected candidates yet")).toBeInTheDocument();
  });

  it("interviews stage exposes only the Select / Reject transitions", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ status: "INTERVIEW_SCHEDULED" })],
    });
    renderStage(["INTERVIEW_SCHEDULED"], { heading: "Interviews", emptyTitle: "None" });
    await screen.findByText(/Backend Intern/);

    expect(screen.getByRole("button", { name: "Mark selected" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Shortlist" })).not.toBeInTheDocument();
  });

  it("selected stage offers no status actions (terminal)", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ status: "SELECTED" })],
    });
    renderStage(["SELECTED"], { heading: "Selected", emptyTitle: "None" });
    await screen.findByText(/Backend Intern/);

    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });
});
