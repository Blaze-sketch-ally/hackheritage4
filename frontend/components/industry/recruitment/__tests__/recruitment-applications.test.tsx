import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getApplications: vi.fn(),
  getApplicationsSummary: vi.fn(),
  updateApplicationStatus: vi.fn(),
  scheduleInterview: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("@/lib/industry/applications", () => ({
  getApplications: mocks.getApplications,
  getApplicationsSummary: mocks.getApplicationsSummary,
  updateApplicationStatus: mocks.updateApplicationStatus,
}));
vi.mock("@/lib/industry/interviews", () => ({
  scheduleInterview: mocks.scheduleInterview,
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
  usePathname: () => "/industry/applicants",
  useSearchParams: () => mocks.searchParams,
}));

import { RecruitmentApplications } from "@/components/industry/recruitment/recruitment-applications";
import { ApiError } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/types/application";
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
  afterEach(() => {
    vi.resetAllMocks();
    mocks.searchParams = new URLSearchParams();
  });

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

  // ---- Schedule interview directly from the Shortlisted card (and the
  // Applicants table, which shares the same component) ----

  it("Shortlisted card's Schedule interview opens the real scheduling dialog, not the generic confirm dialog", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-1", status: "SHORTLISTED" })],
    });
    renderStage(["SHORTLISTED"]);
    await screen.findByText(/Backend Intern/);

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Schedule interview" })).toBeInTheDocument();
    const description = dialog.querySelector('[data-slot="dialog-description"]');
    expect(description).toHaveTextContent("Backend Intern");
    expect(mocks.updateApplicationStatus).not.toHaveBeenCalled();
  });

  it("scheduling from the Shortlisted card updates status and funnel without a full reload", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-1", status: "SHORTLISTED" })],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ SHORTLISTED: 1 }));
    mocks.scheduleInterview.mockResolvedValueOnce(interview());
    renderStage(["SHORTLISTED"], { showFunnel: true });
    await screen.findByText(/Backend Intern/);

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Date & time"), futureLocal());
    await userEvent.click(within(dialog).getByRole("button", { name: "Schedule interview" }));

    await waitFor(() => expect(mocks.scheduleInterview).toHaveBeenCalledTimes(1));
    expect(mocks.scheduleInterview.mock.calls[0][0].application_id).toBe("app-1");
    expect(await screen.findByText("Interview scheduled.")).toBeInTheDocument();
    // Only ever fetched once -- the update is a local patch, not a reload.
    expect(mocks.getApplications).toHaveBeenCalledTimes(1);
    // Now Interview scheduled, gone from the SHORTLISTED-locked stage view.
    expect(screen.queryByText(/Backend Intern/)).not.toBeInTheDocument();
  });

  it("a failed schedule keeps the dialog open and does not change the application's status", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-1", status: "SHORTLISTED" })],
    });
    mocks.scheduleInterview.mockRejectedValueOnce(
      new ApiError(409, "This slot overlaps another interview you already have scheduled."),
    );
    renderStage(["SHORTLISTED"]);
    await screen.findByText(/Backend Intern/);

    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Date & time"), futureLocal());
    await userEvent.click(within(dialog).getByRole("button", { name: "Schedule interview" }));

    expect(
      await screen.findByText("This slot overlaps another interview you already have scheduled."),
    ).toBeInTheDocument();
    // Dialog stays open; no false transition (no status-change API called at all).
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(mocks.updateApplicationStatus).not.toHaveBeenCalled();
    expect(screen.queryByText("Interview scheduled.")).not.toBeInTheDocument();
  });

  it("the Applicants table's Schedule interview button (same shared component) also opens the real scheduling dialog", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-1", status: "SHORTLISTED" })],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ SHORTLISTED: 1 }));
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    await userEvent.click(table.getByRole("button", { name: "Schedule interview" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Schedule interview" })).toBeInTheDocument();
    expect(mocks.updateApplicationStatus).not.toHaveBeenCalled();
  });

  // ---- Job/Internship "View Applicants" deep-link (?job_id=/?internship_id=)
  // and Dashboard funnel deep-link (?status=) ----

  it("reads job_id from the URL and sends it to the server as a real filter, not a client-side fetch-all", async () => {
    mocks.searchParams = new URLSearchParams("job_id=job-9");
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({
          id: "app-1",
          job_id: "job-9",
          internship_id: null,
          opportunity_type: "JOB",
          opportunity: { id: "job-9", title: "Machine Learning Engineer", status: "PUBLISHED" },
        }),
      ],
    });
    renderApplicants();

    await screen.findByRole("table");
    expect(mocks.getApplications).toHaveBeenCalledWith({
      job_id: "job-9",
      internship_id: undefined,
    });
    // Context header derived from the already-fetched data -- no extra fetch.
    expect(screen.getByText("Applicants for Machine Learning Engineer")).toBeInTheDocument();
    const clear = screen.getByRole("link", { name: "View all applicants" });
    expect(clear).toHaveAttribute("href", "/industry/applicants");
  });

  it("reads internship_id from the URL and sends it to the server as a real filter", async () => {
    mocks.searchParams = new URLSearchParams("internship_id=int-9");
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-1", internship_id: "int-9" })],
    });
    renderApplicants();

    await screen.findByRole("table");
    expect(mocks.getApplications).toHaveBeenCalledWith({
      job_id: undefined,
      internship_id: "int-9",
    });
  });

  it("shows a generic scoped header when a posting filter is active but the fetch came back empty", async () => {
    mocks.searchParams = new URLSearchParams("job_id=job-9");
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    renderApplicants();

    expect(await screen.findByText("Applicants for this posting")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View all applicants" })).toBeInTheDocument();
  });

  it("does not show posting-scope UI (header override / clear link) with no job_id or internship_id", async () => {
    mocks.getApplications.mockResolvedValueOnce({ applications: [application()] });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1 }));
    renderApplicants();

    await screen.findByRole("table");
    expect(screen.getByText("All applications.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View all applicants" })).not.toBeInTheDocument();
  });

  it("initializes the status filter from ?status= on the Applicants page", async () => {
    mocks.searchParams = new URLSearchParams("status=SHORTLISTED");
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-1", status: "APPLIED" }),
        application({ id: "app-2", status: "SHORTLISTED" }),
      ],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1, SHORTLISTED: 1 }));
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    expect(table.getByText("Shortlisted")).toBeInTheDocument();
    // APPLIED is filtered out client-side by the initial status, same
    // mechanism the funnel/dropdown already use.
    await waitFor(() => expect(table.queryAllByText("Applied").length).toBe(0));
  });

  it("ignores an invalid ?status= value and falls back to all", async () => {
    mocks.searchParams = new URLSearchParams("status=NOT_A_REAL_STATUS");
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-1", status: "APPLIED" })],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1 }));
    renderApplicants();

    const table = within(await screen.findByRole("table"));
    expect(table.getByText("Applied")).toBeInTheDocument();
  });

  it("clicking a funnel stage reflects the new status into the URL via router.replace", async () => {
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-1", status: "APPLIED" }),
        application({ id: "app-2", status: "SHORTLISTED" }),
      ],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ APPLIED: 1, SHORTLISTED: 1 }));
    renderApplicants();

    await screen.findByRole("table");
    const funnel = screen.getByRole("region", { name: "Recruitment pipeline" });
    await userEvent.click(within(funnel).getByRole("button", { name: /Shortlisted/ }));

    expect(mocks.replace).toHaveBeenCalledWith("/industry/applicants?status=SHORTLISTED");
  });

  it("clicking the same active funnel stage again clears the status from the URL", async () => {
    mocks.searchParams = new URLSearchParams("status=SHORTLISTED");
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-2", status: "SHORTLISTED" })],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ SHORTLISTED: 1 }));
    renderApplicants();

    await screen.findByRole("table");
    const funnel = screen.getByRole("region", { name: "Recruitment pipeline" });
    await userEvent.click(within(funnel).getByRole("button", { name: /Shortlisted/ }));

    expect(mocks.replace).toHaveBeenCalledWith("/industry/applicants");
  });

  it("preserves job_id in the URL when the status filter changes via the funnel", async () => {
    mocks.searchParams = new URLSearchParams("job_id=job-9");
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({
          id: "app-1",
          job_id: "job-9",
          internship_id: null,
          status: "SHORTLISTED",
        }),
      ],
    });
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary({ SHORTLISTED: 1 }));
    renderApplicants();

    await screen.findByRole("table");
    const funnel = screen.getByRole("region", { name: "Recruitment pipeline" });
    await userEvent.click(within(funnel).getByRole("button", { name: /Shortlisted/ }));

    expect(mocks.replace).toHaveBeenCalledWith("/industry/applicants?job_id=job-9&status=SHORTLISTED");
  });
});
