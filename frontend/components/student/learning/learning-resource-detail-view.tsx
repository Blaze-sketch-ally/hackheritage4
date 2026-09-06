"use client";

import { useEffect, useState } from "react";
import { AlertCircle, ArrowUpRight, Clock, GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LearningProgressBadge } from "@/components/student/learning/learning-progress-badge";
import { LearningProgressControls } from "@/components/student/learning/learning-progress-controls";
import { formatMinutes } from "@/components/student/learning/learning-resource-card";
import { ApiError } from "@/lib/api";
import { getLearningResource } from "@/lib/student/learning";
import {
  resourceTypeLabel,
  type LearningResourceDetail,
  type ProgressUpdateResponse,
} from "@/types/student-learning";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; resource: LearningResourceDetail };

/** Renders one learning resource from GET
 * /api/v1/student/learning/resources/{id}. The resource URL opens in a
 * new tab with rel="noopener noreferrer" -- never iframed. */
export function LearningResourceDetailView({ resourceId }: { resourceId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const resource = await getLearningResource(resourceId);
        if (cancelled) return;
        setState({ status: "ready", resource });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError ? err : new ApiError(0, "Could not load this learning resource."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [resourceId, reloadKey]);

  function handleProgressUpdated(result: ProgressUpdateResponse) {
    setState((prev) =>
      prev.status === "ready"
        ? {
            ...prev,
            resource: {
              ...prev.resource,
              progress: {
                status: result.status,
                started_at: result.started_at,
                completed_at: result.completed_at,
                updated_at: result.updated_at,
              },
            },
          }
        : prev,
    );
  }

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading learning resource">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    const notFound = state.error.status === 404;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {notFound
                ? "This learning resource is not available."
                : "Could not load this learning resource."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {!notFound && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { resource } = state;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary">{resourceTypeLabel(resource.resource_type)}</Badge>
            {resource.difficulty && <Badge variant="outline">{resource.difficulty}</Badge>}
            <LearningProgressBadge status={resource.progress?.status} />
          </div>
          <CardTitle className="text-xl">{resource.title}</CardTitle>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {resource.provider && <span>{resource.provider}</span>}
            {resource.estimated_minutes != null && (
              <span className="flex items-center gap-1">
                <Clock className="size-3.5" aria-hidden="true" />
                {formatMinutes(resource.estimated_minutes)}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {resource.description && (
            <p className="text-sm whitespace-pre-wrap text-muted-foreground">
              {resource.description}
            </p>
          )}

          {resource.skills.length > 0 && (
            <div>
              <h3 className="text-sm font-medium">Skills this covers</h3>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {resource.skills.map((skill) => (
                  <Badge key={skill.skill_id} variant="outline" className="gap-1">
                    <GraduationCap className="size-3" aria-hidden="true" />
                    {skill.skill_name}
                    {skill.target_level ? ` · ${skill.target_level}` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <Button
            render={
              <a href={resource.url} target="_blank" rel="noopener noreferrer">
                Open resource <ArrowUpRight className="size-3.5" />
              </a>
            }
            nativeButton={false}
          />

          <LearningProgressControls
            resourceId={resource.id}
            progress={resource.progress}
            onUpdated={handleProgressUpdated}
          />

          {resource.progress && (
            <ProgressTimestamps
              startedAt={resource.progress.started_at}
              completedAt={resource.progress.completed_at}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ProgressTimestamps({
  startedAt,
  completedAt,
}: {
  startedAt: string | null;
  completedAt: string | null;
}) {
  if (!startedAt && !completedAt) return null;
  return (
    <p className="text-xs text-muted-foreground">
      {startedAt && <>Started {new Date(startedAt).toLocaleDateString()}</>}
      {startedAt && completedAt && " · "}
      {completedAt && <>Completed {new Date(completedAt).toLocaleDateString()}</>}
    </p>
  );
}
