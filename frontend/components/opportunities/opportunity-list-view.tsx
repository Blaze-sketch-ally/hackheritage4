"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Briefcase, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { listOpportunities } from "@/lib/student/opportunities";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import type { Opportunity, OpportunityType } from "@/types/opportunity";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; opportunities: Opportunity[] };

/** GET /api/v1/opportunities via the FastAPI bridge -- the single list
 * implementation shared by /student/opportunities (all types, with the
 * type toggle below), /student/jobs, and /student/internships (both pass
 * `lockedType` and hide the toggle -- Jobs/Internships are filters over
 * this one component, never a second implementation). `detailBasePath`
 * lets each route link into its own canonical detail path. */
export function OpportunityListView({
  lockedType,
  detailBasePath,
}: {
  lockedType?: OpportunityType;
  detailBasePath: string;
}) {
  const [activeType, setActiveType] = useState<OpportunityType | "ALL">(lockedType ?? "ALL");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  // The transition to "loading" happens in the event handlers below
  // (the type-toggle buttons, the retry button), not here -- setting
  // state synchronously inside an effect body is the
  // react-hooks/set-state-in-effect anti-pattern this codebase has hit
  // before (see docs/PROJECT_CONTEXT.md §16). This effect only performs
  // the fetch itself.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { opportunities } = await listOpportunities(activeType === "ALL" ? undefined : activeType);
        if (cancelled) return;
        setState({ status: "ready", opportunities });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load opportunities."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [activeType, reloadKey]);

  return (
    <div className="flex flex-col gap-4">
      {!lockedType && (
        <div className="inline-flex w-fit gap-1 rounded-lg bg-muted p-1">
          {(["ALL", "JOB", "INTERNSHIP"] as const).map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => {
                setState({ status: "loading" });
                setActiveType(type);
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                activeType === type ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {type === "ALL" ? "All" : type === "JOB" ? "Jobs" : "Internships"}
            </button>
          ))}
        </div>
      )}

      {state.status === "loading" && <OpportunityListSkeleton />}

      {state.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <div>
              <p className="font-medium">Could not load opportunities.</p>
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

      {state.status === "ready" && state.opportunities.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <Briefcase className="size-8" />
            <p className="font-medium text-foreground">No opportunities available right now</p>
            <p className="text-sm">Check back later — new postings are added periodically.</p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && state.opportunities.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {state.opportunities.map((opportunity) => (
            <OpportunityCard
              key={opportunity.id}
              opportunity={opportunity}
              href={`${detailBasePath}/${opportunity.id}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function OpportunityListSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading opportunities">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-4">
            <div className="h-4 w-16 rounded bg-muted" />
            <div className="h-5 w-3/4 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
