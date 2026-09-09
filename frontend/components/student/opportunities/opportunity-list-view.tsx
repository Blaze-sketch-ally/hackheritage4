"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, Briefcase, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { listOpportunities } from "@/lib/student/opportunities";
import { OpportunityCard } from "@/components/student/opportunities/opportunity-card";
import {
  OpportunityFilters,
  opportunityFiltersFromParams,
  opportunityFiltersNarrow,
  opportunityFiltersToApiParams,
  opportunityFiltersToQuery,
  type OpportunityFilterState,
} from "@/components/student/opportunities/opportunity-filters";
import type { SourceType, StudentOpportunitySummary } from "@/types/student-opportunity";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; opportunities: StudentOpportunitySummary[] };

const NOUN: Record<SourceType, string> = { INTERNSHIP: "internships", JOB: "jobs" };
const SEARCH_DEBOUNCE_MS = 300;

/** GET /api/v1/student/opportunities via the FastAPI bridge. Each route
 * (/student/internships, /student/jobs) passes its own `sourceType` and
 * `detailBasePath` -- one implementation, not a per-type duplicate.
 *
 * The URL query string is the single source of truth for the active
 * filters/sort: it is read on mount and after every back/forward, and
 * every filter change writes to it (via `router.replace`, so filtering
 * does not flood the history stack). Search is mirrored locally so typing
 * stays responsive, then debounced into the URL. All filtering and
 * sorting happens server-side — the browser never downloads the full list
 * and filters it. */
export function OpportunityListView({
  sourceType,
  detailBasePath,
}: {
  sourceType: SourceType;
  detailBasePath: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Canonical, committed filter state — derived purely from the URL and
  // sanitized (unknown values snap back to defaults).
  const urlFilters = opportunityFiltersFromParams(
    new URLSearchParams(searchParams.toString()),
    sourceType,
  );
  const { search: urlSearch, workMode: urlWorkMode, minComp: urlMinComp, sort: urlSort } = urlFilters;

  const [searchDraft, setSearchDraft] = useState(urlSearch);
  const [syncedSearch, setSyncedSearch] = useState(urlSearch);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  // Follow the URL's search value whenever it changes from the outside
  // (Reset, browser back/forward, a shared link). This is the React
  // "adjust state while rendering" pattern -- NOT an effect -- so there is
  // no cascading-render lint issue and no extra paint.
  if (urlSearch !== syncedSearch) {
    setSyncedSearch(urlSearch);
    setSearchDraft(urlSearch);
  }

  // What the filter bar renders: URL state, but with the live search draft.
  const filters: OpportunityFilterState = { ...urlFilters, search: searchDraft };

  function commit(next: OpportunityFilterState) {
    const qs = opportunityFiltersToQuery(next, sourceType);
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  function handleFilterChange(next: OpportunityFilterState) {
    setSearchDraft(next.search);
    const selectChanged =
      next.workMode !== urlWorkMode || next.minComp !== urlMinComp || next.sort !== urlSort;
    // A Select change applies immediately (and flushes the current search
    // draft with it). A search-only change is left to the debounce effect.
    if (selectChanged) commit(next);
  }

  function handleReset() {
    setSearchDraft("");
    router.replace(pathname, { scroll: false });
  }

  // Debounced search draft -> URL. Self-terminating: once the URL catches
  // up, `searchDraft === urlSearch` and the effect no-ops.
  useEffect(() => {
    if (searchDraft === urlSearch) return;
    const id = setTimeout(() => {
      const qs = opportunityFiltersToQuery(
        { search: searchDraft, workMode: urlWorkMode, minComp: urlMinComp, sort: urlSort },
        sourceType,
      );
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [searchDraft, urlSearch, urlWorkMode, urlMinComp, urlSort, sourceType, pathname, router]);

  // Fetch whenever the COMMITTED (URL) filter state changes. The previous
  // results stay on screen until the new ones land (no skeleton flash on a
  // filter change) -- only the first mount and an explicit retry show the
  // skeleton, via the initial/`reloadKey` state.
  useEffect(() => {
    let cancelled = false;
    listOpportunities(
      opportunityFiltersToApiParams(
        { search: urlSearch, workMode: urlWorkMode, minComp: urlMinComp, sort: urlSort },
        sourceType,
      ),
    )
      .then(({ opportunities }) => {
        if (!cancelled) setState({ status: "ready", opportunities });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError ? err : new ApiError(0, `Could not load ${NOUN[sourceType]}.`),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [urlSearch, urlWorkMode, urlMinComp, urlSort, sourceType, reloadKey]);

  const filtersNarrow = opportunityFiltersNarrow(urlFilters);

  return (
    <div className="flex flex-col gap-4">
      <OpportunityFilters
        sourceType={sourceType}
        filters={filters}
        onChange={handleFilterChange}
        onReset={handleReset}
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

      {state.status === "ready" && state.opportunities.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <Briefcase className="size-8" />
            {filtersNarrow ? (
              <>
                <p className="font-medium text-foreground">
                  No {NOUN[sourceType]} match your filters
                </p>
                <p className="text-sm">Try removing a filter or widening your search.</p>
                <Button size="sm" variant="outline" className="mt-1" onClick={handleReset}>
                  Reset filters
                </Button>
              </>
            ) : (
              <>
                <p className="font-medium text-foreground">
                  No {NOUN[sourceType]} available right now
                </p>
                <p className="text-sm">Check back later — new postings are added periodically.</p>
              </>
            )}
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
