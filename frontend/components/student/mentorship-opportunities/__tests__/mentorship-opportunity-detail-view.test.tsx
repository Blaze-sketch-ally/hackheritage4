import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMentorshipOpportunity: vi.fn(),
}));

vi.mock("@/lib/student/mentorship-opportunities", () => ({
  getMentorshipOpportunity: mocks.getMentorshipOpportunity,
}));

import { MentorshipOpportunityDetailView } from "@/components/student/mentorship-opportunities/mentorship-opportunity-detail-view";
import { ApiError } from "@/lib/api";
import type { StudentMentorshipOpportunityDetail } from "@/types/student-mentorship-opportunity";

function detail(
  overrides: Partial<StudentMentorshipOpportunityDetail> = {},
): StudentMentorshipOpportunityDetail {
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

describe("MentorshipOpportunityDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getMentorshipOpportunity.mockReturnValue(new Promise(() => {}));
    render(<MentorshipOpportunityDetailView mentorshipId="m-1" />);
    expect(screen.getByLabelText("Loading mentorship opportunity")).toBeInTheDocument();
  });

  it("renders the real mentorship details", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(detail());
    render(<MentorshipOpportunityDetailView mentorshipId="m-1" />);

    expect(await screen.findByText("Cloud-Native Engineering Mentorship")).toBeInTheDocument();
    expect(screen.getByText(/Acme/)).toBeInTheDocument();
    expect(screen.getByText("A six-month mentoring engagement.")).toBeInTheDocument();
    expect(screen.getByText("Open to final-year students.")).toBeInTheDocument();
  });

  it("shows an honest 'requests not available yet' state and no request button", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(detail());
    render(<MentorshipOpportunityDetailView mentorshipId="m-1" />);
    await screen.findByText("Cloud-Native Engineering Mentorship");

    expect(
      screen.getByText(/mentorship request from the portal isn.t available yet/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /request mentorship/i })).not.toBeInTheDocument();
  });

  it("shows a not-found state (no retry) on a 404", async () => {
    mocks.getMentorshipOpportunity.mockRejectedValueOnce(
      new ApiError(404, "This mentorship opportunity is not available."),
    );
    render(<MentorshipOpportunityDetailView mentorshipId="missing" />);
    expect(
      await screen.findByText("This mentorship opportunity is not available."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("shows an error state with retry on a server error, then recovers", async () => {
    mocks.getMentorshipOpportunity
      .mockRejectedValueOnce(new ApiError(500, "Server is down."))
      .mockResolvedValueOnce(detail());
    render(<MentorshipOpportunityDetailView mentorshipId="m-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Cloud-Native Engineering Mentorship")).toBeInTheDocument();
  });

  it("does not fabricate mentor ratings or session counts", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(detail());
    const { container } = render(<MentorshipOpportunityDetailView mentorshipId="m-1" />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(container.textContent).not.toMatch(
      /\d+(\.\d+)?\s*(★|stars?|rating|% (match|response|success)|sessions?|reviews?)/i,
    );
  });
});
