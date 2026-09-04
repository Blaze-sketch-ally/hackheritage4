"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { SubmissionStatusBadge } from "@/components/common/submission-status-badge";
import { ApiError } from "@/lib/api";
import { listMyWorkspaceAssignments } from "@/lib/student/internship-workspace";
import type { WorkspaceAssignmentSummary } from "@/types/internship-workspace";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; assignments: WorkspaceAssignmentSummary[] };

/** The published assignments in the student's own workspace, grouped by
 * module. Shown only once the workspace is ACCEPTED / IN_PROGRESS (the
 * caller gates that). Each row links to the assignment detail page where
 * the student submits work. */
export function WorkspaceAssignments({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    listMyWorkspaceAssignments(workspaceId)
      .then(({ assignments }) => {
        if (!cancelled) setState({ status: "ready", assignments });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load assignments.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading assignments">
        <div className="h-16 animate-pulse rounded-lg bg-muted" />
      </section>
    );
  }

  if (state.status === "error") {
    return <p className="text-sm text-destructive">{state.message}</p>;
  }

  if (state.assignments.length === 0) {
    return (
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
          Assignments
        </h2>
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            No assignments have been published for this internship yet.
          </CardContent>
        </Card>
      </section>
    );
  }

  const byModule = new Map<string, WorkspaceAssignmentSummary[]>();
  for (const a of state.assignments) {
    const key = a.module_title ?? "Assignments";
    const group = byModule.get(key) ?? [];
    group.push(a);
    byModule.set(key, group);
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
        Assignments
      </h2>
      {[...byModule.entries()].map(([moduleTitle, group]) => (
        <div key={moduleTitle} className="flex flex-col gap-2">
          <p className="text-xs font-medium text-muted-foreground">{moduleTitle}</p>
          {group.map((a) => (
            <Card key={a.id}>
              <CardContent className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-3">
                <Link
                  href={`/student/my-internships/${workspaceId}/assignments/${a.id}`}
                  className="group min-w-0 flex-1"
                >
                  <span className="flex items-center gap-1 font-medium group-hover:underline">
                    {a.title}
                    <ChevronRight className="size-3.5 text-muted-foreground" />
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {a.is_required ? "Required" : "Optional"}
                    {a.due_offset_days != null
                      ? ` · due day ${a.due_offset_days}`
                      : ""}
                  </span>
                </Link>
                {a.latest_submission ? (
                  <SubmissionStatusBadge status={a.latest_submission.submission_status} />
                ) : a.can_submit ? (
                  <Badge variant="outline">Not started</Badge>
                ) : null}
                {a.attempt_count > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <CheckCircle2 className="size-3.5" />
                    {a.attempt_count} attempt{a.attempt_count === 1 ? "" : "s"}
                  </span>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ))}
    </section>
  );
}
