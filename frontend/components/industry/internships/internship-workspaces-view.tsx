"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, CalendarDays, Inbox, RefreshCw } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { Filters } from "@/components/common/filters";
import { ApiError } from "@/lib/api";
import { getInternshipWorkspaces } from "@/lib/industry/internship-workspaces";
import {
  WORKSPACE_STATUSES,
  WORKSPACE_STATUS_LABEL,
  type InternshipWorkspaceSummary,
  type WorkspaceStatus,
} from "@/types/internship-workspace";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; workspaces: InternshipWorkspaceSummary[] };

const STATUS_CLASSES: Record<WorkspaceStatus, string> = {
  PENDING_ACCEPTANCE: "bg-muted text-muted-foreground",
  ACCEPTED: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  IN_PROGRESS: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
  COMPLETED: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  DECLINED: "bg-destructive/10 text-destructive",
  RESCINDED: "bg-foreground/5 text-muted-foreground",
};

const FILTER_OPTIONS = [
  { value: "ALL", label: "All" },
  ...WORKSPACE_STATUSES.map((value) => ({ value, label: WORKSPACE_STATUS_LABEL[value] })),
];

function initials(displayName: string): string {
  const words = displayName.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  return displayName.slice(-2).toUpperCase();
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** The Active/Enrolled/Completed roster for one internship's Internship
 * Workspaces -- the post-SELECTED lifecycle (050_internship_workspace.sql)
 * this internship's applicants moved into. Read-only: workspace status
 * transitions (accept/decline, submissions, completion) already have
 * their own dedicated flows elsewhere; this view exists so Industry can
 * see, in one place, which students are currently Active/Enrolled versus
 * Completed for THIS internship -- a gap that previously required opening
 * one application at a time. */
export function InternshipWorkspacesView({ internshipId }: { internshipId: string }) {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getInternshipWorkspaces({
      internshipId,
      status: statusFilter === "ALL" ? undefined : (statusFilter as WorkspaceStatus),
    })
      .then(({ workspaces }) => {
        if (!cancelled) setState({ status: "ready", workspaces });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load workspaces."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [internshipId, statusFilter, reloadKey]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/industry/internships/${internshipId}`}
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> Back to internship
        </Link>
        <Filters value={statusFilter} onChange={setStatusFilter} options={FILTER_OPTIONS} aria-label="Status" />
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" && state.workspaces.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No enrolled students yet"
          description="Students selected for this internship's workspace will show up here."
        />
      ) : null}

      {state.status === "ready" && state.workspaces.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {state.workspaces.map((workspace) => {
            const name = workspace.student_name?.trim() || `Applicant ${workspace.student_id.slice(0, 8)}`;
            const started = formatDate(workspace.started_at);
            const completed = formatDate(workspace.completed_at);
            return (
              <Card key={workspace.id}>
                <CardContent className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <Avatar size="sm" className="shrink-0">
                        <AvatarFallback>{initials(name)}</AvatarFallback>
                      </Avatar>
                      <p className="truncate font-medium">{name}</p>
                    </div>
                    <Badge variant="ghost" className={STATUS_CLASSES[workspace.workspace_status]}>
                      {WORKSPACE_STATUS_LABEL[workspace.workspace_status]}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    {started ? (
                      <span className="inline-flex items-center gap-1">
                        <CalendarDays className="size-3.5" aria-hidden="true" /> Started {started}
                      </span>
                    ) : null}
                    {completed ? (
                      <span className="inline-flex items-center gap-1">
                        <CalendarDays className="size-3.5" aria-hidden="true" /> Completed {completed}
                      </span>
                    ) : null}
                  </div>
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      render={<Link href={`/industry/applicants/${workspace.application_id}`} />}
                    >
                      View Application
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
