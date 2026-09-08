"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Building2, CalendarClock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobTrainingProgramContent } from "@/components/student/job-training/job-training-program-content";
import { JobTrainingStatusBadge } from "@/components/student/job-training/job-training-status-badge";
import { ApiError } from "@/lib/api";
import { getMyJobTrainingEnrollment } from "@/lib/student/job-training";
import type { StudentJobTrainingDetail } from "@/types/job-training";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; detail: StudentJobTrainingDetail };

function heading(detail: StudentJobTrainingDetail): string {
  return detail.program.title?.trim() || detail.enrollment.job_title?.trim() || "Job Training";
}

/**
 * GET /api/v1/student/job-training/{enrollmentId}. The backend returns
 * this ONLY for the caller's own non-revoked enrollment whose program is
 * PUBLISHED -- every other case (foreign enrollment id, revoked, no
 * program, unpublished) is a plain 404, so a manually-typed id can never
 * expose another student's training.
 */
export function JobTrainingDetailView({ enrollmentId }: { enrollmentId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const detail = await getMyJobTrainingEnrollment(enrollmentId);
        if (!cancelled) setState({ status: "ready", detail });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load this job training program."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [enrollmentId, reloadKey]);

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading job training program">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    const notFound = state.error.status === 404 || state.error.status === 403;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {notFound
                ? "Job training program not found."
                : "Could not load this job training program."}
            </p>
            <p className="text-sm text-muted-foreground">
              {notFound
                ? "This training isn't available to you, or hasn't been published yet."
                : state.error.message}
            </p>
          </div>
          {!notFound && (
            <Button variant="outline" size="sm" onClick={reload}>
              Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { enrollment, program, modules, skills } = state.detail;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold break-words">{heading(state.detail)}</h1>
          <JobTrainingStatusBadge status={enrollment.enrollment_status} />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
          {enrollment.job_title ? (
            <span className="flex items-center gap-1">
              <Building2 className="size-3.5" aria-hidden="true" />
              {enrollment.job_title}
            </span>
          ) : null}
          {program.estimated_weeks != null ? (
            <span className="flex items-center gap-1">
              <CalendarClock className="size-3.5" aria-hidden="true" />
              {program.estimated_weeks} week{program.estimated_weeks === 1 ? "" : "s"}
            </span>
          ) : null}
          {enrollment.completed_at ? (
            <span>Completed {new Date(enrollment.completed_at).toLocaleDateString()}</span>
          ) : null}
        </div>
        {program.summary ? (
          <p className="max-w-prose text-sm text-muted-foreground">{program.summary}</p>
        ) : null}
      </div>

      <Card>
        <CardContent className="py-4 text-sm">
          <span className="font-medium text-emerald-700 dark:text-emerald-400">
            You&apos;re enrolled in this job training.
          </span>{" "}
          Work through the modules below. Assignments are shown for reference — submissions
          open in a later phase.
          <div className="mt-2">
            <Badge variant="outline">Job Training</Badge>
          </div>
        </CardContent>
      </Card>

      <JobTrainingProgramContent modules={modules} skills={skills} />
    </div>
  );
}
