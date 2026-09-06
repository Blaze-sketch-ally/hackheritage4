"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, BookmarkCheck, CircleDashed, CircleDot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listMyLearningProgress } from "@/lib/student/learning";
import { summarizeLearning } from "@/lib/student/dashboard";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; summary: ReturnType<typeof summarizeLearning> };

/**
 * Real learning progress for the authenticated student, from
 * GET /api/v1/student/learning/progress. Only the three statuses the
 * system actually stores are shown (SAVED / IN_PROGRESS / COMPLETED) —
 * no XP, streaks, hours, certificates, or fabricated completion %.
 */
export function DashboardLearning() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { progress } = await listMyLearningProgress();
        if (!cancelled) setState({ status: "ready", summary: summarizeLearning(progress) });
      } catch {
        // Any failure (including an expired session) shows the retryable
        // error state — never leaves the card stuck on its skeleton.
        if (!cancelled) setState({ status: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Learning Progress</CardTitle>
        <CardAction>
          <Button
            variant="ghost"
            size="sm"
            render={<Link href="/student/learning" />}
            nativeButton={false}
          >
            View All
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {state.status === "loading" && (
          <div className="grid grid-cols-3 gap-3" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        )}

        {state.status === "error" && (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Couldn&apos;t load your learning progress.</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          </div>
        )}

        {state.status === "ready" && state.summary.total === 0 && (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <p className="text-sm font-medium">No learning progress yet</p>
            <p className="text-xs text-muted-foreground">
              Save a course or mark one in progress from the catalog.
            </p>
            <Button
              size="sm"
              className="mt-1"
              render={<Link href="/student/learning" />}
              nativeButton={false}
            >
              Browse Learning
            </Button>
          </div>
        )}

        {state.status === "ready" && state.summary.total > 0 && (
          <div className="grid grid-cols-3 gap-3 text-center">
            <ProgressStat
              icon={BookmarkCheck}
              label="Saved"
              value={state.summary.saved}
              className="text-sky-600 dark:text-sky-400"
            />
            <ProgressStat
              icon={CircleDot}
              label="In progress"
              value={state.summary.inProgress}
              className="text-amber-600 dark:text-amber-400"
            />
            <ProgressStat
              icon={CircleDashed}
              label="Completed"
              value={state.summary.completed}
              className="text-emerald-600 dark:text-emerald-400"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ProgressStat({
  icon: Icon,
  label,
  value,
  className,
}: {
  icon: typeof CircleDot;
  label: string;
  value: number;
  className: string;
}) {
  return (
    <div className="rounded-lg border border-border/60 px-2 py-3">
      <Icon className={`mx-auto mb-1 size-4 ${className}`} aria-hidden="true" />
      <p className="text-lg font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
