"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BadgeCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getSkillGapDetail } from "@/lib/institution/skill-gaps";
import { cn } from "@/lib/utils";
import {
  APPLICATION_STATUS_LABELS,
  MATCH_RECOMMENDATION_LABELS,
  OPPORTUNITY_TYPE_LABELS,
  type MatchRecommendation,
  type MatchSkill,
} from "@/types/application";
import { SKILL_IMPORTANCE_LABELS } from "@/types/skill-requirement";
import type { SkillGapDetail as SkillGapDetailData, StudentSkillEntry } from "@/types/institution-skill-gap";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; detail: SkillGapDetailData };

const RECOMMENDATION_CLASS: Record<MatchRecommendation, string> = {
  STRONG: "bg-green-600/10 text-green-700 dark:text-green-400",
  GOOD: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  PARTIAL: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  LOW: "bg-muted text-muted-foreground",
};

function importanceLabel(value: string): string {
  return SKILL_IMPORTANCE_LABELS[value as keyof typeof SKILL_IMPORTANCE_LABELS] ?? value;
}

function SkillRow({ skill }: { skill: MatchSkill }) {
  return (
    <li className="flex flex-col gap-0.5 rounded-lg border px-2.5 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
      <span className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium">{skill.skill_name}</span>
        <Badge variant="outline" className="font-normal">
          {importanceLabel(skill.importance)}
        </Badge>
        {skill.candidate_has ? (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-xs",
              skill.candidate_verified ? "text-green-700 dark:text-green-400" : "text-muted-foreground",
            )}
          >
            {skill.candidate_verified ? (
              <>
                <BadgeCheck className="size-3.5" aria-hidden="true" /> Verified
              </>
            ) : (
              "Self-reported"
            )}
          </span>
        ) : null}
      </span>
      <span className="text-xs text-muted-foreground">
        Requires {skill.required_level}
        {skill.candidate_has ? ` · student declares ${skill.candidate_level}` : " · not in student's skill list"}
      </span>
    </li>
  );
}

function SkillGroup({ title, skills }: { title: string; skills: MatchSkill[] }) {
  if (skills.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
        {title} ({skills.length})
      </p>
      <ul className="space-y-1.5">
        {skills.map((skill) => (
          <SkillRow key={skill.skill_id} skill={skill} />
        ))}
      </ul>
    </div>
  );
}

function StudentSkillList({ skills }: { skills: StudentSkillEntry[] }) {
  if (skills.length === 0) {
    return <p className="text-sm text-muted-foreground">This student has not recorded any skills yet.</p>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {skills.map((skill) => (
        <li key={skill.skill_name}>
          <Badge variant="outline" className="gap-1 font-normal">
            {skill.skill_name}
            <span className="text-muted-foreground">· {skill.proficiency_level}</span>
            {skill.is_verified ? <BadgeCheck className="size-3 text-green-600 dark:text-green-400" aria-hidden="true" /> : null}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

export function SkillGapDetail({ applicationId }: { applicationId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getSkillGapDetail(applicationId)
      .then((detail) => {
        if (!cancelled) setState({ status: "ready", detail });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this application's skill gap."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, reloadKey]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link
        href="/institution/skill-gaps"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden="true" /> Back to skill gap analysis
      </Link>

      {state.status === "loading" ? <Loading label="Loading skill gap…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      ) : null}

      {state.status === "ready" ? <ReadyView detail={state.detail} /> : null}
    </div>
  );
}

function ReadyView({ detail }: { detail: SkillGapDetailData }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{detail.full_name ?? "Unknown student"}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {detail.company_name ?? "Unknown company"} · {detail.opportunity_title ?? "Untitled posting"} ·{" "}
            {OPPORTUNITY_TYPE_LABELS[detail.opportunity_type]}
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Application Status:</span>
            <Badge variant="outline">{APPLICATION_STATUS_LABELS[detail.status]}</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Skill Match</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {detail.required_count === 0 ? (
            <p className="text-sm text-muted-foreground">
              This opportunity has no required skills on file, so a match cannot be calculated.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-3xl font-semibold tabular-nums">{detail.score}</span>
                  <span className="text-sm text-muted-foreground">/ 100</span>
                </div>
                <Badge variant="ghost" className={RECOMMENDATION_CLASS[detail.recommendation]}>
                  {MATCH_RECOMMENDATION_LABELS[detail.recommendation]}
                </Badge>
              </div>

              <div
                className="h-2 w-full overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-valuenow={detail.score}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Skill match score ${detail.score} out of 100`}
              >
                <div className="h-full rounded-full bg-indigo-500" style={{ width: `${detail.score}%` }} />
              </div>

              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted-foreground">Coverage</dt>
                  <dd className="text-sm font-medium">{detail.skill_coverage} skills</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Matched</dt>
                  <dd className="text-sm font-medium tabular-nums">{detail.matched_count}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Needs improvement</dt>
                  <dd className="text-sm font-medium tabular-nums">{detail.needs_improvement_count}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Missing</dt>
                  <dd className="text-sm font-medium tabular-nums">{detail.missing_count}</dd>
                </div>
              </dl>

              <div className="space-y-3">
                <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                  Required Skills
                </p>
                <div className="space-y-3">
                  <SkillGroup title="Matched" skills={detail.matched_skills} />
                  <SkillGroup title="Needs improvement" skills={detail.needs_improvement_skills} />
                  <SkillGroup title="Missing" skills={detail.missing_skills} />
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                Advisory only. This compares the student&apos;s declared proficiency against the skills this
                opportunity requires — it is not a hiring decision.
              </p>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Student Skills</CardTitle>
        </CardHeader>
        <CardContent>
          <StudentSkillList skills={detail.student_skills} />
        </CardContent>
      </Card>
    </>
  );
}
