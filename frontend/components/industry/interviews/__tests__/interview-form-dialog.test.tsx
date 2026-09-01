import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  scheduleInterview: vi.fn(),
  rescheduleInterview: vi.fn(),
}));

vi.mock("@/lib/industry/interviews", () => ({
  scheduleInterview: mocks.scheduleInterview,
  rescheduleInterview: mocks.rescheduleInterview,
}));

import { InterviewFormDialog } from "@/components/industry/interviews/interview-form-dialog";
import { ApiError } from "@/lib/api";
import type { Application } from "@/types/application";
import type { Interview } from "@/types/interview";

function application(overrides: Partial<Application> = {}): Application {
  return {
    id: "app-1",
    student_id: "student-abcdef12",
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

function interview(overrides: Partial<Interview> = {}): Interview {
  return {
    id: "iv-1",
    application_id: "app-1",
    industry_id: "industry-1",
    student_id: "student-abcdef12",
    scheduled_at: "2099-01-01T10:00:00.000Z",
    duration_minutes: 30,
    mode: "ONLINE",
    location: "https://meet.example.com/x",
    notes: null,
    status: "SCHEDULED",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    opportunity: { id: "job-1", title: "Backend Engineer", status: "PUBLISHED" },
    opportunity_type: "JOB",
    ...overrides,
  };
}

function futureLocal(daysAhead = 3): string {
  const d = new Date(Date.now() + daysAhead * 86400000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

describe("InterviewFormDialog", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders nothing when closed", () => {
    const { container } = render(
      <InterviewFormDialog open={false} onOpenChange={vi.fn()} mode="schedule" onSubmitted={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("schedule mode shows a candidate picker with eligible applications", () => {
    render(
      <InterviewFormDialog
        open
        onOpenChange={vi.fn()}
        mode="schedule"
        eligibleApplications={[application()]}
        onSubmitted={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Candidate")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Backend Engineer/i })).toBeInTheDocument();
  });

  it("blocks submit and flags the date field when it is empty", async () => {
    render(
      <InterviewFormDialog
        open
        onOpenChange={vi.fn()}
        mode="schedule"
        eligibleApplications={[application()]}
        onSubmitted={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    expect(screen.getByText("Pick a date and time.")).toBeInTheDocument();
    expect(mocks.scheduleInterview).not.toHaveBeenCalled();
  });

  it("rejects a past date/time client-side", async () => {
    render(
      <InterviewFormDialog
        open
        onOpenChange={vi.fn()}
        mode="schedule"
        eligibleApplications={[application()]}
        onSubmitted={vi.fn()}
      />,
    );
    // one application -> auto-selected; set a past datetime
    const dt = screen.getByLabelText("Date & time");
    await userEvent.type(dt, "2000-01-01T09:00");
    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    expect(screen.getByText("The interview must be in the future.")).toBeInTheDocument();
    expect(mocks.scheduleInterview).not.toHaveBeenCalled();
  });

  it("submits a valid schedule with the resolved payload", async () => {
    mocks.scheduleInterview.mockResolvedValueOnce(interview());
    const onSubmitted = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <InterviewFormDialog
        open
        onOpenChange={onOpenChange}
        mode="schedule"
        eligibleApplications={[application()]}
        onSubmitted={onSubmitted}
      />,
    );
    await userEvent.type(screen.getByLabelText("Date & time"), futureLocal());
    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));

    expect(mocks.scheduleInterview).toHaveBeenCalledTimes(1);
    const payload = mocks.scheduleInterview.mock.calls[0][0];
    expect(payload.application_id).toBe("app-1");
    expect(payload.mode).toBe("ONLINE");
    expect(typeof payload.scheduled_at).toBe("string");
    expect(onSubmitted).toHaveBeenCalledWith(interview());
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("surfaces a backend conflict error", async () => {
    mocks.scheduleInterview.mockRejectedValueOnce(
      new ApiError(409, "This application already has a scheduled interview."),
    );
    render(
      <InterviewFormDialog
        open
        onOpenChange={vi.fn()}
        mode="schedule"
        eligibleApplications={[application()]}
        onSubmitted={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText("Date & time"), futureLocal());
    await userEvent.click(screen.getByRole("button", { name: "Schedule interview" }));
    expect(
      await screen.findByText("This application already has a scheduled interview."),
    ).toBeInTheDocument();
  });

  it("reschedule mode prefills from the interview and calls rescheduleInterview", async () => {
    mocks.rescheduleInterview.mockResolvedValueOnce(interview({ duration_minutes: 60 }));
    render(
      <InterviewFormDialog
        open
        onOpenChange={vi.fn()}
        mode="reschedule"
        interview={interview()}
        onSubmitted={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("Candidate")).not.toBeInTheDocument();
    expect((screen.getByLabelText("Date & time") as HTMLInputElement).value).toMatch(/^2099-01-01T/);

    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(mocks.rescheduleInterview).toHaveBeenCalledWith("iv-1", expect.objectContaining({ mode: "ONLINE" }));
  });

  it("disables submit when there are no eligible candidates", () => {
    render(
      <InterviewFormDialog
        open
        onOpenChange={vi.fn()}
        mode="schedule"
        eligibleApplications={[]}
        onSubmitted={vi.fn()}
      />,
    );
    expect(screen.getByText(/No shortlisted candidates/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schedule interview" })).toBeDisabled();
  });
});
