"use client";

import { useState } from "react";
import { AlertCircle, BadgeCheck, Gauge, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getApplicationMatch } from "@/lib/industry/applications";
import { cn } from "@/lib/utils";
import { SKILL_IMPORTANCE_LABELS } from "@/types/skill-requirement";
import {
  MATCH_RECOMMENDATION_LABELS,
  type ApplicationMatch,
  type MatchRecommendation,
  type MatchSkill,
} from "@/types/application";

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; match: ApplicationMatch };

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
              skill.candidate_verified
                ? "text-green-700 dark:text-green-400"
                : "text-muted-foreground",
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
        Requires {skill.required_level} ·{" "}
        {skill.candidate_has
          ? `candidate declares ${skill.candidate_level}`
          : "candidate has not declared this skill"}
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

function MatchResult({ match, onRecalculate }: { match: ApplicationMatch; onRecalculate: () => void }) {
  if (match.required_count === 0) {
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium">Match unavailable</p>
        <p className="text-sm text-muted-foreground">
          This opportunity has no required skills yet. Add required skills to it to calculate a
          candidate match.
        </p>
        <Button size="sm" variant="outline" onClick={onRecalculate}>
          <RefreshCw className="size-3.5" /> Check again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-baseline gap-1.5">
          <span className="text-3xl font-semibold tabular-nums">{match.score}</span>
          <span className="text-sm text-muted-foreground">/ 100</span>
        </div>
        <Badge variant="ghost" className={RECOMMENDATION_CLASS[match.recommendation]}>
          {MATCH_RECOMMENDATION_LABELS[match.recommendation]}
        </Badge>
      </div>

      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={match.score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Skill match score ${match.score} out of 100`}
      >
        <div
          className="h-full rounded-full bg-indigo-500 transition-all"
          style={{ width: `${match.score}%` }}
        />
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted-foreground">Skill coverage</dt>
          <dd className="text-sm font-medium">{match.skill_coverage} skills</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Matched</dt>
          <dd className="text-sm font-medium tabular-nums">{match.matched_count}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Needs improvement</dt>
          <dd className="text-sm font-medium tabular-nums">{match.needs_improvement_count}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Missing</dt>
          <dd className="text-sm font-medium tabular-nums">{match.missing_count}</dd>
        </div>
      </dl>

      <div className="space-y-3">
        <SkillGroup title="Matched" skills={match.matched_skills} />
        <SkillGroup title="Needs improvement" skills={match.needs_improvement_skills} />
        <SkillGroup title="Missing" skills={match.missing_skills} />
      </div>

      <p className="text-xs text-muted-foreground">
        Advisory only. This compares the candidate&apos;s declared proficiency against the skills this
        opportunity requires — it is not a hiring decision.
      </p>

      <Button size="sm" variant="outline" onClick={onRecalculate}>
        <RefreshCw className="size-3.5" /> Recalculate
      </Button>
    </div>
  );
}

/** Deterministic, advisory skill-match for one application. Never
 * auto-runs — the recruiter clicks "Calculate skill match". The frontend
 * never computes the score; GET /api/v1/applications/{id}/match is the
 * sole source of truth. */
export function MatchScore({ applicationId }: { applicationId: string }) {
  const [state, setState] = useState<LoadState>({ status: "idle" });

  async function calculate() {
    setState({ status: "loading" });
    try {
      const match = await getApplicationMatch(applicationId);
      setState({ status: "ready", match });
    } catch (err) {
      setState({
        status: "error",
        message:
          err instanceof ApiError
            ? err.message
            : "Could not calculate the skill match. Please try again.",
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="size-4 text-muted-foreground" aria-hidden="true" />
          Skill Match
        </CardTitle>
      </CardHeader>
      <CardContent>
        {state.status === "idle" ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Advisory match based on the skills this opportunity requires.
            </p>
            <Button size="sm" onClick={calculate}>
              Calculate skill match
            </Button>
          </div>
        ) : null}

        {state.status === "loading" ? (
          <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground" aria-busy="true">
            <RefreshCw className="size-4 animate-spin" aria-hidden="true" /> Calculating…
          </p>
        ) : null}

        {state.status === "error" ? (
          <div className="flex flex-col items-start gap-3">
            <p className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="size-4 shrink-0" aria-hidden="true" /> {state.message}
            </p>
            <Button size="sm" variant="outline" onClick={calculate}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </div>
        ) : null}

        {state.status === "ready" ? (
          <MatchResult match={state.match} onRecalculate={calculate} />
        ) : null}
      </CardContent>
    </Card>
  );
}
