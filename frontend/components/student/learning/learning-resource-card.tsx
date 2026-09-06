import Link from "next/link";
import { ArrowUpRight, Clock, GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { LearningProgressBadge } from "@/components/student/learning/learning-progress-badge";
import { resourceTypeLabel, type LearningResource } from "@/types/student-learning";

/** One learning-resource summary, used by LearningBrowseView. `href`
 * links into the detail page; the resource URL opens externally. All data
 * comes from the Phase 6B API -- nothing here is hardcoded. */
export function LearningResourceCard({ resource }: { resource: LearningResource }) {
  const href = `/student/learning/${resource.id}`;
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{resourceTypeLabel(resource.resource_type)}</Badge>
          {resource.difficulty && <Badge variant="outline">{resource.difficulty}</Badge>}
          <LearningProgressBadge status={resource.progress?.status} />
        </div>
        <CardTitle className="text-base">{resource.title}</CardTitle>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {resource.provider && <span>{resource.provider}</span>}
          {resource.estimated_minutes != null && (
            <span className="flex items-center gap-1">
              <Clock className="size-3" aria-hidden="true" />
              {formatMinutes(resource.estimated_minutes)}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm text-muted-foreground">
        {resource.description && <p className="line-clamp-3">{resource.description}</p>}
        {resource.skills.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {resource.skills.slice(0, 4).map((skill) => (
              <Badge key={skill.skill_id} variant="outline" className="gap-1 font-normal">
                <GraduationCap className="size-3" aria-hidden="true" />
                {skill.skill_name}
              </Badge>
            ))}
            {resource.skills.length > 4 && (
              <span className="text-xs">+{resource.skills.length - 4} more</span>
            )}
          </div>
        )}
      </CardContent>
      <CardFooter className="flex-col items-stretch gap-2">
        <Button className="w-full" render={<Link href={href} />} nativeButton={false}>
          View details
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          render={
            <a href={resource.url} target="_blank" rel="noopener noreferrer">
              Open resource <ArrowUpRight className="size-3.5" />
            </a>
          }
          nativeButton={false}
        />
      </CardFooter>
    </Card>
  );
}

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours % 1 === 0 ? hours : hours.toFixed(1)} hr`;
}
