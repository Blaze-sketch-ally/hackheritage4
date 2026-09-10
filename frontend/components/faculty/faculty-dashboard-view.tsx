"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Briefcase,
  ClipboardCheck,
  Inbox,
  LayoutGrid,
  ListChecks,
  RefreshCw,
  ShieldAlert,
  User,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { StatCard } from "@/components/dashboard/stat-card";
import { ApiError } from "@/lib/api";
import {
  type AssessmentCapability,
  hasEvaluationWorkspaceAccess,
  hasQuestionStudioAccess,
  useFacultyCapabilitiesContext,
} from "@/lib/faculty/capabilities";
import { getFacultyProfile } from "@/lib/faculty/profile";
import { listFacultyOpportunities } from "@/lib/faculty/opportunities";
import { getFacultyTasks } from "@/lib/faculty/tasks";
import { getIncomingCollaborations } from "@/lib/industry/collaborations";
import type { FacultyProfile } from "@/types/faculty-profile";
import type { FacultyTasks } from "@/types/faculty-tasks";

/** Phase 1 (Faculty Dashboard Architecture): this is now the Faculty
 * Connect dashboard -- the general-Faculty experience every FACULTY user
 * gets, regardless of capability. Question-authoring/review KPIs and
 * quick actions used to live here unconditionally; they moved to
 * AssessmentStudioOverview (the Question Studio dashboard), which is
 * only ever shown/linked to a caller who actually holds
 * assessment_author or assessment_reviewer. This view no longer reads
 * the question bank at all -- see that component for the moved content.
 *
 * Real data throughout -- no mock values. Composed client-side from the
 * Phase F3.1 faculty profile endpoint and the Phase F3.2 opportunity-
 * discovery/application (incoming collaboration) reads. */

type LoadState =
  | { status: "loading" }
  | {
      status: "error";
      error: ApiError;
    }
  | {
      status: "ready";
      profile: FacultyProfile;
      opportunityCount: number;
      pendingApplicationCount: number;
      tasks: FacultyTasks;
    };

export function FacultyDashboardView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const capabilityState = useFacultyCapabilitiesContext();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [profile, { opportunities }, { collaborations }, tasks] = await Promise.all([
          getFacultyProfile(),
          listFacultyOpportunities(),
          getIncomingCollaborations({ status: "SENT" }),
          getFacultyTasks(),
        ]);
        if (cancelled) return;
        setState({
          status: "ready",
          profile,
          opportunityCount: opportunities.length,
          pendingApplicationCount: collaborations.length,
          tasks,
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

  const { profile, opportunityCount, pendingApplicationCount, tasks } = state;
  const capabilities = capabilityState.status === "ready" ? capabilityState.capabilities : null;
  const showWorkspaceSwitcher =
    capabilities !== null && (hasQuestionStudioAccess(capabilities) || hasEvaluationWorkspaceAccess(capabilities));

  return (
    <div className="space-y-6">
      <ProfileSummaryCard profile={profile} />

      {showWorkspaceSwitcher && capabilities !== null && <WorkspaceSwitcherCard capabilities={capabilities} />}

      <FacultyTasksCard tasks={tasks} />

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

      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
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
  );
}

/** Only rendered once capabilities have resolved to at least one
 * additional workspace -- a Faculty member with no assessment
 * capability at all never sees a "switcher" implying workspaces that
 * don't exist for them (see the audit's "do not show contributor
 * widgets merely because the user is Faculty" finding). */
function WorkspaceSwitcherCard({ capabilities }: { capabilities: readonly AssessmentCapability[] }) {
  const isQuestionStudio = hasQuestionStudioAccess(capabilities);
  const isEvaluator = hasEvaluationWorkspaceAccess(capabilities);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Your Faculty Workspaces</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Badge variant="outline" className="pointer-events-none">
          Faculty Connect (current)
        </Badge>
        {isQuestionStudio && (
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/faculty/assessment-studio" />}
            nativeButton={false}
          >
            <LayoutGrid className="size-3.5" /> Question Studio
          </Button>
        )}
        {isEvaluator && (
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/faculty/evaluation-workspace" />}
            nativeButton={false}
          >
            <ClipboardCheck className="size-3.5" /> Evaluation Workspace
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

/** Deterministic "what needs my attention" surface (GET /faculty/tasks) --
 * no LLM call, no invented relevance score. Renders nothing at all when
 * every category is empty, rather than an empty "0 pending" card that
 * would just take up space for no reason. Each row links to the actual
 * existing page that owns the action (Question Studio / Evaluation
 * Workspace / Mentorship) -- this card never duplicates those pages'
 * own functionality, only surfaces a ranked pointer into them. */
function FacultyTasksCard({ tasks }: { tasks: FacultyTasks }) {
  const { pending_reviews, pending_evaluations, mentorship_attention, pending_reconciliations } = tasks;
  const total =
    pending_reviews.length + pending_evaluations.length + mentorship_attention.length + pending_reconciliations.length;
  if (total === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Needs Your Attention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {pending_reviews.length > 0 && (
          <Button
            variant="outline"
            className="w-full justify-start"
            render={<Link href="/faculty/questions" />}
            nativeButton={false}
          >
            <ListChecks /> Questions awaiting your review
            <Badge variant="secondary" className="ml-auto">
              {pending_reviews.length}
            </Badge>
          </Button>
        )}
        {pending_evaluations.length > 0 && (
          <Button
            variant="outline"
            className="w-full justify-start"
            render={<Link href="/faculty/evaluation-workspace" />}
            nativeButton={false}
          >
            <ClipboardCheck /> Evaluations awaiting your marks
            <Badge variant="secondary" className="ml-auto">
              {pending_evaluations.length}
            </Badge>
          </Button>
        )}
        {mentorship_attention.length > 0 && (
          <Button
            variant="outline"
            className="w-full justify-start"
            render={<Link href="/faculty/mentorship" />}
            nativeButton={false}
          >
            <Users /> Mentorships awaiting your action
            <Badge variant="secondary" className="ml-auto">
              {mentorship_attention.length}
            </Badge>
          </Button>
        )}
        {pending_reconciliations.length > 0 && (
          <Button
            variant="outline"
            className="w-full justify-start"
            render={<Link href="/faculty/reconciliation" />}
            nativeButton={false}
          >
            <ShieldAlert /> Evaluations requiring reconciliation
            <Badge variant="secondary" className="ml-auto">
              {pending_reconciliations.length}
            </Badge>
          </Button>
        )}
      </CardContent>
    </Card>
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

function DashboardSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2" aria-busy="true" aria-label="Loading dashboard">
      {[0, 1].map((i) => (
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
