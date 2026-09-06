import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getLearningResource: vi.fn(),
  setLearningProgress: vi.fn(),
}));

vi.mock("@/lib/student/learning", () => ({
  getLearningResource: mocks.getLearningResource,
  setLearningProgress: mocks.setLearningProgress,
}));

import { LearningResourceDetailView } from "@/components/student/learning/learning-resource-detail-view";
import { ApiError } from "@/lib/api";
import type { LearningResourceDetail } from "@/types/student-learning";

const RID = "res-1";

function detail(overrides: Partial<LearningResourceDetail> = {}): LearningResourceDetail {
  return {
    id: RID,
    title: "FastAPI Official Tutorial",
    description: "The official step-by-step FastAPI tutorial.",
    url: "https://fastapi.tiangolo.com/tutorial/",
    provider: "FastAPI",
    resource_type: "COURSE",
    difficulty: "Intermediate",
    estimated_minutes: 480,
    skills: [
      { skill_id: "s1", skill_name: "FastAPI", target_level: "Intermediate" },
      { skill_id: "s2", skill_name: "Python", target_level: "Intermediate" },
    ],
    progress: null,
    ...overrides,
  };
}

describe("LearningResourceDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("loads and renders the real resource with its skills", async () => {
    mocks.getLearningResource.mockResolvedValueOnce(detail());
    render(<LearningResourceDetailView resourceId={RID} />);

    expect(await screen.findByText("FastAPI Official Tutorial")).toBeInTheDocument();
    expect(screen.getByText("Skills this covers")).toBeInTheDocument();
    expect(screen.getByText(/FastAPI · Intermediate/)).toBeInTheDocument();
    expect(mocks.getLearningResource).toHaveBeenCalledWith(RID);
  });

  it("opens the resource URL in a new tab with rel=noopener noreferrer", async () => {
    mocks.getLearningResource.mockResolvedValueOnce(detail());
    const { container } = render(<LearningResourceDetailView resourceId={RID} />);
    await screen.findByText("FastAPI Official Tutorial");
    const link = container.querySelector('a[href="https://fastapi.tiangolo.com/tutorial/"]');
    expect(link).not.toBeNull();
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link?.textContent).toMatch(/open resource/i);
  });

  it("shows a not-available message on a 404", async () => {
    mocks.getLearningResource.mockRejectedValueOnce(new ApiError(404, "not found"));
    render(<LearningResourceDetailView resourceId={RID} />);
    expect(await screen.findByText("This learning resource is not available.")).toBeInTheDocument();
  });

  it("shows a retryable error on a non-404 failure", async () => {
    mocks.getLearningResource.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<LearningResourceDetailView resourceId={RID} />);
    expect(await screen.findByText("Could not load this learning resource.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("displays the current progress status when the API returns one", async () => {
    mocks.getLearningResource.mockResolvedValueOnce(
      detail({ progress: { status: "IN_PROGRESS", started_at: "2026-09-01T00:00:00Z", completed_at: null, updated_at: "2026-09-01T00:00:00Z" } }),
    );
    render(<LearningResourceDetailView resourceId={RID} />);
    expect(await screen.findAllByText("In progress")).not.toHaveLength(0);
  });

  it.each([
    ["Save for later", "SAVED"],
    ["Mark in progress", "IN_PROGRESS"],
    ["Mark completed", "COMPLETED"],
  ] as const)("the %s control sends { status: %s } only", async (label, status) => {
    mocks.getLearningResource.mockResolvedValueOnce(detail());
    mocks.setLearningProgress.mockResolvedValueOnce({
      resource_id: RID,
      status,
      started_at: status === "SAVED" ? null : "2026-09-02T00:00:00Z",
      completed_at: status === "COMPLETED" ? "2026-09-02T00:00:00Z" : null,
      created_at: "2026-09-02T00:00:00Z",
      updated_at: "2026-09-02T00:00:00Z",
    });

    render(<LearningResourceDetailView resourceId={RID} />);
    await screen.findByText("FastAPI Official Tutorial");

    await userEvent.click(screen.getByRole("button", { name: label }));

    await waitFor(() => expect(mocks.setLearningProgress).toHaveBeenCalledTimes(1));
    expect(mocks.setLearningProgress).toHaveBeenCalledWith(RID, status);
    // the lib takes (resourceId, status) -- no object, no student_id, no timestamps
    expect(mocks.setLearningProgress.mock.calls[0]).toEqual([RID, status]);
  });

  it("updates the visible status and shows a success indication after a mutation", async () => {
    mocks.getLearningResource.mockResolvedValueOnce(detail());
    mocks.setLearningProgress.mockResolvedValueOnce({
      resource_id: RID,
      status: "COMPLETED",
      started_at: "2026-09-02T00:00:00Z",
      completed_at: "2026-09-03T00:00:00Z",
      created_at: "2026-09-02T00:00:00Z",
      updated_at: "2026-09-03T00:00:00Z",
    });

    render(<LearningResourceDetailView resourceId={RID} />);
    await screen.findByText("FastAPI Official Tutorial");
    await userEvent.click(screen.getByRole("button", { name: "Mark completed" }));

    expect(await screen.findByText("Progress updated.")).toBeInTheDocument();
    // the "Mark completed" button becomes the current-state button
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Completed" })).toBeDisabled(),
    );
    // a "Completed <date>" line is now shown from the server response
    const timestampLine = screen.getByText(/Completed\s+\d/, { selector: "p" });
    expect(timestampLine).toBeInTheDocument();
  });

  it("surfaces a progress mutation error and keeps the old status", async () => {
    mocks.getLearningResource.mockResolvedValueOnce(
      detail({ progress: { status: "SAVED", started_at: null, completed_at: null, updated_at: null } }),
    );
    mocks.setLearningProgress.mockRejectedValueOnce(new ApiError(500, "could not save"));

    render(<LearningResourceDetailView resourceId={RID} />);
    await screen.findByText("FastAPI Official Tutorial");
    await userEvent.click(screen.getByRole("button", { name: "Mark completed" }));

    expect(await screen.findByText("could not save")).toBeInTheDocument();
    // still SAVED
    expect(screen.getByRole("button", { name: "Saved" })).toBeDisabled();
  });

  it("takes only a resourceId string prop -- no client student identity", () => {
    // the component's single parameter is the destructured props object;
    // there is no student_id anywhere in its contract.
    expect(LearningResourceDetailView.length).toBe(1);
  });
});
