"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobProgramStatusBadge } from "@/components/industry/job-training-program/program-status-badge";
import { getJobTrainingProgram } from "@/lib/industry/job-training";
import type { JobProgramStatus } from "@/types/job-training-program";

/** Entry point to the job training program editor, shown on the job detail
 * page. Reflects whether a program exists / is published so the CTA reads
 * "Set Up Training Program" vs "Manage Training Program". A failed lookup
 * degrades to a plain link -- it never blocks the job page. Mirrors
 * components/industry/internship-program/internship-program-link.tsx. */
export function JobTrainingProgramLink({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<"loading" | "none" | JobProgramStatus>("loading");

  useEffect(() => {
    let cancelled = false;
    getJobTrainingProgram(jobId)
      .then((bundle) => {
        if (!cancelled) setStatus(bundle.program ? bundle.program.status : "none");
      })
      .catch(() => {
        if (!cancelled) setStatus("none");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const hasProgram = status !== "loading" && status !== "none";
  const href = `/industry/jobs/${jobId}/training-program`;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2">
          <GraduationCap className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">Job Training Program</p>
              {hasProgram ? <JobProgramStatusBadge status={status as JobProgramStatus} /> : null}
            </div>
            <p className="text-sm text-muted-foreground">
              {hasProgram
                ? "Modules, content and skills a selected candidate works through."
                : "Set up the modules and skills a selected candidate will work through."}
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant={hasProgram ? "outline" : "default"}
          render={<Link href={href} />}
          nativeButton={false}
        >
          {status === "loading" ? "Program" : hasProgram ? "Manage Program" : "Set Up Program"}
        </Button>
      </CardContent>
    </Card>
  );
}
