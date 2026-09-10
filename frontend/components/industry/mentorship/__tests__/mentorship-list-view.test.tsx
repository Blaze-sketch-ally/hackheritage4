import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMentorshipOpportunities: vi.fn(),
  publishMentorshipOpportunity: vi.fn(),
  closeMentorshipOpportunity: vi.fn(),
  archiveMentorshipOpportunity: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/mentorship-opportunities", () => ({
  getMentorshipOpportunities: mocks.getMentorshipOpportunities,
  publishMentorshipOpportunity: mocks.publishMentorshipOpportunity,
  closeMentorshipOpportunity: mocks.closeMentorshipOpportunity,
  archiveMentorshipOpportunity: mocks.archiveMentorshipOpportunity,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { MentorshipListView } from "@/components/industry/mentorship/mentorship-list-view";
import { ApiError } from "@/lib/api";
import type { IndustryMentorship } from "@/types/industry-mentorship";

function mentorship(overrides: Partial<IndustryMentorship> = {}): IndustryMentorship {
  return {
    id: "mentorship-1",
    industry_id: "industry-1",
    title: "Frontend Career Mentorship",
    description: "A 3-month 1:1 mentorship.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_months: 3,
    capacity: 5,
    eligibility_criteria: null,
    application_deadline: "2026-12-01T00:00:00Z",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("MentorshipListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("does not fetch more than once on mount", () => {
    mocks.getMentorshipOpportunities.mockReturnValue(new Promise(() => {}));
    render(<MentorshipListView />);
    expect(mocks.getMentorshipOpportunities).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getMentorshipOpportunities.mockReturnValue(new Promise(() => {}));
    render(<MentorshipListView />);
    expect(screen.getByText(/Loading your mentorship opportunities/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getMentorshipOpportunities.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<MentorshipListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no mentorship opportunities", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [] });
    render(<MentorshipListView />);
    expect(await screen.findByText("No mentorship opportunities yet")).toBeInTheDocument();
  });

  it("lists mentorship opportunities with title and status", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({
      mentorship_opportunities: [
        mentorship(),
        mentorship({ id: "mentorship-2", title: "Product Management Mentorship", status: "PUBLISHED" }),
      ],
    });
    render(<MentorshipListView />);

    expect(await screen.findByText("Frontend Career Mentorship")).toBeInTheDocument();
    expect(screen.getByText("Product Management Mentorship")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({
      mentorship_opportunities: [
        mentorship(),
        mentorship({ id: "mentorship-2", title: "Product Management Mentorship" }),
      ],
    });
    render(<MentorshipListView />);
    await screen.findByText("Frontend Career Mentorship");

    await userEvent.type(screen.getByLabelText("Search mentorship opportunities"), "product");

    expect(screen.queryByText("Frontend Career Mentorship")).not.toBeInTheDocument();
    expect(screen.getByText("Product Management Mentorship")).toBeInTheDocument();
  });

  it("publishes a mentorship opportunity through the confirmation dialog", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [mentorship()] });
    mocks.publishMentorshipOpportunity.mockResolvedValueOnce(mentorship({ status: "PUBLISHED" }));

    render(<MentorshipListView />);
    await screen.findByText("Frontend Career Mentorship");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishMentorshipOpportunity).toHaveBeenCalledWith("mentorship-1"));
    expect(await screen.findByText("Mentorship opportunity published.")).toBeInTheDocument();
  });

  it("surfaces a publish error from the API", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [mentorship()] });
    mocks.publishMentorshipOpportunity.mockRejectedValueOnce(
      new ApiError(422, "This mentorship opportunity isn't ready to publish. Add: application_deadline."),
    );

    render(<MentorshipListView />);
    await screen.findByText("Frontend Career Mentorship");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/isn't ready to publish/i)).toBeInTheDocument();
  });

  it("does not call a lifecycle action until the confirmation dialog is confirmed", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [mentorship()] });

    render(<MentorshipListView />);
    await screen.findByText("Frontend Career Mentorship");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    await screen.findByRole("dialog");

    expect(mocks.publishMentorshipOpportunity).not.toHaveBeenCalled();
  });

  it("links the create action to the create page", async () => {
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [] });
    render(<MentorshipListView />);
    await screen.findByText("No mentorship opportunities yet");

    // <Button render={<Link/>}> resolves to an <a href> exposed with
    // role="button" (nativeButton={false}); exact name avoids matching the
    // empty-state "+ Create Mentorship Opportunity" action.
    expect(screen.getByRole("button", { name: "Create Mentorship Opportunity" })).toHaveAttribute(
      "href",
      "/industry/mentorship/create",
    );
  });
});
