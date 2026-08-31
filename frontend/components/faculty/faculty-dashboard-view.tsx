"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, ClipboardList, FileEdit, ListChecks, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";
import { ApiError } from "@/lib/api";
import { listAssessmentsForFaculty, listMyQuestions } from "@/lib/faculty/question-bank";
import type { QuestionBank, ReviewStatus } from "@/types/question-bank";

/** Real data throughout -- no mock values. Composed client-side from the
 * existing Phase 1K question-bank API (GET /questions already returns
 * the full shared bank, any faculty/any status, per its own docstring;
 * this view just groups that same response by created_by/review_status
 * rather than asking the backend for a new endpoint). */

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; questions: QuestionBank[]; assessmentCount: number };

export function FacultyDashboardView({ facultyId }: { facultyId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [questions, { assessments }] = await Promise.all([
          listMyQuestions(),
          listAssessmentsForFaculty(),
        ]);
        if (cancelled) return;
        setState({ status: "ready", questions, assessmentCount: assessments.length });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your dashboard."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return <DashboardSkeleton />;
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your dashboard.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState({ status: "loading" });
              setReloadKey((k) => k + 1);
            }}
          >
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { questions, assessmentCount } = state;
  const mine = questions.filter((q) => q.created_by === facultyId);
  const authored = mine.length;
  const approved = mine.filter((q) => q.review_status === "APPROVED").length;
  const needsRevision = mine.filter((q) => q.review_status === "REJECTED").length;
  const pendingReview = questions.filter((q) => q.review_status === "PENDING" && q.created_by !== facultyId);
  const recent = [...mine].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Questions Authored"
          value={String(authored)}
          helperText={`${assessmentCount} assessment${assessmentCount === 1 ? "" : "s"} in the bank`}
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

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Your Recent Questions</CardTitle>
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
                <Button size="sm" render={<Link href="/faculty/questions/new" />} nativeButton={false}>
                  Create Your First Question
                </Button>
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

        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button className="w-full justify-start" render={<Link href="/faculty/questions/new" />} nativeButton={false}>
              <FileEdit /> Create Question
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              render={<Link href="/faculty/questions" />}
              nativeButton={false}
            >
              <ClipboardList /> Review Queue
              {pendingReview.length > 0 && (
                <Badge variant="secondary" className="ml-auto">
                  {pendingReview.length}
                </Badge>
              )}
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              render={<Link href="/faculty/blueprint" />}
              nativeButton={false}
            >
              <ListChecks /> Manage Blueprints
            </Button>
          </CardContent>
        </Card>
      </div>
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

function DashboardSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true" aria-label="Loading dashboard">
      {[0, 1, 2, 3].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2">
            <div className="h-3 w-20 rounded bg-muted" />
            <div className="h-6 w-12 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
