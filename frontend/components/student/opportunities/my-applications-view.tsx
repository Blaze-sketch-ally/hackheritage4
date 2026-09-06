"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, FileText, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApplicationStatusBadge } from "@/components/student/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import { listMyApplications } from "@/lib/student/opportunities";
import type { SourceType, StudentApplication } from "@/types/student-opportunity";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; applications: StudentApplication[] };

const TYPE_LABEL: Record<SourceType, string> = { JOB: "Job", INTERNSHIP: "Internship" };
const DETAIL_BASE: Record<SourceType, string> = {
  INTERNSHIP: "/student/internships",
  JOB: "/student/jobs",
};

/** GET /api/v1/student/applications -- the authenticated student's own
 * applications only. Status is whatever the owning Industry account last
 * set; this view re-fetches on mount so it always shows the current
 * value. */
export function MyApplicationsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { applications } = await listMyApplications();
        if (cancelled) return;
        setState({ status: "ready", applications });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your applications."),
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
        aria-label="Loading applications"
      />
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your applications.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (state.applications.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <FileText className="size-8" />
          <p className="font-medium text-foreground">No applications yet</p>
          <p className="text-sm">Browse internships and jobs, and apply to track them here.</p>
          <Button size="sm" render={<Link href="/student/internships" />} nativeButton={false}>
            Browse Internships
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Opportunity</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Applied on</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.applications.map((app) => {
              const opp = app.opportunity;
              const type = opp?.source_type ?? app.opportunity_type;
              return (
                <TableRow key={app.id}>
                  <TableCell className="font-medium">
                    {opp?.title && opp.id ? (
                      <Link href={`${DETAIL_BASE[type]}/${opp.id}`} className="hover:underline">
                        {opp.title}
                      </Link>
                    ) : (
                      opp?.title ?? "—"
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{TYPE_LABEL[type]}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {opp?.industry?.company_name ?? "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "—"}
                  </TableCell>
                  <TableCell>
                    <ApplicationStatusBadge status={app.status} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
