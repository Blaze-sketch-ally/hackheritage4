"use client";

import Link from "next/link";
import { AlertCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Current-state summary only -- no history, no trends, no AI. `counts` is
 * a plain tally of whatever statuses the caller's own items currently
 * hold, computed client-side from an already-fetched list. Each module
 * passes its own real status vocabulary (`statusOrder`/`statusLabels`) --
 * this component never assumes a shared lifecycle across modules.
 */
export type ModuleSummaryState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; total: number; counts: Record<string, number> };

export function ModuleSummaryCard({
  title,
  icon: Icon,
  listHref,
  createHref,
  createLabel = "Create",
  statusOrder,
  statusLabels,
  state,
}: {
  title: string;
  icon: LucideIcon;
  listHref: string;
  createHref?: string;
  createLabel?: string;
  statusOrder: readonly string[];
  statusLabels: Record<string, string>;
  state: ModuleSummaryState;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {state.status === "loading" ? (
          <p className="text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </p>
        ) : null}

        {state.status === "error" ? (
          <div className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
            <span>{state.message}</span>
          </div>
        ) : null}

        {state.status === "ready" ? (
          state.total === 0 ? (
            <p className="text-sm text-muted-foreground/70">None yet.</p>
          ) : (
            <>
              <p className="text-2xl font-semibold tabular-nums">{state.total}</p>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {statusOrder
                  .filter((s) => (state.counts[s] ?? 0) > 0)
                  .map((s) => (
                    <span key={s}>
                      {statusLabels[s] ?? s}:{" "}
                      <b className="text-foreground tabular-nums">{state.counts[s]}</b>
                    </span>
                  ))}
              </div>
            </>
          )
        ) : null}

        <div className="flex flex-wrap gap-2 pt-1">
          <Button size="sm" variant="outline" render={<Link href={listHref} />} nativeButton={false}>
            View all
          </Button>
          {createHref ? (
            <Button size="sm" render={<Link href={createHref} />} nativeButton={false}>
              {createLabel}
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
