import Link from "next/link";
import { ArrowRight, Clock, GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMinutes } from "@/components/student/learning/learning-resource-card";
import { resourceTypeLabel, type LearningRecommendation } from "@/types/student-learning";

/** One recommended learning resource. Same canonical shape the existing
 * /student/learning "Recommended for your skill gap" section uses -- the
 * `reason` text is the Skill Gap engine's own server-authored string. */
export function LearningRecommendationCard({ item }: { item: LearningRecommendation }) {
  const { resource, matched_skills } = item;
  const primaryReason = matched_skills[0]?.reason;

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{resourceTypeLabel(resource.resource_type)}</Badge>
          {resource.difficulty && <Badge variant="outline">{resource.difficulty}</Badge>}
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
      <CardContent className="flex-1 space-y-2 text-sm">
        <div className="flex flex-wrap gap-1">
          {matched_skills.map((skill) => (
            <Badge key={skill.skill_id} variant="outline" className="gap-1 font-normal">
              <GraduationCap className="size-3" aria-hidden="true" />
              {skill.skill_name}
            </Badge>
          ))}
        </div>
        {primaryReason && (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Why: </span>
            {primaryReason}
          </p>
        )}
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          className="w-full"
          render={<Link href={`/student/learning/${resource.id}`} />}
          nativeButton={false}
        >
          View resource <ArrowRight className="size-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}
