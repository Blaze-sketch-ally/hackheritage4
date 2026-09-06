"use client";

import { useState } from "react";
import { AlertCircle, Bookmark, CheckCircle2, Loader2, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { setLearningProgress } from "@/lib/student/learning";
import {
  LEARNING_PROGRESS_STATUSES,
  PROGRESS_LABEL,
  type LearningProgressStatus,
  type ProgressUpdateResponse,
  type StudentLearningProgress,
} from "@/types/student-learning";

const ACTION = {
  SAVED: { label: "Save for later", icon: Bookmark },
  IN_PROGRESS: { label: "Mark in progress", icon: PlayCircle },
  COMPLETED: { label: "Mark completed", icon: CheckCircle2 },
} as const;

/** Lets the student move their OWN progress on one resource between
 * SAVED / IN_PROGRESS / COMPLETED. The backend allows any direct
 * transition, so this component just sends the clicked status and renders
 * the authoritative response -- no frontend state machine is enforced.
 * The request body is ONLY `{ status }`. */
export function LearningProgressControls({
  resourceId,
  progress,
  onUpdated,
}: {
  resourceId: string;
  progress: StudentLearningProgress | null;
  onUpdated: (result: ProgressUpdateResponse) => void;
}) {
  const [pending, setPending] = useState<LearningProgressStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [justUpdated, setJustUpdated] = useState(false);

  const current = progress?.status ?? null;

  async function apply(status: LearningProgressStatus) {
    setPending(status);
    setError(null);
    setJustUpdated(false);
    try {
      const result = await setLearningProgress(resourceId, status);
      onUpdated(result);
      setJustUpdated(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not update your progress. Please try again.",
      );
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Your progress</p>
      <div className="flex flex-wrap gap-2">
        {LEARNING_PROGRESS_STATUSES.map((status) => {
          const meta = ACTION[status];
          const Icon = meta.icon;
          const isCurrent = current === status;
          return (
            <Button
              key={status}
              variant={isCurrent ? "default" : "outline"}
              size="sm"
              disabled={pending !== null || isCurrent}
              onClick={() => apply(status)}
              aria-pressed={isCurrent}
            >
              {pending === status ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Icon className="size-3.5" aria-hidden="true" />
              )}
              {isCurrent ? PROGRESS_LABEL[status] : meta.label}
            </Button>
          );
        })}
      </div>

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" /> {error}
        </p>
      )}
      {justUpdated && !error && (
        <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="size-3.5 shrink-0" aria-hidden="true" /> Progress updated.
        </p>
      )}
    </div>
  );
}
