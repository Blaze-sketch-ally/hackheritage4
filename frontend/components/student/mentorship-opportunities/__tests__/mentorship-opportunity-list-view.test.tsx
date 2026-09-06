import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listMentorshipOpportunities: vi.fn(),
}));

vi.mock("@/lib/student/mentorship-opportunities", () => ({
  listMentorshipOpportunities: mocks.listMentorshipOpportunities,
}));

import { MentorshipOpportunityListView } from "@/components/student/mentorship-opportunities/mentorship-opportunity-list-view";
import { ApiError } from "@/lib/api";
import type { StudentMentorshipOpportunitySummary } from "@/types/student-mentorship-opportunity";

function mentorship(
  overrides: Partial<StudentMentorshipOpportunitySummary> = {},
): StudentMentorshipOpportunitySummary {
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
    ...overrides,
  };
}

describe("MentorshipOpportunityListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listMentorshipOpportunities.mockReturnValue(new Promise(() => {}));
    render(<MentorshipOpportunityListView />);
    expect(screen.getByLabelText("Loading mentorship opportunities")).toBeInTheDocument();
  });

  it("renders real mentorship cards with title and organizer", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValueOnce({
      mentorship_opportunities: [
        mentorship(),
        mentorship({ id: "m-2", title: "Data Platform Mentorship" }),
      ],
    });
    render(<MentorshipOpportunityListView />);

    expect(await screen.findByText("Cloud-Native Engineering Mentorship")).toBeInTheDocument();
    expect(screen.getByText("Data Platform Mentorship")).toBeInTheDocument();
    expect(screen.getAllByText("Acme")).toHaveLength(2);
    expect(screen.getAllByText(/6 months/).length).toBeGreaterThan(0);
  });

  it("shows the honest empty state when there are none", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [] });
    render(<MentorshipOpportunityListView />);
    expect(await screen.findByText("No mentorship opportunities yet.")).toBeInTheDocument();
  });

  it("renders no card when the API returns nothing", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [] });
    const { container } = render(<MentorshipOpportunityListView />);
    await screen.findByText("No mentorship opportunities yet.");
    expect(container.querySelector("a[href^='/student/mentorship-opportunities/']")).toBeNull();
  });

  it("shows an error state with retry", async () => {
    mocks.listMentorshipOpportunities.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<MentorshipOpportunityListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("re-fetches with the selected work mode filter", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValue({
      mentorship_opportunities: [mentorship()],
    });
    render(<MentorshipOpportunityListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(mocks.listMentorshipOpportunities).toHaveBeenLastCalledWith(undefined);

    await userEvent.click(screen.getByRole("button", { name: "Online" }));
    expect(mocks.listMentorshipOpportunities).toHaveBeenLastCalledWith({ workMode: "REMOTE" });
  });

  it("filters the rendered list by title search", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValueOnce({
      mentorship_opportunities: [
        mentorship(),
        mentorship({ id: "m-2", title: "Product Design Mentorship" }),
      ],
    });
    render(<MentorshipOpportunityListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");

    await userEvent.type(screen.getByLabelText("Search mentorship opportunities"), "design");

    expect(screen.queryByText("Cloud-Native Engineering Mentorship")).not.toBeInTheDocument();
    expect(screen.getByText("Product Design Mentorship")).toBeInTheDocument();
  });

  it("does not render fabricated metrics (ratings, response rates, session counts)", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValueOnce({
      mentorship_opportunities: [mentorship()],
    });
    const { container } = render(<MentorshipOpportunityListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(container.textContent).not.toMatch(
      /\d+(\.\d+)?\s*(★|stars?|rating|% (match|response|success)|sessions? completed|mentees)/i,
    );
  });

  it("links each card to its detail route", async () => {
    mocks.listMentorshipOpportunities.mockResolvedValueOnce({
      mentorship_opportunities: [mentorship()],
    });
    const { container } = render(<MentorshipOpportunityListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(
      container.querySelector(
        'a[href="/student/mentorship-opportunities/11111111-1111-1111-1111-111111111111"]',
      ),
    ).not.toBeNull();
  });
});
