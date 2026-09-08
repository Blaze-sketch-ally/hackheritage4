"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowUpRight, BriefcaseBusiness, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobTrainingStatusBadge } from "@/components/student/job-training/job-training-status-badge";
import { ApiError } from "@/lib/api";
import { listMyJobTraining } from "@/lib/student/job-training";
import type { JobTrainingEnrollmentSummary } from "@/types/job-training";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; enrollments: JobTrainingEnrollmentSummary[] };

function enrollmentTitle(e: JobTrainingEnrollmentSummary): string {
  return e.program_title?.trim() || e.job_title?.trim() || "Job Training Program";
}

/**
 * GET /api/v1/student/job-training -- the authenticated student's own
 * non-revoked Job Training enrollments. A row appears here only when the
 * student was SELECTED for a JOB AND the industry authored a training
 * program (which is what created the enrollment). Selected internships
 * use the separate Internship Workspace and never appear here.
 */
export function JobTrainingListView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { enrollments } = await listMyJobTraining();
        if (!cancelled) setState({ status: "ready", enrollments });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load your job training."),
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
        aria-label="Loading job training"
      />
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your job training.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (state.enrollments.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <BriefcaseBusiness className="size-8" />
          <p className="font-medium text-foreground">No job training available</p>
          <p className="max-w-sm text-sm">
            Job training becomes available after you are selected for a job that has a
            training program set up by the company.
          </p>
          <Button
            size="sm"
            render={<Link href="/student/applications" />}
            nativeButton={false}
          >
            View My Applications
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <ul className="flex flex-col gap-3" aria-label="Your job training programs">
      {state.enrollments.map((e) => (
        <li key={e.enrollment_id}>
          <Card>
            <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{enrollmentTitle(e)}</p>
                {e.job_title ? (
                  <p className="truncate text-sm text-muted-foreground">{e.job_title}</p>
                ) : null}
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <JobTrainingStatusBadge status={e.enrollment_status} />
                  {e.program_status && e.program_status !== "PUBLISHED" ? (
                    <Badge variant="outline">Program {e.program_status.toLowerCase()}</Badge>
                  ) : null}
                  {e.created_at ? (
                    <span>Enrolled {new Date(e.created_at).toLocaleDateString()}</span>
                  ) : null}
                </div>
              </div>
              {e.program_id ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0"
                  render={<Link href={`/student/job-training/${e.enrollment_id}`} />}
                  nativeButton={false}
                >
                  Open Training <ArrowUpRight className="size-3.5" />
                </Button>
              ) : (
                <span className="shrink-0 text-sm text-muted-foreground">
                  Not published yet
                </span>
              )}
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  );
}
