"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Info, Users, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getInstitutionInternship, removeInstitutionInternship } from "@/lib/institution/internships";
import type { InstitutionInternshipDetail } from "@/types/institution-internship";
import { APPLICATION_STATUS_LABELS, PARTICIPATION_LABELS } from "@/types/institution-internship";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; internship: InstitutionInternshipDetail };

function formatStipend(amount: number | null, currency: string | null): string {
  if (amount == null) return "Unpaid / not specified";
  return `${currency ?? ""} ${amount.toLocaleString()}`.trim();
}

/** Internship Detail (Phase 7, Part 4). Overview + participation summary
 * + institution-scoped applicant list. Never exposes student contact
 * information or industry-private interview notes (see `privacy_note`,
 * always rendered). */
export function InstitutionInternshipDetailView({ internshipId }: { internshipId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getInstitutionInternship(internshipId)
      .then((internship) => {
        if (!cancelled) setState({ status: "ready", internship });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this internship."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [internshipId, reloadKey]);

  function handleRemoved() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Button variant="ghost" size="sm" render={<Link href="/institution/internships" />}>
        <ArrowLeft className="size-4" /> Back to Internships
      </Button>

      {state.status === "loading" ? <Loading label="Loading internship…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 404
              ? "This internship isn't part of your institution's curated list."
              : state.error.message
          }
          onRetry={
            state.error.status !== 401 && state.error.status !== 404
              ? () => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }
              : undefined
          }
        />
      ) : null}

      {state.status === "ready" ? (
        <Ready
          internship={state.internship}
          removing={removing}
          onRemove={async () => {
            setRemoving(true);
            try {
              await removeInstitutionInternship(internshipId);
              handleRemoved();
            } finally {
              setRemoving(false);
            }
          }}
        />
      ) : null}
    </div>
  );
}

function Ready({
  internship: i,
  removing,
  onRemove,
}: {
  internship: InstitutionInternshipDetail;
  removing: boolean;
  onRemove: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{i.title}</h1>
            <Badge variant={i.status === "PUBLISHED" ? "default" : "secondary"}>{i.status}</Badge>
            <Badge variant={i.association_status === "ACTIVE" ? "outline" : "secondary"}>
              {i.association_status === "ACTIVE" ? "Curated" : "Removed"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{i.company_name ?? "Unknown company"}</p>
        </div>
        {i.association_status === "ACTIVE" ? (
          <Button variant="outline" size="sm" disabled={removing} onClick={onRemove}>
            <X className="size-4" /> Remove from Institution
          </Button>
        ) : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Overview</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-3 text-sm sm:col-span-2">
            <p className="text-muted-foreground">{i.description ?? "No description provided."}</p>
          </div>
          {[
            ["Location", i.location ?? "—"],
            ["Mode", i.work_mode ?? "—"],
            ["Duration", i.duration_months != null ? `${i.duration_months} months` : "—"],
            ["Stipend", formatStipend(i.stipend_amount, i.stipend_currency)],
            ["Application Deadline", i.application_deadline ?? "—"],
            ["Start Date", i.start_date ?? "—"],
          ].map(([label, value]) => (
            <div key={label as string}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-sm font-medium">{value}</p>
            </div>
          ))}
          {i.eligibility_criteria ? (
            <div className="sm:col-span-2">
              <p className="text-xs text-muted-foreground">Eligibility Criteria (as written by the company)</p>
              <p className="text-sm">{i.eligibility_criteria}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Student Participation</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Applicants", i.applicants_from_institution],
                ["Selected", i.selected_from_institution],
                ["Active", i.participation.active],
                ["Completed", i.participation.completed],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-lg bg-muted/50 px-3 py-2">
                  <p className="text-xl font-semibold tabular-nums">{value}</p>
                  <p className="text-[11px] text-muted-foreground">{label}</p>
                </div>
              ))}
            </div>
            {i.participation.unknown > 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {i.participation.unknown} selected student(s) have an unknown participation stage (missing start
                date or duration).
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Application Status Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5">
              {i.status_distribution
                .filter((s) => s.count > 0)
                .map((s) => (
                  <li key={s.status} className="flex items-center justify-between text-sm">
                    <span>{APPLICATION_STATUS_LABELS[s.status] ?? s.status}</span>
                    <span className="font-semibold tabular-nums">{s.count}</span>
                  </li>
                ))}
              {i.status_distribution.every((s) => s.count === 0) ? (
                <p className="text-sm text-muted-foreground/70">No applications yet.</p>
              ) : null}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Applicants from Your Institution</CardTitle>
        </CardHeader>
        <CardContent>
          {i.applicants.length === 0 ? (
            <EmptyState icon={Users} title="No applicants from your institution yet" />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead className="text-right">CGPA</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Participation</TableHead>
                  <TableHead>Interview</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {i.applicants.map((a) => (
                  <TableRow key={a.application_id}>
                    <TableCell className="font-medium">
                      <Link href={`/institution/students/${a.student_id}`} className="hover:underline">
                        {a.full_name ?? a.username ?? "Unknown student"}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{a.department}</TableCell>
                    <TableCell className="text-right tabular-nums">{a.cgpa ?? "—"}</TableCell>
                    <TableCell>{APPLICATION_STATUS_LABELS[a.status] ?? a.status}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {a.participation_estimate ? PARTICIPATION_LABELS[a.participation_estimate] : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {a.interview ? `${a.interview.status} · ${a.interview.mode}` : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="space-y-2">
        {[i.eligibility_note, i.participation_note, i.privacy_note].map((note) => (
          <p
            key={note}
            className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground"
          >
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {note}
          </p>
        ))}
      </div>
    </div>
  );
}
