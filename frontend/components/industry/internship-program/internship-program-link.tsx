"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProgramStatusBadge } from "@/components/industry/internship-program/program-status-badge";
import { getInternshipProgram } from "@/lib/industry/internship-program";
import type { ProgramStatus } from "@/types/internship-program";

/** Entry point to the program editor, shown on the internship detail
 * page. Reflects whether a program exists / is published so the CTA reads
 * "Set Up Program" vs "Manage Program". A failed lookup degrades to a
 * plain link -- it never blocks the internship page. */
export function InternshipProgramLink({ internshipId }: { internshipId: string }) {
  const [status, setStatus] = useState<"loading" | "none" | ProgramStatus>("loading");

  useEffect(() => {
    let cancelled = false;
    getInternshipProgram(internshipId)
      .then((bundle) => {
        if (!cancelled) setStatus(bundle.program ? bundle.program.status : "none");
      })
      .catch(() => {
        if (!cancelled) setStatus("none");
      });
    return () => {
      cancelled = true;
    };
  }, [internshipId]);

  const hasProgram = status !== "loading" && status !== "none";
  const href = `/industry/internships/${internshipId}/program`;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2">
          <BookOpen className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium">Training Program</p>
              {hasProgram ? <ProgramStatusBadge status={status as ProgramStatus} /> : null}
            </div>
            <p className="text-sm text-muted-foreground">
              {hasProgram
                ? "Modules, content and skills interns work through after accepting."
                : "Set up the modules and skills interns will work through once they accept."}
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
