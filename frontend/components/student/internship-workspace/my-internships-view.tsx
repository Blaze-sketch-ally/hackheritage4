"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Briefcase, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WorkspaceStatusBadge } from "@/components/student/internship-workspace/workspace-status-badge";
import { ApiError } from "@/lib/api";
import { listMyInternshipWorkspaces } from "@/lib/student/internship-workspace";
import type { InternshipWorkspaceSummary } from "@/types/internship-workspace";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; workspaces: InternshipWorkspaceSummary[] };

function workspaceTitle(ws: InternshipWorkspaceSummary): string {
  return ws.internship?.title?.trim() || "Internship";
}

/** GET /api/v1/student/internship-workspaces -- the authenticated
 * student's own workspaces only. Every workspace is a Remote/Hybrid
 * internship the student was selected for; it stays listed regardless of
 * the internship posting's later status. */
export function MyInternshipsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { workspaces } = await listMyInternshipWorkspaces();
        if (!cancelled) setState({ status: "ready", workspaces });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load your internships."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return (
      <div
        className="h-40 animate-pulse rounded-lg bg-muted"
        aria-busy="true"
        aria-label="Loading internships"
      />
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your internships.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (state.workspaces.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <Briefcase className="size-8" />
          <p className="font-medium text-foreground">No internships yet</p>
          <p className="text-sm">
            When an industry selects you for a Remote or Hybrid internship, its
            workspace appears here.
          </p>
          <Button
            size="sm"
            render={<Link href="/student/internships" />}
            nativeButton={false}
          >
            Browse Internships
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <ul className="flex flex-col gap-3" aria-label="Your internships">
      {state.workspaces.map((ws) => (
        <li key={ws.id}>
          <Card>
            <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="truncate font-medium">{workspaceTitle(ws)}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant="secondary">{ws.work_mode}</Badge>
                  <WorkspaceStatusBadge status={ws.workspace_status} />
                </div>
              </div>
              <Button
                size="sm"
                variant="outline"
                render={<Link href={`/student/my-internships/${ws.id}`} />}
                nativeButton={false}
              >
                Open Internship
              </Button>
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
