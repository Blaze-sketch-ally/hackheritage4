"use client";

import { useEffect, useState } from "react";
import {
  Award,
  Briefcase,
  ClipboardCheck,
  GraduationCap,
  Target,
  TrendingUp,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";
import { getSkillGap } from "@/lib/student/skill-gap";
import { listMyApplications } from "@/lib/student/opportunities";
import { listMyLearningProgress } from "@/lib/student/learning";
import { getAttemptHistory } from "@/lib/student/assessment";
import {
  summarizeApplications,
  summarizeAssessments,
  summarizeLearning,
  toReadinessDisplay,
  type SkillsSummary,
} from "@/lib/student/dashboard";

type SectionState<T> = { status: "ok"; data: T } | { status: "error" };

interface Loaded {
  readiness: SectionState<ReturnType<typeof toReadinessDisplay>>;
  applications: SectionState<ReturnType<typeof summarizeApplications>>;
  learning: SectionState<ReturnType<typeof summarizeLearning>>;
  assessments: SectionState<ReturnType<typeof summarizeAssessments>>;
}

async function loadSection<T>(fn: () => Promise<T>): Promise<SectionState<T>> {
  try {
    return { status: "ok", data: await fn() };
  } catch {
    // Any failure — including an expired session (401) — degrades just this
    // one KPI to an honest "Unavailable". It never takes the page down and
    // never leaves the row stuck on skeletons. Matches the catch-all error
    // handling in SkillGapView / LearningBrowseView.
    return { status: "error" };
  }
}

/**
 * The "at a glance" KPI row. Every value is real:
 *  - Skills:            the student's own student_skills (passed in, no fetch)
 *  - Career Readiness:  GET /api/v1/skill-gap  (canonical engine's readiness_percentage)
 *  - Learning:          GET /api/v1/student/learning/progress
 *  - Applications:      GET /api/v1/student/applications
 *  - Assessments:       GET /api/v1/attempts
 *
 * No fabricated percentages, no demo numbers. A failed section shows an
 * honest "Unavailable" rather than a placeholder value.
 */
export function DashboardKpis({ skills }: { skills: SkillsSummary }) {
  const [state, setState] = useState<Loaded | "loading">("loading");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [readiness, applications, learning, assessments] = await Promise.all([
        loadSection(async () => toReadinessDisplay(await getSkillGap())),
        loadSection(async () => summarizeApplications((await listMyApplications()).applications)),
        loadSection(async () => summarizeLearning((await listMyLearningProgress()).progress)),
        loadSection(async () => summarizeAssessments(await getAttemptHistory())),
      ]);
      if (!cancelled) setState({ readiness, applications, learning, assessments });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const skillsHelper =
    skills.total === 0
      ? "Add your skills"
      : `${skills.verified} verified · ${skills.byLevel.Advanced + skills.byLevel.Expert} advanced+`;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <StatCard
        label="Skills Tracked"
        value={String(skills.total)}
        helperText={skillsHelper}
        icon={Target}
        accent="indigo"
      />

      {state === "loading" ? (
        <>
          <KpiSkeleton />
          <KpiSkeleton />
          <KpiSkeleton />
          <KpiSkeleton />
        </>
      ) : (
        <>
          <ReadinessCard section={state.readiness} />
          <LearningCard section={state.learning} />
          <ApplicationsCard section={state.applications} />
          <AssessmentsCard section={state.assessments} />
        </>
      )}
    </div>
  );
}

function ReadinessCard({ section }: { section: Loaded["readiness"] }) {
  if (section.status === "error") {
    return <StatCard label="Career Readiness" value="Unavailable" icon={TrendingUp} accent="violet" />;
  }
  const r = section.data;
  if (r.mode === "PERSONAL") {
    return (
      <StatCard
        label="Career Readiness"
        value="Not set"
        helperText="Choose a target role"
        icon={TrendingUp}
        accent="violet"
      />
    );
  }
  return (
    <StatCard
      label="Career Readiness"
      value={`${r.readinessPercentage}%`}
      helperText={`${r.matched} matched · ${r.missing} missing`}
      icon={TrendingUp}
      accent="violet"
    />
  );
}

function LearningCard({ section }: { section: Loaded["learning"] }) {
  if (section.status === "error") {
    return <StatCard label="Learning" value="Unavailable" icon={GraduationCap} accent="blue" />;
  }
  const l = section.data;
  return (
    <StatCard
      label="Courses Completed"
      value={String(l.completed)}
      helperText={
        l.total === 0
          ? "Start a course"
          : `${l.inProgress} in progress · ${l.saved} saved`
      }
      icon={GraduationCap}
      accent="blue"
    />
  );
}

function ApplicationsCard({ section }: { section: Loaded["applications"] }) {
  if (section.status === "error") {
    return <StatCard label="Applications" value="Unavailable" icon={Briefcase} accent="amber" />;
  }
  const a = section.data;
  return (
    <StatCard
      label="Applications"
      value={String(a.total)}
      helperText={
        a.total === 0 ? "No applications yet" : `${a.active} active · ${a.selected} selected`
      }
      icon={Briefcase}
      accent="amber"
    />
  );
}

function AssessmentsCard({ section }: { section: Loaded["assessments"] }) {
  if (section.status === "error") {
    return <StatCard label="Assessments" value="Unavailable" icon={ClipboardCheck} accent="emerald" />;
  }
  const s = section.data;
  return (
    <StatCard
      label="Assessments Taken"
      value={String(s.completed)}
      helperText={
        s.completed === 0
          ? "None completed yet"
          : `${s.passed} passed · ${s.skillsVerified} skills verified`
      }
      icon={Award}
      accent="emerald"
    />
  );
}

function KpiSkeleton() {
  return (
    <Card aria-hidden="true">
      <CardContent className="flex items-start justify-between gap-3">
        <div className="w-full space-y-2">
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
          <div className="h-6 w-14 animate-pulse rounded bg-muted" />
          <div className="h-3 w-24 animate-pulse rounded bg-muted" />
        </div>
        <span className="size-9 shrink-0 animate-pulse rounded-lg bg-muted" />
      </CardContent>
    </Card>
  );
}
