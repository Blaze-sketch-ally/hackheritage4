"use client";

import Link from "next/link";
import { AlertCircle, FileText, Layers, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { hasAssessmentCapability, useFacultyCapabilities } from "@/lib/faculty/capabilities";

/**
 * Phase F5A -- the Assessment Studio landing page. This is deliberately
 * NOT a metrics dashboard: FacultyDashboardView (app/faculty/dashboard)
 * already shows the real question-authoring/review numbers this project
 * actually has, and duplicating them here would just be a second,
 * inevitably-drifting copy. This page's only job is to give "Assessment
 * Studio" a front door -- a short explanation of what it is today, the
 * caller's own author/reviewer capability status, and clear links to the
 * two tools that exist (Question Bank, Blueprints). No fabricated
 * evaluator/reviewer/analytics data -- those don't exist yet (F8/F10).
 *
 * Capability display here is a UI convenience only, using the same
 * useFacultyCapabilities()/hasAssessmentCapability() this project already
 * has (lib/faculty/capabilities.ts) -- never a second permission system.
 * The backend (require_assessment_author/reviewer) and RLS
 * (041_assessment_capability_authorization.sql) remain the real,
 * authoritative enforcement regardless of what this page shows or hides.
 */
export function AssessmentStudioOverview() {
  const capabilities = useFacultyCapabilities();

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        Assessment Studio brings together the tools Faculty use to build and maintain the shared assessment
        question bank. Question authoring, peer review, and blueprint configuration live here today; evaluation,
        rubrics, and analytics are planned for future phases.
      </p>

      <CapabilityStatus capabilities={capabilities} />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
              Question Bank
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              Author new questions and review submissions from other Faculty setters.
            </p>
            <Button render={<Link href="/faculty/questions" />} nativeButton={false} className="w-fit">
              Open Question Bank
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
              Blueprints
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              Configure how many questions of each difficulty a student&apos;s attempt randomly draws.
            </p>
            <Button
              variant="outline"
              render={<Link href="/faculty/blueprint" />}
              nativeButton={false}
              className="w-fit"
            >
              Open Blueprints
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CapabilityStatus({
  capabilities,
}: {
  capabilities: ReturnType<typeof useFacultyCapabilities>;
}) {
  if (capabilities.status === "loading") {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-busy="true">
        <Loader2 className="size-4 animate-spin" /> Loading your capabilities…
      </p>
    );
  }

  if (capabilities.status === "error") {
    return (
      <p className="flex items-center gap-1.5 text-sm text-destructive">
        <AlertCircle className="size-3.5 shrink-0" /> Could not load your capabilities.
      </p>
    );
  }

  const isAuthor = hasAssessmentCapability(capabilities.capabilities, "assessment_author");
  const isReviewer = hasAssessmentCapability(capabilities.capabilities, "assessment_reviewer");

  if (!isAuthor && !isReviewer) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
          <AlertCircle className="size-4 shrink-0" />
          An Admin has not yet granted you an assessment capability -- ask an Admin to grant Author or Reviewer
          to author or review questions.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
      <span>Your capabilities:</span>
      {isAuthor && <Badge variant="outline">Author</Badge>}
      {isReviewer && <Badge variant="outline">Reviewer</Badge>}
    </div>
  );
}
