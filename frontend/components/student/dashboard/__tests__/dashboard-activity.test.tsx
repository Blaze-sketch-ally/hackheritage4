import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listMyApplications: vi.fn(),
  listMyLearningProgress: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({ listMyApplications: mocks.listMyApplications }));
vi.mock("@/lib/student/learning", () => ({ listMyLearningProgress: mocks.listMyLearningProgress }));

import { DashboardApplications } from "@/components/student/dashboard/dashboard-applications";
import { DashboardLearning } from "@/components/student/dashboard/dashboard-learning";
import { ApiError } from "@/lib/api";

describe("DashboardApplications", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders real per-status counts from the applications API", async () => {
    mocks.listMyApplications.mockResolvedValue({
      applications: [
        { status: "APPLIED" },
        { status: "APPLIED" },
        { status: "SHORTLISTED" },
        { status: "SELECTED" },
        { status: "REJECTED" },
      ],
    });
    render(<DashboardApplications />);

    const applied = (await screen.findByText("Applied")).closest("div")!;
    expect(applied.textContent).toContain("2");
    expect(screen.getByText("Shortlisted").closest("div")!.textContent).toContain("1");
    expect(screen.getByText("Selected").closest("div")!.textContent).toContain("1");
    expect(screen.getByText(/1 not selected/)).toBeInTheDocument();
    // none of the old demo pipeline numbers
    expect(screen.queryByText("12")).not.toBeInTheDocument();
    expect(screen.queryByText("6")).not.toBeInTheDocument();
  });

  it("shows a truthful empty state when the student has no applications", async () => {
    mocks.listMyApplications.mockResolvedValue({ applications: [] });
    render(<DashboardApplications />);
    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
    expect(screen.queryByText("Applied")).not.toBeInTheDocument();
  });

  it("shows an error state with retry (does not throw)", async () => {
    mocks.listMyApplications.mockRejectedValueOnce(new ApiError(500, "boom")).mockResolvedValueOnce({
      applications: [{ status: "APPLIED" }],
    });
    render(<DashboardApplications />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Applied")).toBeInTheDocument();
  });

  it("a 401 (expired session) shows the retryable error state, not a stuck skeleton", async () => {
    mocks.listMyApplications.mockRejectedValue(new ApiError(401, "You must be signed in to do this."));
    render(<DashboardApplications />);
    expect(await screen.findByText("Couldn't load your applications.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeNull();
  });

  it("links to the real applications page", async () => {
    mocks.listMyApplications.mockResolvedValue({ applications: [] });
    const { container } = render(<DashboardApplications />);
    await screen.findByText("No applications yet");
    expect(container.querySelector('a[href="/student/applications"]')).not.toBeNull();
  });
});

describe("DashboardLearning", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders real SAVED / IN_PROGRESS / COMPLETED counts", async () => {
    mocks.listMyLearningProgress.mockResolvedValue({
      progress: [
        { status: "SAVED" },
        { status: "SAVED" },
        { status: "IN_PROGRESS" },
        { status: "COMPLETED" },
        { status: "COMPLETED" },
        { status: "COMPLETED" },
      ],
    });
    render(<DashboardLearning />);

    expect((await screen.findByText("Saved")).closest("div")!.textContent).toContain("2");
    expect(screen.getByText("In progress").closest("div")!.textContent).toContain("1");
    expect(screen.getByText("Completed").closest("div")!.textContent).toContain("3");
    // no fabricated percentage / XP / streak
    expect(screen.queryByText("64%")).not.toBeInTheDocument();
    expect(screen.queryByText(/XP|streak|hours/i)).not.toBeInTheDocument();
  });

  it("shows a truthful empty state with no progress rows", async () => {
    mocks.listMyLearningProgress.mockResolvedValue({ progress: [] });
    render(<DashboardLearning />);
    expect(await screen.findByText("No learning progress yet")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listMyLearningProgress
      .mockRejectedValueOnce(new ApiError(500, "boom"))
      .mockResolvedValueOnce({ progress: [{ status: "COMPLETED" }] });
    render(<DashboardLearning />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Completed")).toBeInTheDocument();
  });

  it("a 401 (expired session) shows the retryable error state, not a stuck skeleton", async () => {
    mocks.listMyLearningProgress.mockRejectedValue(
      new ApiError(401, "You must be signed in to do this."),
    );
    render(<DashboardLearning />);
    expect(await screen.findByText("Couldn't load your learning progress.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeNull();
  });
});
