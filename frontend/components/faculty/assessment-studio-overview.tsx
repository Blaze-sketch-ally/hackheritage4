"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, ClipboardList, FileEdit, FileText, Layers, ListChecks, Loader2, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { hasAssessmentCapability, useFacultyCapabilitiesContext, type CapabilityState } from "@/lib/faculty/capabilities";
import { listAssessmentsForFaculty, listMyQuestions } from "@/lib/faculty/question-bank";
import type { QuestionBank, ReviewStatus } from "@/types/question-bank";

/**
 * Phase F5A -- the Assessment Studio landing page.
 *
 * Phase 1 (Faculty Dashboard Architecture): this is now the real
 * Question Studio dashboard -- the question-authoring/review KPIs and
 * quick actions that used to live unconditionally on the general
 * Faculty dashboard moved here, since this page is only ever reached
 * through navigation/links gated on assessment_author/assessment_reviewer
 * (see faculty-sidebar.tsx). The original reasoning for keeping metrics
 * out of this page -- "FacultyDashboardView already shows the real
 * numbers, duplicating them here would drift" -- no longer applies now
 * that FacultyDashboardView (Faculty Connect) doesn't show them at all;
 * this is the one place they now live.
 *
 * Capability display here is a UI convenience only, using the same
 * useFacultyCapabilitiesContext()/hasAssessmentCapability() this project
 * already has (lib/faculty/capabilities.tsx) -- never a second permission
 * system. The backend (require_assessment_author/reviewer) and RLS
 * (041_assessment_capability_authorization.sql) remain the real,
 * authoritative enforcement regardless of what this page shows or hides.
 * "Create Question" is hidden without assessment_author -- a
 * capability-less caller is never invited to fill out a form only to be
 * rejected by the backend at submit.
 */

type QuestionDataState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; questions: QuestionBank[]; assessmentCount: number };

export function AssessmentStudioOverview() {
  const capabilities = useFacultyCapabilitiesContext();
  const { user } = useAuth();
  const [data, setData] = useState<QuestionDataState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [questions, { assessments }] = await Promise.all([listMyQuestions(), listAssessmentsForFaculty()]);
        if (cancelled) return;
        setData({ status: "ready", questions, assessmentCount: assessments.length });
      } catch (err) {
        if (cancelled) return;
        setData({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your question-authoring activity.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const isAuthor =
    capabilities.status === "ready" && hasAssessmentCapability(capabilities.capabilities, "assessment_author");

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        Question Studio brings together the tools Faculty use to build and maintain the shared assessment question
        bank. Question authoring, peer review, and blueprint configuration live here today; evaluation, rubrics, and
        analytics are planned for future phases.
      </p>

      <CapabilityStatus capabilities={capabilities} />

      <QuestionActivitySection data={data} facultyId={user?.id} onRetry={() => setReloadKey((k) => k + 1)} />

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
            <div className="flex flex-wrap gap-2">
              <Button render={<Link href="/faculty/questions" />} nativeButton={false} className="w-fit">
                Open Question Bank
              </Button>
              {isAuthor && (
                <Button
                  variant="outline"
                  render={<Link href="/faculty/questions/new" />}
                  nativeButton={false}
                  className="w-fit"
                >
                  <Plus className="size-3.5" /> Create Question
                </Button>
              )}
            </div>
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

function QuestionActivitySection({
  data,
  facultyId,
  onRetry,
}: {
  data: QuestionDataState;
  facultyId: string | undefined;
  onRetry: () => void;
}) {
  if (data.status === "loading") {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-busy="true">
        <Loader2 className="size-4 animate-spin" /> Loading your question activity…
      </p>
    );
  }

  if (data.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-6 text-center">
          <AlertCircle className="size-6 text-destructive" />
          <p className="text-sm text-muted-foreground">{data.message}</p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const mine = data.questions.filter((q) => q.created_by === facultyId);
  const authored = mine.length;
  const approved = mine.filter((q) => q.review_status === "APPROVED").length;
  const needsRevision = mine.filter((q) => q.review_status === "REJECTED").length;
  const pendingReview = data.questions.filter((q) => q.review_status === "PENDING" && q.created_by !== facultyId);
  const recent = [...mine].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Questions Authored"
          value={String(authored)}
          helperText={`${data.assessmentCount} assessment${data.assessmentCount === 1 ? "" : "s"} in the bank`}
          icon={FileEdit}
          accent="indigo"
        />
        <StatCard
          label="Pending Your Review"
          value={String(pendingReview.length)}
          helperText={pendingReview.length > 0 ? "From other setters" : "All caught up"}
          trend={pendingReview.length > 0 ? "up" : "neutral"}
          icon={ClipboardList}
          accent="amber"
        />
        <StatCard
          label="Approved"
          value={String(approved)}
          helperText="Live in the question bank"
          trend="up"
          icon={CheckCircle2}
          accent="emerald"
        />
        <StatCard
          label="Needs Revision"
          value={String(needsRevision)}
          helperText={needsRevision > 0 ? "Rejected by a reviewer" : "None right now"}
          trend={needsRevision > 0 ? "down" : "neutral"}
          icon={ListChecks}
          accent="violet"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your Recent Questions</CardTitle>
          <CardAction>
            <Button variant="ghost" size="sm" render={<Link href="/faculty/questions" />} nativeButton={false}>
              View All
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {recent.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
              <p className="text-sm text-muted-foreground">You haven&apos;t authored any questions yet.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recent.map((q) => (
                <Link
                  key={q.id}
                  href={`/faculty/questions/${q.id}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/60 px-3 py-2 hover:bg-muted/50"
                >
                  <p className="min-w-0 flex-1 truncate text-sm font-medium">{q.question_text}</p>
                  <ReviewStatusBadge status={q.review_status} isActive={q.is_active} />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ReviewStatusBadge({ status, isActive }: { status: ReviewStatus; isActive: boolean }) {
  if (!isActive) return <Badge variant="secondary">Inactive</Badge>;
  if (status === "APPROVED") {
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">Approved</Badge>;
  }
  if (status === "REJECTED") return <Badge variant="destructive">Rejected</Badge>;
  return <Badge variant="outline">Pending</Badge>;
}

function CapabilityStatus({ capabilities }: { capabilities: CapabilityState }) {
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
