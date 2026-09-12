import Link from "next/link";
import { ArrowUpRight, Clock, Eye } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatCompactCount } from "@/lib/utils";
import type { YouTubeVideoCandidate } from "@/types/youtube-learning";

/**
 * One YouTube video recommendation. Every field on `video` is
 * server-owned (backend/app/ai/schemas/youtube_learning.py) -- this
 * component never fabricates a duration, view count, or thumbnail; it
 * only renders what the source actually returned. `watch_url` opens
 * the real YouTube page, never an embedded/autoplaying player.
 */
export function YouTubeLearningCard({
  video,
  skillName,
  reason,
}: {
  video: YouTubeVideoCandidate;
  skillName?: string | null;
  reason?: string;
}) {
  return (
    <Card className="flex flex-col overflow-hidden">
      {video.thumbnail_url && (
        // eslint-disable-next-line @next/next/no-img-element -- external YouTube thumbnail, no next/image remote-pattern configured
        <img
          src={video.thumbnail_url}
          alt={video.title}
          loading="lazy"
          className="aspect-video w-full object-cover"
        />
      )}
      <CardContent className="flex flex-1 flex-col gap-2 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">YouTube</Badge>
          {video.duration_text && (
            <Badge variant="outline" className="gap-1">
              <Clock className="size-3" aria-hidden="true" />
              {video.duration_text}
            </Badge>
          )}
        </div>
        <p className="text-sm font-medium leading-snug">{video.title}</p>
        <p className="text-xs text-muted-foreground">{video.channel_title}</p>
        {skillName && (
          <p className="text-xs text-muted-foreground">
            Relevant to: <span className="text-foreground">{skillName}</span>
          </p>
        )}
        {video.view_count != null && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Eye className="size-3" aria-hidden="true" />
            {formatCompactCount(video.view_count)} views
          </p>
        )}
        {reason && <p className="text-xs text-muted-foreground">{reason}</p>}
        <Button
          size="sm"
          variant="outline"
          className="mt-auto w-full"
          render={<Link href={video.watch_url} target="_blank" rel="noopener noreferrer" />}
          nativeButton={false}
        >
          Watch on YouTube <ArrowUpRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}
