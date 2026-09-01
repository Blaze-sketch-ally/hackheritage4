import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getWorkshop: vi.fn(),
  updateWorkshop: vi.fn(),
  publishWorkshop: vi.fn(),
  closeWorkshop: vi.fn(),
  archiveWorkshop: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/workshops", () => ({
  getWorkshop: mocks.getWorkshop,
  updateWorkshop: mocks.updateWorkshop,
  publishWorkshop: mocks.publishWorkshop,
  closeWorkshop: mocks.closeWorkshop,
  archiveWorkshop: mocks.archiveWorkshop,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { WorkshopDetailView } from "@/components/industry/workshops/workshop-detail-view";
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

describe("WorkshopDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getWorkshop.mockReturnValue(new Promise(() => {}));
    render(<WorkshopDetailView workshopId="workshop-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getWorkshop.mockRejectedValueOnce(new ApiError(404, "Workshop not found."));
    render(<WorkshopDetailView workshopId="workshop-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders workshop detail with status", async () => {
    mocks.getWorkshop.mockResolvedValueOnce(workshop());
    render(<WorkshopDetailView workshopId="workshop-1" />);

    expect(
      await screen.findByRole("heading", { name: "Intro to Git Workshop" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText("Remote").length).toBeGreaterThan(0);
  });

  it("switches to the edit form and saves changes", async () => {
    mocks.getWorkshop.mockResolvedValueOnce(workshop());
    mocks.updateWorkshop.mockResolvedValueOnce(workshop({ title: "Advanced Git Workshop" }));

    render(<WorkshopDetailView workshopId="workshop-1" />);
    await screen.findByRole("heading", { name: "Intro to Git Workshop" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Advanced Git Workshop");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateWorkshop).toHaveBeenCalledTimes(1));
    expect(mocks.updateWorkshop.mock.calls[0][0]).toBe("workshop-1");
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Advanced Git Workshop" })).toBeInTheDocument();
  });

  it("publishes via the confirmation dialog", async () => {
    mocks.getWorkshop.mockResolvedValueOnce(workshop());
    mocks.publishWorkshop.mockResolvedValueOnce(workshop({ status: "PUBLISHED" }));

    render(<WorkshopDetailView workshopId="workshop-1" />);
    await screen.findByRole("heading", { name: "Intro to Git Workshop" });

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishWorkshop).toHaveBeenCalledWith("workshop-1"));
    expect(await screen.findByText("Workshop published.")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("archives a published workshop via the confirmation dialog", async () => {
    mocks.getWorkshop.mockResolvedValueOnce(workshop({ status: "PUBLISHED" }));
    mocks.archiveWorkshop.mockResolvedValueOnce(workshop({ status: "ARCHIVED" }));

    render(<WorkshopDetailView workshopId="workshop-1" />);
    await screen.findByRole("heading", { name: "Intro to Git Workshop" });

    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(mocks.archiveWorkshop).toHaveBeenCalledWith("workshop-1"));
    expect(await screen.findByText("Workshop archived.")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getWorkshop.mockResolvedValueOnce(workshop());
    render(<WorkshopDetailView workshopId="workshop-1" initialEdit />);

    expect(await screen.findByRole("heading", { name: "Edit Workshop" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Intro to Git Workshop");
  });
});
