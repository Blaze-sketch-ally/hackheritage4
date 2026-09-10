import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInterviews: vi.fn(),
  getApplications: vi.fn(),
  completeInterview: vi.fn(),
  cancelInterview: vi.fn(),
  scheduleInterview: vi.fn(),
  rescheduleInterview: vi.fn(),
}));

vi.mock("@/lib/industry/interviews", () => ({
  getInterviews: mocks.getInterviews,
  completeInterview: mocks.completeInterview,
  cancelInterview: mocks.cancelInterview,
  scheduleInterview: mocks.scheduleInterview,
  rescheduleInterview: mocks.rescheduleInterview,
}));
vi.mock("@/lib/industry/applications", () => ({ getApplications: mocks.getApplications }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { InterviewsListView } from "@/components/industry/interviews/interviews-list-view";
import { ApiError } from "@/lib/api";
import type { Application } from "@/types/application";
import type { Interview } from "@/types/interview";

function interview(overrides: Partial<Interview> = {}): Interview {
  return {
    id: "iv-1",
    application_id: "app-1",
    industry_id: "industry-1",
    student_id: "student-abcdef12",
    student_name: null,
    scheduled_at: "2099-01-01T10:00:00.000Z",
    duration_minutes: 30,
    mode: "ONLINE",
    location: null,
    notes: null,
    status: "SCHEDULED",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    opportunity: { id: "job-1", title: "Backend Engineer", status: "PUBLISHED" },
    opportunity_type: "JOB",
    ...overrides,
  };
}

function application(overrides: Partial<Application> = {}): Application {
  return {
    id: "app-2",
    student_id: "student-99887766",
    industry_id: "industry-1",
    opportunity_type: "JOB",
    internship_id: null,
    job_id: "job-1",
    status: "SHORTLISTED",
    cover_note: null,
    match_score: null,
    applied_at: "2026-09-01T00:00:00Z",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    opportunity: { id: "job-1", title: "Backend Engineer", status: "PUBLISHED" },
    ...overrides,
  };
}

describe("InterviewsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches interviews and applications once on mount", () => {
    mocks.getInterviews.mockReturnValue(new Promise(() => {}));
    mocks.getApplications.mockReturnValue(new Promise(() => {}));
    render(<InterviewsListView />);
    expect(mocks.getInterviews).toHaveBeenCalledTimes(1);
    expect(mocks.getApplications).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getInterviews.mockReturnValue(new Promise(() => {}));
    mocks.getApplications.mockReturnValue(new Promise(() => {}));
    render(<InterviewsListView />);
    expect(screen.getByText(/Loading your interviews/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInterviews.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    render(<InterviewsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no interviews", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [] });
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    render(<InterviewsListView />);
    expect(await screen.findByText("No interviews scheduled")).toBeInTheDocument();
  });

  it("lists interviews with candidate ref, opportunity and status", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [interview()] });
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    render(<InterviewsListView />);
    expect(await screen.findByText("Applicant student-")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("shows the applicant's real name on a scheduled interview when resolved", async () => {
    mocks.getInterviews.mockResolvedValueOnce({
      interviews: [interview({ student_name: "Priya Menon" })],
    });
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    render(<InterviewsListView />);
    expect(await screen.findByText("Priya Menon")).toBeInTheDocument();
    expect(screen.queryByText("Applicant student-")).not.toBeInTheDocument();
  });

  it("finds a scheduled interview by the applicant's real name in search", async () => {
    mocks.getInterviews.mockResolvedValueOnce({
      interviews: [interview({ student_name: "Priya Menon" })],
    });
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    render(<InterviewsListView />);
    await screen.findByText("Priya Menon");
    await userEvent.type(screen.getByPlaceholderText(/Search by candidate/i), "priya");
    expect(screen.getByText("Priya Menon")).toBeInTheDocument();
  });

  it("runs the cancel lifecycle action through a confirmation", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [interview()] });
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    mocks.cancelInterview.mockResolvedValueOnce(interview({ status: "CANCELLED" }));
    render(<InterviewsListView />);

    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    // confirmation dialog
    await userEvent.click(screen.getByRole("button", { name: "Cancel interview" }));

    expect(mocks.cancelInterview).toHaveBeenCalledWith("iv-1");
    expect(await screen.findByText("Interview cancelled.")).toBeInTheDocument();
  });

  it("opens the schedule dialog with eligible shortlisted candidates", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [] });
    mocks.getApplications.mockResolvedValueOnce({ applications: [application()] });
    render(<InterviewsListView />);

    await userEvent.click(await screen.findByRole("button", { name: /Schedule interview/i }));
    expect(await screen.findByLabelText("Candidate")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Backend Engineer/i })).toBeInTheDocument();
  });

  it("excludes candidates that already have a live interview from the picker", async () => {
    mocks.getInterviews.mockResolvedValueOnce({
      interviews: [interview({ id: "iv-x", application_id: "app-2", status: "SCHEDULED" })],
    });
    mocks.getApplications.mockResolvedValueOnce({ applications: [application({ id: "app-2" })] });
    render(<InterviewsListView />);

    await userEvent.click(await screen.findByRole("button", { name: /Schedule interview/i }));
    expect(await screen.findByText(/No shortlisted candidates/i)).toBeInTheDocument();
  });

  // --- Regression: an application advanced to INTERVIEW_SCHEDULED from the
  // Applicants page has no `interviews` row, yet the candidate must still
  // appear in the Interview panel (as "awaiting scheduling"). ---

  it("lists an INTERVIEW_SCHEDULED candidate with no interview row as awaiting scheduling", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [] });
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-9", status: "INTERVIEW_SCHEDULED", student_name: "Riya Sharma" }),
      ],
    });
    render(<InterviewsListView />);

    expect(await screen.findByText("Awaiting scheduling")).toBeInTheDocument();
    expect(screen.getByText("Riya Sharma")).toBeInTheDocument();
    expect(screen.getByText("Interview not scheduled")).toBeInTheDocument();
    // NOT the "nothing here" empty state
    expect(screen.queryByText("No interviews scheduled")).not.toBeInTheDocument();
  });

  it("keeps the empty state when there are genuinely no interviews and no interview-stage candidates", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [] });
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-s", status: "SHORTLISTED" })],
    });
    render(<InterviewsListView />);

    expect(await screen.findByText("No interviews scheduled")).toBeInTheDocument();
    expect(screen.queryByText("Awaiting scheduling")).not.toBeInTheDocument();
  });

  it("never shows a SELECTED candidate in the panel (awaiting or scheduling picker)", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [] });
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-sel", status: "SELECTED", student_name: "Selected Sam" }),
      ],
    });
    render(<InterviewsListView />);

    // SELECTED is post-interview -> Job Training / Internship Workspace, not here
    expect(await screen.findByText("No interviews scheduled")).toBeInTheDocument();
    expect(screen.queryByText("Awaiting scheduling")).not.toBeInTheDocument();
    expect(screen.queryByText("Selected Sam")).not.toBeInTheDocument();

    // ...and the schedule picker does not offer them either
    await userEvent.click(screen.getByRole("button", { name: /Schedule interview/i }));
    expect(await screen.findByText(/No shortlisted candidates/i)).toBeInTheDocument();
  });

  it("does not double-list an INTERVIEW_SCHEDULED candidate that already has a scheduled interview", async () => {
    mocks.getInterviews.mockResolvedValueOnce({
      interviews: [interview({ id: "iv-1", application_id: "app-7", status: "SCHEDULED" })],
    });
    mocks.getApplications.mockResolvedValueOnce({
      applications: [application({ id: "app-7", status: "INTERVIEW_SCHEDULED" })],
    });
    render(<InterviewsListView />);

    // the interview card renders...
    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
    // ...and there is no "awaiting" section for the same candidate
    expect(screen.queryByText("Awaiting scheduling")).not.toBeInTheDocument();
  });

  it("shows both a scheduled interview and a separate awaiting candidate", async () => {
    mocks.getInterviews.mockResolvedValueOnce({
      interviews: [interview({ id: "iv-1", application_id: "app-1", status: "SCHEDULED" })],
    });
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-2", status: "INTERVIEW_SCHEDULED", student_name: "Awaiting Amy" }),
      ],
    });
    render(<InterviewsListView />);

    expect(await screen.findByText("Awaiting scheduling")).toBeInTheDocument();
    expect(screen.getByText("Awaiting Amy")).toBeInTheDocument();
    expect(screen.getByText("Scheduled interviews")).toBeInTheDocument();
  });

  it("opens the schedule dialog preselected when scheduling from an awaiting candidate", async () => {
    mocks.getInterviews.mockResolvedValueOnce({ interviews: [] });
    mocks.getApplications.mockResolvedValueOnce({
      applications: [
        application({ id: "app-1", status: "INTERVIEW_SCHEDULED" }),
        application({ id: "app-2", status: "SHORTLISTED" }),
      ],
    });
    render(<InterviewsListView />);

    await userEvent.click(await screen.findByRole("button", { name: "Schedule" }));
    const select = (await screen.findByLabelText("Candidate")) as HTMLSelectElement;
    expect(select.value).toBe("app-1");
  });

  // --- Regression: the backend now stitches `opportunity` from a separate,
  // best-effort `applications` read. When that enrichment is unavailable the
  // interview row comes back with `opportunity: null` (and possibly
  // `opportunity_type: null`). The card must still render, not crash. ---

  it("renders an interview whose opportunity enrichment is null without crashing", async () => {
    mocks.getInterviews.mockResolvedValueOnce({
      interviews: [interview({ opportunity: null, opportunity_type: null })],
    });
    mocks.getApplications.mockResolvedValueOnce({ applications: [] });
    render(<InterviewsListView />);

    // the row still lists (candidate ref + status), with a safe fallback label
    expect(await screen.findByText("Applicant student-")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByText("Opportunity")).toBeInTheDocument();
    expect(screen.queryByText("No interviews scheduled")).not.toBeInTheDocument();

    // search still works (the haystack tolerates the missing title)
    await userEvent.type(screen.getByLabelText("Search interviews"), "student");
    expect(screen.getByText("Applicant student-")).toBeInTheDocument();
    expect(screen.queryByText("No interviews match your filters")).not.toBeInTheDocument();
  });
});
