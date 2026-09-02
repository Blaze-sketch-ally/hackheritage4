"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, BookOpen, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { listLearningResources, listMyLearningProgress } from "@/lib/student/learning";
import { LearningResourceCard } from "@/components/student/learning/learning-resource-card";
import {
  EMPTY_LEARNING_FILTERS,
  LearningResourceFilters,
  learningFiltersActive,
  type LearningFilterState,
} from "@/components/student/learning/learning-resource-filters";
import type {
  LearningDifficulty,
  LearningProgressStatus,
  LearningResource,
  LearningResourceType,
  StudentLearningResource,
} from "@/types/student-learning";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; resources: LearningResource[]; progress: StudentLearningResource[] };

/** GET /api/v1/student/learning/resources + /progress via the FastAPI
 * bridge. Difficulty/type are server-side filters (refetch); the title
 * search is client-side (the backend has no search param). Every value
 * shown comes from the API -- there is no mock course data. */
export function LearningBrowseView() {
  const [filters, setFilters] = useState<LearningFilterState>(EMPTY_LEARNING_FILTERS);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [{ resources }, { progress }] = await Promise.all([
          listLearningResources({
            difficulty:
              filters.difficulty === "all"
                ? undefined
                : (filters.difficulty as LearningDifficulty),
            resourceType:
              filters.resourceType === "all"
                ? undefined
                : (filters.resourceType as LearningResourceType),
          }),
          listMyLearningProgress(),
        ]);
        if (cancelled) return;
        setState({ status: "ready", resources, progress });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError ? err : new ApiError(0, "Could not load learning resources."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [filters.difficulty, filters.resourceType, reloadKey]);

  const summary = useMemo(() => {
    if (state.status !== "ready") return null;
    const counts: Record<LearningProgressStatus, number> = {
      SAVED: 0,
      IN_PROGRESS: 0,
      COMPLETED: 0,
    };
    for (const row of state.progress) {
      if (row.status in counts) counts[row.status] += 1;
    }
    return counts;
  }, [state]);

  const visible = useMemo(() => {
    if (state.status !== "ready") return [];
    const q = filters.search.trim().toLowerCase();
    if (!q) return state.resources;
    return state.resources.filter(
      (r) =>
        r.title.toLowerCase().includes(q) ||
        (r.provider ?? "").toLowerCase().includes(q),
    );
  }, [state, filters.search]);

  return (
    <div className="flex flex-col gap-4">
      {summary && (
        <div className="grid grid-cols-3 gap-3">
          <SummaryChip label="Saved" value={summary.SAVED} />
          <SummaryChip label="In progress" value={summary.IN_PROGRESS} />
          <SummaryChip label="Completed" value={summary.COMPLETED} />
        </div>
      )}

      <LearningResourceFilters filters={filters} onChange={setFilters} />

      {state.status === "loading" && <LearningListSkeleton />}

      {state.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <div>
              <p className="font-medium">Could not load learning resources.</p>
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
      )}

      {state.status === "ready" && visible.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <BookOpen className="size-8" />
            <p className="font-medium text-foreground">
              {state.resources.length === 0
                ? "No learning resources available right now"
                : "No resources match your filters"}
            </p>
            <p className="text-sm">
              {learningFiltersActive(filters)
                ? "Try clearing a filter."
                : "Check back later — the catalog is added to periodically."}
            </p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && visible.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((resource) => (
            <LearningResourceCard key={resource.id} resource={resource} />
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryChip({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="py-3 text-center">
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

function LearningListSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-busy="true"
      aria-label="Loading learning resources"
    >
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-4">
            <div className="h-4 w-20 rounded bg-muted" />
            <div className="h-5 w-3/4 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
