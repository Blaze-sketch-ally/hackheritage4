"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Briefcase,
  BookOpen,
  ExternalLink,
  FolderKanban,
  GraduationCap,
  Handshake,
  Network,
  Presentation,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { RecruitmentFunnel } from "@/components/industry/recruitment-funnel";
import { ModuleSummaryCard, type ModuleSummaryState } from "@/components/industry/dashboard/module-summary-card";
import { getIndustryProfile } from "@/lib/industry/profile";
import { getApplicationsSummary } from "@/lib/industry/applications";
import { getInternships } from "@/lib/industry/internships";
import { getJobs } from "@/lib/industry/jobs";
import { getProjects } from "@/lib/industry/projects";
import { getTrainings } from "@/lib/industry/training";
import { getWorkshops } from "@/lib/industry/workshops";
import { getMentorshipOpportunities } from "@/lib/industry/mentorship-opportunities";
import { getCollaborations } from "@/lib/industry/collaborations";
import { getIndustryProfileCompletion, type IndustryProfile } from "@/types/industry";
import type { ApplicationSummary } from "@/types/application";
import { INTERNSHIP_STATUSES, INTERNSHIP_STATUS_LABELS } from "@/types/internship";
import { JOB_STATUSES, JOB_STATUS_LABELS } from "@/types/job";
import { PROJECT_STATUSES, PROJECT_STATUS_LABELS } from "@/types/industry-project";
import { TRAINING_STATUSES, TRAINING_STATUS_LABELS } from "@/types/industry-training";
import { WORKSHOP_STATUSES, WORKSHOP_STATUS_LABELS } from "@/types/industry-workshop";
import { MENTORSHIP_STATUSES, MENTORSHIP_STATUS_LABELS } from "@/types/industry-mentorship";
import { COLLABORATION_STATUSES, COLLABORATION_STATUS_LABELS } from "@/types/industry-collaboration";

/**
 * Industry Dashboard -- a READ-ONLY composition layer over already-shipped
 * 10A-10F/Phase 9 functionality. Every data point here is fetched through
 * an existing, already-tested lib function and tallied client-side; there
 * is no new backend endpoint, no new table, and no historical/trend data
 * (that boundary belongs to a future, separate Analytics phase, not this
 * one). Nine independent loads (profile, recruitment summary, 7 modules)
 * so one failing section never blocks the rest of the page -- mirrors the
 * same per-section loading/error pattern every existing list-view in this
 * app already uses, just run in parallel instead of one-per-page.
 */

type ProfileLoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; profile: IndustryProfile };

type SummaryLoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; summary: ApplicationSummary };

function countByStatus(items: { status: string }[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) counts[item.status] = (counts[item.status] ?? 0) + 1;
  return counts;
}

// Stable module-level fetch adapters (not recreated per render) -- each
// just unwraps the module's own existing list response to a bare array.
function fetchInternshipItems() {
  return getInternships().then((r) => r.internships);
}
function fetchJobItems() {
  return getJobs().then((r) => r.jobs);
}
function fetchProjectItems() {
  return getProjects().then((r) => r.projects);
}
function fetchTrainingItems() {
  return getTrainings().then((r) => r.trainings);
}
function fetchWorkshopItems() {
  return getWorkshops().then((r) => r.workshops);
}
function fetchMentorshipItems() {
  return getMentorshipOpportunities().then((r) => r.mentorship_opportunities);
}
function fetchCollaborationItems() {
  return getCollaborations().then((r) => r.collaborations);
}

function useModuleSummary(fetchItems: () => Promise<{ status: string }[]>): ModuleSummaryState {
  const [state, setState] = useState<ModuleSummaryState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchItems()
      .then((items) => {
        if (cancelled) return;
        setState({ status: "ready", total: items.length, counts: countByStatus(items) });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load this data.",
        });
      });
    return () => {
      cancelled = true;
    };
    // fetchItems is always one of the stable module-level functions above
    // -- intentionally runs once on mount only (no polling, no refetch).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return state;
}

