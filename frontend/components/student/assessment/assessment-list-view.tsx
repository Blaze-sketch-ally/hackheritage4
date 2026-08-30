"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Clock, ListChecks, RefreshCw } from "lucide-react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { listAssessments } from "@/lib/student/assessment";
import { createClient } from "@/lib/supabase/client";
import { fetchActiveSkills, type CatalogSkill } from "@/lib/student/skills";
import type { Assessment } from "@/types/assessment";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; assessments: Assessment[]; skillNames: Map<string, string> };

/** GET /api/v1/assessments via the FastAPI bridge -- the assessment list
 * page's real content. Skill names are resolved via the existing,
 * already-tested lib/student/skills.ts (direct Supabase read of the
 * `skills` catalog), not a new backend endpoint -- the assessment
 * response itself only carries skill_id. */
export function AssessmentListView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [{ assessments }, skills] = await Promise.all([
          listAssessments(),
          fetchActiveSkills(createClient()),
        ]);
        if (cancelled) return;
        const skillNames = new Map<string, string>(
          skills.map((skill: CatalogSkill) => [skill.id, skill.name]),
        );
        setState({ status: "ready", assessments, skillNames });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load assessments."),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return <AssessmentListSkeleton />;
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {state.error.status === 401
                ? "Your session has expired. Please sign in again."
                : "Could not load assessments."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {state.error.status !== 401 && (
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
          )}
        </CardContent>
      </Card>
    );
  }

  const { assessments, skillNames } = state;

  if (assessments.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <ListChecks className="size-8" />
          <p className="font-medium text-foreground">No assessments available right now</p>
          <p className="text-sm">Check back later — new assessments are added periodically.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {assessments.map((assessment) => (
        <AssessmentListCard
          key={assessment.id}
          assessment={assessment}
          skillName={skillNames.get(assessment.skill_id)}
        />
      ))}
    </div>
  );
}

function AssessmentListCard({ assessment, skillName }: { assessment: Assessment; skillName?: string }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          {skillName && <Badge variant="secondary">{skillName}</Badge>}
          <Badge variant="outline">{assessment.difficulty}</Badge>
        </div>
        <CardTitle className="text-base">{assessment.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 text-sm text-muted-foreground">
        {assessment.description && <p className="mb-3">{assessment.description}</p>}
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {assessment.duration_minutes != null && (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" /> {assessment.duration_minutes} min
            </span>
          )}
          {assessment.question_count != null && (
            <span className="flex items-center gap-1">
              <ListChecks className="size-3.5" /> {assessment.question_count} questions
            </span>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          render={<Link href={`/student/assessment/${assessment.id}`} />}
          nativeButton={false}
        >
          Start assessment
        </Button>
      </CardFooter>
    </Card>
  );
}

function AssessmentListSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading assessments">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardHeader>
            <div className="h-4 w-16 rounded bg-muted" />
            <div className="mt-2 h-5 w-3/4 rounded bg-muted" />
          </CardHeader>
          <CardContent>
            <div className="h-3 w-full rounded bg-muted" />
            <div className="mt-2 h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
