import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getWorkshops: vi.fn(),
  publishWorkshop: vi.fn(),
  closeWorkshop: vi.fn(),
  archiveWorkshop: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/workshops", () => ({
  getWorkshops: mocks.getWorkshops,
  publishWorkshop: mocks.publishWorkshop,
  closeWorkshop: mocks.closeWorkshop,
  archiveWorkshop: mocks.archiveWorkshop,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { WorkshopsListView } from "@/components/industry/workshops/workshops-list-view";
import { ApiError } from "@/lib/api";
import type { IndustryWorkshop } from "@/types/industry-workshop";

function workshop(overrides: Partial<IndustryWorkshop> = {}): IndustryWorkshop {
  return {
    id: "workshop-1",
    industry_id: "industry-1",
    title: "Intro to Git Workshop",
    description: "A hands-on session.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_days: 1,
    capacity: 50,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("WorkshopsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("does not fetch more than once on mount", () => {
    mocks.getWorkshops.mockReturnValue(new Promise(() => {}));
    render(<WorkshopsListView />);
    expect(mocks.getWorkshops).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getWorkshops.mockReturnValue(new Promise(() => {}));
    render(<WorkshopsListView />);
    expect(screen.getByText(/Loading your workshops/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getWorkshops.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<WorkshopsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no workshops", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({ workshops: [] });
    render(<WorkshopsListView />);
    expect(await screen.findByText("No workshops yet")).toBeInTheDocument();
  });

  it("lists workshops with title and status", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({
      workshops: [workshop(), workshop({ id: "workshop-2", title: "React Deep Dive", status: "PUBLISHED" })],
    });
    render(<WorkshopsListView />);

    expect(await screen.findByText("Intro to Git Workshop")).toBeInTheDocument();
    expect(screen.getByText("React Deep Dive")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({
      workshops: [workshop(), workshop({ id: "workshop-2", title: "React Deep Dive" })],
    });
    render(<WorkshopsListView />);
    await screen.findByText("Intro to Git Workshop");

    await userEvent.type(screen.getByLabelText("Search workshops"), "react");

    expect(screen.queryByText("Intro to Git Workshop")).not.toBeInTheDocument();
    expect(screen.getByText("React Deep Dive")).toBeInTheDocument();
  });

  it("publishes a workshop through the confirmation dialog", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({ workshops: [workshop()] });
    mocks.publishWorkshop.mockResolvedValueOnce(workshop({ status: "PUBLISHED" }));

    render(<WorkshopsListView />);
    await screen.findByText("Intro to Git Workshop");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishWorkshop).toHaveBeenCalledWith("workshop-1"));
    expect(await screen.findByText("Workshop published.")).toBeInTheDocument();
  });

  it("surfaces a publish error from the API", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({ workshops: [workshop()] });
    mocks.publishWorkshop.mockRejectedValueOnce(
      new ApiError(422, "This workshop isn't ready to publish. Add: work_mode."),
    );

    render(<WorkshopsListView />);
    await screen.findByText("Intro to Git Workshop");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/isn't ready to publish/i)).toBeInTheDocument();
  });

  it("does not call a lifecycle action until the confirmation dialog is confirmed", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({ workshops: [workshop()] });

    render(<WorkshopsListView />);
    await screen.findByText("Intro to Git Workshop");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    await screen.findByRole("dialog");

    expect(mocks.publishWorkshop).not.toHaveBeenCalled();
  });

  it("links the create action to the create page", async () => {
    mocks.getWorkshops.mockResolvedValueOnce({ workshops: [] });
    render(<WorkshopsListView />);
    await screen.findByText("No workshops yet");

    // <Button render={<Link/>}> resolves to an <a href> exposed with
    // role="button" (nativeButton={false}); exact name avoids matching the
    // empty-state "+ Create Workshop" action.
    expect(screen.getByRole("button", { name: "Create Workshop" })).toHaveAttribute(
      "href",
      "/industry/workshops/create",
    );
  });
});
