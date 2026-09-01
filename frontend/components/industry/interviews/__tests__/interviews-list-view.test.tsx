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
});
