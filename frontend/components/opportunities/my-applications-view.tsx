"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, FileText, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApplicationStatusBadge } from "@/components/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import { listMyApplications } from "@/lib/student/opportunities";
import type { Application } from "@/types/application";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; applications: Application[] };

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
    return <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading applications" />;
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
          <p className="text-sm">Browse opportunities and apply to track them here.</p>
          <Button size="sm" render={<Link href="/student/opportunities" />} nativeButton={false}>
            Browse Opportunities
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
              <TableHead>Applied</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.applications.map((app) => (
              <TableRow key={app.id}>
                <TableCell className="font-medium">
                  {app.opportunity ? (
                    <Link href={`/student/opportunities/${app.opportunity_id}`} className="hover:underline">
                      {app.opportunity.title}
                    </Link>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>
                  {app.opportunity && <Badge variant="secondary">{app.opportunity.opportunity_type}</Badge>}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {new Date(app.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <ApplicationStatusBadge status={app.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
