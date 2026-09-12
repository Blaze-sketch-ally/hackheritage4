"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, Sparkles, Target } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { describeNextAction, getCareerGuidance } from "@/lib/student/career-guidance";
import type { CareerGuidanceResponse } from "@/types/career-guidance";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: CareerGuidanceResponse };

/**
 * Compact dashboard preview of the Phase 6 Career Orchestrator
 * (POST /api/v1/ai/career-guidance). Deliberately small: target role +
 * readiness, one top skill gap, one next action, and a CTA to the full
 * Career page -- never the whole plan. Every number/name here is
 * server-grounded (skill_gap_service / match_service / the specialist
 * agents' own grounding) -- this card never renders raw model text.
 * Self-contained: its own error state never blanks the dashboard.
 */
export function DashboardAiSuggestions() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getCareerGuidance()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-violet-600 dark:text-violet-400" aria-hidden="true" />
          Career Readiness
        </CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" render={<Link href="/student/career" />} nativeButton={false}>
            View plan
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        {state.status === "loading" && (
          <div className="space-y-2" aria-hidden="true">
            {[0, 1].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        )}

        {state.status === "error" && (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Couldn&apos;t load your career readiness.</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          </div>
        )}

        {state.status === "ready" && <ReadyContent data={state.data} />}
      </CardContent>
    </Card>
  );
}

function ReadyContent({ data }: { data: CareerGuidanceResponse }) {
  const { career_summary, priority_skills, next_actions } = data;
  const topSkill = priority_skills[0];
  const topAction = next_actions[0];
  const hasNothingYet = !career_summary.target_role && priority_skills.length === 0;

  if (hasNothingYet) {
    return (
      <div className="flex flex-col items-center gap-2 py-4 text-center">
        <Target className="size-6 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium">Set up your career plan</p>
        <p className="text-xs text-muted-foreground">
          Add skills or pick a target role to get a personalized readiness summary.
        </p>
        <Button
          variant="outline"
          size="sm"
          render={<Link href="/student/career" />}
          nativeButton={false}
        >
          Get started
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">
          {career_summary.target_role ?? "Personal development"}
        </p>
        {career_summary.readiness_score !== null && (
          <Badge variant="outline">{career_summary.readiness_score}% ready</Badge>
        )}
      </div>

      {career_summary.headline && (
        <p className="text-sm text-muted-foreground">{career_summary.headline}</p>
      )}

      {topSkill && (
        <Link
          href="/student/skill-gap"
          className="flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors hover:bg-muted"
        >
          <Target className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">Top skill gap: {topSkill.skill_name}</span>
            <span className="block truncate text-xs text-muted-foreground">{topSkill.reason}</span>
          </span>
          <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        </Link>
      )}

      {topAction && (
        <Link
          href="/student/career"
          className="flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors hover:bg-muted"
        >
          <Sparkles className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate font-medium">{describeNextAction(topAction)}</span>
          <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        </Link>
      )}
    </div>
  );
}
