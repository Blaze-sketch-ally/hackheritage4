"use client";

import { cn } from "@/lib/utils";
import {
  APPLICATION_STATUS_LABELS,
  RECRUITMENT_EXITS,
  RECRUITMENT_PIPELINE,
  type ApplicationStatus,
  type ApplicationSummary,
} from "@/types/application";

/** Deterministic recruitment funnel — count per pipeline stage with a
 * proportional bar. No AI, no analytics: just the current application
 * statuses. Stages are clickable when `onStageClick` is given (used to
 * drive the applicant table's status filter). */
export function RecruitmentFunnel({
  summary,
  activeStatus,
  onStageClick,
}: {
  summary: ApplicationSummary;
  activeStatus?: ApplicationStatus | "all";
  onStageClick?: (status: ApplicationStatus) => void;
}) {
  const pipelineMax = Math.max(
    1,
    ...RECRUITMENT_PIPELINE.map((s) => summary.counts[s] ?? 0),
  );
  const hasExits = RECRUITMENT_EXITS.some((s) => (summary.counts[s] ?? 0) > 0);

  return (
    <section
      aria-label="Recruitment pipeline"
      className="space-y-3 rounded-xl bg-card p-4 ring-1 ring-foreground/10"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Recruitment pipeline</h2>
        <span className="text-xs text-muted-foreground">
          {`${summary.total} application${summary.total === 1 ? "" : "s"}`}
        </span>
      </div>

      <ul className="space-y-1.5">
        {RECRUITMENT_PIPELINE.map((status) => {
          const count = summary.counts[status] ?? 0;
          const pct = Math.round((count / pipelineMax) * 100);
          const active = activeStatus === status;
          return (
            <li key={status}>
              <button
                type="button"
                disabled={!onStageClick}
                onClick={() => onStageClick?.(status)}
                aria-pressed={onStageClick ? active : undefined}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors",
                  onStageClick ? "hover:bg-muted" : "cursor-default",
                  active && "bg-indigo-500/10",
                )}
              >
                <span className="w-32 shrink-0 text-xs font-medium text-muted-foreground">
                  {APPLICATION_STATUS_LABELS[status]}
                </span>
                <span className="relative h-5 flex-1 overflow-hidden rounded bg-muted">
                  <span
                    className="absolute inset-y-0 left-0 rounded bg-indigo-500/70"
                    style={{ width: `${pct}%` }}
                  />
                </span>
                <span className="w-8 shrink-0 text-right text-sm font-semibold tabular-nums">
                  {count}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      {hasExits ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1 border-t pt-2 text-xs text-muted-foreground">
          {RECRUITMENT_EXITS.map((status) => (
            <span key={status}>
              {`${APPLICATION_STATUS_LABELS[status]}: `}
              <b className="text-foreground tabular-nums">{summary.counts[status] ?? 0}</b>
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}
