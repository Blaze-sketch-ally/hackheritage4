import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getCourseRecommendations: vi.fn(),
}));

vi.mock("@/lib/student/course-recommendations", () => ({
  getCourseRecommendations: mocks.getCourseRecommendations,
}));

import { YouTubeLearningPanel } from "@/components/student/learning/youtube-learning-panel";
import type { CourseRecommendationResponse } from "@/types/course-recommendation";

const BASE_META = {
  provider: "groq" as const,
  model: "test",
  ai_ranking_available: false,
  ranking_status: "DETERMINISTIC" as const,
  external_discovery_available: false,
  external_discovery_status: "CONFIGURATION_REQUIRED" as const,
  internal_discovery_available: true,
  message: null,
  youtube_available: true,
  youtube_ai_ranking_available: false,
  youtube_status: "AVAILABLE" as const,
};

function response(overrides: Partial<CourseRecommendationResponse> = {}): CourseRecommendationResponse {
  return {
    canonical: { mode: "JOB_ROLE", target_role: "Backend Developer", skills_considered: [] },
    recommendations: [],
    learning_plan: [],
    youtube_videos: [
      {
        video: {
          video_ref: "Y1",
          video_id: "dQw4w9WgXcQ",
          skill_id: "s1",
          skill_name: "Python",
          title: "Python Full Course for Beginners",
          description: "Learn python basics.",
          channel_id: "UCabc123",
          channel_title: "Example Academy",
          published_at: "2026-01-01T00:00:00Z",
          thumbnail_url: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
          duration_iso8601: "PT1H20M",
          duration_text: "1h 20m",
          view_count: 12_345,
          like_count: 678,
          source: "YouTube",
          resource_type: "VIDEO",
          metadata_source: "YOUTUBE_DATA_API",
          watch_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        },
        for_skill: {
          ref: "G1",
          skill_id: "s1",
          skill_name: "Python",
          status: "MISSING",
          importance: "CORE",
          target_level: "Beginner",
        },
        reason: "This video is for a skill in your learning priorities.",
        rank: 1,
      },
    ],
    meta: BASE_META,
    disclaimer: "test",
    ...overrides,
  };
}

describe("YouTubeLearningPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the section with real video data once loaded", async () => {
    mocks.getCourseRecommendations.mockResolvedValue(response());
    render(<YouTubeLearningPanel />);

    expect(await screen.findByText("YouTube Learning")).toBeInTheDocument();
    expect(screen.getByText("Python Full Course for Beginners")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /watch on youtube/i })).toHaveAttribute(
      "href",
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    );
  });

  it("renders nothing while loading -- never a raw developer state", () => {
    mocks.getCourseRecommendations.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = render(<YouTubeLearningPanel />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when there are no videos (provider unconfigured/unavailable)", async () => {
    mocks.getCourseRecommendations.mockResolvedValue(
      response({ youtube_videos: [], meta: { ...BASE_META, youtube_available: false, youtube_status: "CONFIGURATION_REQUIRED" } }),
    );
    const { container } = render(<YouTubeLearningPanel />);
    await waitFor(() => expect(mocks.getCourseRecommendations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("CONFIGURATION_REQUIRED")).not.toBeInTheDocument();
  });

  it("renders nothing on a fetch error -- never a raw error message", async () => {
    mocks.getCourseRecommendations.mockRejectedValue(new Error("network down"));
    const { container } = render(<YouTubeLearningPanel />);
    await waitFor(() => expect(mocks.getCourseRecommendations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/network down/)).not.toBeInTheDocument();
  });
});
