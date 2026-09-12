import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { YouTubeLearningCard } from "@/components/student/learning/youtube-learning-card";
import type { YouTubeVideoCandidate } from "@/types/youtube-learning";

function video(overrides: Partial<YouTubeVideoCandidate> = {}): YouTubeVideoCandidate {
  return {
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
    view_count: 125_000,
    like_count: 4_200,
    source: "YouTube",
    resource_type: "VIDEO",
    metadata_source: "YOUTUBE_DATA_API",
    watch_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ...overrides,
  };
}

describe("YouTubeLearningCard", () => {
  it("renders title, channel, duration, thumbnail, skill and a real watch link", () => {
    render(<YouTubeLearningCard video={video()} skillName="Python" reason="Matches your skill gap." />);

    expect(screen.getByText("Python Full Course for Beginners")).toBeInTheDocument();
    expect(screen.getByText("Example Academy")).toBeInTheDocument();
    expect(screen.getByText("1h 20m")).toBeInTheDocument();
    expect(screen.getByText(/Relevant to:/)).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Matches your skill gap.")).toBeInTheDocument();
    expect(screen.getByText("125K views")).toBeInTheDocument();

    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg");

    const link = screen.getByRole("button", { name: /watch on youtube/i });
    expect(link).toHaveAttribute("href", "https://www.youtube.com/watch?v=dQw4w9WgXcQ");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("omits thumbnail/duration/skill/views when the source didn't provide them -- never fabricated", () => {
    render(
      <YouTubeLearningCard
        video={video({
          thumbnail_url: null,
          duration_text: null,
          view_count: null,
          like_count: null,
        })}
        skillName={null}
      />,
    );

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByText(/Relevant to:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/views/)).not.toBeInTheDocument();
    // Title and the watch CTA are still present -- a sparse video is still a real, usable candidate.
    expect(screen.getByText("Python Full Course for Beginners")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /watch on youtube/i })).toBeInTheDocument();
  });

  it("never renders raw view counts, only the compact formatted form", () => {
    render(<YouTubeLearningCard video={video({ view_count: 1_200_000 })} />);
    expect(screen.getByText("1.2M views")).toBeInTheDocument();
    expect(screen.queryByText("1200000")).not.toBeInTheDocument();
  });
});
