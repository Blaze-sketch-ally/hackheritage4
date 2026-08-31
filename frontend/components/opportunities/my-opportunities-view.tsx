"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Briefcase, Plus, RefreshCw, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { closeOpportunity, listMyOpportunities, publishOpportunity } from "@/lib/industry/opportunities";
import type { Opportunity, OpportunityType } from "@/types/opportunity";

const STATUS_VARIANT: Record<Opportunity["status"], "outline" | "secondary" | "destructive"> = {
  DRAFT: "outline",
  PUBLISHED: "secondary",
  CLOSED: "destructive",
};

/** The industry owner's own opportunities -- shared by
 * /industry/opportunities (all types), /industry/jobs, and
 * /industry/internships (both pass `lockedType`) -- same
 * filter-over-one-component pattern as the student side. */
export function MyOpportunitiesView({ lockedType }: { lockedType?: OpportunityType }) {
  const [opportunities, setOpportunities] = useState<Opportunity[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { opportunities: rows } = await listMyOpportunities(lockedType);
        if (cancelled) return;
        setOpportunities(rows);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err : new ApiError(0, "Could not load your opportunities."));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [lockedType, reloadKey]);

  async function handlePublish(id: string) {
    setBusyId(id);
    try {
      await publishOpportunity(id);
      setReloadKey((k) => k + 1);
    } catch {
      // Surfaced via the reload -- a stale list is preferable to a silent failure.
      setReloadKey((k) => k + 1);
    } finally {
      setBusyId(null);
    }
  }

  async function handleClose(id: string) {
    setBusyId(id);
    try {
      await closeOpportunity(id);
      setReloadKey((k) => k + 1);
    } finally {
      setBusyId(null);
    }
  }

  if (error) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your opportunities.</p>
            <p className="text-sm text-muted-foreground">{error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (opportunities === null) {
    return <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading opportunities" />;
  }

  if (opportunities.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <Briefcase className="size-8" />
          <p className="font-medium text-foreground">No opportunities yet</p>
          <Button size="sm" render={<Link href="/industry/opportunities/new" />} nativeButton={false}>
            <Plus /> Post an Opportunity
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
              <TableHead>Title</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {opportunities.map((opp) => (
              <TableRow key={opp.id}>
                <TableCell className="font-medium">
                  <Link href={`/industry/opportunities/${opp.id}/edit`} className="hover:underline">
                    {opp.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{opp.opportunity_type}</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[opp.status]}>{opp.status}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">{new Date(opp.created_at).toLocaleDateString()}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1.5">
                    {opp.status === "DRAFT" && (
                      <Button size="sm" disabled={busyId === opp.id} onClick={() => handlePublish(opp.id)}>
                        Publish
                      </Button>
                    )}
                    {opp.status === "PUBLISHED" && (
                      <Button size="sm" variant="outline" disabled={busyId === opp.id} onClick={() => handleClose(opp.id)}>
                        Close
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      render={<Link href={`/industry/opportunities/${opp.id}/applicants`} />}
                      nativeButton={false}
                    >
                      <Users /> Applicants
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
