import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getTrainings: vi.fn(),
  publishTraining: vi.fn(),
  closeTraining: vi.fn(),
  archiveTraining: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/training", () => ({
  getTrainings: mocks.getTrainings,
  publishTraining: mocks.publishTraining,
  closeTraining: mocks.closeTraining,
  archiveTraining: mocks.archiveTraining,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { TrainingsListView } from "@/components/industry/training/trainings-list-view";
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

describe("TrainingsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("does not fetch more than once on mount", () => {
    mocks.getTrainings.mockReturnValue(new Promise(() => {}));
    render(<TrainingsListView />);
    expect(mocks.getTrainings).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getTrainings.mockReturnValue(new Promise(() => {}));
    render(<TrainingsListView />);
    expect(screen.getByText(/Loading your training records/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getTrainings.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<TrainingsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no training records", async () => {
    mocks.getTrainings.mockResolvedValueOnce({ trainings: [] });
    render(<TrainingsListView />);
    expect(await screen.findByText("No training records yet")).toBeInTheDocument();
  });

  it("lists training records with title and status", async () => {
    mocks.getTrainings.mockResolvedValueOnce({
      trainings: [training(), training({ id: "training-2", title: "Data Analytics Program", status: "PUBLISHED" })],
    });
    render(<TrainingsListView />);

    expect(await screen.findByText("Cloud Fundamentals Bootcamp")).toBeInTheDocument();
    expect(screen.getByText("Data Analytics Program")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getTrainings.mockResolvedValueOnce({
      trainings: [training(), training({ id: "training-2", title: "Data Analytics Program" })],
    });
    render(<TrainingsListView />);
    await screen.findByText("Cloud Fundamentals Bootcamp");

    await userEvent.type(screen.getByLabelText("Search training"), "data");

    expect(screen.queryByText("Cloud Fundamentals Bootcamp")).not.toBeInTheDocument();
    expect(screen.getByText("Data Analytics Program")).toBeInTheDocument();
  });

  it("publishes a training record through the confirmation dialog", async () => {
    mocks.getTrainings.mockResolvedValueOnce({ trainings: [training()] });
    mocks.publishTraining.mockResolvedValueOnce(training({ status: "PUBLISHED" }));

    render(<TrainingsListView />);
    await screen.findByText("Cloud Fundamentals Bootcamp");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishTraining).toHaveBeenCalledWith("training-1"));
    expect(await screen.findByText("Training published.")).toBeInTheDocument();
  });

  it("surfaces a publish error from the API", async () => {
    mocks.getTrainings.mockResolvedValueOnce({ trainings: [training()] });
    mocks.publishTraining.mockRejectedValueOnce(
      new ApiError(422, "This training record isn't ready to publish. Add: work_mode."),
    );

    render(<TrainingsListView />);
    await screen.findByText("Cloud Fundamentals Bootcamp");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/isn't ready to publish/i)).toBeInTheDocument();
  });

  it("does not call a lifecycle action until the confirmation dialog is confirmed", async () => {
    mocks.getTrainings.mockResolvedValueOnce({ trainings: [training()] });

    render(<TrainingsListView />);
    await screen.findByText("Cloud Fundamentals Bootcamp");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    await screen.findByRole("dialog");

    expect(mocks.publishTraining).not.toHaveBeenCalled();
  });
});
