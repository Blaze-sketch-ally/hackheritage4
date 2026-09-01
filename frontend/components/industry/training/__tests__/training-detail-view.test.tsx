import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getTraining: vi.fn(),
  updateTraining: vi.fn(),
  publishTraining: vi.fn(),
  closeTraining: vi.fn(),
  archiveTraining: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/training", () => ({
  getTraining: mocks.getTraining,
  updateTraining: mocks.updateTraining,
  publishTraining: mocks.publishTraining,
  closeTraining: mocks.closeTraining,
  archiveTraining: mocks.archiveTraining,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { TrainingDetailView } from "@/components/industry/training/training-detail-view";
import { ApiError } from "@/lib/api";
import type { IndustryTraining } from "@/types/industry-training";

function training(overrides: Partial<IndustryTraining> = {}): IndustryTraining {
  return {
    id: "training-1",
    industry_id: "industry-1",
    title: "Cloud Fundamentals Bootcamp",
    description: "A hands-on introduction.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_months: 2,
    capacity: 30,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("TrainingDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getTraining.mockReturnValue(new Promise(() => {}));
    render(<TrainingDetailView trainingId="training-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getTraining.mockRejectedValueOnce(new ApiError(404, "Training not found."));
    render(<TrainingDetailView trainingId="training-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders training detail with status", async () => {
    mocks.getTraining.mockResolvedValueOnce(training());
    render(<TrainingDetailView trainingId="training-1" />);

    expect(
      await screen.findByRole("heading", { name: "Cloud Fundamentals Bootcamp" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText("Remote").length).toBeGreaterThan(0);
  });

  it("switches to the edit form and saves changes", async () => {
    mocks.getTraining.mockResolvedValueOnce(training());
    mocks.updateTraining.mockResolvedValueOnce(training({ title: "Advanced Cloud Bootcamp" }));

    render(<TrainingDetailView trainingId="training-1" />);
    await screen.findByRole("heading", { name: "Cloud Fundamentals Bootcamp" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Advanced Cloud Bootcamp");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateTraining).toHaveBeenCalledTimes(1));
    expect(mocks.updateTraining.mock.calls[0][0]).toBe("training-1");
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Advanced Cloud Bootcamp" })).toBeInTheDocument();
  });

  it("publishes via the confirmation dialog", async () => {
    mocks.getTraining.mockResolvedValueOnce(training());
    mocks.publishTraining.mockResolvedValueOnce(training({ status: "PUBLISHED" }));

    render(<TrainingDetailView trainingId="training-1" />);
    await screen.findByRole("heading", { name: "Cloud Fundamentals Bootcamp" });

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishTraining).toHaveBeenCalledWith("training-1"));
    expect(await screen.findByText("Training published.")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("archives a published training record via the confirmation dialog", async () => {
    mocks.getTraining.mockResolvedValueOnce(training({ status: "PUBLISHED" }));
    mocks.archiveTraining.mockResolvedValueOnce(training({ status: "ARCHIVED" }));

    render(<TrainingDetailView trainingId="training-1" />);
    await screen.findByRole("heading", { name: "Cloud Fundamentals Bootcamp" });

    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(mocks.archiveTraining).toHaveBeenCalledWith("training-1"));
    expect(await screen.findByText("Training archived.")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getTraining.mockResolvedValueOnce(training());
    render(<TrainingDetailView trainingId="training-1" initialEdit />);

    expect(await screen.findByRole("heading", { name: "Edit Training" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Cloud Fundamentals Bootcamp");
  });
});
