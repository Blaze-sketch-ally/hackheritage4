"use client";

import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Filters, type FilterOption } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { WORK_MODES, WORK_MODE_LABELS, type WorkMode } from "@/types/job";
import type { OpportunitySort, SourceType } from "@/types/student-opportunity";

/**
 * The Student opportunity browse filter bar — a presentational, fully
 * controlled component (same shape as
 * components/student/learning/learning-resource-filters.tsx).
 *
 * `OpportunityListView` owns the canonical state (derived from the URL)
 * and the fetching; this component only renders the controls and reports
 * changes. Every filter here is server-side — nothing is filtered in the
 * browser.
 *
 * Sentinel `"all"` = "no filter" (the @base-ui Select reserves the empty
 * string as its placeholder state, so `"all"` is the project convention
 * for an Any/All option — see components/common/filters.tsx call sites).
 */

export interface OpportunityFilterState {
  /** Case-insensitive title search (server-side `search` param). */
  search: string;
  /** `"all"` | `"ONSITE"` | `"REMOTE"` | `"HYBRID"` -> server `work_mode`. */
  workMode: string;
  /** `"all"` or a threshold string ("10000", "500000", …). Maps to
   * `min_stipend` (internships) or `min_salary` (jobs). */
  minComp: string;
  /** `"newest"` (default, never serialized) | `"deadline"`. */
  sort: OpportunitySort;
}

export const EMPTY_OPPORTUNITY_FILTERS: OpportunityFilterState = {
  search: "",
  workMode: "all",
  minComp: "all",
  sort: "newest",
};

/** Minimum-stipend bands for internships (₹ / month). Values are the
 * `min_stipend` integers sent to the API — not opportunity data. */
const STIPEND_OPTIONS: FilterOption[] = [
  { value: "all", label: "Any stipend" },
  { value: "10000", label: "₹10k+ / month" },
  { value: "20000", label: "₹20k+ / month" },
  { value: "30000", label: "₹30k+ / month" },
];

/** Minimum-salary bands for jobs (₹ / year). Values are the `min_salary`
 * integers sent to the API. */
const SALARY_OPTIONS: FilterOption[] = [
  { value: "all", label: "Any salary" },
  { value: "500000", label: "₹5L+" },
  { value: "1000000", label: "₹10L+" },
  { value: "2000000", label: "₹20L+" },
  { value: "3000000", label: "₹30L+" },
];

const STIPEND_VALUES = new Set(STIPEND_OPTIONS.map((o) => o.value).filter((v) => v !== "all"));
const SALARY_VALUES = new Set(SALARY_OPTIONS.map((o) => o.value).filter((v) => v !== "all"));
const WORK_MODE_VALUES = new Set<string>(WORK_MODES);

const WORK_MODE_OPTIONS: FilterOption[] = [
  { value: "all", label: "Any work mode" },
  ...WORK_MODES.map((m) => ({ value: m, label: WORK_MODE_LABELS[m] })),
];

const SORT_OPTIONS: FilterOption[] = [
  { value: "newest", label: "Newest" },
  { value: "deadline", label: "Closing soon" },
];

/** True when ANY control differs from its default (drives the Reset button). */
export function opportunityFiltersActive(f: OpportunityFilterState): boolean {
  return (
    f.search.trim() !== "" ||
    f.workMode !== "all" ||
    f.minComp !== "all" ||
    f.sort !== "newest"
  );
}

/** True when an active filter could hide results (search / work mode /
 * compensation). Sort never changes the count, so it is excluded — this
 * decides the "no match" vs "nothing published" empty state without a
 * second API call. */
export function opportunityFiltersNarrow(f: OpportunityFilterState): boolean {
  return f.search.trim() !== "" || f.workMode !== "all" || f.minComp !== "all";
}

/**
 * Read filter state from URL query params, snapping anything unrecognised
 * (`?work_mode=banana`, `?order_by=cheapest`, `?min_stipend=abc`) back to
 * its default. A hand-edited or stale URL therefore renders clean controls
 * and never produces an invalid API request; the backend's 422 validation
 * is unchanged and remains the real guard.
 */
export function opportunityFiltersFromParams(
  params: URLSearchParams,
  sourceType: SourceType,
): OpportunityFilterState {
  const workModeRaw = params.get("work_mode") ?? "";
  const compRaw =
    (sourceType === "INTERNSHIP" ? params.get("min_stipend") : params.get("min_salary")) ?? "";
  const compValues = sourceType === "INTERNSHIP" ? STIPEND_VALUES : SALARY_VALUES;
  return {
    search: params.get("search") ?? "",
    workMode: WORK_MODE_VALUES.has(workModeRaw) ? workModeRaw : "all",
    minComp: compValues.has(compRaw) ? compRaw : "all",
    sort: params.get("order_by") === "deadline" ? "deadline" : "newest",
  };
}

/**
 * Serialize filter state to a query string — only non-default values, so a
 * clean browse stays at `/student/internships` (no `?order_by=newest`).
 */
export function opportunityFiltersToQuery(
  f: OpportunityFilterState,
  sourceType: SourceType,
): string {
  const p = new URLSearchParams();
  if (f.search.trim()) p.set("search", f.search.trim());
  if (f.workMode !== "all") p.set("work_mode", f.workMode);
  if (f.minComp !== "all") {
    p.set(sourceType === "INTERNSHIP" ? "min_stipend" : "min_salary", f.minComp);
  }
  if (f.sort === "deadline") p.set("order_by", "deadline");
  return p.toString();
}

/** Map filter state to the `listOpportunities` argument object. */
export function opportunityFiltersToApiParams(
  f: OpportunityFilterState,
  sourceType: SourceType,
) {
  const minComp = f.minComp === "all" ? undefined : Number(f.minComp);
  return {
    sourceType,
    search: f.search.trim() || undefined,
    workMode: f.workMode === "all" ? undefined : (f.workMode as WorkMode),
    minStipend: sourceType === "INTERNSHIP" ? minComp : undefined,
    minSalary: sourceType === "JOB" ? minComp : undefined,
    sort: f.sort,
  };
}

export function OpportunityFilters({
  sourceType,
  filters,
  onChange,
  onReset,
}: {
  sourceType: SourceType;
  filters: OpportunityFilterState;
  onChange: (next: OpportunityFilterState) => void;
  onReset: () => void;
}) {
  const isInternship = sourceType === "INTERNSHIP";
  const noun = isInternship ? "internships" : "jobs";

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      <SearchBar
        value={filters.search}
        onChange={(search) => onChange({ ...filters, search })}
        placeholder={`Search ${noun} by title...`}
        aria-label={`Search ${noun}`}
      />
      <Filters
        value={filters.workMode}
        onChange={(workMode) => onChange({ ...filters, workMode })}
        options={WORK_MODE_OPTIONS}
        aria-label="Filter by work mode"
      />
      <Filters
        value={filters.minComp}
        onChange={(minComp) => onChange({ ...filters, minComp })}
        options={isInternship ? STIPEND_OPTIONS : SALARY_OPTIONS}
        aria-label={isInternship ? "Filter by minimum stipend" : "Filter by minimum salary"}
      />
      <Filters
        value={filters.sort}
        onChange={(sort) => onChange({ ...filters, sort: sort as OpportunitySort })}
        options={SORT_OPTIONS}
        aria-label="Sort opportunities"
      />
      {opportunityFiltersActive(filters) && (
        <Button variant="ghost" size="sm" onClick={onReset}>
          <X className="size-3.5" /> Reset
        </Button>
      )}
    </div>
  );
}
