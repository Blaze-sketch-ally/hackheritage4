"use client";

import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface AssessmentProgressProps {
  /** 1-based index of the question currently on screen. */
  current: number;
  total: number;
  answeredCount: number;
  className?: string;
}

/** Progress summary shown above the question card while taking an
 * assessment: question X of Y, how many are answered so far, and a
 * visual bar. Purely presentational -- owns no save/attempt state. */
export function AssessmentProgress({
  current,
  total,
  answeredCount,
  className,
}: AssessmentProgressProps) {
  const percentComplete = total > 0 ? Math.round((answeredCount / total) * 100) : 0;

  return (
    <div className={cn("flex flex-col gap-2", className)} aria-live="polite">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">
          Question {current} of {total}
        </span>
        <span className="text-muted-foreground">
          {answeredCount} of {total} answered
        </span>
      </div>
      <Progress value={percentComplete} aria-label="Assessment progress" />
    </div>
  );
}
