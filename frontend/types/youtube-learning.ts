/**
 * Mirrors `YouTubeVideoCandidate` (app.ai.schemas.youtube_learning) --
 * every field here is source-owned (the YouTube Data API v3 response);
 * never LLM-authored. `watch_url` is a computed field on the backend,
 * derived only from `video_id` -- never built here from a title/slug.
 */
export interface YouTubeVideoCandidate {
  video_ref: string;
  video_id: string;
  skill_id: string;
  skill_name: string;
  title: string;
  description: string | null;
  channel_id: string | null;
  channel_title: string;
  published_at: string | null;
  thumbnail_url: string | null;
  duration_iso8601: string | null;
  duration_text: string | null;
  view_count: number | null;
  like_count: number | null;
  source: "YouTube";
  resource_type: "VIDEO";
  metadata_source: "YOUTUBE_DATA_API";
  watch_url: string;
}
