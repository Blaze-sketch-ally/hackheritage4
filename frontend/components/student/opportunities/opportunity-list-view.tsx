"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Briefcase, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { listOpportunities } from "@/lib/student/opportunities";
import { OpportunityCard } from "@/components/student/opportunities/opportunity-card";
import type { SourceType, StudentOpportunitySummary } from "@/types/student-opportunity";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; opportunities: StudentOpportunitySummary[] };

const NOUN: Record<SourceType, string> = { INTERNSHIP: "internships", JOB: "jobs" };

/** GET /api/v1/student/opportunities via the FastAPI bridge. Each route
 * (/student/internships, /student/jobs) passes its own `sourceType` and
 * `detailBasePath` -- this is one implementation, not a per-type
 * duplicate. */
export function OpportunityListView({
  sourceType,
  detailBasePath,
}: {
  sourceType: SourceType;
  detailBasePath: string;
}) {
  const [search, setSearch] = useState("");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { opportunities } = await listOpportunities({ sourceType });
        if (cancelled) return;
        setState({ status: "ready", opportunities });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, `Could not load ${NOUN[sourceType]}.`),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [sourceType, reloadKey]);

  const visible =
    state.status === "ready"
      ? state.opportunities.filter((o) =>
          search.trim() ? o.title.toLowerCase().includes(search.trim().toLowerCase()) : true,
        )
      : [];

  return (
    <div className="flex flex-col gap-4">
      <Input
        type="search"
        aria-label={`Search ${NOUN[sourceType]}`}
        placeholder={`Search ${NOUN[sourceType]} by title...`}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {state.status === "loading" && <OpportunityListSkeleton />}

      {state.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <div>
              <p className="font-medium">Could not load {NOUN[sourceType]}.</p>
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
            <Briefcase className="size-8" />
            <p className="font-medium text-foreground">
              {state.opportunities.length === 0
                ? `No ${NOUN[sourceType]} available right now`
                : `No ${NOUN[sourceType]} match "${search.trim()}"`}
            </p>
            <p className="text-sm">Check back later — new postings are added periodically.</p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && visible.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((opportunity) => (
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
    <div
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-busy="true"
      aria-label="Loading opportunities"
    >
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
