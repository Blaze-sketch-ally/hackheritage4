"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, BriefcaseBusiness } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { listMyJobTraining } from "@/lib/student/job-training";
import type { JobTrainingEnrollmentSummary } from "@/types/job-training";

/**
 * Dashboard nudge for Job Training. Renders NOTHING unless the student
 * actually has an accessible enrollment (GET /api/v1/student/job-training)
 * -- no fabricated progress / completion / score, and never shown just
 * because an application is SELECTED. Loading and error both render null
 * so the dashboard layout never jumps for a student who has no training.
 */
export function DashboardJobTraining() {
  const [enrollments, setEnrollments] = useState<JobTrainingEnrollmentSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { enrollments } = await listMyJobTraining();
        if (!cancelled) setEnrollments(enrollments);
      } catch {
        if (!cancelled) setEnrollments([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!enrollments || enrollments.length === 0) return null;

  const openable = enrollments.find((e) => e.program_id);
  const count = enrollments.length;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <BriefcaseBusiness className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-medium">Job training available</p>
            <p className="text-sm text-muted-foreground">
              You have {count} job training program{count === 1 ? "" : "s"} from a company that
              selected you.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="shrink-0"
          render={
            <Link
              href={
                count === 1 && openable
                  ? `/student/job-training/${openable.enrollment_id}`
                  : "/student/job-training"
              }
            />
          }
          nativeButton={false}
        >
          {count === 1 && openable ? "Open Training" : "View Job Training"}
          <ArrowUpRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}
