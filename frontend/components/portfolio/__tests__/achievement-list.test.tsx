import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyAchievements, createAchievement, deleteAchievement } = vi.hoisted(() => ({
  listMyAchievements: vi.fn(),
  createAchievement: vi.fn(),
  updateAchievement: vi.fn(),
  deleteAchievement: vi.fn(),
}));

vi.mock("@/lib/student/portfolio", () => ({
  listMyAchievements,
  createAchievement,
  updateAchievement: vi.fn(),
  deleteAchievement,
}));

import { AchievementList } from "@/components/portfolio/achievement-list";
import { ApiError } from "@/lib/api";

function achievement(overrides = {}) {
  return {
    id: "a1",
    student_id: "s1",
    title: "Winner, Regional Hackathon",
    description: "Best overall project among 40 teams.",
    achievement_date: "2025-11-01",
    issuing_organization: "State Tech Council",
    url: "https://example.com/hackathon-results",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("AchievementList", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    listMyAchievements.mockReturnValue(new Promise(() => {}));
    render(<AchievementList />);
    expect(screen.getByLabelText("Loading achievements")).toBeInTheDocument();
  });

  it("shows the empty state with no mock data", async () => {
    listMyAchievements.mockResolvedValue({ achievements: [] });
    render(<AchievementList />);
    expect(
      await screen.findByText("Add awards, recognitions, or milestones worth highlighting."),
    ).toBeInTheDocument();
  });

  it("renders an achievement once loaded", async () => {
    listMyAchievements.mockResolvedValue({ achievements: [achievement()] });
    render(<AchievementList />);
    expect(await screen.findByText("Winner, Regional Hackathon")).toBeInTheDocument();
    expect(screen.getByText("State Tech Council")).toBeInTheDocument();
    expect(screen.getByText("View")).toBeInTheDocument();
  });

  it("shows an error state when the API call fails", async () => {
    listMyAchievements.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    render(<AchievementList />);
    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
  });

  it("creates an achievement through the inline form", async () => {
    listMyAchievements
      .mockResolvedValueOnce({ achievements: [] })
      .mockResolvedValueOnce({ achievements: [achievement()] });
    createAchievement.mockResolvedValue(achievement());
    render(<AchievementList />);
    await screen.findByText("Add awards, recognitions, or milestones worth highlighting.");

    await userEvent.click(screen.getByRole("button", { name: /add achievement/i }));
    await userEvent.type(screen.getByLabelText("Title"), "Winner, Regional Hackathon");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(createAchievement).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Winner, Regional Hackathon")).toBeInTheDocument();
  });

  it("deletes an achievement after confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    listMyAchievements
      .mockResolvedValueOnce({ achievements: [achievement()] })
      .mockResolvedValueOnce({ achievements: [] });
    deleteAchievement.mockResolvedValue(undefined);
    render(<AchievementList />);
    await screen.findByText("Winner, Regional Hackathon");

    await userEvent.click(screen.getByRole("button", { name: /delete achievement/i }));

    await waitFor(() => expect(deleteAchievement).toHaveBeenCalledWith("a1"));
    confirmSpy.mockRestore();
  });
});
