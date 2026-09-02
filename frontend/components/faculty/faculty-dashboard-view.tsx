"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Briefcase,
  CheckCircle2,
  ClipboardList,
  FileEdit,
  Inbox,
  ListChecks,
  RefreshCw,
  User,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { StatCard } from "@/components/dashboard/stat-card";
import { ApiError } from "@/lib/api";
import { listAssessmentsForFaculty, listMyQuestions } from "@/lib/faculty/question-bank";
import { getFacultyProfile } from "@/lib/faculty/profile";
import { listFacultyOpportunities } from "@/lib/faculty/opportunities";
import { getIncomingCollaborations } from "@/lib/industry/collaborations";
import type { QuestionBank, ReviewStatus } from "@/types/question-bank";
import type { FacultyProfile } from "@/types/faculty-profile";

/** Real data throughout -- no mock values. Composed client-side from the
 * existing Phase 1K question-bank API, the Phase F3.1 faculty profile
 * endpoint, and the Phase F3.2 opportunity-discovery/application (incoming
 * collaboration) reads. Deliberately still NOT shown: evaluator/reviewer
 * metrics, which need F5+ evaluation infrastructure that doesn't exist. */

type LoadState =
  | { status: "loading" }
  | {
      status: "error";
      error: ApiError;
    }
  | {
      status: "ready";
      questions: QuestionBank[];
      assessmentCount: number;
      profile: FacultyProfile;
      opportunityCount: number;
      pendingApplicationCount: number;
    };

export function FacultyDashboardView({ facultyId }: { facultyId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [questions, { assessments }, profile, { opportunities }, { collaborations }] = await Promise.all([
          listMyQuestions(),
          listAssessmentsForFaculty(),
          getFacultyProfile(),
          listFacultyOpportunities(),
          getIncomingCollaborations({ status: "SENT" }),
        ]);
        if (cancelled) return;
        setState({
          status: "ready",
          questions,
          assessmentCount: assessments.length,
          profile,
          opportunityCount: opportunities.length,
          pendingApplicationCount: collaborations.length,
        });
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

  const { questions, assessmentCount, profile, opportunityCount, pendingApplicationCount } = state;
  const mine = questions.filter((q) => q.created_by === facultyId);
  const authored = mine.length;
  const approved = mine.filter((q) => q.review_status === "APPROVED").length;
  const needsRevision = mine.filter((q) => q.review_status === "REJECTED").length;
  const pendingReview = questions.filter((q) => q.review_status === "PENDING" && q.created_by !== facultyId);
  const recent = [...mine].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);

  return (
    <div className="space-y-6">
      <ProfileSummaryCard profile={profile} />

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

      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard
          label="Available Opportunities"
          value={String(opportunityCount)}
          helperText="Published projects, training, workshops & mentorship"
          icon={Briefcase}
          accent="indigo"
        />
        <StatCard
          label="Applications Needing Action"
          value={String(pendingApplicationCount)}
          helperText={pendingApplicationCount > 0 ? "Collaboration requests awaiting your response" : "All caught up"}
          trend={pendingApplicationCount > 0 ? "up" : "neutral"}
          icon={Inbox}
          accent="amber"
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
            <Button
              variant="outline"
              className="w-full justify-start"
              render={<Link href="/faculty/opportunities" />}
              nativeButton={false}
            >
              <Briefcase /> Browse Opportunities
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              render={<Link href="/faculty/applications" />}
              nativeButton={false}
            >
              <Inbox /> View Applications
              {pendingApplicationCount > 0 && (
                <Badge variant="secondary" className="ml-auto">
                  {pendingApplicationCount}
                </Badge>
              )}
            </Button>
            {profile.completeness < 1 && (
              <Button
                variant="outline"
                className="w-full justify-start"
                render={<Link href="/faculty/profile" />}
                nativeButton={false}
              >
                <User /> Complete Your Profile
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ProfileSummaryCard({ profile }: { profile: FacultyProfile }) {
  const pct = Math.round(profile.completeness * 100);
  const summaryParts = [profile.designation, profile.department, profile.institution_name].filter(Boolean);

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
            <User className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {summaryParts.length > 0 ? summaryParts.join(" · ") : "Complete your academic profile"}
            </p>
            <p className="text-xs text-muted-foreground">
              {summaryParts.length > 0
                ? "Academic profile"
                : "Add your designation, department, and expertise so collaborators know who you are."}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 sm:w-64">
          <div className="flex-1">
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>Profile completeness</span>
              <span>{pct}%</span>
            </div>
            <Progress value={pct} />
          </div>
          <Button size="sm" variant="outline" render={<Link href="/faculty/profile" />} nativeButton={false}>
            {profile.completeness > 0 ? "Edit" : "Start"}
          </Button>
        </div>
      </CardContent>
    </Card>
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
