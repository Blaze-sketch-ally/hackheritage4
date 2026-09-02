"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listMyApplications } from "@/lib/student/opportunities";
import { summarizeApplications } from "@/lib/student/dashboard";
import { STATUS_LABEL, type StudentApplicationStatus } from "@/types/student-opportunity";
import { cn } from "@/lib/utils";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; summary: ReturnType<typeof summarizeApplications> };

// The pipeline the student cares about, in order. REJECTED / WITHDRAWN are
// shown only when non-zero (below), so a clean run reads as a funnel.
const PIPELINE: StudentApplicationStatus[] = [
  "APPLIED",
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
  "SELECTED",
];

const BAR_ACCENTS = [
  "bg-indigo-500",
  "bg-blue-500",
  "bg-violet-500",
  "bg-amber-500",
  "bg-emerald-500",
];

/**
 * Real application pipeline for the authenticated student, from
 * GET /api/v1/student/applications. Counts are grouped by the seven live
 * `applications.status` values — no hardcoded numbers, no demo pipeline.
 */
export function DashboardApplications() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { applications } = await listMyApplications();
        if (!cancelled) setState({ status: "ready", summary: summarizeApplications(applications) });
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
        <CardTitle>Application Pipeline</CardTitle>
        <CardAction>
          <Button
            variant="ghost"
            size="sm"
            render={<Link href="/student/applications" />}
            nativeButton={false}
          >
            View All
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        {state.status === "loading" && <PipelineSkeleton />}

        {state.status === "error" && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Couldn&apos;t load your applications.</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          </div>
        )}

        {state.status === "ready" && state.summary.total === 0 && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <FileText className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">No applications yet</p>
            <p className="text-xs text-muted-foreground">
              Apply to an internship or job to start tracking it here.
            </p>
            <Button
              size="sm"
              className="mt-1"
              render={<Link href="/student/internships" />}
              nativeButton={false}
            >
              Browse Internships
            </Button>
          </div>
        )}

        {state.status === "ready" && state.summary.total > 0 && (
          <>
            {PIPELINE.map((status, i) => {
              const count = state.summary.byStatus[status];
              const pct = (count / state.summary.total) * 100;
              return (
                <div key={status} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">{STATUS_LABEL[status]}</span>
                    <span className="font-medium tabular-nums">{count}</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn("h-full rounded-full transition-all", BAR_ACCENTS[i % BAR_ACCENTS.length])}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
            {(state.summary.byStatus.REJECTED > 0 || state.summary.byStatus.WITHDRAWN > 0) && (
              <p className="pt-1 text-xs text-muted-foreground">
                {state.summary.byStatus.REJECTED > 0 && `${state.summary.byStatus.REJECTED} not selected`}
                {state.summary.byStatus.REJECTED > 0 && state.summary.byStatus.WITHDRAWN > 0 && " · "}
                {state.summary.byStatus.WITHDRAWN > 0 && `${state.summary.byStatus.WITHDRAWN} withdrawn`}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function PipelineSkeleton() {
  return (
    <div className="space-y-3" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-1">
          <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          <div className="h-2 w-full animate-pulse rounded-full bg-muted" />
        </div>
      ))}
    </div>
  );
}