export function DashboardView() {
  const [profileState, setProfileState] = useState<ProfileLoadState>({ status: "loading" });
  const [summaryState, setSummaryState] = useState<SummaryLoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getIndustryProfile()
      .then((profile) => {
        if (!cancelled) setProfileState({ status: "ready", profile });
      })
      .catch((err) => {
        if (!cancelled) {
          setProfileState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load your company profile.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getApplicationsSummary()
      .then((summary) => {
        if (!cancelled) setSummaryState({ status: "ready", summary });
      })
      .catch((err) => {
        if (!cancelled) {
          setSummaryState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load your recruitment summary.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const internshipsState = useModuleSummary(fetchInternshipItems);
  const jobsState = useModuleSummary(fetchJobItems);
  const projectsState = useModuleSummary(fetchProjectItems);
  const trainingState = useModuleSummary(fetchTrainingItems);
  const workshopsState = useModuleSummary(fetchWorkshopItems);
  const mentorshipState = useModuleSummary(fetchMentorshipItems);
  const collaborationsState = useModuleSummary(fetchCollaborationItems);

  const completion =
    profileState.status === "ready" ? getIndustryProfileCompletion(profileState.profile) : null;
  const companyName =
    profileState.status === "ready" ? profileState.profile.company_name : null;

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* 1. Welcome / overview */}
      <div>
        <h1 className="text-xl font-semibold">{companyName ? `Welcome, ${companyName}` : "Dashboard"}</h1>
        <p className="text-sm text-muted-foreground">
          A current snapshot of your Industry account — opportunities, collaborations, and recruitment.
        </p>
      </div>

      {/* 2. Company Profile Completion */}
      <Card>
        <CardHeader>
          <CardTitle>Company Profile</CardTitle>
        </CardHeader>
        <CardContent>
          {profileState.status === "loading" ? (
            <p className="text-sm text-muted-foreground" aria-busy="true">
              Loading…
            </p>
          ) : null}

          {profileState.status === "error" ? (
            <div className="flex items-start gap-2 text-sm text-muted-foreground">
              <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
              <span>{profileState.message}</span>
            </div>
          ) : null}

          {profileState.status === "ready" && completion !== null ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex-1 space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Profile completion</span>
                  <span className="font-medium tabular-nums">{completion}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-indigo-500" style={{ width: `${completion}%` }} />
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="shrink-0"
                render={<Link href="/industry/profile" />}
                nativeButton={false}
              >
                Manage Company Profile <ExternalLink className="size-3.5" />
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* 3. Recruitment Pipeline Snapshot */}
      <div>
        {summaryState.status === "loading" ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
              Loading your recruitment summary…
            </CardContent>
          </Card>
        ) : null}

        {summaryState.status === "error" ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
              <AlertCircle className="size-6 text-destructive" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">{summaryState.message}</p>
            </CardContent>
          </Card>
        ) : null}

        {summaryState.status === "ready" ? <RecruitmentFunnel summary={summaryState.summary} /> : null}
      </div>

      {/* 4. Industry Opportunity/Collaboration Module Summary */}
      <div>
        <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
          Your opportunities &amp; collaborations
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <ModuleSummaryCard
            title="Internships"
            icon={GraduationCap}
            listHref="/industry/internships"
            createHref="/industry/internships/create"
            statusOrder={INTERNSHIP_STATUSES}
            statusLabels={INTERNSHIP_STATUS_LABELS}
            state={internshipsState}
          />
          <ModuleSummaryCard
            title="Jobs"
            icon={Briefcase}
            listHref="/industry/jobs"
            createHref="/industry/jobs/create"
            statusOrder={JOB_STATUSES}
            statusLabels={JOB_STATUS_LABELS}
            state={jobsState}
          />
          <ModuleSummaryCard
            title="Projects"
            icon={FolderKanban}
            listHref="/industry/projects"
            createHref="/industry/projects/create"
            statusOrder={PROJECT_STATUSES}
            statusLabels={PROJECT_STATUS_LABELS}
            state={projectsState}
          />
          <ModuleSummaryCard
            title="Training"
            icon={BookOpen}
            listHref="/industry/training"
            createHref="/industry/training/create"
            statusOrder={TRAINING_STATUSES}
            statusLabels={TRAINING_STATUS_LABELS}
            state={trainingState}
          />
          <ModuleSummaryCard
            title="Workshops"
            icon={Presentation}
            listHref="/industry/workshops"
            createHref="/industry/workshops/create"
            statusOrder={WORKSHOP_STATUSES}
            statusLabels={WORKSHOP_STATUS_LABELS}
            state={workshopsState}
          />
          <ModuleSummaryCard
            title="Mentorship"
            icon={Handshake}
            listHref="/industry/mentorship"
            createHref="/industry/mentorship/create"
            statusOrder={MENTORSHIP_STATUSES}
            statusLabels={MENTORSHIP_STATUS_LABELS}
            state={mentorshipState}
          />
          <ModuleSummaryCard
            title="Collaborations"
            icon={Network}
            listHref="/industry/collaborations"
            createHref="/industry/collaborations/create"
            statusOrder={COLLABORATION_STATUSES}
            statusLabels={COLLABORATION_STATUS_LABELS}
            state={collaborationsState}
          />
        </div>
      </div>

      {/* 5. Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" render={<Link href="/industry/internships/create" />} nativeButton={false}>
            Post Internship
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/jobs/create" />} nativeButton={false}>
            Post Job
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/projects/create" />} nativeButton={false}>
            Create Project
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/training/create" />} nativeButton={false}>
            Create Training
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/workshops/create" />} nativeButton={false}>
            Create Workshop
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/mentorship/create" />} nativeButton={false}>
            Create Mentorship
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/collaborations/create" />} nativeButton={false}>
            Propose Collaboration
          </Button>
          <Button size="sm" variant="outline" render={<Link href="/industry/applicants" />} nativeButton={false}>
            View Applicants
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
