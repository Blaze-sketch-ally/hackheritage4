import Link from "next/link";
import { ArrowRight, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMinutes } from "@/components/student/learning/learning-resource-card";
import type { RecommendedAssessment } from "@/types/student-recommendation";

const REASON_LABEL: Record<RecommendedAssessment["reason_type"], string> = {
  NOT_ASSESSED: "Not yet assessed",
  SKILL_GAP: "Below required level",
};

export function AssessmentRecommendationCard({ item }: { item: RecommendedAssessment }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{item.skill_name}</Badge>
          <Badge variant="outline">{REASON_LABEL[item.reason_type]}</Badge>
          {item.difficulty && <Badge variant="outline">{item.difficulty}</Badge>}
        </div>
        <CardTitle className="text-base">{item.title}</CardTitle>
        {item.duration_minutes != null && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="size-3" aria-hidden="true" />
            {formatMinutes(item.duration_minutes)}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm">
        {/* The Skill Gap engine's own explanation string -- never a
            hardcoded UI-authored justification. */}
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Why: </span>
          {item.reason}
        </p>
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          className="w-full"
          render={<Link href={`/student/assessment/${item.id}`} />}
          nativeButton={false}
        >
          Take assessment <ArrowRight className="size-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}
