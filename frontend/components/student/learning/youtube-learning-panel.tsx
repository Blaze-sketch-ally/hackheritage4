"use client";

import { useEffect, useState } from "react";
import { Video } from "lucide-react";
import { getCourseRecommendations } from "@/lib/student/course-recommendations";
import { YouTubeLearningCard } from "@/components/student/learning/youtube-learning-card";
import type { YouTubeRecommendation } from "@/types/course-recommendation";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; videos: YouTubeRecommendation[] };

/**
 * Self-contained "YouTube Learning" section -- fetches its own data
 * (POST /api/v1/ai/course-recommendations) independently of whatever
 * page embeds it, so its own loading/error state never blocks the rest
 * of that page (matching CareerGuidancePanel's own self-containment
 * pattern). Renders NOTHING while loading, on error, or when there are
 * no real candidates -- students never see a raw developer state
 * (CONFIGURATION_REQUIRED / quota / API errors); silence is preferred
 * over a placeholder when internal recommendations are already shown
 * elsewhere on the page.
 */
export function YouTubeLearningPanel() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getCourseRecommendations()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", videos: data.youtube_videos });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status !== "ready" || state.videos.length === 0) return null;

  return (
    <div className="space-y-3">
      <h2 className="flex items-center gap-2 text-base font-semibold">
        <Video className="size-4 text-muted-foreground" aria-hidden="true" />
        YouTube Learning
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {state.videos.map((item) => (
          <YouTubeLearningCard
            key={item.video.video_id}
            video={item.video}
            skillName={item.for_skill.skill_name}
            reason={item.reason}
          />
        ))}
      </div>
    </div>
  );
}
