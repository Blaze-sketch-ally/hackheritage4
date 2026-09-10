"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Briefcase,
  ClipboardCheck,
  Compass,
  GraduationCap,
  Target,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { ReadinessSummary } from "@/components/student/skill-gap/readiness-summary";
import { SkillGapList } from "@/components/student/skill-gap/skill-gap-list";
import { TargetRoleSelector } from "@/components/student/skill-gap/target-role-selector";
import { ApiError } from "@/lib/api";
import {
  clearTargetJobRole,
  getSkillGap,
  listJobRoles,
  setTargetJobRole,
} from "@/lib/student/skill-gap";
import type { JobRole, SkillGapAnalysis, SkillGapJobRoleAnalysis } from "@/types/skill-gap";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; analysis: SkillGapAnalysis; jobRoles: JobRole[] };

export function CareerView({ careerGoals }: { careerGoals: string | null }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSkillGap(), listJobRoles()])
      .then(([analysis, { job_roles }]) => {
        if (!cancelled) setState({ status: "ready", analysis, jobRoles: job_roles });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load your career workspace.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function refreshAnalysis() {
    try {
      const analysis = await getSkillGap();
      setState((s) => (s.status === "ready" ? { ...s, analysis } : s));
    } catch {
      /* keep the last-good analysis; the selector still updated */
    }
  }

  async function handleSelectRole(jobRoleId: string) {
    setSaving(true);
    setActionError(null);
    try {
      await setTargetJobRole(jobRoleId);
      await refreshAnalysis();
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not set your target role. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleClearRole() {
    setSaving(true);
    setActionError(null);
    try {
      await clearTargetJobRole();
      await refreshAnalysis();
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not clear your target role. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Career</h1>
        <p className="text-sm text-muted-foreground">
          Your career direction, based on your target role and canonical Skill Gap.
        </p>
      </div>

      <CareerDirectionCard careerGoals={careerGoals} />

      {state.status === "loading" && <CareerSkeleton />}

      {state.status === "error" && (
        <ErrorState
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {state.status === "ready" && (
        <>
          {actionError && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {actionError}
            </p>
          )}
          {state.analysis.mode === "JOB_ROLE" ? (
            <JobRoleCareer
              analysis={state.analysis}
              jobRoles={state.jobRoles}
              saving={saving}
              onSelectRole={handleSelectRole}
              onClearRole={handleClearRole}
            />
          ) : (
            <NoTargetRole
              jobRoles={state.jobRoles}
              saving={saving}
              onSelectRole={handleSelectRole}
            />
          )}
        </>
      )}
    </div>
  );
}

// ---- Career Direction (always shown) ----

function CareerDirectionCard({ careerGoals }: { careerGoals: string | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Compass className="size-4 text-muted-foreground" aria-hidden="true" />
          Career Direction
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {careerGoals ? (
          <p className="text-sm whitespace-pre-wrap">{careerGoals}</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            You haven&apos;t set any career goals yet.
          </p>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-fit px-0 text-muted-foreground"
          render={<Link href="/student/settings" />}
          nativeButton={false}
        >
          {careerGoals ? "Edit career goals" : "Add career goals"} <ArrowUpRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

// ---- No target role ----

function NoTargetRole({
  jobRoles,
  saving,
  onSelectRole,
}: {
  jobRoles: JobRole[];
  saving: boolean;
  onSelectRole: (id: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Target className="size-4 text-muted-foreground" aria-hidden="true" />
          Target Job Role
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          No target job role selected yet. Choosing one unlocks a career‑readiness figure, a
          role‑specific skill gap, and the assessments that verify the right skills.
        </p>
        <TargetRoleSelector
          jobRoles={jobRoles}
          selectedJobRoleId={null}
          saving={saving}
          onSelect={onSelectRole}
          onClear={() => {}}
        />
        <Button
          variant="ghost"
          size="sm"
          className="w-fit px-0 text-muted-foreground"
          render={<Link href="/student/skill-gap" />}
          nativeButton={false}
        >
          Open the full Skill Gap page <ArrowUpRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

// ---- With a target role ----

function JobRoleCareer({
  analysis,
  jobRoles,
  saving,
  onSelectRole,
  onClearRole,
}: {
  analysis: SkillGapJobRoleAnalysis;
  jobRoles: JobRole[];
  saving: boolean;
  onSelectRole: (id: string) => void;
  onClearRole: () => void;
}) {
  const role = analysis.job_role;
  const toStrengthen = analysis.skills
    .filter((s) => s.status !== "MATCHED")
    .slice()
    .sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority));
  const withAssessment = analysis.skills.filter((s) => s.assessment_available && s.assessment_id);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Target className="size-4 text-muted-foreground" aria-hidden="true" />
            Target Job Role
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-semibold">{role.name}</p>
            {role.category && <Badge variant="outline">{role.category}</Badge>}
          </div>
          {role.description && (
            <p className="text-sm whitespace-pre-wrap text-muted-foreground">{role.description}</p>
          )}
          <TargetRoleSelector
            jobRoles={jobRoles}
            selectedJobRoleId={role.id}
            saving={saving}
            onSelect={onSelectRole}
            onClear={onClearRole}
          />
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" />
          Skill Gap
        </h2>
        <ReadinessSummary
          readinessPercentage={analysis.readiness_percentage}
          summary={analysis.summary}
        />
        <p className="text-xs text-muted-foreground">
          These numbers come straight from the Skill Gap engine — see the{" "}
          <Link href="/student/skill-gap" className="underline">
            full Skill Gap page
          </Link>
          .
        </p>
      </div>

      <div className="space-y-3">
        <h2 className="text-base font-semibold">Skills to Strengthen</h2>
        {toStrengthen.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Every skill this role needs is already matched. Nice work.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {toStrengthen.map((s) => (
              <Badge
                key={s.skill_id}
                variant="outline"
                className={priorityClass(s.priority)}
                title={`${s.status} · ${s.priority} priority`}
              >
                {s.skill_name}
                <span className="ml-1 opacity-70">
                  {s.current_level ?? "Not added"} → {s.required_level}
                </span>
              </Badge>
            ))}
          </div>
        )}
        <SkillGapList skills={analysis.skills} />
      </div>

      <div className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <ClipboardCheck className="size-4 text-muted-foreground" aria-hidden="true" />
          Relevant Assessments
        </h2>
        {withAssessment.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No relevant assessments available yet for this role&apos;s skills.
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {withAssessment.map((s) => (
              <Card key={s.skill_id}>
                <CardContent className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{s.skill_name}</p>
                    <p className="text-xs text-muted-foreground">Target level: {s.required_level}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    render={<Link href={`/student/assessment/${s.assessment_id}`} />}
                    nativeButton={false}
                  >
                    Take assessment
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <Briefcase className="size-4 text-muted-foreground" aria-hidden="true" />
          Relevant Opportunities
        </h2>
        <p className="text-sm text-muted-foreground">
          Browse published internships and jobs — each one shows your real skill match on its detail
          page. A ranked, role‑matched feed is coming in a later phase.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            render={<Link href="/student/internships" />}
            nativeButton={false}
          >
            <GraduationCap className="size-4" /> Browse internships
          </Button>
          <Button
            variant="outline"
            size="sm"
            render={<Link href="/student/jobs" />}
            nativeButton={false}
          >
            <Briefcase className="size-4" /> Browse jobs
          </Button>
        </div>
      </div>
    </div>
  );
}

function priorityRank(p: "HIGH" | "MEDIUM" | "LOW"): number {
  return { HIGH: 0, MEDIUM: 1, LOW: 2 }[p];
}
function priorityClass(p: "HIGH" | "MEDIUM" | "LOW"): string {
  return {
    HIGH: "border-destructive/30 bg-destructive/10 text-destructive",
    MEDIUM: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    LOW: "border-border text-muted-foreground",
  }[p];
}

function CareerSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-label="Loading career workspace" aria-busy="true">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-4 w-1/3 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
