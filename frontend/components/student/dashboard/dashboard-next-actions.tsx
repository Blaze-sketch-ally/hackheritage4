"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarClock, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listMyApplications } from "@/lib/student/opportunities";
import { listMyInternshipWorkspaces } from "@/lib/student/internship-workspace";
import { listMyProjectApplications } from "@/lib/student/industry-projects";
import { listMyTrainingApplications } from "@/lib/student/training";
import { listMyWorkshopApplications } from "@/lib/student/workshops";
import { buildNextActions, type NextAction } from "@/lib/student/dashboard";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; actions: NextAction[] };

/**
 * A small, prioritized "what should I do next" section -- NOT a second
 * funnel/status view. Every action here reuses an existing Phase 1/2
 * route; this component only aggregates already-existing list endpoints
 * (buildNextActions, lib/student/dashboard.ts) and never fetches per-item.
 * Best-effort: any failed source is treated as empty rather than failing
 * the whole card, and a total failure renders nothing -- the funnel/other
 * cards already report the same underlying data.
 */
export function DashboardNextActions() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [applications, internshipWorkspaces, projectApplications, trainingApplications, workshopApplications] =
          await Promise.all([
            listMyApplications().then((r) => r.applications),
            listMyInternshipWorkspaces()
              .then((r) => r.workspaces)
              .catch(() => []),
            listMyProjectApplications()
              .then((r) => r.applications)
              .catch(() => []),
            listMyTrainingApplications()
              .then((r) => r.applications)
              .catch(() => []),
            listMyWorkshopApplications()
              .then((r) => r.applications)
              .catch(() => []),
          ]);
        if (cancelled) return;
        setState({
          status: "ready",
          actions: buildNextActions({
            applications,
            internshipWorkspaces,
            projectApplications,
            trainingApplications,
            workshopApplications,
          }),
        });
      } catch {
        if (!cancelled) setState({ status: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Best-effort card: a failure here never blocks the rest of the
  // dashboard, and the applications funnel below already surfaces the
  // same underlying data with its own retry.
  if (state.status === "error") return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Next Actions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {state.status === "loading" && <NextActionsSkeleton />}

        {state.status === "ready" && state.actions.length === 0 && (
          <p className="py-2 text-sm text-muted-foreground">You&apos;re all caught up.</p>
        )}

        {state.status === "ready" &&
          state.actions.map((action) => {
            const Icon = action.kind === "interview" ? CalendarClock : FolderOpen;
            return (
              <div
                key={action.key}
                className="flex flex-col gap-2 rounded-lg border px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-2.5">
                  <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{action.title}</p>
                    <p className="text-xs text-muted-foreground">{action.subtitle}</p>
                  </div>
                </div>
                <Button
                  size="sm"
                  className="shrink-0"
                  render={<Link href={action.href} />}
                  nativeButton={false}
                >
                  {action.ctaLabel}
                </Button>
              </div>
            );
          })}
      </CardContent>
    </Card>
  );
}

function NextActionsSkeleton() {
  return (
    <div className="space-y-2.5" aria-busy="true" aria-label="Loading next actions">
      {[0, 1].map((i) => (
        <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
      ))}
    </div>
  );
}
