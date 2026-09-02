import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getRecommendedLearningResources: vi.fn(),
}));

vi.mock("@/lib/student/learning", () => ({
  getRecommendedLearningResources: mocks.getRecommendedLearningResources,
}));

import { LearningRecommendations } from "@/components/student/learning/learning-recommendations";
import { ApiError } from "@/lib/api";
import type {
  LearningRecommendation,
  LearningRecommendationListResponse,
} from "@/types/student-learning";

function recommendation(overrides: Partial<LearningRecommendation> = {}): LearningRecommendation {
  return {
    resource: {
      id: "res-1",
      title: "FastAPI Official Tutorial",
      description: "Step by step.",
      url: "https://fastapi.tiangolo.com/tutorial/",
      provider: "FastAPI",
      resource_type: "COURSE",
      difficulty: "Intermediate",
      estimated_minutes: 480,
      skills: [{ skill_id: "s1", skill_name: "FastAPI", target_level: "Intermediate" }],
      progress: null,
    },
    matched_skills: [
      {
        skill_id: "s1",
        skill_name: "FastAPI",
        reason: "FastAPI is a core requirement for Backend Developer and isn't in your skill list yet.",
        priority: "HIGH",
      },
    ],
    ...overrides,
  };
}

function payload(
  overrides: Partial<LearningRecommendationListResponse> = {},
): LearningRecommendationListResponse {
  return { mode: "JOB_ROLE", recommendations: [recommendation()], ...overrides };
}

describe("LearningRecommendations", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders recommendations from the API with the matched skill and reason", async () => {
    mocks.getRecommendedLearningResources.mockResolvedValueOnce(payload());
    render(<LearningRecommendations />);

    expect(await screen.findByText("FastAPI Official Tutorial")).toBeInTheDocument();
    // matched Skill Gap skill is shown
    expect(screen.getAllByText("FastAPI").length).toBeGreaterThan(0);
    // the Skill Gap engine's own reason text is surfaced verbatim
    expect(
      screen.getByText(/core requirement for Backend Developer/i),
    ).toBeInTheDocument();
  });

  it("shows the job-role subtitle in JOB_ROLE mode and the personal one in PERSONAL mode", async () => {
    mocks.getRecommendedLearningResources.mockResolvedValueOnce(payload({ mode: "JOB_ROLE" }));
    const { unmount } = render(<LearningRecommendations />);
    expect(await screen.findByText(/your target role still needs/i)).toBeInTheDocument();
    unmount();

    mocks.getRecommendedLearningResources.mockResolvedValueOnce(
      payload({ mode: "PERSONAL" }),
    );
    render(<LearningRecommendations />);
    expect(await screen.findByText(/suggests learning next/i)).toBeInTheDocument();
  });

  it("shows a truthful empty state when nothing is mapped to the student's gaps", async () => {
    mocks.getRecommendedLearningResources.mockResolvedValueOnce(
      payload({ recommendations: [] }),
    );
    render(<LearningRecommendations />);

    expect(
      await screen.findByText("No learning resources are currently mapped to your skill gaps."),
    ).toBeInTheDocument();
  });

  it("isolates a recommendation API failure -- it renders its own notice and never throws", async () => {
    mocks.getRecommendedLearningResources.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(
      <div>
        <LearningRecommendations />
        <p>catalog sibling still here</p>
      </div>,
    );

    expect(
      await screen.findByText("Couldn't load your skill-gap recommendations right now."),
    ).toBeInTheDocument();
    expect(screen.getByText(/full catalog below is unaffected/i)).toBeInTheDocument();
    // a sibling in the same tree is unaffected
    expect(screen.getByText("catalog sibling still here")).toBeInTheDocument();
  });

  it("retries the request when Try again is clicked after an error", async () => {
    mocks.getRecommendedLearningResources
      .mockRejectedValueOnce(new ApiError(500, "boom"))
      .mockResolvedValueOnce(payload());
    render(<LearningRecommendations />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText("FastAPI Official Tutorial")).toBeInTheDocument();
    expect(mocks.getRecommendedLearningResources).toHaveBeenCalledTimes(2);
  });

  it("links to the full Skill Gap page and to each resource's detail page", async () => {
    mocks.getRecommendedLearningResources.mockResolvedValueOnce(payload());
    const { container } = render(<LearningRecommendations />);
    await screen.findByText("FastAPI Official Tutorial");

    expect(container.querySelector('a[href="/student/skill-gap"]')).not.toBeNull();
    expect(container.querySelector('a[href="/student/learning/res-1"]')).not.toBeNull();
  });

  it("opens the external resource URL in a new tab safely", async () => {
    mocks.getRecommendedLearningResources.mockResolvedValueOnce(payload());
    const { container } = render(<LearningRecommendations />);
    await screen.findByText("FastAPI Official Tutorial");

    const link = container.querySelector('a[href="https://fastapi.tiangolo.com/tutorial/"]');
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("requests only the caller's own recommendations -- no student_id, no skill id", async () => {
    mocks.getRecommendedLearningResources.mockResolvedValueOnce(payload({ recommendations: [] }));
    render(<LearningRecommendations />);
    await screen.findByText(/No learning resources are currently mapped/i);

    expect(mocks.getRecommendedLearningResources).toHaveBeenCalledTimes(1);
    expect(mocks.getRecommendedLearningResources.mock.calls[0]).toEqual([]);
  });

  it("takes no props -- there is no client-supplied identity", () => {
    expect(LearningRecommendations.length).toBe(0);
  });
});
