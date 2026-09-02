"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowUpRight, Clock, GraduationCap, Sparkles, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getRecommendedLearningResources } from "@/lib/student/learning";
import { LearningProgressBadge } from "@/components/student/learning/learning-progress-badge";
import { formatMinutes } from "@/components/student/learning/learning-resource-card";
import {
  resourceTypeLabel,
  type LearningRecommendation,
  type LearningRecommendationListResponse,
} from "@/types/student-learning";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: LearningRecommendationListResponse };

const MODE_SUBTITLE: Record<LearningRecommendationListResponse["mode"], string> = {
  JOB_ROLE:
    "Courses and resources mapped to the skills your target role still needs from you.",
  PERSONAL:
    "Courses and resources mapped to the skills your Skill Gap analysis suggests learning next.",
};

/**
 * GET /api/v1/student/learning/recommended -- learning resources mapped to
 * the student's OWN canonical Skill Gap skills. The gap is computed by the
 * backend (skill_gap_service); this component never recomputes it and only
 * asks for "my" recommendations (no student_id, no skill id sent).
 *
 * This is a self-contained section: it owns its fetch and its error state,
 * so a recommendation failure NEVER breaks the main Learning catalog
 * rendered alongside it on /student/learning.
 */
export function LearningRecommendations() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getRecommendedLearningResources();
        if (cancelled) return;
        setState({ status: "ready", data });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load your skill-gap recommendations."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <section aria-labelledby="learning-recommendations-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
          <h2 id="learning-recommendations-heading" className="text-base font-semibold">
            Recommended for your skill gap
          </h2>
        </div>
        <Button
          variant="ghost"
          size="sm"
          render={<Link href="/student/skill-gap" />}
          nativeButton={false}
        >
          <TrendingUp className="size-3.5" /> View your full Skill Gap
        </Button>
      </div>

      {state.status === "ready" && (
        <p className="text-sm text-muted-foreground">{MODE_SUBTITLE[state.data.mode]}</p>
      )}

      {state.status === "loading" && <RecommendationsSkeleton />}

      {state.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-6 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">
              Couldn&apos;t load your skill-gap recommendations right now.
            </p>
            <p className="text-xs text-muted-foreground">
              The full catalog below is unaffected.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-1"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && state.data.recommendations.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-1 py-6 text-center text-muted-foreground">
            <p className="text-sm font-medium text-foreground">
              No learning resources are currently mapped to your skill gaps.
            </p>
            <p className="text-xs">
              Browse the full catalog below, or check your Skill Gap analysis to see which skills to
              work on.
            </p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && state.data.recommendations.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {state.data.recommendations.map((rec) => (
            <RecommendationCard key={rec.resource.id} recommendation={rec} />
          ))}
        </div>
      )}
    </section>
  );
}

function RecommendationCard({ recommendation }: { recommendation: LearningRecommendation }) {
  const { resource, matched_skills } = recommendation;
  // matched_skills is already priority-ordered by the backend; the first
  // one's reason is the strongest "why this is recommended" line.
  const primaryReason = matched_skills[0]?.reason;

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{resourceTypeLabel(resource.resource_type)}</Badge>
          {resource.difficulty && <Badge variant="outline">{resource.difficulty}</Badge>}
          <LearningProgressBadge status={resource.progress?.status} />
        </div>
        <CardTitle className="text-base">{resource.title}</CardTitle>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {resource.provider && <span>{resource.provider}</span>}
          {resource.estimated_minutes != null && (
            <span className="flex items-center gap-1">
              <Clock className="size-3" aria-hidden="true" />
              {formatMinutes(resource.estimated_minutes)}
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm">
        <div className="flex flex-wrap gap-1">
          {matched_skills.map((skill) => (
            <Badge key={skill.skill_id} variant="outline" className="gap-1 font-normal">
              <GraduationCap className="size-3" aria-hidden="true" />
              {skill.skill_name}
            </Badge>
          ))}
        </div>
        {primaryReason && (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Why: </span>
            {primaryReason}
          </p>
        )}
      </CardContent>
      <CardFooter className="flex-col items-stretch gap-2">
        <Button
          className="w-full"
          render={<Link href={`/student/learning/${resource.id}`} />}
          nativeButton={false}
        >
          View details
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          render={
            <a href={resource.url} target="_blank" rel="noopener noreferrer">
              Open resource <ArrowUpRight className="size-3.5" />
            </a>
          }
          nativeButton={false}
        />
      </CardFooter>
    </Card>
  );
}

function RecommendationsSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-busy="true"
      aria-label="Loading skill-gap recommendations"
    >
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-4">
            <div className="h-4 w-20 rounded bg-muted" />
            <div className="h-5 w-3/4 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
