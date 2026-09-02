import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMentorship: vi.fn(),
}));

vi.mock("@/lib/student/mentorship", () => ({ getMentorship: mocks.getMentorship }));

import { MentorshipDetailView } from "@/components/student/mentorship/mentorship-detail-view";
import { ApiError } from "@/lib/api";
import type { StudentMentorshipDetail } from "@/types/student-mentorship";

function detail(overrides: Partial<StudentMentorshipDetail> = {}): StudentMentorshipDetail {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Cloud-Native Engineering Mentorship",
    description: "A six-month mentoring engagement.",
    location: "Bengaluru",
    work_mode: "HYBRID",
    duration_months: 6,
    capacity: 5,
    start_date: "2026-10-01",
    application_deadline: "2026-09-20T00:00:00Z",
    organizer: { id: "i-1", company_name: "Acme", industry_sector: "Software", logo_url: null },
    created_at: "2026-09-01T00:00:00Z",
    eligibility_criteria: "Open to final-year students.",
    requests_available: false,
    ...overrides,
  };
}

describe("MentorshipDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getMentorship.mockReturnValue(new Promise(() => {}));
    render(<MentorshipDetailView mentorshipId="m-1" />);
    expect(screen.getByLabelText("Loading mentorship opportunity")).toBeInTheDocument();
  });

  it("renders the real mentorship details", async () => {
    mocks.getMentorship.mockResolvedValueOnce(detail());
    render(<MentorshipDetailView mentorshipId="m-1" />);

    expect(await screen.findByText("Cloud-Native Engineering Mentorship")).toBeInTheDocument();
    expect(screen.getByText(/Acme/)).toBeInTheDocument();
    expect(screen.getByText("A six-month mentoring engagement.")).toBeInTheDocument();
    expect(screen.getByText("Open to final-year students.")).toBeInTheDocument();
  });

  it("shows an honest 'requests not available yet' state and no request button", async () => {
    mocks.getMentorship.mockResolvedValueOnce(detail());
    render(<MentorshipDetailView mentorshipId="m-1" />);
    await screen.findByText("Cloud-Native Engineering Mentorship");

    expect(
      screen.getByText(/mentorship request from the portal isn.t available yet/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /request mentorship/i })).not.toBeInTheDocument();
  });

  it("shows a not-found state (no retry) on a 404", async () => {
    mocks.getMentorship.mockRejectedValueOnce(
      new ApiError(404, "This mentorship opportunity is not available."),
    );
    render(<MentorshipDetailView mentorshipId="missing" />);
    expect(
      await screen.findByText("This mentorship opportunity is not available."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("shows an error state with retry on a server error, then recovers", async () => {
    mocks.getMentorship
      .mockRejectedValueOnce(new ApiError(500, "Server is down."))
      .mockResolvedValueOnce(detail());
    render(<MentorshipDetailView mentorshipId="m-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Cloud-Native Engineering Mentorship")).toBeInTheDocument();
  });

  it("does not fabricate mentor ratings or session counts", async () => {
    mocks.getMentorship.mockResolvedValueOnce(detail());
    const { container } = render(<MentorshipDetailView mentorshipId="m-1" />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(container.textContent).not.toMatch(
      /\d+(\.\d+)?\s*(★|stars?|rating|% (match|response|success)|sessions?|reviews?)/i,
    );
  });
});
