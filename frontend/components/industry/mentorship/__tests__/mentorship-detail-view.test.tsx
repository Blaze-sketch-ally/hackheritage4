import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMentorshipOpportunity: vi.fn(),
  updateMentorshipOpportunity: vi.fn(),
  publishMentorshipOpportunity: vi.fn(),
  closeMentorshipOpportunity: vi.fn(),
  archiveMentorshipOpportunity: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/mentorship-opportunities", () => ({
  getMentorshipOpportunity: mocks.getMentorshipOpportunity,
  updateMentorshipOpportunity: mocks.updateMentorshipOpportunity,
  publishMentorshipOpportunity: mocks.publishMentorshipOpportunity,
  closeMentorshipOpportunity: mocks.closeMentorshipOpportunity,
  archiveMentorshipOpportunity: mocks.archiveMentorshipOpportunity,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { MentorshipDetailView } from "@/components/industry/mentorship/mentorship-detail-view";
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

describe("MentorshipDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getMentorshipOpportunity.mockReturnValue(new Promise(() => {}));
    render(<MentorshipDetailView mentorshipId="mentorship-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getMentorshipOpportunity.mockRejectedValueOnce(
      new ApiError(404, "Mentorship opportunity not found."),
    );
    render(<MentorshipDetailView mentorshipId="mentorship-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders mentorship detail with status", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(mentorship());
    render(<MentorshipDetailView mentorshipId="mentorship-1" />);

    expect(
      await screen.findByRole("heading", { name: "Frontend Career Mentorship" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText("Remote").length).toBeGreaterThan(0);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("switches to the edit form and saves changes", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(mentorship());
    mocks.updateMentorshipOpportunity.mockResolvedValueOnce(
      mentorship({ title: "Senior Frontend Mentorship" }),
    );

    render(<MentorshipDetailView mentorshipId="mentorship-1" />);
    await screen.findByRole("heading", { name: "Frontend Career Mentorship" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Senior Frontend Mentorship");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateMentorshipOpportunity).toHaveBeenCalledTimes(1));
    expect(mocks.updateMentorshipOpportunity.mock.calls[0][0]).toBe("mentorship-1");
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Senior Frontend Mentorship" })).toBeInTheDocument();
  });

  it("publishes via the confirmation dialog", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(mentorship());
    mocks.publishMentorshipOpportunity.mockResolvedValueOnce(mentorship({ status: "PUBLISHED" }));

    render(<MentorshipDetailView mentorshipId="mentorship-1" />);
    await screen.findByRole("heading", { name: "Frontend Career Mentorship" });

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishMentorshipOpportunity).toHaveBeenCalledWith("mentorship-1"));
    expect(await screen.findByText("Mentorship opportunity published.")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("archives a published mentorship opportunity via the confirmation dialog", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(mentorship({ status: "PUBLISHED" }));
    mocks.archiveMentorshipOpportunity.mockResolvedValueOnce(mentorship({ status: "ARCHIVED" }));

    render(<MentorshipDetailView mentorshipId="mentorship-1" />);
    await screen.findByRole("heading", { name: "Frontend Career Mentorship" });

    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(mocks.archiveMentorshipOpportunity).toHaveBeenCalledWith("mentorship-1"));
    expect(await screen.findByText("Mentorship opportunity archived.")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getMentorshipOpportunity.mockResolvedValueOnce(mentorship());
    render(<MentorshipDetailView mentorshipId="mentorship-1" initialEdit />);

    expect(
      await screen.findByRole("heading", { name: "Edit Mentorship Opportunity" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Frontend Career Mentorship");
  });
});
