"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, RefreshCw, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApplicationStatusBadge } from "@/components/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import { listApplicants, updateApplicationStatus } from "@/lib/industry/opportunities";
import { APPLICATION_STATUSES, type Applicant, type ApplicationStatus } from "@/types/application";

const STATUS_ITEMS: Record<ApplicationStatus, string> = {
  APPLIED: "Applied",
  SHORTLISTED: "Shortlisted",
  INTERVIEW: "Interview",
  SELECTED: "Selected",
  REJECTED: "Rejected",
};

/** The industry owner's applicant list for one opportunity -- never
 * exposes answer keys, raw assessment answers, or another opportunity's
 * applicants (see app.services.application_service.
 * list_opportunity_applicants on the backend). Each row's match score is
 * freshly computed, never a stored value. */
export function ApplicantTable({ opportunityId }: { opportunityId: string }) {
  const [applicants, setApplicants] = useState<Applicant[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { applicants: rows } = await listApplicants(opportunityId);
        if (cancelled) return;
        setApplicants(rows.sort((a, b) => Number(b.overall_match_score) - Number(a.overall_match_score)));
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err : new ApiError(0, "Could not load applicants."));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [opportunityId, reloadKey]);

  async function handleStatusChange(applicationId: string, next: ApplicationStatus) {
    setBusyId(applicationId);
    try {
      await updateApplicationStatus(applicationId, next);
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
            <p className="font-medium">Could not load applicants.</p>
            <p className="text-sm text-muted-foreground">{error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (applicants === null) {
    return <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading applicants" />;
  }

  if (applicants.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <Users className="size-8" />
          <p className="font-medium text-foreground">No applicants yet</p>
          <p className="text-sm">Applicants will appear here once the opportunity is published.</p>
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
              <TableHead>Student</TableHead>
              <TableHead className="text-right">Match</TableHead>
              <TableHead>Applied</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Update Status</TableHead>
              <TableHead className="text-right">Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {applicants.map((applicant) => (
              <TableRow key={applicant.id}>
                <TableCell className="font-medium">{applicant.student_name ?? "Unknown"}</TableCell>
                <TableCell className="text-right tabular-nums">{Number(applicant.overall_match_score).toFixed(0)}%</TableCell>
                <TableCell className="text-muted-foreground">{new Date(applicant.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <ApplicationStatusBadge status={applicant.status} />
                </TableCell>
                <TableCell className="text-right">
                  <Select
                    value={applicant.status}
                    onValueChange={(v) => v && handleStatusChange(applicant.id, v as ApplicationStatus)}
                    items={STATUS_ITEMS}
                    disabled={busyId === applicant.id}
                  >
                    <SelectTrigger className="ml-auto w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {APPLICATION_STATUSES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {STATUS_ITEMS[s]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    render={<Link href={`/industry/opportunities/${opportunityId}/applicants/${applicant.id}`} />}
                    nativeButton={false}
                  >
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
