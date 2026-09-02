import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listMentorships: vi.fn(),
}));

vi.mock("@/lib/student/mentorship", () => ({ listMentorships: mocks.listMentorships }));

import { MentorshipListView } from "@/components/student/mentorship/mentorship-list-view";
import { ApiError } from "@/lib/api";
import type { StudentMentorshipSummary } from "@/types/student-mentorship";

function mentorship(overrides: Partial<StudentMentorshipSummary> = {}): StudentMentorshipSummary {
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

describe("MentorshipListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listMentorships.mockReturnValue(new Promise(() => {}));
    render(<MentorshipListView />);
    expect(screen.getByLabelText("Loading mentorship opportunities")).toBeInTheDocument();
  });

  it("renders real mentorship cards with title and organizer", async () => {
    mocks.listMentorships.mockResolvedValueOnce({
      mentorship_opportunities: [
        mentorship(),
        mentorship({ id: "m-2", title: "Data Platform Mentorship" }),
      ],
    });
    render(<MentorshipListView />);

    expect(await screen.findByText("Cloud-Native Engineering Mentorship")).toBeInTheDocument();
    expect(screen.getByText("Data Platform Mentorship")).toBeInTheDocument();
    expect(screen.getAllByText("Acme")).toHaveLength(2);
    expect(screen.getAllByText(/6 months/).length).toBeGreaterThan(0);
  });

  it("shows the honest empty state when there are none", async () => {
    mocks.listMentorships.mockResolvedValueOnce({ mentorship_opportunities: [] });
    render(<MentorshipListView />);
    expect(await screen.findByText("No mentorship opportunities yet.")).toBeInTheDocument();
  });

  it("renders no card when the API returns nothing", async () => {
    mocks.listMentorships.mockResolvedValueOnce({ mentorship_opportunities: [] });
    const { container } = render(<MentorshipListView />);
    await screen.findByText("No mentorship opportunities yet.");
    expect(container.querySelector("a[href^='/student/mentorship/']")).toBeNull();
  });

  it("shows an error state with retry", async () => {
    mocks.listMentorships.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<MentorshipListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("re-fetches with the selected work mode filter", async () => {
    mocks.listMentorships.mockResolvedValue({ mentorship_opportunities: [mentorship()] });
    render(<MentorshipListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(mocks.listMentorships).toHaveBeenLastCalledWith(undefined);

    await userEvent.click(screen.getByRole("button", { name: "Online" }));
    expect(mocks.listMentorships).toHaveBeenLastCalledWith({ workMode: "REMOTE" });
  });

  it("filters the rendered list by title search", async () => {
    mocks.listMentorships.mockResolvedValueOnce({
      mentorship_opportunities: [
        mentorship(),
        mentorship({ id: "m-2", title: "Product Design Mentorship" }),
      ],
    });
    render(<MentorshipListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");

    await userEvent.type(screen.getByLabelText("Search mentorship opportunities"), "design");

    expect(screen.queryByText("Cloud-Native Engineering Mentorship")).not.toBeInTheDocument();
    expect(screen.getByText("Product Design Mentorship")).toBeInTheDocument();
  });

  it("does not render fabricated metrics (ratings, response rates, session counts)", async () => {
    mocks.listMentorships.mockResolvedValueOnce({
      mentorship_opportunities: [mentorship()],
    });
    const { container } = render(<MentorshipListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(container.textContent).not.toMatch(
      /\d+(\.\d+)?\s*(★|stars?|rating|% (match|response|success)|sessions? completed|mentees)/i,
    );
  });

  it("links each card to its detail route", async () => {
    mocks.listMentorships.mockResolvedValueOnce({ mentorship_opportunities: [mentorship()] });
    const { container } = render(<MentorshipListView />);
    await screen.findByText("Cloud-Native Engineering Mentorship");
    expect(
      container.querySelector('a[href="/student/mentorship/11111111-1111-1111-1111-111111111111"]'),
    ).not.toBeNull();
  });
});
