import Link from "next/link";
import { Clock, ListChecks } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Assessment } from "@/lib/student/assessments";

const DIFFICULTY_ACCENT: Record<Assessment["difficulty"], string> = {
  Beginner: "bg-muted text-muted-foreground",
  Intermediate: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
  Advanced: "border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  Expert: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400",
};

export function AssessmentCard({ assessment }: { assessment: Assessment }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="leading-snug">{assessment.title}</CardTitle>
          <Badge variant="outline" className={DIFFICULTY_ACCENT[assessment.difficulty]}>
            {assessment.difficulty}
          </Badge>
        </div>
        {assessment.skill ? <CardDescription>{assessment.skill.name}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {assessment.description ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{assessment.description}</p>
        ) : null}

        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {assessment.duration_minutes ? (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden="true" />
              {assessment.duration_minutes} min
            </span>
          ) : null}
          {assessment.question_count ? (
            <span className="flex items-center gap-1">
              <ListChecks className="size-3.5" aria-hidden="true" />
              {assessment.question_count} questions
            </span>
          ) : null}
        </div>

        <Button className="w-full" render={<Link href={`/student/assessments/${assessment.id}`} />} nativeButton={false}>
          View Assessment
        </Button>
      </CardContent>
    </Card>
  );
}
