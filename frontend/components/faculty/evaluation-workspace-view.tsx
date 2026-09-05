"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, ClipboardList, Hourglass, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";
import { EvaluationStatusBadge } from "@/components/faculty/evaluation-status-badge";
import { ApiError } from "@/lib/api";
import { listMyEvaluations } from "@/lib/faculty/evaluations";
import type { EvaluationStatus, EvaluationSummary } from "@/types/evaluation";

/**
 * Phase 2: the real Evaluation Workspace, replacing Phase 1's honest
 * placeholder. Real data only, throughout -- every count/row here comes
 * straight from GET /faculty/evaluations (already scoped to the
 * caller's own ACTIVE assignments by RLS, 046_evaluator_answer_access.sql)
 * -- no fabricated statistics, no mock assignments.
 */

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; evaluations: EvaluationSummary[] };

function actionLabel(status: EvaluationStatus): string {
  switch (status) {
    case "ASSIGNED":
      return "Start Evaluation";
    case "IN_PROGRESS":
      return "Continue";
    case "SUBMITTED":
      return "View";
    case "FINALIZED":
      return "View Result";
  }
}

export function EvaluationWorkspaceView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const evaluations = await listMyEvaluations();
        if (!cancelled) setState({ status: "ready", evaluations });
      } catch (err) {
        if (!cancelled) {
          setState({
            status: "error",
            error: err instanceof ApiError ? err : new ApiError(0, "Could not load your evaluations."),
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return <WorkspaceSkeleton />;
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">Could not load your evaluations.</p>
          <p className="text-sm text-muted-foreground">{state.error.message}</p>
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
    );
  }

  const { evaluations } = state;
  const pending = evaluations.filter((e) => e.status === "ASSIGNED").length;
  const inProgress = evaluations.filter((e) => e.status === "IN_PROGRESS" || e.status === "SUBMITTED").length;
  const completed = evaluations.filter((e) => e.status === "FINALIZED").length;
  const sorted = [...evaluations].sort((a, b) => b.assigned_at.localeCompare(a.assigned_at));

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Pending"
          value={String(pending)}
          icon={ClipboardList}
          accent="amber"
          helperText={pending > 0 ? "Not yet started" : "All caught up"}
          trend={pending > 0 ? "up" : "neutral"}
        />
        <StatCard
          label="In Progress"
          value={String(inProgress)}
          icon={Hourglass}
          accent="indigo"
          helperText="Started or submitted, not yet finalized"
        />
        <StatCard label="Completed" value={String(completed)} icon={CheckCircle2} accent="emerald" helperText="Finalized" trend="up" />
      </div>

      <Card>
        <CardContent className="p-0">
          {sorted.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <p className="font-medium">No evaluations assigned yet.</p>
              <p className="text-sm text-muted-foreground">
                When an assessment is assigned to you, it will appear here.
              </p>
            </div>
          ) : (
            <ul className="divide-y">
              {sorted.map((evaluation) => (
                <li
                  key={evaluation.evaluation_id}
                  className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{evaluation.assessment_title}</p>
                    <p className="text-xs text-muted-foreground">
                      Assigned {new Date(evaluation.assigned_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <EvaluationStatusBadge status={evaluation.status} />
                    <Button
                      size="sm"
                      variant={evaluation.status === "ASSIGNED" ? "default" : "outline"}
                      render={<Link href={`/faculty/evaluation-workspace/${evaluation.evaluation_id}`} />}
                      nativeButton={false}
                    >
                      {actionLabel(evaluation.status)}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function WorkspaceSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-3" aria-busy="true" aria-label="Loading evaluation workspace">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2">
            <div className="h-3 w-20 rounded bg-muted" />
            <div className="h-6 w-12 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
